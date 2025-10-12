from PySide6.QtWidgets import QMainWindow
from page_stack import PageStack
from pages.title import Title
from pages.car import Car
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from System_State import DigitalTwin

class MainWindow(QMainWindow):
    """
    The window containing the GUI and its pages.
    """
    def __init__(self):
        """
        Initializes the main window with a set aspect ratio that can be
        scaled with the "scale" parameter.
        """
        super().__init__()
        self.setWindowTitle("EV Digital Twin")
        self.digital_twin = DigitalTwin()

        scale = 1.2
        self.base_width = 930 * scale
        self.base_height = 550  * scale
        self.aspect_ratio = self.base_width / self.base_height

        self.resize(self.base_width, self.base_height)

        self.stack = PageStack()
        page1 = Title(lambda: self.stack.fade_to_index(1))
        page2 = Car(lambda: self.stack.fade_to_index(0), digital_twin=self.digital_twin)

        self.stack.addWidget(page1)
        self.stack.addWidget(page2)
        self.setCentralWidget(self.stack)

    def resizeEvent(self, event):
        """
        Forces the window to maintain the initial aspect ratio.
        """
        w = self.width()
        h = self.height()

        target_h = int(w / self.aspect_ratio)

        if target_h != h:
            self.blockSignals(True)
            self.resize(w, target_h)
            self.blockSignals(False)

        super().resizeEvent(event)
