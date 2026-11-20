# PyInstaller spec for the GUI. Build with: pyinstaller packaging/yummy-dl-gui.spec
#
# One-folder build (not --onefile) on purpose: a one-file exe unpacks ~100 MB of Qt DLLs to %TEMP%
# on every launch, and antivirus rescans them each time. That is what made startup take 10+ s.
from pathlib import Path

root = Path(SPECPATH).parent

# Not needed by a widgets-only app; they only add load/scan time and size.
DROP_BINARIES = {
    "opengl32sw.dll",  # 20 MB software OpenGL fallback
    "qdirect2d.dll",  # alternative platform plugin (qwindows is used)
}
EXCLUDES = [
    "yummy_dl.cli", "typer", "click", "rich", "pydantic", "pydantic_core",  # CLI-only deps
    "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick", "tkinter",
]

a = Analysis(
    [str(root / "src" / "yummy_dl" / "gui" / "__main__.py")],
    pathex=[str(root / "src")],
    excludes=EXCLUDES,
    noarchive=False,
)
a.binaries = [b for b in a.binaries if Path(b[0]).name.lower() not in DROP_BINARIES]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="yummy-dl-gui",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="yummy-dl", upx=False)
