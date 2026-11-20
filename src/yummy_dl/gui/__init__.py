"""Desktop GUI (PySide6). Install with: pip install 'yummy-dl[gui]'."""

from __future__ import annotations

import sys


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

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("yummy-dl")
    theme.apply(app, theme.resolve(cfgmod.load().theme))
    win = MainWindow()
    win.show()
    return app.exec()
