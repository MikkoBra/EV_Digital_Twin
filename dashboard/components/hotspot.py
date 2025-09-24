from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QColor

class Hotspot(QWidget):
    clicked = Signal()

    def __init__(self, parent, original_rect: QRect, rotation=0, padding=20):
        super().__init__(parent)
        self.original_rect = original_rect
        self.rotation = rotation
        self.padding = padding
        self.setCursor(Qt.PointingHandCursor)

        # Track hover state
        self.hovered = False

        # Base and hover colors
        self.base_color = QColor(0, 0, 0, 0)  # fully transparent
        self.hover_color = QColor(200, 200, 200, 100)  # light grey, partially transparent

    def update_position(self, image_rect: QRect, scale_x=1.0, scale_y=1.0):
        new_w = int(self.original_rect.width() * scale_x) + 2 * self.padding
        new_h = int(self.original_rect.height() * scale_y) + 2 * self.padding
        new_x = int(image_rect.x() + self.original_rect.x() * scale_x - self.padding)
        new_y = int(image_rect.y() + self.original_rect.y() * scale_y - self.padding)
        self.setGeometry(QRect(new_x, new_y, new_w, new_h))
        self.raise_()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Choose color based on hover state
        color = self.hover_color if self.hovered else self.base_color
        painter.setBrush(color)
        if self.hovered:
            pen = painter.pen()
            pen.setColor(QColor(100, 100, 100))  # gray
            pen.setWidth(2)  # thicker border
            painter.setPen(pen)
        else:
            painter.setPen(Qt.NoPen)

        cx, cy = self.width() / 2, self.height() / 2
        painter.translate(cx, cy)
        painter.rotate(self.rotation)
        painter.translate(-cx, -cy)

        painter.drawEllipse(self.padding, self.padding,
                            self.width() - 2 * self.padding,
                            self.height() - 2 * self.padding)

        super().paintEvent(event)

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
