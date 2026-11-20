from __future__ import annotations

from typing import Protocol

import httpx

from ..models import Stream, Video


class ExtractError(Exception):
    pass


class Extractor(Protocol):
    name: str

    def matches(self, video: Video) -> bool: ...

    def extract(self, video: Video, http: httpx.Client) -> Stream: ...
