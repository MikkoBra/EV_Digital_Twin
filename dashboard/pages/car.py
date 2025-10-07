from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
from pathlib import Path
from components.hotspot import Hotspot
from pages.popups.popup import PopupPage
from pages.popups.run_settings import RunSettings
from pages.popups.plot_popup import BatteryPopup, MotorPopup, WheelPopup
from services.data_handler import DataHandler


class Car(QWidget):
    def __init__(self, go_back_callback, digital_twin=None):
        super().__init__()
        self.digital_twin = digital_twin
        self.data_handler = DataHandler(digital_twin=digital_twin)

        image_path = Path(__file__).resolve().parent.parent / "assets" / "car.jpg"
        self.bg_pixmap = QPixmap(str(image_path))
        self.scale_factor = 0.6

        # === Back Button (Blue) ===
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

        # === run Button (Green) ===
        self.run_btn = QPushButton(self)
        self.run_btn.setFixedSize(40, 40)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;  /* green */
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1e7e34;
            }
        """)
        self.run_btn.move(self.back_btn.x() + self.back_btn.width() + 10, 10)
        self.run_btn.clicked.connect(self.show_run_popup)
        self.run_btn.raise_()

        # === Stop Button (Red) ===
        self.stop_btn = QPushButton(self)
        self.stop_btn.setFixedSize(40, 40)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #a71d2a;
            }
        """)
        self.stop_btn.move(self.run_btn.x() + self.run_btn.width() + 10, 10)
        self.stop_btn.clicked.connect(self.stop_run)
        self.stop_btn.raise_()

        # === Hotspots ===
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
        self.init_motor()
        self.init_text_boxes()
        self.data_handler.new_data_signal.connect(self.update_text_boxes)
    
    def init_text_boxes(self):
        """Create two horizontal rows of parameter boxes anchored to the bottom."""
        self.param_boxes = {}
        self.param_containers = {}

        param_names = [
            "timestamp", "soc", "soh", "charging_cycles",
            "battery_temp", "motor_rpm", "motor_torque",
            "motor_temp", "brake_pad_wear", "charging_voltage",
            "tire_pressure", "dtc"
        ]

        # Split into two rows
        num_rows = 2
        rows = [
            param_names[:len(param_names)//2],
            param_names[len(param_names)//2:]
        ]

        # Main container anchored to bottom
        self.bottom_container = QWidget(self)
        self.bottom_layout = QVBoxLayout(self.bottom_container)
        self.bottom_layout.setSpacing(10)
        self.bottom_layout.setContentsMargins(20, 0, 20, 20)  # left, top, right, bottom

        for row_params in rows:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setSpacing(20)  # fixed spacing between boxes
            row_layout.setContentsMargins(0, 0, 0, 0)

            for name in row_params:
                container = QWidget()
                v_layout = QVBoxLayout(container)
                v_layout.setSpacing(2)
                v_layout.setContentsMargins(0, 0, 0, 0)

                # Name label (top)
                label_name = QLabel(name.replace("_", " ").title())
                label_name.setAlignment(Qt.AlignCenter)
                label_name.setStyleSheet("color: black; font-weight: bold;")
                
                # Value label (bottom)
                value_label = QLabel("-")
                value_label.setAlignment(Qt.AlignCenter)
                value_label.setStyleSheet("color: black;")

                v_layout.addWidget(label_name)
                v_layout.addWidget(value_label)

                row_layout.addWidget(container)
                self.param_boxes[name] = value_label
                self.param_containers[name] = container

            self.bottom_layout.addWidget(row_widget)

        # Anchor the bottom container
        self.update_bottom_container_geometry()

    def update_bottom_container_geometry(self):
        """Position the bottom container at the bottom of the window."""
        container_height = 100  # adjust if needed
        self.bottom_container.setGeometry(0, self.height() - container_height, self.width(), container_height)

    def resizeEvent(self, event):
        """Update bottom container when window is resized."""
        super().resizeEvent(event)
        self.update_bottom_container_geometry()

    def update_text_boxes(self, state):
        """Update all text boxes with values from the State object."""
        self.param_boxes["timestamp"].setText(str(state.timestamp))
        self.param_boxes["soc"].setText(f"{state.soc:.2f}")
        self.param_boxes["soh"].setText(f"{state.soh:.2f}")
        self.param_boxes["charging_cycles"].setText(str(state.charging_cycles))  # integer
        self.param_boxes["battery_temp"].setText(f"{state.battery_temp:.2f}")
        self.param_boxes["motor_rpm"].setText(f"{state.motor_rpm:.2f}")
        self.param_boxes["motor_torque"].setText(f"{state.motor_torque:.2f}")
        self.param_boxes["motor_temp"].setText(f"{state.motor_temp:.2f}")
        self.param_boxes["brake_pad_wear"].setText(f"{state.brake_pad_wear:.2f}")
        self.param_boxes["charging_voltage"].setText(f"{state.charging_voltage:.2f}")
        self.param_boxes["tire_pressure"].setText(f"{state.tire_pressure:.2f}")
        self.param_boxes["dtc"].setText(str(state.dtc))


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
    
    def init_motor(self):
        """Initialize motor hotspots - front and rear motors with grouped behavior."""
        # Front motor (between front wheels)
        front_motor_rect = QRect(240, 280, 140, 100)
        front_motor_hotspot = Hotspot(self, front_motor_rect, rotation=30, shape="square", padding=20, group="motors")
        front_motor_hotspot.clicked.connect(self.show_motor_popup)
        self.hotspots.append(front_motor_hotspot)
        
        # Rear motor (battery area, slightly behind center)
        rear_motor_rect = QRect(550, 180, 120, 90)
        rear_motor_hotspot = Hotspot(self, rear_motor_rect, rotation=28, shape="square", padding=20, group="motors")
        rear_motor_hotspot.clicked.connect(self.show_motor_popup)
        self.hotspots.append(rear_motor_hotspot)

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
        popup = WheelPopup(
            digital_twin=self.digital_twin,
            current_state=self.data_handler.receiver.digital_twin.current_state if hasattr(self.data_handler.receiver, 'digital_twin') else None,
            parent=self
        )
        popup.exec()

    def show_battery_popup(self):
        # Get current state from digital twin
        current_state = self.digital_twin.current_state if self.digital_twin else None
        
        popup = BatteryPopup(
            digital_twin=self.digital_twin,
            current_state=current_state,
            parent=self
        )
        popup.exec()
    
    def show_motor_popup(self):
        """Show motor status popup with live plots."""
        current_state = self.digital_twin.current_state if self.digital_twin else None
        
        popup = MotorPopup(
            digital_twin=self.digital_twin,
            current_state=current_state,
            parent=self
        )
        popup.exec()

    def show_run_popup(self):
        """Popup for green run button."""
        popup = RunSettings(title="Run Settings", parent=self)
        popup.start_run.connect(self.run_data)  # connect the signal
        popup.exec()

    def run_data(self, playback_speed, data_window):
        print(f"Playback Speed: {playback_speed}")
        print(f"Data Window: {data_window}")
        self.data_handler.start_run(playback_speed, data_window)
    
    def stop_run(self):
        self.data_handler.stop_run()
