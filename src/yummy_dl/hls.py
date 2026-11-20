"""Minimal HLS (m3u8) downloader: concurrent segments, resumable, optional ffmpeg remux to MP4."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx

ProgressFn = Callable[[int, int], None]  # (segments_done, segments_total)


class HlsError(Exception):
    pass


@dataclass
class Variant:
    url: str
    bandwidth: int = 0
    height: int = 0


_ATTR = re.compile(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)')


def _attrs(line: str) -> dict[str, str]:
    body = line.split(":", 1)[1] if ":" in line else ""
    return {k: v.strip('"') for k, v in _ATTR.findall(body)}


def parse_playlist(text: str, base_url: str) -> tuple[list[Variant], list[str]]:
    """Return (variants, segments). Exactly one is non-empty for a valid playlist."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].startswith("#EXTM3U"):
        raise HlsError("not an m3u8 playlist")
    variants: list[Variant] = []
    segments: list[str] = []
    pending: Variant | None = None
    for ln in lines[1:]:
        if ln.startswith("#EXT-X-STREAM-INF"):
            a = _attrs(ln)
            res = a.get("RESOLUTION", "")
            height = int(res.split("x")[1]) if "x" in res else 0
            pending = Variant(url="", bandwidth=int(a.get("BANDWIDTH", "0") or 0), height=height)
        elif ln.startswith("#EXT-X-KEY"):
            method = _attrs(ln).get("METHOD", "NONE")
            if method != "NONE":
                raise HlsError(f"encrypted HLS ({method}) is not supported")
        elif ln.startswith("#"):
            continue
        elif pending is not None:
            pending.url = urljoin(base_url, ln)
            variants.append(pending)
            pending = None
        else:
            segments.append(urljoin(base_url, ln))
    return variants, segments


def resolve_segments(http: httpx.Client, url: str, headers: dict[str, str] | None = None) -> list[str]:
    for _ in range(3):  # follow master -> media
        resp = http.get(url, headers=headers)
        resp.raise_for_status()
        variants, segments = parse_playlist(resp.text, str(resp.url))
        if segments:
            return segments
        if not variants:
            raise HlsError("playlist has no segments")
        url = max(variants, key=lambda v: (v.height, v.bandwidth)).url
    raise HlsError("too many nested playlists")


def find_ffmpeg() -> str | None:
    env = os.environ.get("YUMMY_FFMPEG")
    if env and Path(env).exists():
        return env
    # Next to the frozen .exe (PyInstaller) or the current dir, then PATH.
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    for d in (Path(sys.executable).parent, Path.cwd()):
        if (d / exe).exists():
            return str(d / exe)
    return shutil.which("ffmpeg")


def _fetch_segment(http: httpx.Client, url: str, target: Path, headers: dict[str, str], retries: int = 4) -> None:
    tmp = target.with_suffix(".tmp")
    for attempt in range(retries):
        try:
            with http.stream("GET", url, headers=headers) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in resp.iter_bytes(1 << 16):
                        f.write(chunk)
            tmp.replace(target)
            return
        except (httpx.HTTPError, OSError) as e:
            if attempt == retries - 1:
                raise HlsError(f"segment failed after {retries} tries: {e}") from e
            time.sleep(1.5 * (attempt + 1))


def download(
    playlist_url: str,
    dest: Path,
    *,
    headers: dict[str, str] | None = None,
    workers: int = 8,
    progress: ProgressFn | None = None,
    http: httpx.Client | None = None,
) -> Path:
    """Download an HLS stream to `dest` (.mp4 via ffmpeg if available, otherwise .ts).

    Segments are kept in `<dest>.parts/` until complete, so an interrupted run resumes.
    Returns the path actually written.
    """
    headers = headers or {}
    own = http is None
    http = http or httpx.Client(timeout=60, follow_redirects=True)
    try:
        segments = resolve_segments(http, playlist_url, headers)
        dest.parent.mkdir(parents=True, exist_ok=True)
        parts = dest.with_name(dest.name + ".parts")
        parts.mkdir(exist_ok=True)
        files = [parts / f"{i:05d}.ts" for i in range(len(segments))]

        done = sum(f.exists() for f in files)
        total = len(segments)
        if progress:
            progress(done, total)
        todo = [(u, f) for u, f in zip(segments, files) if not f.exists()]
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = [pool.submit(_fetch_segment, http, u, f, headers) for u, f in todo]
            try:
                for fut in as_completed(futures):
                    fut.result()
                    done += 1
                    if progress:
                        progress(done, total)
            except BaseException:
                for fut in futures:
                    fut.cancel()
                raise
    finally:
        if own:
            http.close()

    ts_path = dest.with_suffix(".ts")
    with open(ts_path, "wb") as out:
        for f in files:
            with open(f, "rb") as src:
                shutil.copyfileobj(src, out)

    result = ts_path
    ffmpeg = find_ffmpeg()
    if ffmpeg and dest.suffix.lower() != ".ts":
        proc = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(ts_path), "-c", "copy",
             "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart", str(dest)],
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if proc.returncode == 0:
            ts_path.unlink()
            result = dest
        elif dest.exists():
            dest.unlink()  # keep the .ts; a failed remux shouldn't lose the download
    shutil.rmtree(parts, ignore_errors=True)
    return result
