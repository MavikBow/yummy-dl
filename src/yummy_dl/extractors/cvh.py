"""CVH player (cdnvideohub, embedded by YummyAnime as ru.yummyani.me/iframeCVH.html).

The iframe page only mounts cdnvideohub's <video-player> with these attributes:
  data-aggregator="mali", data-publisher-id=745, data-title-id=<anime_id>,
  priority-voice=<dubbing_code>, episode=<episode>
The player then calls:
  GET {API}/player/sv/playlist?pub=745&aggr=mali&id=<anime_id>  -> items[{vkId, voiceStudio, season, episode}]
  GET {API}/player/sv/video/<vkId>                              -> sources{mpegFullHdUrl, ..., hlsUrl}
The mpeg*Url sources are plain MP4 files (OK.ru CDN) that support HTTP Range.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx

from .. import USER_AGENT
from ..models import Stream, Video
from .base import ExtractError

API = "https://plapi.cdnvideohub.com/api/v1"
PUBLISHER_ID = "745"
AGGREGATOR = "mali"
REFERER = "https://ru.yummyani.me/"

# source key -> video height
QUALITY_KEYS = {
    "mpeg4kUrl": 2160,
    "mpeg2kUrl": 1440,
    "mpegQhdUrl": 1440,
    "mpegFullHdUrl": 1080,
    "mpegHighUrl": 720,
    "mpegMediumUrl": 480,
    "mpegLowUrl": 360,
    "mpegLowestUrl": 240,
    "mpegTinyUrl": 144,
}


def parse_iframe(url: str) -> tuple[str, str, int | None]:
    """Return (anime_id, dubbing_code, episode) from an iframeCVH.html URL."""
    q = parse_qs(urlparse(url).query)
    anime_id = (q.get("anime_id") or [""])[0]
    dub = (q.get("dubbing_code") or [""])[0]
    ep_raw = (q.get("episode") or [""])[0]
    if not anime_id or not dub:
        raise ExtractError("CVH: iframe URL lacks anime_id/dubbing_code")
    try:
        episode = int(float(ep_raw)) if ep_raw else None
    except ValueError:
        episode = None
    return anime_id, dub, episode


def find_item(playlist: dict, dub: str, episode: int | None) -> dict:
    all_items = playlist.get("items") or []
    items = [i for i in all_items if (i.get("voiceStudio") or "").casefold() == dub.casefold()]
    if not items:  # e.g. subtitles have only voiceType="Субтитры"
        items = [i for i in all_items if not i.get("voiceStudio")
                 and (i.get("voiceType") or "").casefold() == dub.casefold()]
    if not items:
        raise ExtractError(f"CVH: dub {dub!r} not in playlist")
    if playlist.get("isSerial") and episode is not None:
        items = [i for i in items if i.get("episode") == episode]
        if not items:
            raise ExtractError(f"CVH: episode {episode} not found for {dub!r}")
    return min(items, key=lambda i: (i.get("season") or 0))


def parse_sources(video: dict) -> dict[int, str]:
    sources = video.get("sources") or {}
    out: dict[int, str] = {}
    for key, height in QUALITY_KEYS.items():
        url = sources.get(key)
        if url and height not in out:
            out[height] = url
    if not out:
        raise ExtractError(f"CVH: no MP4 sources (status {video.get('status')})")
    return out


class CvhExtractor:
    name = "CVH"

    def __init__(self) -> None:
        self._playlists: dict[str, dict] = {}

    def matches(self, video: Video) -> bool:
        return "iframecvh" in urlparse(video.iframe_url).path.lower()

    def _get(self, http: httpx.Client, path: str, **params) -> dict:
        resp = http.get(f"{API}{path}", params=params or None,
                        headers={"User-Agent": USER_AGENT, "Referer": REFERER, "Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()

    def extract(self, video: Video, http: httpx.Client) -> Stream:
        anime_id, dub, episode = parse_iframe(video.iframe_url)
        try:
            if anime_id not in self._playlists:
                self._playlists[anime_id] = self._get(
                    http, "/player/sv/playlist", pub=PUBLISHER_ID, aggr=AGGREGATOR, id=anime_id)
            item = find_item(self._playlists[anime_id], dub, episode)
            data = self._get(http, f"/player/sv/video/{item['vkId']}")
        except (httpx.HTTPError, ValueError) as e:
            raise ExtractError(f"CVH: {e}") from e
        return Stream(qualities=parse_sources(data), headers={"User-Agent": USER_AGENT}, kind="file")
