from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QSlider, QLineEdit,
    QPushButton, QHBoxLayout, QMessageBox
)
from PySide6.QtCore import Qt, Signal


class RunSettings(QDialog):
    """Popup for run configuration: playback speed and data window."""
    start_run = Signal(float, int)  # emits seconds per message and data window

    def __init__(self, title="Run Settings", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 250)

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

    def handle_start(self):
        """Validate inputs and emit start_run signal with seconds per message."""
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

        self.accept()  # close the dialog
        self.start_run.emit(playback_rate, data_window)
