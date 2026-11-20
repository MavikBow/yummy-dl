"""Full-screen image viewer: click, Esc, or any key closes it."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QWidget


class ClickableLabel(QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.pixmap() is not None and not self.pixmap().isNull():
            self.clicked.emit()
        super().mouseReleaseEvent(event)


CAPTION_H = 40  # strip at the bottom reserved for the caption, so it never covers the image


class ImageViewer(QDialog):
    def __init__(self, pixmap: QPixmap, caption: str = "", parent: QWidget | None = None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.PointingHandCursor)
        self.setWindowTitle(caption or "Poster")
        self._pixmap = pixmap
        self._scaled: QPixmap | None = None
        self._caption = caption
        self.loading = False

    def set_pixmap(self, pixmap: QPixmap) -> None:
        """Swap in a higher-resolution image once it arrives."""
        if not pixmap.isNull():
            self._pixmap = pixmap
            self._scaled = None  # rescale from the new source on next paint
        self.loading = False
        self.update()

    def show_on(self, widget: QWidget) -> None:
        screen = widget.screen() if widget is not None else None
        if screen is not None:
            self.setGeometry(screen.geometry())
        self.showFullScreen()
        self.activateWindow()

    def _area(self) -> QSize:
        return QSize(self.width(), max(1, self.height() - CAPTION_H))

    def _fit(self) -> QPixmap:
        if self._scaled is None:
            self._scaled = self._pixmap.scaled(self._area(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return self._scaled

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0))
        if not self._pixmap.isNull():
            img = self._fit()
            x = (self.width() - img.width()) // 2
            y = (self._area().height() - img.height()) // 2
            p.drawPixmap(x, y, img)
        p.setPen(QColor(170, 170, 170))
        hint = "Loading full resolution…   " if self.loading else ""
        text = f"{self._caption}   ·   {hint}click or press Esc to close" if self._caption else f"{hint}click or press Esc to close"
        p.drawText(QRect(0, self.height() - CAPTION_H, self.width(), CAPTION_H), Qt.AlignCenter, text)

    def resizeEvent(self, event) -> None:
        self._scaled = None
        super().resizeEvent(event)

    def mouseReleaseEvent(self, _event) -> None:
        self.close()

    def keyPressEvent(self, _event) -> None:
        self.close()
