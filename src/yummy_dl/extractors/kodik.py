"""Kodik player (kodikplayer.com).

Flow (mirrors the player's own JS):
1. GET the iframe page -> `urlParams` JSON (signed domain/referrer) and `vInfo.type/hash/id`.
2. POST those to the endpoint the player JS hides as `url:atob("...")` (currently `/ftor`).
3. Response `links` maps quality -> [{src}], where `src` is a letter-shifted base64 string
   that decodes to an HLS playlist URL.
"""

from __future__ import annotations

import base64
import json
import re
from urllib.parse import unquote, urljoin, urlparse

import httpx

from .. import USER_AGENT
from ..models import Stream, Video
from .base import ExtractError

REFERER = "https://ru.yummyani.me/"
DEFAULT_ENDPOINT = "/ftor"

_URL_PARAMS = re.compile(r"urlParams\s*=\s*'(\{.*?\})'")
_VINFO = re.compile(r"vInfo\.(\w+)\s*=\s*'([^']*)'")
_PLAYER_JS = re.compile(r'src="(/assets/js/app\.player_single[^"]+\.js)"')
_ENDPOINT = re.compile(r'type:"POST",url:atob\("([A-Za-z0-9+/=]+)"\)')


def parse_page(html: str) -> tuple[dict, dict]:
    """Return (signed url params, vInfo) from a Kodik iframe page."""
    m = _URL_PARAMS.search(html)
    if not m:
        raise ExtractError("Kodik: urlParams not found (video removed or page layout changed)")
    params = json.loads(m.group(1))
    vinfo = dict(_VINFO.findall(html))
    if not {"type", "hash", "id"} <= vinfo.keys():
        raise ExtractError("Kodik: vInfo not found in page")
    return params, vinfo


def build_form(params: dict, vinfo: dict) -> dict:
    form = {
        "d": params["d"],
        "d_sign": params["d_sign"],
        "pd": params["pd"],
        "pd_sign": params["pd_sign"],
        # urlParams carries ref percent-encoded; the player sends it decoded (encoded -> HTTP 500).
        "ref": unquote(params.get("ref", "")),
        "ref_sign": params.get("ref_sign", ""),
        "bad_user": "false",
        "cdn_is_working": "true",
    }
    for key in ("type", "hash", "id", "link", "secret", "uid"):
        if vinfo.get(key):
            form[key] = vinfo[key]
    return form


def _shift(s: str, n: int) -> str:
    out = []
    for c in s:
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + n) % 26 + 97))
        elif "A" <= c <= "Z":
            out.append(chr((ord(c) - 65 + n) % 26 + 65))
        else:
            out.append(c)
    return "".join(out)


def decode_src(src: str) -> str:
    """Decode a Kodik link. Tries every letter shift since Kodik rotates it periodically."""
    if src.startswith(("http", "//")):
        return src
    for n in range(26):
        candidate = _shift(src, n)
        candidate += "=" * (-len(candidate) % 4)
        try:
            decoded = base64.b64decode(candidate, validate=True).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            continue
        if decoded.startswith(("http", "//")) and (".m3u8" in decoded or ".mp4" in decoded):
            return "https:" + decoded if decoded.startswith("//") else decoded
    raise ExtractError("Kodik: could not decode stream link")


def parse_links(data: dict) -> dict[int, str]:
    links = data.get("links") or {}
    out: dict[int, str] = {}
    for quality, items in links.items():
        if items and quality.isdigit():
            out[int(quality)] = decode_src(items[0]["src"])
    if not out:
        raise ExtractError("Kodik: response has no links")
    return out


class KodikExtractor:
    name = "Kodik"

    def matches(self, video: Video) -> bool:
        host = urlparse(video.iframe_url).hostname or ""
        return "kodik" in host

    def _endpoint(self, http: httpx.Client, html: str, page_url: str) -> str:
        m = _PLAYER_JS.search(html)
        if m:
            try:
                js = http.get(urljoin(page_url, m.group(1))).text
                e = _ENDPOINT.search(js)
                if e:
                    return base64.b64decode(e.group(1)).decode()
            except (httpx.HTTPError, ValueError):
                pass
        return DEFAULT_ENDPOINT

    def extract(self, video: Video, http: httpx.Client) -> Stream:
        page_url = video.iframe_url
        headers = {"User-Agent": USER_AGENT, "Referer": REFERER}
        try:
            resp = http.get(page_url, headers=headers)
            resp.raise_for_status()
            params, vinfo = parse_page(resp.text)
            endpoint = urljoin(page_url, self._endpoint(http, resp.text, page_url))
            api = http.post(
                endpoint,
                data=build_form(params, vinfo),
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": page_url,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            api.raise_for_status()
            data = api.json()
        except httpx.HTTPError as e:
            raise ExtractError(f"Kodik: {e}") from e
        return Stream(qualities=parse_links(data), headers={"User-Agent": USER_AGENT})
