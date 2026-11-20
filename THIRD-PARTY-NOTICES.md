# Third-party notices

yummy-dl's own code is licensed under the MIT License (see `LICENSE`).

The Windows release (`yummy-dl-windows.zip`) also bundles other people's software. That software keeps its own
licence. The `licenses/` folder next to this file has the full licence texts, and `licenses/VERSIONS.txt` lists the
exact version of every bundled component. None of these components was modified.

## Qt and Qt for Python (PySide6, Shiboken6)

- **Licence:** GNU Lesser General Public License v3 (LGPL-3.0). Texts: `licenses/python-packages/PySide6_Essentials-*/`.
- **Where they are:** the Qt and PySide6 libraries are separate DLL and `.pyd` files in `_internal/PySide6/` and
  `_internal/shiboken6/`. Under the LGPL you may replace them with your own builds of the same version,
  including modified ones.
- **Source code:**
  - Qt for Python: <https://download.qt.io/official_releases/QtForPython/> and <https://code.qt.io/cgit/pyside/pyside-setup.git/>
  - Qt: <https://download.qt.io/official_releases/qt/>
  - Third-party code inside Qt: <https://doc.qt.io/qt-6/licenses-used-in-qt.html>

## FFmpeg

- **Licence:** GNU General Public License v3 or later (GPL-3.0-or-later). Text: `licenses/ffmpeg/GPL-3.0.txt`.
- **Which build:** `ffmpeg.exe` is an unmodified Windows release build from <https://www.gyan.dev/ffmpeg/builds/>,
  built with `--enable-gpl --enable-version3`. The exact version and build configuration are in
  `licenses/ffmpeg/ffmpeg-version.txt`.
- **Source code:**
  - FFmpeg: the source of the bundled version is included as `licenses/ffmpeg/ffmpeg-<version>.tar.xz`. All
    releases are also at <https://ffmpeg.org/releases/>.
  - The external libraries it's built with (x264, x265, libmp3lame, …) are listed in the build configuration, and
    each has its own project page.
- **How yummy-dl uses it:** yummy-dl runs `ffmpeg.exe` as a separate program. It isn't linked into yummy-dl, so the
  GPL covers `ffmpeg.exe` only. You can delete `ffmpeg.exe` or replace it with any other build.

## Python

- **Licence:** PSF License Agreement, plus the notices for the libraries in CPython's Windows build (OpenSSL,
  libffi, zlib, …). Text: `licenses/python/LICENSE.txt`.
- **Source code:** <https://www.python.org/downloads/source/>

## Python packages

The licence texts are in `licenses/python-packages/<name>-<version>/`.

| Package | Licence | Used by |
|---|---|---|
| httpx, httpcore, idna | BSD-3-Clause | both programs |
| h11, anyio, platformdirs | MIT | both programs |
| certifi | MPL-2.0 (source: <https://github.com/certifi/python-certifi>) | both programs |
| typer, rich, markdown-it-py, mdurl, annotated-doc, pydantic and its helpers | MIT | command-line tool |
| shellingham | ISC | command-line tool |
| Pygments | BSD-2-Clause | command-line tool |
| typing_extensions | PSF-2.0 | command-line tool |
| colorama | BSD-3-Clause | command-line tool (Windows) |

## PyInstaller

The programs are packed with PyInstaller. Its bootloader is part of each `.exe`. PyInstaller is licensed under the
GPL-2.0-or-later with a special exception that lets programs built with it use any licence. Text:
`licenses/python-packages/pyinstaller-*/COPYING.txt`.

## Content

These licences cover software only. Videos downloaded with yummy-dl belong to their rights holders, and the
YummyAnime API is for personal use only.
