"""Desktop GUI (PySide6). Install with: pip install 'yummy-dl[gui]'."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"


def asset(name: str) -> str:
    """Path to a bundled asset (works from source, installed wheel, and PyInstaller build)."""
    return str(ASSETS / name)


def _windows_app_id() -> None:
    """Give the process its own taskbar identity, so Windows shows our icon (not python.exe's)."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("yummy-dl.gui")
        except (AttributeError, OSError):
            pass


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        hint = "run yummy-dl-gui.exe instead" if getattr(sys, "frozen", False) else "pip install 'yummy-dl[gui]'"
        print(f"The GUI needs PySide6: {hint}", file=sys.stderr)
        return 1
    from .. import config as cfgmod
    from . import theme
    from .window import MainWindow

    from PySide6.QtGui import QIcon

    _windows_app_id()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("yummy-dl")
    app.setWindowIcon(QIcon(asset("logo.png")))
    theme.apply(app, theme.resolve(cfgmod.load().theme))
    win = MainWindow()
    win.show()
    if os.environ.get("YUMMY_EXIT_AFTER_SHOW"):  # startup-time measurement: quit once the window is up
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, app.quit)
    return app.exec()
