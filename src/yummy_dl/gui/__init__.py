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


def _qt_import_hint(e: ImportError) -> str:
    if getattr(e, "name", None) == "PySide6" or "No module named 'PySide6'" in str(e):
        if getattr(sys, "frozen", False):  # the CLI build ships without Qt
            return "This build has no GUI: run yummy-dl-gui instead."
        return "The GUI needs PySide6: pip install -e '.[gui]'"
    msg = f"Qt failed to load: {e}"  # PySide6 is there, but a system library it needs is missing
    if sys.platform.startswith("linux"):
        msg += ("\nInstall Qt's runtime libraries, e.g. on Debian/Ubuntu:\n"
                "  sudo apt install libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libegl1")
    return msg


def _install_qt_translation(app) -> None:
    """Qt's own strings (Yes/No/Cancel, Save/Close, context menus) in the app's language."""
    from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator

    from .. import i18n

    if i18n.current() == "en":
        return
    tr = QTranslator(app)
    import PySide6

    folders = [QLibraryInfo.path(QLibraryInfo.TranslationsPath), str(Path(PySide6.__file__).parent / "translations")]
    if any(tr.load(QLocale(i18n.current()), "qtbase", "_", d) for d in folders):
        app.installTranslator(tr)
        app._qt_translator = tr  # keep a reference


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError as e:
        print(_qt_import_hint(e), file=sys.stderr)
        return 1
    from .. import config as cfgmod
    from .. import i18n
    from . import theme
    from .window import MainWindow

    from PySide6.QtGui import QIcon

    _windows_app_id()
    cfg = cfgmod.load()
    i18n.set_language(i18n.resolve(cfg.language))
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("yummy-dl")
    app.setWindowIcon(QIcon(asset("logo.png")))
    _install_qt_translation(app)
    theme.apply(app, theme.resolve(cfg.theme))
    win = MainWindow()
    win.show()
    if os.environ.get("YUMMY_EXIT_AFTER_SHOW"):  # startup-time measurement: quit once the window is up
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, app.quit)
    return app.exec()
