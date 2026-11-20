"""Minimal MPEG-DASH (.mpd) downloader for static (VOD) manifests.

Supports SegmentTemplate (with SegmentTimeline or fixed @duration) and single-file BaseURL
representations. The best video representation up to the requested height and the best audio
representation are downloaded as fMP4 segments (resumable, in parallel) and muxed with ffmpeg.
"""

from __future__ import annotations

import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from urllib.parse import urljoin

import httpx

from . import hls
from .hls import ProgressFn

NS = {"d": "urn:mpeg:dash:schema:mpd:2011"}


class DashError(Exception):
    pass


@dataclass
class Representation:
    kind: str  # "video" | "audio"
    id: str
    bandwidth: int = 0
    height: int = 0
    lang: str = ""
    init: str | None = None
    segments: list[str] = field(default_factory=list)


def parse_duration(value: str | None) -> float:
    """ISO-8601 duration like PT23M36.4S -> seconds."""
    if not value:
        return 0.0
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?)?", value.strip())
    if not m:
        raise DashError(f"bad duration {value!r}")
    d, h, mi, s = m.groups()
    return int(d or 0) * 86400 + int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)


def _fill(template: str, rep_id: str, bandwidth: int, number: int | None = None, time: int | None = None) -> str:
    def sub(m: re.Match) -> str:
        name, fmt = m.group(1), m.group(2)
        if name == "":
            return "$"
        value = {"RepresentationID": rep_id, "Bandwidth": bandwidth, "Number": number, "Time": time}.get(name)
        if value is None:
            raise DashError(f"unsupported template variable ${name}$")
        return (fmt % value) if fmt else str(value)

    return re.sub(r"\$(\w*)(%0\d+d)?\$", sub, template)


def _base(elem: ET.Element, parent_base: str) -> str:
    b = elem.find("d:BaseURL", NS)
    return urljoin(parent_base, b.text.strip()) if b is not None and b.text else parent_base


def _segments(tpl: ET.Element, rep_id: str, bandwidth: int, base: str, total_seconds: float) -> tuple[str | None, list[str]]:
    init_t = tpl.get("initialization")
    init = urljoin(base, _fill(init_t, rep_id, bandwidth)) if init_t else None
    media = tpl.get("media")
    if not media:
        raise DashError("SegmentTemplate without @media")
    number = int(tpl.get("startNumber", "1"))
    timescale = int(tpl.get("timescale", "1"))
    urls: list[str] = []
    timeline = tpl.find("d:SegmentTimeline", NS)
    if timeline is not None:
        t = 0
        for s in timeline.findall("d:S", NS):
            if s.get("t") is not None:
                t = int(s.get("t"))
            d = int(s.get("d"))
            for _ in range(int(s.get("r", "0")) + 1):
                urls.append(urljoin(base, _fill(media, rep_id, bandwidth, number, t)))
                t += d
                number += 1
    else:
        seg_dur = int(tpl.get("duration", "0")) / timescale
        if seg_dur <= 0 or total_seconds <= 0:
            raise DashError("SegmentTemplate needs a SegmentTimeline or @duration")
        for i in range(ceil(total_seconds / seg_dur)):
            urls.append(urljoin(base, _fill(media, rep_id, bandwidth, number + i)))
    return init, urls


def parse_mpd(text: str, mpd_url: str) -> list[Representation]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise DashError(f"bad MPD: {e}") from None
    if root.get("type", "static") != "static":
        raise DashError("live DASH streams are not supported")
    total = parse_duration(root.get("mediaPresentationDuration"))
    base_mpd = _base(root, mpd_url)
    reps: list[Representation] = []
    for period in root.findall("d:Period", NS)[:1]:  # VOD episodes have a single period
        base_p = _base(period, base_mpd)
        for aset in period.findall("d:AdaptationSet", NS):
            base_a = _base(aset, base_p)
            aset_tpl = aset.find("d:SegmentTemplate", NS)
            for rep in aset.findall("d:Representation", NS):
                mime = rep.get("mimeType") or aset.get("mimeType") or ""
                kind = aset.get("contentType") or mime.split("/")[0]
                if kind not in ("video", "audio"):
                    continue
                rid = rep.get("id", "")
                bw = int(rep.get("bandwidth", "0"))
                base_r = _base(rep, base_a)
                tpl = rep.find("d:SegmentTemplate", NS)
                tpl = tpl if tpl is not None else aset_tpl
                if tpl is not None:
                    init, segs = _segments(tpl, rid, bw, base_r, total)
                elif base_r != base_a or rep.find("d:BaseURL", NS) is not None:
                    init, segs = None, [base_r]  # whole track in one file
                else:
                    raise DashError(f"representation {rid!r}: unsupported segment addressing")
                reps.append(Representation(
                    kind=kind, id=rid, bandwidth=bw,
                    height=int(rep.get("height") or aset.get("maxHeight") or 0),
                    lang=(rep.get("lang") or aset.get("lang") or "").lower(),
                    init=init, segments=segs,
                ))
    if not any(r.kind == "video" for r in reps):
        raise DashError("MPD has no video track")
    return reps


def choose(reps: list[Representation], quality: int) -> tuple[Representation, Representation | None]:
    videos = [r for r in reps if r.kind == "video"]
    fitting = [r for r in videos if r.height <= quality]
    video = max(fitting, key=lambda r: (r.height, r.bandwidth)) if fitting else \
        min(videos, key=lambda r: (r.height, r.bandwidth))
    audios = [r for r in reps if r.kind == "audio"]
    ru = [r for r in audios if r.lang.startswith("ru")]
    audio = max(ru or audios, key=lambda r: r.bandwidth) if audios else None
    return video, audio


def _track_jobs(rep: Representation, parts: Path, prefix: str) -> list[tuple[str, Path]]:
    urls = ([rep.init] if rep.init else []) + rep.segments
    return [(u, parts / f"{prefix}{i:05d}.m4s") for i, u in enumerate(urls)]


def _concat(files: list[Path], out: Path) -> None:
    with open(out, "wb") as dst:
        for f in files:
            with open(f, "rb") as src:
                shutil.copyfileobj(src, dst)


def download(
    mpd_url: str,
    dest: Path,
    *,
    quality: int = 1080,
    headers: dict[str, str] | None = None,
    workers: int = 8,
    progress: ProgressFn | None = None,
    http: httpx.Client | None = None,
) -> Path:
    """Download a DASH stream to `dest` (MP4). Requires ffmpeg to mux video and audio."""
    if not hls.find_ffmpeg():
        raise DashError("ffmpeg is required for this player (DASH): install it or put ffmpeg.exe next to the app")
    headers = headers or {}
    own = http is None
    http = http or httpx.Client(timeout=60, follow_redirects=True)
    try:
        resp = http.get(mpd_url, headers=headers)
        resp.raise_for_status()
        video, audio = choose(parse_mpd(resp.text, str(resp.url)), quality)
        dest.parent.mkdir(parents=True, exist_ok=True)
        parts = dest.with_name(dest.name + ".parts")
        parts.mkdir(exist_ok=True)
        v_jobs = _track_jobs(video, parts, "v")
        a_jobs = _track_jobs(audio, parts, "a") if audio else []
        hls.fetch_all(http, v_jobs + a_jobs, headers=headers, workers=workers, progress=progress)
    finally:
        if own:
            http.close()

    v_file, a_file = parts / "video.mp4", parts / "audio.m4a"
    _concat([f for _, f in v_jobs], v_file)
    args = ["-i", str(v_file)]
    if a_jobs:
        _concat([f for _, f in a_jobs], a_file)
        args += ["-i", str(a_file), "-map", "0:v:0", "-map", "1:a:0"]
    tmp = dest.with_name(dest.stem + ".muxing" + dest.suffix)
    proc = hls.run_ffmpeg([*args, "-c", "copy", "-movflags", "+faststart", str(tmp)])
    if proc.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise DashError(f"ffmpeg mux failed: {proc.stderr.strip()[-300:]}")
    tmp.replace(dest)
    shutil.rmtree(parts, ignore_errors=True)
    return dest
