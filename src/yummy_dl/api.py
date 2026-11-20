"""Client for the YummyAnime API (https://api.yani.tv/swagger)."""

from __future__ import annotations

import httpx

from . import USER_AGENT
from .models import Anime, Video

BASE_URL = "https://api.yani.tv"


class ApiError(Exception):
    pass


class YummyClient:
    def __init__(self, token: str | None = None, lang: str = "ru", client: httpx.Client | None = None):
        headers = {"Accept": "application/json", "Lang": lang, "User-Agent": USER_AGENT}
        if token:
            headers["X-Application"] = token
        self._http = client or httpx.Client(base_url=BASE_URL, timeout=30, follow_redirects=True)
        self._http.headers.update(headers)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> YummyClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, path: str, **params):
        try:
            resp = self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        except httpx.HTTPError as e:
            raise ApiError(f"network error: {e}") from e
        try:
            body = resp.json()
        except ValueError:
            raise ApiError(f"HTTP {resp.status_code}: non-JSON response") from None
        if resp.status_code >= 400 or "error" in body:
            raise ApiError(f"HTTP {resp.status_code}: {body.get('error', 'unknown error')}")
        return body["response"]

    def search(self, query: str, limit: int = 10, offset: int = 0) -> list[Anime]:
        return [Anime.from_api(a) for a in self._get("/anime", q=query, limit=limit, offset=offset)]

    def get_anime(self, url_or_id: str | int) -> Anime:
        return Anime.from_api(self._get(f"/anime/{url_or_id}"))

    def get_videos(self, anime_id: int) -> list[Video]:
        return [Video.from_api(v) for v in self._get(f"/anime/{anime_id}/videos")]
