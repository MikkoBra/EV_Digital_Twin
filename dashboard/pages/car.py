from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
from pathlib import Path
from components.hotspot import Hotspot
from dashboard.pages.popups.popup import PopupPage

class Car(QWidget):
    def __init__(self, go_back_callback):
        super().__init__()

        image_path = Path(__file__).resolve().parent.parent / "assets" / "car.jpg"
        self.bg_pixmap = QPixmap(str(image_path))
        self.scale_factor = 0.6

        arrow_path = Path(__file__).resolve().parent.parent / "assets" / "arrow-left.png"
        self.back_btn = QPushButton(self)
        self.back_btn.setIcon(QIcon(str(arrow_path)))
        self.back_btn.setIconSize(QSize(24, 24))
        self.back_btn.setFixedSize(40, 40)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #2d89ef;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1e5cb3;
            }
        """)
        self.back_btn.clicked.connect(go_back_callback)
        self.back_btn.move(10, 10)
        self.back_btn.raise_()

        self.click_boxes = []

        example_box = QRect(355, 350, 130, 170)
        click_box = Hotspot(self, example_box, rotation=30)
        click_box.clicked.connect(self.show_example_popup)
        self.click_boxes.append(click_box)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))

        if not self.bg_pixmap.isNull():
            target_w = int(self.width() * self.scale_factor)
            target_h = int(self.height() * self.scale_factor)
            scaled_pix = self.bg_pixmap.scaled(
                target_w,
                target_h,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            x = (self.width() - scaled_pix.width()) // 2
            y = (self.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x, y, scaled_pix)

            scale_x = scaled_pix.width() / self.bg_pixmap.width()
            scale_y = scaled_pix.height() / self.bg_pixmap.height()

            image_rect = QRect(x, y, scaled_pix.width(), scaled_pix.height())
            for box in self.click_boxes:
                box.update_position(image_rect, scale_x, scale_y)

        super().paintEvent(event)

    def show_example_popup(self):
        """Show the separate popup page."""
        popup = PopupPage(title="Example Popup", content_text="This is a popup placeholder", parent=self)
        popup.exec()
