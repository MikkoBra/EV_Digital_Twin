from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from pathlib import Path
from components.hotspot import Hotspot
from pages.popups.popup import PopupPage
from pages.popups.run_settings import RunSettings
from pages.popups.plot_popup import BatteryPopup, MotorPopup, WheelPopup
from services.data_handler import DataHandler
from components.buttons import BackButton, RunButton, StopButton
from components.meters import BatteryMeter, TachoMeter


class Car(QWidget):
    def __init__(self, go_back_callback, digital_twin=None):
        super().__init__()
        self.digital_twin = digital_twin
        self.data_handler = DataHandler(digital_twin=digital_twin)

        image_path = Path(__file__).resolve().parent.parent / "assets" / "car.jpg"
        self.bg_pixmap = QPixmap(str(image_path))
        self.scale_factor = 0.6
        self.bg_x_offset = 50

        # === Back Button (Blue) ===
        arrow_path = Path(__file__).resolve().parent.parent / "assets" / "arrow-left.png"
        self.back_btn = BackButton(arrow_path, go_back_callback, parent=self)
        self.back_btn.move(10, 10)

        # === run Button (Green) ===
        play_icon_path = Path(__file__).resolve().parent.parent / "assets" / "play-button.png"
        self.run_btn = RunButton(play_icon_path, self.show_run_popup, parent=self)
        self.run_btn.move(self.back_btn.x() + self.back_btn.width() + 10, 10)

        # === Stop Button (Red) ===
        stop_icon_path = Path(__file__).resolve().parent.parent / "assets" / "stop-button.png"
        self.stop_btn = StopButton(stop_icon_path, self.stop_run, parent=self)
        self.stop_btn.move(self.run_btn.x() + self.run_btn.width() + 10, 10)

        # === Hotspots ===
        self.hotspots = []
        self.init_battery()
        self.init_wheels()
        self.init_motor()

        # === State Indicators ===
        self.init_text_boxes()
        self.battery_meter = BatteryMeter(parent=self)
        self.battery_meter.update_charge(100)
        self.tacho_meter = TachoMeter(parent=self)
        self.tacho_meter.update_position(image_rect=QRect(50, 50, 100, 100))  # adjust as needed
        self.data_handler.new_data_signal.connect(self.update_state)

    def init_text_boxes(self):
        """Create right-side panel with parameter boxes."""
        self.param_boxes = {}
        self.param_containers = {}

        param_names = [
            "charging_cycles",
            "battery_temp", "motor_rpm", "motor_torque",
            "motor_temp", "brake_pad_wear", "charging_voltage",
            "tire_pressure", "dtc"
        ]

        # Split into rows with at most 2 entries each
        rows = [param_names[i:i+2] for i in range(0, len(param_names), 2)]

        # Right-side container
        self.right_container = QWidget(self)
        self.right_layout = QVBoxLayout(self.right_container)
        self.right_layout.setContentsMargins(10, 10, 10, 10)  # panel margins

        # Define fonts
        name_font = QFont("Segoe UI", 10, QFont.Bold)
        value_font = QFont("Segoe UI", 9)

        for i, row_params in enumerate(rows):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)

            for name in row_params:
                container = QWidget()
                container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                v_layout = QVBoxLayout(container)
                v_layout.setSpacing(2)          # vertical spacing within pair (fixed)
                v_layout.setContentsMargins(0, 0, 0, 0)

                # Name label
                label_name = QLabel(name.replace("_", " ").title() + ":")
                label_name.setAlignment(Qt.AlignCenter)
                label_name.setFont(name_font)
                label_name.setStyleSheet("color: #333;")  # dark gray instead of black

                # Value label
                value_label = QLabel("-")
                value_label.setAlignment(Qt.AlignCenter)
                value_label.setFont(value_font)
                value_label.setStyleSheet("color: #000;")  # pure black

                v_layout.addWidget(label_name)
                v_layout.addWidget(value_label)

                row_layout.addWidget(container)
                self.param_boxes[name] = value_label
                self.param_containers[name] = container

            self.right_layout.addWidget(row_widget)

            # Add stretch **after each row except the last** to allow dynamic spacing
            if i < len(rows) - 1:
                self.right_layout.addStretch(1)
    
    def update_right_container_geometry(self):
        container_width = 300
        x = self.width() - container_width - 20
        y = 100
        container_height = self.height() - y - 100  # bottom margin
        self.right_container.setGeometry(x, y, container_width, container_height)
        
    def resizeEvent(self, event):
        """Update bottom container when window is resized."""
        super().resizeEvent(event)
        self.update_right_container_geometry()

    def update_state(self, state):
        """Update all text boxes with values from the State object."""
        # self.param_boxes["timestamp"].setText(str(state.timestamp))
        # self.param_boxes["soc"].setText(f"{state.soc:.2f}")
        # self.param_boxes["soh"].setText(f"{state.soh:.2f}")
        self.param_boxes["charging_cycles"].setText(str(state.charging_cycles))  # integer
        self.param_boxes["battery_temp"].setText(f"{state.battery_temp:.2f}")
        self.param_boxes["motor_rpm"].setText(f"{state.motor_rpm:.2f}")
        self.param_boxes["motor_torque"].setText(f"{state.motor_torque:.2f}")
        self.param_boxes["motor_temp"].setText(f"{state.motor_temp:.2f}")
        self.param_boxes["brake_pad_wear"].setText(f"{state.brake_pad_wear:.2f}")
        self.param_boxes["charging_voltage"].setText(f"{state.charging_voltage:.2f}")
        self.param_boxes["tire_pressure"].setText(f"{state.tire_pressure:.2f}")
        self.param_boxes["dtc"].setText(str(state.dtc))

        self.battery_meter.update_charge(state.soc)
        self.tacho_meter.update_rpm(state.motor_rpm)
        
        self.update()

    def init_battery(self):
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

            x = self.bg_x_offset
            y = (self.height() - scaled_pix.height()) // 2
            painter.drawPixmap(x, y, scaled_pix)

            scale_x = scaled_pix.width() / self.bg_pixmap.width()
            scale_y = scaled_pix.height() / self.bg_pixmap.height()

            image_rect = QRect(x, y, scaled_pix.width(), scaled_pix.height())

            # === Position BatteryMeter ===
            self.battery_meter.update_position(image_rect)

            # === Position TachoMeter to the right of BatteryMeter ===
            battery_rect = self.battery_meter.geometry()
            spacing = 10  # pixels between battery and tachometer
            tacho_x = battery_rect.right() + spacing
            tacho_y = battery_rect.top() + (battery_rect.height() - self.tacho_meter.height()) // 2
            self.tacho_meter.move(tacho_x, tacho_y)

            # Update hotspots
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
