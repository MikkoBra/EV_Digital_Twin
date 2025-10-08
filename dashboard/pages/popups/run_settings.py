from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QSlider, QLineEdit,
    QPushButton, QHBoxLayout, QMessageBox, QDateTimeEdit, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QDateTime


class RunSettings(QDialog):
    """Popup for run configuration: playback speed, data window, and start datetime."""
    start_run = Signal(float, int, str)  # emits seconds per message, data window, and start datetime (ISO string or None)

    def __init__(self, title="Run Settings", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 350)

        # Layouts
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)

        # === Playback speed ===
        speed_label = QLabel("Playback Speed (messages per second):", self)
        self.speed_value_label = QLabel("1", self)  # default msg/sec
        self.speed_value_label.setAlignment(Qt.AlignCenter)

        self.speed_slider = QSlider(Qt.Horizontal, self)
        self.speed_slider.setMinimum(1)      # 1 msg/sec
        self.speed_slider.setMaximum(10)     # 10 msg/sec
        self.speed_slider.setValue(1)
        self.speed_slider.setTickInterval(1)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.valueChanged.connect(self.update_speed_label)

        main_layout.addWidget(speed_label)
        main_layout.addWidget(self.speed_slider)
        main_layout.addWidget(self.speed_value_label)

        # === Data history window ===
        window_label = QLabel("Window for Data History (hours):", self)
        self.window_input = QLineEdit(self)
        self.window_input.setPlaceholderText("Enter a number >= 5")
        main_layout.addWidget(window_label)
        main_layout.addWidget(self.window_input)

        # === Custom start datetime ===
        self.use_custom_start_checkbox = QCheckBox("Start from custom datetime", self)
        self.use_custom_start_checkbox.setChecked(False)
        self.use_custom_start_checkbox.toggled.connect(self.toggle_datetime_picker)
        main_layout.addWidget(self.use_custom_start_checkbox)

        datetime_label = QLabel("Start DateTime:", self)
        self.datetime_picker = QDateTimeEdit(self)
        self.datetime_picker.setCalendarPopup(True)
        self.datetime_picker.setDisplayFormat("yyyy-MM-dd HH:00:00")
        # Set default to 2020-01-01 00:00:00
        default_datetime = QDateTime(2020, 1, 1, 0, 0, 0)
        self.datetime_picker.setDateTime(default_datetime)
        # Configure time edit to only allow whole hours
        self.datetime_picker.setTimeSpec(Qt.LocalTime)
        self.datetime_picker.setEnabled(False)  # Disabled by default
        main_layout.addWidget(datetime_label)
        main_layout.addWidget(self.datetime_picker)

        # === Start button ===
        button_layout = QHBoxLayout()
        start_button = QPushButton("Start", self)
        start_button.setStyleSheet("""
            QPushButton {
                background-color: #2d89ef;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1e5cb3;
            }
        """)
        start_button.clicked.connect(self.handle_start)
        button_layout.addStretch()
        button_layout.addWidget(start_button)
        button_layout.addStretch()

        main_layout.addLayout(button_layout)

    def update_speed_label(self):
        """Update label to show messages per second."""
        msg_per_sec = self.speed_slider.value()
        self.speed_value_label.setText(f"{msg_per_sec}")
    
    def toggle_datetime_picker(self, checked):
        """Enable/disable datetime picker based on checkbox."""
        self.datetime_picker.setEnabled(checked)

    def handle_start(self):
        """Validate inputs and emit start_run signal with seconds per message and optional start datetime."""
        msg_per_sec = self.speed_slider.value()
        playback_rate = 1.0 / msg_per_sec  # seconds per message

        try:
            data_window = int(self.window_input.text())
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please enter an integer greater than or equal to 5."
            )
            return

        if data_window < 5:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Data window must be greater than or equal to 5."
            )
            return

        # Get start datetime if custom start is enabled
        start_datetime = None
        if self.use_custom_start_checkbox.isChecked():
            # Convert QDateTime to ISO string format (hele uren)
            dt = self.datetime_picker.dateTime()
            # Zorg dat minuten en seconden 0 zijn
            dt.setTime(dt.time().addSecs(-dt.time().minute() * 60 - dt.time().second()))
            start_datetime = dt.toString("yyyy-MM-ddTHH:00:00")

        self.accept()  # close the dialog
        self.start_run.emit(playback_rate, data_window, start_datetime)
