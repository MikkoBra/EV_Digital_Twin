from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QIcon
from PySide6.QtCore import QSize

class IconButton(QPushButton):
    def __init__(self, icon_path=None, color="#2d89ef", hover_color="#1e5cb3", size=QSize(40, 40), callback=None, parent=None):
        super().__init__(parent)
        self.setFixedSize(size)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """)
        if icon_path:
            self.setIcon(QIcon(str(icon_path)))
            self.setIconSize(QSize(24, 24))

        if callback:
            self.clicked.connect(callback)

class BackButton(IconButton):
    def __init__(self, icon_path, callback, parent=None):
        super().__init__(
            icon_path=icon_path,
            color="#2d89ef",
            hover_color="#1e5cb3",
            callback=callback,
            parent=parent
        )

class RunButton(IconButton):
    def __init__(self, icon_path, callback, parent=None):
        super().__init__(
            icon_path=icon_path,
            color="#28a745",
            hover_color="#1e7e34",
            callback=callback,
            parent=parent
        )
        self.setIconSize(QSize(30, 30))

class StopButton(IconButton):
    def __init__(self, icon_path, callback, parent=None):
        super().__init__(
            icon_path=icon_path,
            color="#dc3545",
            hover_color="#a71d2a",
            callback=callback,
            parent=parent
        )
        self.setIconSize(QSize(14, 14))

class PauseButton(IconButton):
    def __init__(self, icon_path, callback, parent=None):
        super().__init__(
            icon_path=icon_path,
            color="#ffc107",
            hover_color="#e0a800",
            callback=callback,
            parent=parent
        )
        self.setIconSize(QSize(20, 20))