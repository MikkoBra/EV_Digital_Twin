from PySide6.QtWidgets import QMainWindow
from page_stack import PageStack
from pages.title import Title
from pages.car import Car

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EV Digital Twin")

        self.base_width = 930
        self.base_height = 550
        self.aspect_ratio = self.base_width / self.base_height

        self.resize(self.base_width, self.base_height)

        self.stack = PageStack()
        page1 = Title(lambda: self.stack.fade_to_index(1))
        page2 = Car(lambda: self.stack.fade_to_index(0))

        self.stack.addWidget(page1)
        self.stack.addWidget(page2)
        self.setCentralWidget(self.stack)

    def resizeEvent(self, event):
        """
        Force the window to maintain the initial aspect ratio.
        """
        w = self.width()
        h = self.height()

        target_h = int(w / self.aspect_ratio)

        if target_h != h:
            self.blockSignals(True)
            self.resize(w, target_h)
            self.blockSignals(False)

        super().resizeEvent(event)
