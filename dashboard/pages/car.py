from PySide6.QtWidgets import QWidget, QPushButton
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
from pathlib import Path
from components.hotspot import Hotspot
from pages.popups.popup import PopupPage

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

        self.hotspots = []

        battery = QRect(380, 210, 177, 187)
        battery_hotspot = Hotspot(
            self,
            battery,
            shape="square",
            rotation=25,
            shear_x=-0.80,
            shear_y=-0.05,
            padding=60
        )
        battery_hotspot.clicked.connect(self.show_battery_popup)
        self.hotspots.append(battery_hotspot)
        
        self.init_wheels()
    
    def init_wheels(self):
        r_f_wheel_rect = QRect(139, 265, 122, 140)
        r_f_wheel_hotspot = Hotspot(self, r_f_wheel_rect, rotation=30, shape="circle", group="wheels")
        r_f_wheel_hotspot.clicked.connect(self.show_wheel_popup)
        self.hotspots.append(r_f_wheel_hotspot)

        l_f_wheel_rect = QRect(358, 352, 122, 162)
        l_f_wheel_hotspot = Hotspot(self, l_f_wheel_rect, rotation=30, shape="circle", group="wheels")
        l_f_wheel_hotspot.clicked.connect(self.show_wheel_popup)
        self.hotspots.append(l_f_wheel_hotspot)

        r_b_wheel_rect = QRect(685, 190, 95, 140)
        r_b_wheel_hotspot = Hotspot(self, r_b_wheel_rect, rotation=28, shape="circle", group="wheels")
        r_b_wheel_hotspot.clicked.connect(self.show_wheel_popup)
        self.hotspots.append(r_b_wheel_hotspot)

        l_b_wheel_rect = QRect(477, 120, 92, 117)
        l_b_wheel_hotspot = Hotspot(self, l_b_wheel_rect, rotation=30, shape="circle", group="wheels")
        l_b_wheel_hotspot.clicked.connect(self.show_wheel_popup)
        self.hotspots.append(l_b_wheel_hotspot)


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
            for box in self.hotspots:
                box.update_position(image_rect, scale_x, scale_y)

        super().paintEvent(event)

    def show_wheel_popup(self):
        """Show the separate popup page."""
        popup = PopupPage(title="Example Popup", content_text="This is a wheel placeholder", parent=self)
        popup.exec()

    def show_battery_popup(self):
        """Show the separate popup page."""
        popup = PopupPage(title="Example Popup", content_text="This is a battery placeholder", parent=self)
        popup.exec()
