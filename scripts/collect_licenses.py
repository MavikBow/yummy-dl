"""Gather the licence texts for everything the Windows release bundles into one folder.

Run it with the build virtualenv's Python, so the versions recorded are the ones PyInstaller packed:

    python scripts/collect_licenses.py OUT_DIR [--ffmpeg PATH_TO_FFMPEG_EXE]

Writes OUT_DIR/VERSIONS.txt plus one subfolder per component with its licence files.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GPL3 = ROOT / "packaging" / "licenses" / "GPL-3.0.txt"
LGPL3 = ROOT / "packaging" / "licenses" / "LGPL-3.0.txt"
# Not runtime requirements, but part of the built program (bootloader).
EXTRA = ["pyinstaller"]


def _name(req: str) -> str:
    return re.split(r"[\s;\[<>=!~(]", req, maxsplit=1)[0].lower().replace("_", "-")


def runtime_closure(root: str, extras: set[str]) -> list[metadata.Distribution]:
    """`root` and everything it needs at runtime (environment markers honoured)."""
    try:
        from packaging.requirements import Requirement
    except ImportError:
        Requirement = None
    seen: dict[str, metadata.Distribution] = {}
    todo = [(root, extras)]
    while todo:
        name, wanted_extras = todo.pop()
        key = _name(name)
        if key in seen:
            continue
        try:
            dist = metadata.distribution(key)
        except metadata.PackageNotFoundError:
            continue
        seen[key] = dist
        for req in dist.requires or []:
            if Requirement is not None:
                r = Requirement(req)
                envs = [{"extra": e} for e in wanted_extras] or [{"extra": ""}]
                if r.marker and not any(r.marker.evaluate(env) for env in envs):
                    continue
                todo.append((r.name, set(r.extras)))
            elif "extra ==" not in req:
                todo.append((_name(req), set()))
    return sorted(seen.values(), key=lambda d: d.metadata["Name"].lower())


def licence_files(dist: metadata.Distribution) -> list[Path]:
    files = []
    for f in dist.files or []:
        parts = [p.lower() for p in f.parts]
        if parts and parts[0].endswith(".dist-info") and (
                "licenses" in parts or re.match(r"(licen[cs]e|copying|notice|authors)", parts[-1])):
            path = Path(f.locate())
            if path.is_file():
                files.append(path)
    return files


def licence_of(dist: metadata.Distribution) -> str:
    m = dist.metadata
    if m.get("License-Expression"):
        return m["License-Expression"]
    classifiers = [c.split(" :: ")[-1] for c in m.get_all("Classifier") or [] if c.startswith("License ::")]
    if classifiers:
        return ", ".join(classifiers)
    return (m.get("License") or "see files").splitlines()[0][:80]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--ffmpeg", type=Path)
    args = ap.parse_args()
    out: Path = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    lines = ["Components bundled in this build, with their licences.",
             "See THIRD-PARTY-NOTICES.md for where to get their source code.", ""]

    # Python runtime (python3X.dll and the standard library). Its LICENSE.txt also covers the
    # third-party libraries in the Windows build of CPython (OpenSSL, libffi, zlib, ...).
    py = out / "python"
    py.mkdir()
    for candidate in ("LICENSE.txt", "LICENSE"):
        src = Path(sys.base_prefix) / candidate
        if src.is_file():
            shutil.copy2(src, py / "LICENSE.txt")
            break
    else:
        (py / "LICENSE-NOT-INCLUDED.txt").write_text(
            "Python is distributed under the PSF License Agreement: https://docs.python.org/3/license.html\n",
            encoding="utf-8")
    lines.append(f"Python {sys.version.split()[0]}  PSF-2.0 (+ notices for its bundled libraries)  python/")

    dists = runtime_closure("yummy-dl", {"gui"})
    for extra in EXTRA:
        try:
            dists.append(metadata.distribution(extra))
        except metadata.PackageNotFoundError:
            pass
    for dist in dists:
        name, version = dist.metadata["Name"], dist.version
        if name.lower().replace("_", "-") == "yummy-dl":
            continue
        folder = out / "python-packages" / f"{name}-{version}"
        folder.mkdir(parents=True)
        for f in licence_files(dist):
            shutil.copy2(f, folder / f.name)
        lic = licence_of(dist)
        if _name(name) in ("pyside6-essentials", "pyside6", "shiboken6"):  # the wheels ship only a commercial notice
            shutil.copy2(LGPL3, folder / "LGPL-3.0.txt")
            shutil.copy2(GPL3, folder / "GPL-3.0.txt")
        if not any(folder.iterdir()):
            (folder / "LICENSE-NOT-INCLUDED.txt").write_text(
                f"{name} {version} is distributed under: {lic}\nIts package didn't include a licence file.\n",
                encoding="utf-8")
        lines.append(f"{name} {version}  {lic}  python-packages/{folder.name}/")

    if args.ffmpeg:
        ff = out / "ffmpeg"
        ff.mkdir()
        shutil.copy2(GPL3, ff / "GPL-3.0.txt")
        try:
            version = subprocess.run([str(args.ffmpeg), "-hide_banner", "-version"], capture_output=True,
                                     text=True, encoding="utf-8", errors="replace").stdout
        except OSError:
            version = ""
        (ff / "ffmpeg-version.txt").write_text(version, encoding="utf-8")
        first = version.splitlines()[0] if version else "ffmpeg (version unknown)"
        lines.append(f"{first}  GPL-3.0-or-later  ffmpeg/")

    (out / "VERSIONS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Collected licences for {len(lines) - 3} components into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
