"""Tiny translation layer shared by the CLI and the GUI.

Source strings are the English text itself: `_("Download selected")`. Other languages map that text to a
translation in `locales/<code>.py`; a missing entry falls back to English, so nothing ever breaks.
`tests/test_i18n.py` makes sure every `_()` / `ngettext()` literal has a Russian entry.
"""

from __future__ import annotations

import locale
import os
import sys

LANGUAGES = {"en": "English", "ru": "Русский"}
DEFAULT = "en"

_lang = DEFAULT
_catalog: dict[str, str | tuple[str, ...]] = {}


def system_language() -> str:
    """'ru' if the OS UI language is Russian, else 'en'."""
    if sys.platform == "win32":
        try:
            import ctypes

            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return "ru" if langid & 0x3FF == 0x19 else DEFAULT
        except (AttributeError, OSError):
            pass
    candidates = [os.environ.get(k, "") for k in ("LC_ALL", "LC_MESSAGES", "LANG")]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    for value in candidates:
        code = value.split("_")[0].split(".")[0].lower()
        if code in LANGUAGES:
            return code
        if value:
            break
    return DEFAULT


def resolve(setting: str) -> str:
    """Config value ('' = follow system, 'en', 'ru') -> language code."""
    return setting if setting in LANGUAGES else system_language()


def set_language(code: str) -> None:
    global _lang, _catalog
    _lang = code if code in LANGUAGES else DEFAULT
    if _lang == "ru":
        from .locales.ru import MESSAGES

        _catalog = MESSAGES
    else:
        _catalog = {}


def current() -> str:
    return _lang


def _format(text: str, fmt: dict) -> str:
    return text.format(**fmt) if fmt else text


def _(text: str, **fmt) -> str:
    """Translate `text`, then fill `{placeholders}` from keyword arguments."""
    tr = _catalog.get(text, text)
    return _format(tr if isinstance(tr, str) else text, fmt)


def N_(text: str) -> str:
    """Mark a string for translation without translating it yet (it is passed to `_()` later)."""
    return text


def ru_plural(n: int) -> int:
    """Index of the Russian plural form: 0 = 1 файл, 1 = 2 файла, 2 = 5 файлов."""
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return 0
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return 1
    return 2


def ngettext(singular: str, plural: str, n: int, **fmt) -> str:
    """Plural-aware translation; `{n}` is filled in automatically."""
    fmt = {"n": n, **fmt}
    tr = _catalog.get(singular)
    if isinstance(tr, tuple) and _lang == "ru":
        return _format(tr[ru_plural(n)], fmt)
    return _format(singular if n == 1 else plural, fmt)
