from __future__ import annotations

from ..models import Video
from .base import ExtractError, Extractor
from .kodik import KodikExtractor

EXTRACTORS: list[Extractor] = [KodikExtractor()]


def find_extractor(video: Video) -> Extractor | None:
    return next((e for e in EXTRACTORS if e.matches(video)), None)


def is_supported(video: Video) -> bool:
    return find_extractor(video) is not None


__all__ = ["EXTRACTORS", "ExtractError", "Extractor", "find_extractor", "is_supported"]
