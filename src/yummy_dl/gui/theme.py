"""Light/dark Fusion palettes."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


def system_prefers_dark() -> bool:
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # Qt < 6.5
        return False


def resolve(setting: str) -> bool:
    """Config value ("", "dark", "light") -> whether to use dark."""
    return system_prefers_dark() if setting not in ("dark", "light") else setting == "dark"


def _dark_palette() -> QPalette:
    p = QPalette()
    window, base, alt, text = QColor(37, 37, 38), QColor(30, 30, 30), QColor(45, 45, 48), QColor(220, 220, 220)
    disabled = QColor(120, 120, 120)
    accent = QColor(64, 128, 214)
    roles = {
        QPalette.Window: window,
        QPalette.WindowText: text,
        QPalette.Base: base,
        QPalette.AlternateBase: alt,
        QPalette.ToolTipBase: alt,
        QPalette.ToolTipText: text,
        QPalette.PlaceholderText: disabled,
        QPalette.Text: text,
        QPalette.Button: alt,
        QPalette.ButtonText: text,
        QPalette.BrightText: QColor(255, 80, 80),
        QPalette.Link: QColor(100, 160, 240),
        QPalette.Highlight: accent,
        QPalette.HighlightedText: QColor(255, 255, 255),
        QPalette.Light: QColor(60, 60, 63),
        QPalette.Midlight: QColor(52, 52, 55),
        QPalette.Mid: QColor(45, 45, 48),
        QPalette.Dark: QColor(25, 25, 25),
        QPalette.Shadow: QColor(0, 0, 0),
    }
    for role, color in roles.items():
        p.setColor(role, color)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, disabled)
    p.setColor(QPalette.Disabled, QPalette.Highlight, QColor(70, 70, 70))
    return p


def apply(app: QApplication, dark: bool) -> None:
    app.setStyle("Fusion")
    try:  # Qt 6.8+: also switches native bits such as the Windows title bar
        app.styleHints().setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)
    except AttributeError:
        pass
    app.setPalette(_dark_palette() if dark else app.style().standardPalette())
