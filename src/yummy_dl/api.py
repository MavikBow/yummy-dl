"""Client for the YummyAnime API (https://api.yani.tv/swagger)."""

from __future__ import annotations

import threading

import httpx

from . import USER_AGENT
from .models import Anime, Video

BASE_URL = "https://api.yani.tv"


class ApiError(Exception):
    pass


class YummyClient:
    def __init__(self, token: str | None = None, lang: str = "ru", client: httpx.Client | None = None):
        self._headers = {"Accept": "application/json", "Lang": lang, "User-Agent": USER_AGENT}
        if token:
            self._headers["X-Application"] = token
        self._client = client
        if client is not None:
            client.headers.update(self._headers)
        self._lock = threading.Lock()

    @property
    def _http(self) -> httpx.Client:
        # Created lazily: building the TLS context costs ~0.7 s, which shouldn't delay GUI startup.
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = httpx.Client(base_url=BASE_URL, timeout=30, follow_redirects=True,
                                                headers=self._headers)
        return self._client

    def warm(self) -> None:
        """Create the HTTP client now (call from a background thread)."""
        self._http  # noqa: B018

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

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

    def get_image(self, url: str) -> bytes:
        """Fetch a poster/image (WebP/JPEG; AVIF is avoided since not every Qt build decodes it)."""
        resp = self._http.get(url, headers={"Accept": "image/webp,image/jpeg,image/*;q=0.8"})
        resp.raise_for_status()
        return resp.content
