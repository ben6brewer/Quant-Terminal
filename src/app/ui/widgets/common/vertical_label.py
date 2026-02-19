"""Vertical Label - QLabel that paints text rotated -90 degrees (bottom-to-top)."""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter


class VerticalLabel(QLabel):
    """QLabel that paints its text rotated -90 degrees (bottom-to-top)."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().windowText().color())
        painter.rotate(-90)
        painter.translate(-self.height(), 0)
        painter.drawText(
            QRect(0, 0, self.height(), self.width()), Qt.AlignCenter, self.text()
        )
        painter.end()

    def sizeHint(self):
        return super().sizeHint().transposed()

    def minimumSizeHint(self):
        return self.sizeHint()
