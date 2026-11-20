import ast
import re
import string
from pathlib import Path

import pytest

from yummy_dl import i18n
from yummy_dl.locales.ru import MESSAGES

SRC = Path(__file__).resolve().parent.parent / "src" / "yummy_dl"


def source_messages() -> dict[str, str]:
    """Every literal passed to _(), N_() or ngettext() in src/ -> 'file:line'."""
    found: dict[str, str] = {}
    for path in SRC.rglob("*.py"):
        if "locales" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("_", "N_", "ngettext") and node.args):
                continue
            arg = node.args[0]
            where = f"{path.relative_to(SRC)}:{node.lineno}"
            assert not isinstance(arg, ast.JoinedStr), f"f-string passed to {node.func.id}() at {where}"
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found[arg.value] = where
    return found


def fields(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


def test_every_message_has_russian():
    missing = {k: w for k, w in source_messages().items() if k not in MESSAGES}
    assert not missing, "add these to locales/ru.py:\n" + "\n".join(f"{w}: {k!r}" for k, w in missing.items())


def test_no_stale_translations():
    stale = set(MESSAGES) - set(source_messages())
    assert not stale, f"unused entries in locales/ru.py: {sorted(stale)}"


def test_placeholders_match():
    for key, tr in MESSAGES.items():
        for form in (tr if isinstance(tr, tuple) else (tr,)):
            assert fields(form) == fields(key), f"placeholders differ: {key!r} -> {form!r}"


def test_plural_entries_have_three_forms():
    plural_keys = set()
    for path in SRC.rglob("*.py"):
        plural_keys |= set(re.findall(r'ngettext\(\s*"([^"]+)"', path.read_text(encoding="utf-8")))
    for key in plural_keys:
        assert isinstance(MESSAGES[key], tuple) and len(MESSAGES[key]) == 3, key
    for key, tr in MESSAGES.items():
        if isinstance(tr, tuple):
            assert key in plural_keys, f"{key!r} has plural forms but isn't used with ngettext"


@pytest.mark.parametrize("n,form", [(1, 0), (2, 1), (4, 1), (5, 2), (11, 2), (12, 2), (14, 2), (21, 0),
                                    (22, 1), (25, 2), (101, 0), (111, 2)])
def test_ru_plural_rule(n, form):
    assert i18n.ru_plural(n) == form


def test_translate_and_fallback():
    try:
        i18n.set_language("ru")
        assert i18n._("Search") == MESSAGES["Search"]
        assert i18n._("not in the catalog {x}", x=1) == "not in the catalog 1"
        assert i18n.ngettext("{n} result", "{n} results", 5) == MESSAGES["{n} result"][2].format(n=5)
        i18n.set_language("en")
        assert i18n._("Search") == "Search"
        assert i18n.ngettext("{n} result", "{n} results", 1) == "1 result"
        assert i18n.ngettext("{n} result", "{n} results", 3) == "3 results"
    finally:
        i18n.set_language("en")


def test_resolve(monkeypatch):
    assert i18n.resolve("ru") == "ru" and i18n.resolve("en") == "en"
    monkeypatch.setattr(i18n, "system_language", lambda: "ru")
    assert i18n.resolve("") == "ru"
    assert i18n.resolve("de") == "ru"  # unknown setting -> follow system


def test_system_language_from_env(monkeypatch):
    monkeypatch.setattr(i18n.sys, "platform", "linux")
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert i18n.system_language() == "ru"
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert i18n.system_language() == "en"
