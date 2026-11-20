"""Aksor player (player.aksor.tv/video/<id>).

The page is an empty shell; its JS calls GET /api/video/<id>, which returns
qualities{q4k, q2k, q1080, q720, q480, q360} -> DASH manifest (.mpd) URLs (null when absent).
"""

from __future__ import annotations

from urllib.parse import quote, urlparse

import httpx

from .. import USER_AGENT
from ..models import Stream, Video
from .base import ExtractError

API = "https://player.aksor.tv/api/video/"
QUALITY_KEYS = {"q4k": 2160, "q2k": 1440, "q1080": 1080, "q720": 720, "q480": 480, "q360": 360}


def video_id(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    if len(parts) < 2 or parts[0] != "video":
        raise ExtractError(f"Aksor: unexpected iframe URL {url!r}")
    return parts[1]


def parse_qualities(data: dict) -> dict[int, str]:
    out: dict[int, str] = {}
    for key, height in QUALITY_KEYS.items():
        url = (data.get("qualities") or {}).get(key)
        if url and url.strip():
            # Paths contain raw spaces (".../MC Entertainment/01/1080.mpd").
            out[height] = quote(url.strip(), safe=":/?&=%#@+,;")
    if not out:
        raise ExtractError("Aksor: video has no available qualities")
    return out


class AksorExtractor:
    name = "Aksor"

    def matches(self, video: Video) -> bool:
        return (urlparse(video.iframe_url).hostname or "").endswith("aksor.tv")

    def extract(self, video: Video, http: httpx.Client) -> Stream:
        vid = video_id(video.iframe_url)
        try:
            resp = http.get(API + vid, headers={
                "User-Agent": USER_AGENT, "Accept": "application/json", "Referer": video.iframe_url})
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ExtractError(f"Aksor: {e}") from e
        headers = {"User-Agent": USER_AGENT, "Referer": "https://player.aksor.tv/"}
        return Stream(qualities=parse_qualities(data), headers=headers, kind="dash")
