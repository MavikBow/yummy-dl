# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`yummy-dl`: downloader for Russian-dubbed anime from YummyAnime (API: https://api.yani.tv, swagger at /swagger). Ships a Typer CLI (`yummy-dl`) and a PySide6 desktop app (`yummy-dl-gui`). Windows is the primary target, Linux is supported. Python 3.11+, src layout (`src/yummy_dl`), hatchling build.

## Commands

```bash
uv venv && uv pip install -e '.[dev]'     # dev env (pytest, pyinstaller, PySide6)
pytest                                     # offline unit tests (live tests excluded via addopts)
pytest -m live                             # hits the real API and players
pytest tests/test_core.py::test_kodik_parse_page   # single test
yummy-dl --help / yummy-dl-gui             # run CLI / GUI (also: python -m yummy_dl, python -m yummy_dl.gui)
pyinstaller --noconfirm packaging/yummy-dl-gui.spec          # GUI one-folder build -> dist/yummy-dl/
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -BundleFfmpeg   # full Windows release zip
```

No linter/formatter is configured. CI (`.github/workflows/build.yml`) runs `pytest` then builds the Windows zip, only on `v*` tags or manual dispatch.

## Architecture

Pipeline: `api.YummyClient` (search / anime / videos) → `models.Video` (one per episode × dub × player; each is a third-party player **iframe URL**) → `core.group_by_dub` → `core.pick_videos` → extractor resolves iframe to a `models.Stream` → downloader by `Stream.kind`.

- **`core.py`** is the UI-independent layer shared by CLI and GUI (dub grouping, episode-spec parsing like `1-5,8`, player choice, output paths, `download_episode`). Put new logic here, not in `cli.py` or `gui/`.
- **Extractors** (`extractors/`): each implements the `Extractor` protocol in `base.py` (`name`, `matches(video)`, `extract(video, http) -> Stream`). The order of `EXTRACTORS` in `extractors/__init__.py` is the default player preference (CVH → Kodik → Aksor). Deliberately unsupported players go in `UNSUPPORTED_REASONS` (shown to users). Adding a player = new extractor + register it + fixture-based tests.
- **Downloaders** dispatched on `Stream.kind`: `"hls"` → `hls.py` (Kodik; optional ffmpeg remux to .mp4, else .ts), `"file"` → `direct.py` (CVH MP4, parallel chunked), `"dash"` → `dash.py` (Aksor; separate video/audio, ffmpeg required to merge).
- **Resume contract**: partial data lives in `<target>.parts` next to the output; its presence means "unfinished". `core.existing_download` treats a file as done only when no `.parts` sibling exists. Cancellation = raise `core.Cancelled` from the progress callback; partial files are kept.
- **ffmpeg lookup**: `hls.find_ffmpeg()` — `YUMMY_FFMPEG` env, then next to the frozen exe / cwd, then PATH.
- **Scripts** (`scripts.py`): user-saved ffmpeg argument templates (`{input} {name} {ext} {episode} {outdir}`) stored in `scripts.json` beside the config. `run_script` writes into a `.yummy-tmp-<name>` work dir, then deletes the original and moves the outputs in; on failure/cancel the original is untouched. `core.existing_download` also recognizes converted outputs (`<stem>.*`, `<stem>_NN.*`, a `<stem>/` folder, optionally prefixed by the episode number), so keep those naming rules in sync.
- **Translations** (`i18n.py`, `locales/ru.py`): user-facing text is wrapped as `_("English text", **fmt)`, `ngettext(...)` for counts, `N_()` for constants translated later. The English text is the key; `locales/ru.py` holds the Russian. `tests/test_i18n.py` fails if a wrapped string has no Russian entry, the `{placeholders}` differ, or an entry is unused, so add the translation with every new UI string. Never pass an f-string to `_()`, and don't use `_` as a throwaway variable in modules that import it. The CLI sets the language at import time, because Typer evaluates `help=` then.
- **Config** (`config.py`): TOML in the platform config dir; token also from `YUMMY_APP_TOKEN`, sent as `X-Application` header.
- **GUI** (`gui/`): `window.py` main window, `help.py` Help dialog (quick start, guided token setup, CLI cheat sheet; keep its CLI reference in sync when CLI options change), `workers.py` threading. One-off API calls go through `run_bg` (Qt thread pool, callbacks on GUI thread, must tolerate the window being closed). Downloads run one job at a time on the `DownloadManager` daemon thread, reporting via Qt signals. `gui/__init__.py` imports PySide6 lazily so the CLI works without Qt; assets are resolved with `gui.asset()` so they work from source, wheel and PyInstaller.

## Tests

`tests/test_core.py` is offline and driven by captured real responses in `tests/fixtures/` (API JSON, Kodik page, CVH JSON, Aksor MPD). `tests/test_live.py` is marked `live` and opt-in.

## Packaging notes

- The GUI is intentionally a PyInstaller **one-folder** build (`_internal/` must stay next to the exe); one-file Qt builds started in 10+ s. The CLI is a one-file build without Qt.
- Licensing: the code is MIT. The release bundles LGPL Qt and GPL ffmpeg, so `build_windows.ps1` runs `scripts/collect_licenses.py` to put their licence texts into the zip. When adding a bundled dependency, check that it lands there and update `THIRD-PARTY-NOTICES.md`.
- Build Windows releases from a Windows drive, not a `\\wsl.localhost` path. A stale exe icon after rebuild is Windows' icon cache (`ie4uinit.exe -show`).
- The API is for personal use only; don't add features that redistribute content.
