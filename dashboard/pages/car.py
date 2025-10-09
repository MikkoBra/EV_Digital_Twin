from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy, QScrollArea, QTextEdit, QFrame
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from pathlib import Path
from components.hotspot import Hotspot
from pages.popups.run_settings import RunSettings
from pages.popups.plot_popup import BatteryPopup, MotorPopup, WheelPopup
from services.data_handler import DataHandler
from components.buttons import BackButton, RunButton, StopButton, PauseButton
from components.meters import BatteryMeter, TachoMeter, CycleMeter, DTCMeter
import pandas as pd


class Car(QWidget):
    def __init__(self, go_back_callback, digital_twin=None):
        super().__init__()
        self.digital_twin = digital_twin
        self.data_handler = DataHandler(digital_twin=digital_twin)
        self.last_dtc_code = 0

        image_path = Path(__file__).resolve().parent.parent / "assets" / "car.jpg"
        self.bg_pixmap = QPixmap(str(image_path))
        self.scale_factor = 0.65
        self.bg_x_offset = 50

        # === Back Button (Blue) ===
        arrow_path = Path(__file__).resolve().parent.parent / "assets" / "arrow-left.png"
        self.back_btn = BackButton(arrow_path, go_back_callback, parent=self)
        self.back_btn.move(10, 10)

        # === run Button (Green) ===
        play_icon_path = Path(__file__).resolve().parent.parent / "assets" / "play-button.png"
        self.run_btn = RunButton(play_icon_path, self.show_run_popup, parent=self)
        self.run_btn.move(self.back_btn.x() + self.back_btn.width() + 10, 10)

        # === Pause Button (Orange) ===
        pause_icon_path = Path(__file__).resolve().parent.parent / "assets" / "pause_button.png"
        self.pause_btn = PauseButton(pause_icon_path, self.toggle_pause, parent=self)
        self.pause_btn.move(self.run_btn.x() + self.run_btn.width() + 10, 10)
        self.is_paused = False

        # === Stop Button (Red) ===
        stop_icon_path = Path(__file__).resolve().parent.parent / "assets" / "stop-button.png"
        self.stop_btn = StopButton(stop_icon_path, self.stop_run, parent=self)
        self.stop_btn.move(self.pause_btn.x() + self.pause_btn.width() + 10, 10)

        # === DateTime Display ===
        self.datetime_label = QLabel("----------- --:--:--", parent=self)
        datetime_font = QFont("Segoe UI", 18, QFont.Bold)
        self.datetime_label.setFont(datetime_font)
        self.datetime_label.setStyleSheet("""
            QLabel {
                color: #2196F3;
                background-color: rgba(255, 255, 255, 0.9);
                padding: 10px 30px;
                border-radius: 8px;
                border: 2px solid #2196F3;
            }
        """)
        self.datetime_label.setAlignment(Qt.AlignCenter)
        self.datetime_label.setMinimumWidth(300)
        # Position will be set in resizeEvent

        # === Status Panel (Anomaly Detection & DTC Prediction) ===
        self.init_status_panel()

        # === Hotspots ===
        self.hotspots = []
        self.init_battery()
        self.init_wheels()
        self.init_motor()

        # === State Indicators ===
        self.init_meters_panel()
        self.data_handler.new_data_signal.connect(self.update_state)

    def init_status_panel(self):
        """Create status panel for anomaly detection and DTC prediction."""
        self.status_panel = QWidget(self)
        status_layout = QVBoxLayout(self.status_panel)
        status_layout.setContentsMargins(8, 8, 8, 8)
        status_layout.setSpacing(6)
        
        # Panel styling
        self.status_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 8px;
                border: 2px solid #E0E0E0;
            }
        """)
        
        # Title font
        title_font = QFont("Segoe UI", 11, QFont.Bold)
        value_font = QFont("Segoe UI", 9)
        
        # === Anomaly Detection Status ===
        anomaly_title = QLabel("Anomaly Detection")
        anomaly_title.setFont(title_font)
        anomaly_title.setStyleSheet("color: #333; border: none; background: transparent;")
        anomaly_title.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(anomaly_title)
        
        # Anomaly status indicator (centered text like DTC)
        self.anomaly_text = QLabel("Normal")
        self.anomaly_text.setFont(value_font)
        self.anomaly_text.setStyleSheet("color: #4CAF50; border: none; background: transparent;")
        self.anomaly_text.setAlignment(Qt.AlignCenter)
        self.anomaly_text.setWordWrap(True)
        status_layout.addWidget(self.anomaly_text)
        
        # === DTC Prediction ===
        dtc_title = QLabel("DTC Prediction (24h)")
        dtc_title.setFont(title_font)
        dtc_title.setStyleSheet("color: #333; border: none; background: transparent;")
        dtc_title.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(dtc_title)
        
        # DTC prediction value
        self.dtc_prediction_label = QLabel("No fault codes predicted")
        self.dtc_prediction_label.setFont(value_font)
        self.dtc_prediction_label.setStyleSheet("color: #4CAF50; border: none; background: transparent;")
        self.dtc_prediction_label.setAlignment(Qt.AlignCenter)
        self.dtc_prediction_label.setWordWrap(True)
        status_layout.addWidget(self.dtc_prediction_label)
        
        # Position will be set in resizeEvent
        self.status_panel.setFixedSize(220, 130)
    
    def init_meters_panel(self):
        """Create right-side panel and arrange meters in rows of up to 2."""
        self.right_container = QWidget(self)
        main_layout = QVBoxLayout(self.right_container)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(20)
        self.battery_meter = BatteryMeter(parent=self.right_container)
        self.tacho_meter = TachoMeter(parent=self.right_container)
        self.cycle_meter = CycleMeter(parent=self.right_container)
        self.dtc_meter = DTCMeter(parent=self.right_container)

        # Create meters
        meters = [
            self.battery_meter,
            self.cycle_meter,
            self.tacho_meter,
            self.dtc_meter
        ]
        meters[0].update_charge(100)

        # Arrange meters in rows of 2
        row_layout = None
        for i, meter in enumerate(meters):
            if i % 2 == 0:
                # Start a new row
                row_layout = QHBoxLayout()
                row_layout.setSpacing(10)
                main_layout.addLayout(row_layout)

                # Add left stretch before first widget
                row_layout.addStretch(1)

            # Add the meter
            row_layout.addWidget(meter, alignment=Qt.AlignCenter)

            # If it's the second widget in the row OR last in list
            # → Add right stretch to balance the row
            if i % 2 == 1 or i == len(meters) - 1:
                row_layout.addStretch(1)

        # --- DTC History below ---
        self.dtc_history_frame = QFrame(self)
        self.dtc_history_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.95);
                border: 1px solid #CCC;
                border-radius: 8px;
            }
        """)
        dtc_layout = QVBoxLayout(self.dtc_history_frame)
        dtc_layout.setContentsMargins(10, 10, 10, 10)

        dtc_label = QLabel("DTC History")
        dtc_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        dtc_label.setAlignment(Qt.AlignCenter)
        dtc_label.setStyleSheet("color: #333; margin-bottom: 6px;")
        dtc_layout.addWidget(dtc_label)

        self.dtc_history_box = QTextEdit()
        self.dtc_history_box.setReadOnly(True)
        self.dtc_history_box.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.9);
                border: none;
                padding: 6px;
                color: #000;
                font-family: 'Segoe UI';
                font-size: 9pt;
            }
        """)
        dtc_layout.addWidget(self.dtc_history_box)

    
    def update_right_container_geometry(self):
        """Keep right-side layout logic identical."""
        container_width = 230
        x = self.width() - container_width - 15
        y = 200 # Top margin
        container_height = self.height() - y - 220 # Bottom margin
        self.right_container.setGeometry(x, y, container_width, container_height)

        history_y = y + container_height + 40
        history_height = 140
        self.dtc_history_frame.setGeometry(x, history_y, container_width, history_height)
        
    def resizeEvent(self, event):
        """Ensure meters reposition with window resize."""
        super().resizeEvent(event)
        self.update_right_container_geometry()
        
        # Position datetime label in top-center
        self.datetime_label.adjustSize()
        datetime_x = (self.width() - self.datetime_label.width()) // 2
        datetime_y = 10
        self.datetime_label.move(datetime_x, datetime_y)
        
        # Position status panel on the RIGHT (gespiegeld)
        # Right side: total_width - panel_width - margin
        status_x = self.width() - 220 - 10  # 220px panel width, 10px margin
        status_y = 10  # Same height as datetime
        self.status_panel.move(status_x, status_y)
        self.status_panel.raise_()  # Bring to front to ensure visibility

    def update_state(self, state):
        """Update all text boxes with values from the State object."""
        # Update datetime display
        if hasattr(state, 'timestamp') and state.timestamp:
            # Convert timestamp to datetime string
            if isinstance(state.timestamp, str):
                dt = pd.to_datetime(state.timestamp)
            else:
                dt = state.timestamp
            self.datetime_label.setText(dt.strftime("%Y-%m-%d %H:%M:%S"))
        
        # Update status panel (placeholder for now - will be replaced with real anomaly detection)
        self.update_status_panel(state)
        
        # self.param_boxes["timestamp"].setText(str(state.timestamp))
        # self.param_boxes["soc"].setText(f"{state.soc:.2f}")
        # self.param_boxes["soh"].setText(f"{state.soh:.2f}")
        # self.param_boxes["charging_cycles"].setText(str(state.charging_cycles))  # integer
        # self.param_boxes["battery_temp"].setText(f"{state.battery_temp:.2f}")
        # self.param_boxes["motor_rpm"].setText(f"{state.motor_rpm:.2f}")
        # self.param_boxes["motor_torque"].setText(f"{state.motor_torque:.2f}")
        # self.param_boxes["motor_temp"].setText(f"{state.motor_temp:.2f}")
        # self.param_boxes["brake_pad_wear"].setText(f"{state.brake_pad_wear:.2f}")
        # self.param_boxes["charging_voltage"].setText(f"{state.charging_voltage:.2f}")
        # self.param_boxes["tire_pressure"].setText(f"{state.tire_pressure:.2f}")
        # === Handle DTC Change and Log History ===
        current_dtc = getattr(state, "dtc", '0')
        timestamp = getattr(state, "timestamp", None)

        # Detect change from 0 → something non-zero
        if self.last_dtc_code == '0' and current_dtc != '0':
            if timestamp:
                if isinstance(timestamp, str):
                    dt = pd.to_datetime(timestamp)
                else:
                    dt = timestamp
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp_str = "(no timestamp)"
            
            log_entry = f"[{timestamp_str}]  DTC Code Detected: {current_dtc}\n"
            self.dtc_history_box.append(log_entry)

        # Update tracking: when it returns to 0, arm for next event
        self.last_dtc_code = current_dtc

        self.battery_meter.update_charge(state.soc)
        self.tacho_meter.update_rpm(state.motor_rpm)
        self.cycle_meter.update_cycles(state.charging_cycles)
        self.dtc_meter.update_dtc(state.dtc)
        
        self.update()
    
    def update_status_panel(self, state):
        """Update anomaly detection and DTC prediction status from real model predictions."""
        
        # === Anomaly Detection ===
        # Get anomaly score from state (if available)
        if hasattr(state, 'anomaly_score') and state.anomaly_score is not None:
            score = state.anomaly_score
            
            # Determine color based on score thresholds:
            # Red if score < -0.25 (anomaly)
            # Orange if -0.25 <= score < 0 (warning)
            # Green otherwise (normal)
            if score < -0.25:
                color = "#F44336"  # Red
                text = f"Anomaly ({score:.3f})"
            elif score < 0:
                color = "#FF9800"  # Orange
                text = f"Warning ({score:.3f})"
            else:
                color = "#4CAF50"  # Green
                text = f"Normal ({score:.3f})"
        else:
            # No anomaly score available yet
            color = "#9E9E9E"  # Grey
            text = "Calculating..."
        
        self.anomaly_text.setText(text)
        self.anomaly_text.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        
        # === DTC Prediction ===
        # Get DTC probability from state (if available)
        if hasattr(state, 'dtc_score') and state.dtc_score is not None:
            dtc_prob = state.dtc_score
            dtc_label = state.dtc_label if hasattr(state, 'dtc_label') else (dtc_prob >= 0.5)
            
            # Determine color based on probability:
            # Red if prob >= 0.5 (fault predicted)
            # Orange if 0.25 <= prob < 0.5 (warning)
            # Green otherwise (no fault)
            if dtc_prob >= 0.5:
                dtc_color = "#F44336"  # Red
                dtc_text = f"Fault predicted ({dtc_prob:.1%})"
            elif dtc_prob >= 0.25:
                dtc_color = "#FF9800"  # Orange
                dtc_text = f"Warning ({dtc_prob:.1%})"
            else:
                dtc_color = "#4CAF50"  # Green
                dtc_text = f"Normal ({dtc_prob:.1%})"
        else:
            # No DTC prediction available yet
            dtc_color = "#9E9E9E"  # Grey
            dtc_text = "Calculating..."
        
        self.dtc_prediction_label.setText(dtc_text)
        self.dtc_prediction_label.setStyleSheet(f"color: {dtc_color}; border: none; background: transparent;")

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

            # # === Position BatteryMeter ===
            # self.battery_meter.update_position(image_rect)

            # # === Position TachoMeter to the right of BatteryMeter ===
            # battery_rect = self.battery_meter.geometry()
            # spacing = 10  # pixels between battery and tachometer
            # tacho_x = battery_rect.right() + spacing
            # tacho_y = battery_rect.top() + (battery_rect.height() - self.tacho_meter.height()) // 2
            # self.tacho_meter.move(tacho_x, tacho_y)

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

    def run_data(self, playback_speed, data_window, start_datetime=None):
        print(f"Playback Speed: {playback_speed}")
        print(f"Data Window: {data_window}")
        print(f"Start DateTime: {start_datetime}")
        self.data_handler.start_run(playback_speed, data_window, start_datetime)
    
    def toggle_pause(self):
        """Toggle pause/resume of the simulation."""
        if self.is_paused:
            # Resume
            self.data_handler.resume_run()
            self.is_paused = False
            print("Simulation resumed")
        else:
            # Pause
            self.data_handler.pause_run()
            self.is_paused = True
            print("Simulation paused")
    
    def stop_run(self):
        self.data_handler.stop_run()
        self.is_paused = False  # Reset pause state when stopping
