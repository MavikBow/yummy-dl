from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Anime:
    anime_id: int
    url: str
    title: str
    year: int | None = None
    type: str = ""
    status: str = ""
    episodes: int | None = None
    other_titles: list[str] = field(default_factory=list)
    posters: dict[str, str] = field(default_factory=dict)  # size -> absolute URL (small/medium/big/...)

    def poster(self, *sizes: str) -> str | None:
        """First available poster URL among `sizes` (in order of preference)."""
        return next((self.posters[s] for s in sizes if self.posters.get(s)), None)

    @classmethod
    def from_api(cls, d: dict) -> Anime:
        episodes = d.get("episodes") or {}
        return cls(
            anime_id=int(d["anime_id"]),
            url=d.get("anime_url", ""),
            title=d.get("title", ""),
            year=d.get("year"),
            type=(d.get("type") or {}).get("shortname", ""),
            status=(d.get("anime_status") or {}).get("title", ""),
            episodes=episodes.get("count") if isinstance(episodes, dict) else None,
            other_titles=list(d.get("other_titles") or []),
            posters={k: ("https:" + v if v.startswith("//") else v)
                     for k, v in (d.get("poster") or {}).items() if isinstance(v, str) and v},
        )


@dataclass
class Video:
    video_id: int
    number: str
    index: int
    dubbing: str
    player: str
    player_id: int
    iframe_url: str
    duration: int = 0

    @classmethod
    def from_api(cls, d: dict) -> Video:
        data = d.get("data") or {}
        url = d.get("iframe_url", "")
        if url.startswith("//"):
            url = "https:" + url
        return cls(
            video_id=int(d["video_id"]),
            number=str(d.get("number", "")),
            index=int(d.get("index") or 0),
            dubbing=data.get("dubbing", ""),
            player=data.get("player", ""),
            player_id=int(data.get("player_id") or 0),
            iframe_url=url,
            duration=int(d.get("duration") or 0),
        )

    @property
    def dub_name(self) -> str:
        """Dubbing name without the 'Озвучка ' prefix."""
        prefix = "Озвучка "
        return self.dubbing[len(prefix):] if self.dubbing.startswith(prefix) else self.dubbing

    @property
    def player_name(self) -> str:
        prefix = "Плеер "
        return self.player[len(prefix):] if self.player.startswith(prefix) else self.player


@dataclass
class Stream:
    """Resolved playable stream: quality (height) -> URL.

    kind "hls": m3u8 playlists; "dash": .mpd manifests; "file": plain media files (e.g. MP4).
    """

    qualities: dict[int, str]
    headers: dict[str, str] = field(default_factory=dict)
    kind: str = "hls"

    def pick(self, quality: int) -> tuple[int, str]:
        """Return the best quality <= requested, else the lowest available."""
        if not self.qualities:
            raise ValueError("stream has no qualities")
        below = [q for q in self.qualities if q <= quality]
        q = max(below) if below else min(self.qualities)
        return q, self.qualities[q]
