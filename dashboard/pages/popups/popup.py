from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

class PopupPage(QDialog):
    """Generic popup page to show plots or information."""
    def __init__(self, title="Popup", content_text="This is a plot placeholder", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        label = QLabel(content_text, self)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)