from __future__ import annotations

from ..models import Video
from .base import ExtractError, Extractor
from .aksor import AksorExtractor
from .cvh import CvhExtractor
from .kodik import KodikExtractor

# Order = default preference when a dub is on several players.
# CVH first: plain MP4 up to 1080p, no ffmpeg needed. Aksor last: DASH, always needs ffmpeg.
EXTRACTORS: list[Extractor] = [CvhExtractor(), KodikExtractor(), AksorExtractor()]

# Players we deliberately don't support, with the reason shown to the user.
UNSUPPORTED_REASONS = {
    "Alloha": "protected by an anti-bot challenge",
}


def find_extractor(video: Video) -> Extractor | None:
    return next((e for e in EXTRACTORS if e.matches(video)), None)


def is_supported(video: Video) -> bool:
    return find_extractor(video) is not None


__all__ = ["UNSUPPORTED_REASONS", "EXTRACTORS", "ExtractError", "Extractor", "find_extractor", "is_supported"]
