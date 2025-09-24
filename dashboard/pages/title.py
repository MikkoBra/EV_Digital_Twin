
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

class Title(QWidget):
    def __init__(self, go_next_callback):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        label = QLabel("Electric Vehicle Digital Twin\nTeam O")
        label.setAlignment(Qt.AlignCenter)
        label_font = QFont("Segoe UI", 14)
        label.setFont(label_font)
        layout.addWidget(label)

        btn = QPushButton("Start")
        btn.clicked.connect(go_next_callback)

        btn_font = QFont("Segoe UI", 14, QFont.Bold)
        btn.setFont(btn_font)

        btn.setFixedHeight(50)
        btn.setFixedWidth(160)

        btn.setStyleSheet("""
            QPushButton {
                background-color: #2d89ef;
                color: white;
                border-radius: 16px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #1e5cb3;
            }
        """)
        layout.addWidget(btn, alignment=Qt.AlignCenter)
