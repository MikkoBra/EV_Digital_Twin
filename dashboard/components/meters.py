from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import Qt, QRect, QPointF
from pathlib import Path
import math


class Meter(QWidget):
    """
    General class for fixed-position meters (icon + optional text).
    """

    def __init__(self, icon_path: Path = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Icon
        self.icon_label = None
        if icon_path:
            self.icon_label = QLabel(self)
            pixmap = QPixmap(str(icon_path))
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setScaledContents(True)
            self.icon_label.setFixedSize(60, 60)
            self.icon_label.setStyleSheet("background: transparent;")
            self.layout.addWidget(self.icon_label, alignment=Qt.AlignCenter)

        # Text
        self.text_label = QLabel("", self)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setStyleSheet("color: black; font-size: 10pt; font-weight: bold;")
        self.layout.addWidget(self.text_label, alignment=Qt.AlignCenter)

    def update_position(self, image_rect: QRect, offset_x=0, offset_y=0):
        """
        Aligns meter relative to background image.
        """
        x = image_rect.x() + offset_x
        y = image_rect.y() + offset_y
        self.move(x, y)


class BatteryMeter(Meter):
    """
    Battery meter with SOC icon and text.
    """

    def __init__(self, parent=None):
        """
        Fetches battery SOC icons from assets and sets initial charge to 100.
        """
        base_path = Path(__file__).resolve().parent.parent / "assets"
        icon_path = base_path / "full-battery.png"
        super().__init__(icon_path, parent)
        self.base_path = base_path
        self.charge = 100
        self.update_charge(self.charge)

    def update_charge(self, charge: float):
        """
        Determine which icon should be displayed depending on the current
        SOC value.
        """
        self.charge = charge

        if charge > 90:
            icon = "full-battery.png"
        elif charge > 63:
            icon = "80-battery.png"
        elif charge > 26:
            icon = "half-battery.png"
        elif charge > 10:
            icon = "low-battery.png"
        else:
            icon = "empty-battery.png"

        pixmap = QPixmap(str(self.base_path / icon))
        if not pixmap.isNull():
            self.icon_label.setPixmap(pixmap.scaled(50, 50, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self.text_label.setText(f"{charge:.0f}%")



class TachoMeter(Meter):
    """Circular RPM gauge with needle and digital readout below it."""

    def __init__(self, max_rpm=7000, parent=None, gauge_radius=25):
        """
        Tachometer size is determined by gauge_radius. Increase to make
        the meter bigger.
        """
        super().__init__(icon_path=None, parent=parent)
        self.rpm = 0.0
        self.max_rpm = max_rpm
        self.gauge_radius = gauge_radius
        self.font = QFont("Segoe UI", 10, QFont.Bold)
        self.setFixedSize(self.gauge_radius * 2 + 20, self.gauge_radius * 2 + 40)
        self.text_label.hide()

    def update_rpm(self, rpm: float):
        """
        Updates the RPM value and triggers repaint.
        """
        self.rpm = rpm
        self.update()

    def paintEvent(self, event):
        """
        Determines what should happen when the meter is painted.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Center the gauge horizontally, leave space below for text
        center = QPointF(self.width() / 2, self.gauge_radius + 10)
        radius = self.gauge_radius

        # Draw outer circle
        outer_pen = painter.pen()
        outer_pen.setWidth(4)
        outer_pen.setColor(QColor("#444"))
        painter.setPen(outer_pen)
        painter.setBrush(QColor("#f0f0f0"))
        painter.drawEllipse(center, radius, radius)

        # Draw tick marks
        tick_pen = painter.pen()
        tick_pen.setWidth(2)
        tick_pen.setColor(QColor("#222"))
        painter.setPen(tick_pen)
        for i in range(11):
            angle = 135 + i * 270 / 10
            rad = math.radians(angle)
            x1 = center.x() + radius * 0.8 * math.cos(rad)
            y1 = center.y() - radius * 0.8 * math.sin(rad)
            x2 = center.x() + radius * math.cos(rad)
            y2 = center.y() - radius * math.sin(rad)
            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw needle
        needle_pen = painter.pen()
        needle_pen.setWidth(4)
        needle_pen.setColor(QColor("red"))
        painter.setPen(needle_pen)
        painter.setBrush(QColor("red"))

        rpm_ratio = min(max(self.rpm / self.max_rpm, 0), 1)
        needle_angle = 135 + 270 * rpm_ratio
        rad = math.radians(needle_angle)
        needle_x = center.x() + radius * 0.9 * math.cos(rad)
        needle_y = center.y() - radius * 0.9 * math.sin(rad)
        painter.drawLine(center.x(), center.y(), int(needle_x), int(needle_y))

        # Draw RPM text below the gauge
        painter.setFont(self.font)
        painter.setPen(QColor("#000"))
        text_rect = QRect(0, int(center.y() + radius + 5), self.width(), 25)
        painter.drawText(text_rect, Qt.AlignCenter, f"{int(self.rpm)} RPM")


class CycleMeter(Meter):
    """
    Charging cycle meter showing number of charging cycles.
    """

    def __init__(self, parent=None):
        """
        Fetches charging cycle icon from assets and sets initial cycles to 0.
        """
        base_path = Path(__file__).resolve().parent.parent / "assets"
        icon_path = base_path / "cycle.png"
        super().__init__(icon_path, parent)
        self.base_path = base_path
        self.cycles = 0
        self.update_cycles(self.cycles)

    def update_cycles(self, cycles: int):
        """
        Updates the number of cycles and display.
        """
        self.cycles = cycles
        self.text_label.setText(f"{cycles} Charges")

class DTCMeter(Meter):
    """
    DTC meter showing the current error code with a warning icon.
    """

    def __init__(self, parent=None):
        """
        Fetches warning icon from assets and sets initial DTC code to 0.
        """
        base_path = Path(__file__).resolve().parent.parent / "assets"
        icon_path = base_path / "warning.png"
        super().__init__(icon_path, parent)
        self.base_path = base_path
        self.dtc = "0"
        self.update_dtc(self.dtc)

    def update_dtc(self, dtc):
        """
        Updates the DTC code shown on the label.
        """
        self.dtc = dtc
        if str(dtc) == "0" or dtc in [None, "", "None"]:
            self.text_label.setText("None")
            self.text_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.text_label.setText(f"Code: {dtc}")
            self.text_label.setStyleSheet("color: #F44336; font-weight: bold;")