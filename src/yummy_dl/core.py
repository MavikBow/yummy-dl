"""UI-independent logic shared by the CLI (and a future GUI)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import dash, direct, hls
from .extractors import EXTRACTORS, UNSUPPORTED_REASONS, ExtractError, find_extractor
from .models import Anime, Video
from .naming import episode_filename, episode_number, sanitize


class Cancelled(Exception):
    """Raise from a progress callback to abort a download (partial files are kept for resume)."""


def _ep_key(number: str) -> tuple[int, float, str]:
    try:
        return (0, float(number), "")
    except ValueError:
        return (1, 0.0, number)


@dataclass
class DubOption:
    dubbing: str
    dub_name: str
    by_player: dict[str, list[Video]] = field(default_factory=dict)

    @property
    def episodes(self) -> list[str]:
        nums = {v.number for vids in self.by_player.values() for v in vids}
        return sorted(nums, key=_ep_key)

    @property
    def supported_episodes(self) -> list[str]:
        nums = {v.number for vids in self.by_player.values() for v in vids if find_extractor(v)}
        return sorted(nums, key=_ep_key)

    @property
    def supported(self) -> bool:
        return bool(self.supported_episodes)


def group_by_dub(videos: list[Video]) -> list[DubOption]:
    groups: dict[str, DubOption] = {}
    for v in videos:
        opt = groups.setdefault(v.dubbing, DubOption(v.dubbing, v.dub_name))
        opt.by_player.setdefault(v.player_name, []).append(v)
    return sorted(groups.values(), key=lambda o: (not o.supported, -len(o.supported_episodes), o.dub_name))


def unsupported_note(options: list[DubOption]) -> str | None:
    """e.g. '2 dub(s) only on unsupported players: Alloha (protected by an anti-bot challenge)'."""
    missing = [o for o in options if not o.supported]
    if not missing:
        return None
    players = sorted({p for o in missing for p in o.by_player})
    named = ", ".join(f"{p} ({UNSUPPORTED_REASONS[p]})" if p in UNSUPPORTED_REASONS else p for p in players)
    return f"{len(missing)} dub(s) only on unsupported players: {named}"


def find_dub(options: list[DubOption], query: str) -> DubOption | None:
    q = query.casefold()
    exact = [o for o in options if q in (o.dub_name.casefold(), o.dubbing.casefold())]
    if exact:
        return exact[0]
    partial = [o for o in options if q in o.dubbing.casefold()]
    return partial[0] if partial else None


def parse_episodes(spec: str | None, available: list[str]) -> list[str]:
    """'1-3,7' / 'all' / None -> episode numbers from `available`, in order."""
    if not spec or spec.strip().lower() == "all":
        return list(available)
    wanted: set[str] = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            try:
                lo_f = float(lo) if lo else float("-inf")
                hi_f = float(hi) if hi else float("inf")
            except ValueError:
                raise ValueError(f"bad episode range: {part!r}") from None
            wanted.update(n for n in available if _ep_key(n)[0] == 0 and lo_f <= float(n) <= hi_f)
        else:
            match = [n for n in available if n == part or (_ep_key(n)[0] == 0 and _ep_key(part)[0] == 0
                                                         and float(n) == float(part))]
            if not match:
                raise ValueError(f"episode {part} is not available")
            wanted.update(match)
    return [n for n in available if n in wanted]


def pick_videos(dub: DubOption, episodes: list[str], player: str | None = None) -> dict[str, Video]:
    """One downloadable video per episode, preferring `player`, then extractor order."""
    order = [e.name.casefold() for e in EXTRACTORS]
    if player:
        order.insert(0, player.casefold())
    candidates: dict[str, list[Video]] = defaultdict(list)
    for name, vids in dub.by_player.items():
        for v in vids:
            if v.number in episodes and find_extractor(v):
                candidates[v.number].append(v)

    def rank(v: Video) -> int:
        n = v.player_name.casefold()
        return order.index(n) if n in order else len(order)

    return {ep: min(candidates[ep], key=rank) for ep in episodes if candidates.get(ep)}


def episode_path(anime: Anime, video: Video, out_dir: Path) -> Path:
    return out_dir / sanitize(anime.title, 80) / episode_filename(anime.title, video.number, video.dub_name)


VIDEO_EXTS = {".mp4", ".mkv", ".ts", ".avi", ".webm", ".mov", ".m4v"}


def existing_download(target: Path) -> Path | None:
    """The finished file for this episode, if any.

    Besides the download itself this finds what a user script turned it into (the original is
    deleted then): `<stem>.mkv`, `<stem>_00.mkv`, or a folder named `<stem>` holding the parts,
    optionally with the episode number in front (`01 <stem>.mkv`, `01. <stem>.mkv`).
    """
    if target.with_name(target.name + ".parts").exists():
        return None  # unfinished download; resume it
    for p in (target, target.with_suffix(".ts")):
        if p.exists():
            return p
    folder, stem = target.parent, target.stem
    if not folder.is_dir():
        return None
    episode = episode_number(stem)
    for p in sorted(folder.iterdir()):
        at = p.name.find(stem)
        if at < 0 or (at > 0 and (not episode or p.name[:at].strip(" ._-") != episode)):
            continue
        rest = p.name[at + len(stem):]
        if p.is_dir():
            if rest == "" and any(p.iterdir()):
                return p
        elif rest[:1] in (".", "_") and p.suffix.lower() in VIDEO_EXTS and ".muxing" not in rest:
            return p
    return None


def download_episode(
    anime: Anime,
    video: Video,
    out_dir: Path,
    *,
    quality: int = 720,
    workers: int = 8,
    progress: hls.ProgressFn | None = None,
    http: httpx.Client | None = None,
) -> tuple[Path, int]:
    """Download one episode. Returns (written path, actual quality)."""
    extractor = find_extractor(video)
    if extractor is None:
        raise ExtractError(f"player {video.player_name!r} is not supported yet")
    own = http is None
    http = http or httpx.Client(timeout=60, follow_redirects=True)
    try:
        stream = extractor.extract(video, http)
        q, url = stream.pick(quality)
        target = episode_path(anime, video, out_dir)
        if stream.kind == "dash":
            path = dash.download(url, target, quality=quality, headers=stream.headers, workers=workers,
                                 progress=progress, http=http)
        elif stream.kind == "file":
            path = direct.download(url, target, headers=stream.headers, workers=workers,
                                   progress=progress, http=http)
        else:
            path = hls.download(url, target, headers=stream.headers,
                                workers=workers, progress=progress, http=http)
        return path, q
    finally:
        if own:
            http.close()
