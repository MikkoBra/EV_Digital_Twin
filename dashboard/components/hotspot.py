from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, Signal, QPointF
from PySide6.QtGui import QPainter, QColor, QPainterPath, QTransform, QCursor

class Hotspot(QWidget):
    clicked = Signal()
    groups = {}

    def __init__(self, parent, original_rect: QRect, rotation=0, padding=20,
                 shape="circle", group=None, shear_x=0.0, shear_y=0.0):
        super().__init__(parent)
        self.original_rect = original_rect
        self.rotation = rotation
        self.padding = padding
        self.shape_type = shape
        self.group = group
        self.shear_x = shear_x
        self.shear_y = shear_y

        self.setMouseTracking(True)

        self.hovered = False
        self.base_color = QColor(0, 0, 0, 0)
        self.hover_color = QColor(200, 200, 200, 100)

        if group:
            Hotspot.groups.setdefault(group, []).append(self)

    def update_position(self, image_rect: QRect, scale_x=1.0, scale_y=1.0):
        new_w = int(self.original_rect.width() * scale_x) + 2 * self.padding
        new_h = int(self.original_rect.height() * scale_y) + 2 * self.padding
        new_x = int(image_rect.x() + self.original_rect.x() * scale_x - self.padding)
        new_y = int(image_rect.y() + self.original_rect.y() * scale_y - self.padding)
        self.setGeometry(QRect(new_x, new_y, new_w, new_h))
        self.raise_()
        self.update()

    def set_hovered(self, hovered: bool):
        if self.hovered == hovered:
            return
        self.hovered = hovered
        self.update()

    def shape(self) -> QPainterPath:
        """Return a QPainterPath for the exact clickable area with transforms applied."""
        rect = QRect(self.padding, self.padding,
                     max(0, self.width() - 2 * self.padding),
                     max(0, self.height() - 2 * self.padding))

        path = QPainterPath()
        if self.shape_type == "circle":
            path.addEllipse(rect)
        else:
            path.addRect(rect)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        transform = QTransform()
        transform.translate(cx, cy)
        transform.rotate(self.rotation)
        transform.shear(self.shear_x, self.shear_y)
        transform.translate(-cx, -cy)

        return transform.map(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = self.hover_color if self.hovered else self.base_color
        painter.setBrush(color)

        if self.hovered:
            pen = painter.pen()
            pen.setColor(QColor(100, 100, 100))
            pen.setWidth(2)
            painter.setPen(pen)
        else:
            painter.setPen(Qt.NoPen)

        cx, cy = self.width() / 2.0, self.height() / 2.0
        painter.translate(cx, cy)
        painter.rotate(self.rotation)
        painter.shear(self.shear_x, self.shear_y)
        painter.translate(-cx, -cy)

        if self.shape_type == "circle":
            painter.drawEllipse(self.padding, self.padding,
                                max(0, self.width() - 2 * self.padding),
                                max(0, self.height() - 2 * self.padding))
        else:
            painter.drawRect(self.padding, self.padding,
                             max(0, self.width() - 2 * self.padding),
                             max(0, self.height() - 2 * self.padding))

        super().paintEvent(event)

    def enterEvent(self, event):
        global_pos = QCursor.pos()
        self._update_group_hover_from_global(global_pos)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.group and self.group in Hotspot.groups:
            for h in Hotspot.groups[self.group]:
                h.set_hovered(False)
        else:
            self.set_hovered(False)
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        try:
            local_pos = event.position()
        except AttributeError:
            local_pos = event.localPos()
        global_pos = self.mapToGlobal(local_pos.toPoint())
        self._update_group_hover_from_global(global_pos)
        super().mouseMoveEvent(event)

    def _update_group_hover_from_global(self, global_pos):
        """Helper: given a global mouse pos, set hovered for this widget or for its group."""
        if self.group and self.group in Hotspot.groups:
            any_contains = False
            for h in Hotspot.groups[self.group]:
                local = h.mapFromGlobal(global_pos)  # QPoint
                p = QPointF(local.x(), local.y())
                if h.shape().contains(p):
                    any_contains = True
                    break
            for h in Hotspot.groups[self.group]:
                h.set_hovered(any_contains)
        else:
            local = self.mapFromGlobal(global_pos)
            p = QPointF(local.x(), local.y())
            self.set_hovered(self.shape().contains(p))

    def mousePressEvent(self, event):
        try:
            pos = event.position()
        except AttributeError:
            pos = event.localPos()

        if event.button() == Qt.LeftButton and self.shape().contains(pos):
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        try:
            local_pos = event.position()
        except AttributeError:
            local_pos = event.localPos()

        inside = self.shape().contains(local_pos)
        if inside:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.unsetCursor()

        global_pos = self.mapToGlobal(local_pos.toPoint())
        self._update_group_hover_from_global(global_pos)
        super().mouseMoveEvent(event)
