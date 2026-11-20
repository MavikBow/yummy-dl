"""Resumable single-file HTTP download (for players that serve plain MP4).

CDNs throttle each connection, so the file is fetched as parallel Range chunks written in place
into `<dest>.part`. Finished chunk indexes go to `<dest>.part.done` so an interrupted run resumes.
Falls back to one sequential stream if the server ignores Range.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from .hls import ProgressFn

CHUNK = 4 * 1024 * 1024


class DirectError(Exception):
    pass


def _probe(http: httpx.Client, url: str, headers: dict[str, str]) -> int | None:
    """Total size if the server supports Range, else None."""
    with http.stream("GET", url, headers={**headers, "Range": "bytes=0-0"}) as resp:
        resp.raise_for_status()
        cr = resp.headers.get("Content-Range", "")
        if resp.status_code == 206 and "/" in cr and cr.rsplit("/", 1)[1].isdigit():
            return int(cr.rsplit("/", 1)[1])
    return None


def _retry(fn, retries: int):
    for attempt in range(retries):
        try:
            return fn()
        except (httpx.HTTPError, DirectError, OSError) as e:
            if attempt == retries - 1:
                raise DirectError(f"download failed after {retries} tries: {e}") from e
            time.sleep(2 * (attempt + 1))


def _sequential(http, url, part, headers, progress) -> None:
    with http.stream("GET", url, headers=headers) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0)) or None
        done = 0
        with open(part, "wb") as f:
            for chunk in resp.iter_bytes(1 << 17):
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total or done)
        if total and done < total:
            raise DirectError(f"connection closed at {done}/{total} bytes")


def _chunked(http, url, part, state, total, headers, workers, progress, retries) -> None:
    n = (total + CHUNK - 1) // CHUNK
    done_set: set[int] = set()
    if part.exists() and state.exists() and part.stat().st_size == total:
        done_set = {int(x) for x in state.read_text().split() if x.isdigit() and int(x) < n}
    else:
        with open(part, "wb") as f:
            f.truncate(total)
        state.write_text("")

    lock = threading.Lock()
    done_bytes = sum(min(CHUNK, total - i * CHUNK) for i in done_set)
    if progress:
        progress(done_bytes, total)

    def fetch(i: int) -> int:
        start, end = i * CHUNK, min(total, (i + 1) * CHUNK) - 1

        def once() -> int:
            resp = http.get(url, headers={**headers, "Range": f"bytes={start}-{end}"})
            resp.raise_for_status()
            data = resp.content
            if resp.status_code != 206 or len(data) != end - start + 1:
                raise DirectError(f"bad range response for chunk {i}")
            with open(part, "r+b") as f:
                f.seek(start)
                f.write(data)
            return len(data)

        size = _retry(once, retries)
        with lock:
            with open(state, "a") as s:
                s.write(f"{i}\n")
        return size

    todo = [i for i in range(n) if i not in done_set]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = [pool.submit(fetch, i) for i in todo]
        try:
            for fut in as_completed(futures):
                done_bytes += fut.result()
                if progress:
                    progress(done_bytes, total)
        except BaseException:
            for fut in futures:
                fut.cancel()
            raise


def download(
    url: str,
    dest: Path,
    *,
    headers: dict[str, str] | None = None,
    workers: int = 8,
    progress: ProgressFn | None = None,
    http: httpx.Client | None = None,
    retries: int = 5,
) -> Path:
    """Download `url` to `dest`. Progress is reported in bytes."""
    headers = dict(headers or {})
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    state = dest.with_name(dest.name + ".part.done")
    own = http is None
    http = http or httpx.Client(timeout=60, follow_redirects=True)
    try:
        total = _retry(lambda: _probe(http, url, headers), retries)
        if total:
            _chunked(http, url, part, state, total, headers, workers, progress, retries)
        else:
            _retry(lambda: _sequential(http, url, part, headers, progress), retries)
    finally:
        if own:
            http.close()
    part.replace(dest)
    state.unlink(missing_ok=True)
    return dest
