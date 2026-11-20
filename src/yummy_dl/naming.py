"""Filesystem-safe names (Windows rules are the strictest, so apply them everywhere)."""

from __future__ import annotations

import re

_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def sanitize(name: str, max_len: int = 120) -> str:
    name = _INVALID.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    if not name:
        name = "_"
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name[:max_len].rstrip(". ")


def episode_label(number: str) -> str:
    """'1' -> 'E01', '12.5' -> 'E12.5', 'OVA' -> 'OVA'."""
    try:
        n = float(number)
    except ValueError:
        return sanitize(number)
    return f"E{int(n):02d}" if n.is_integer() else f"E{n:g}"


def episode_number(stem: str) -> str:
    """Episode number from an episode file name made by `episode_filename`, else ''.

    'Берсерк - E01 [AniDub]' -> '01', 'X - E12.5 [Dub]' -> '12.5', 'X - OVA [Dub]' -> 'OVA'.
    """
    m = _EPISODE_RE.match(stem)
    if not m:
        return ""
    label = m.group(1)
    return label[1:] if re.fullmatch(r"E\d+(?:\.\d+)?", label) else label


_EPISODE_RE = re.compile(r"^.+ - ([^\[\]]+?) \[[^\[\]]*\]$")


def episode_filename(title: str, number: str, dub: str, ext: str = "mp4") -> str:
    return sanitize(f"{sanitize(title, 80)} - {episode_label(number)} [{sanitize(dub, 40)}]", 200) + f".{ext}"
