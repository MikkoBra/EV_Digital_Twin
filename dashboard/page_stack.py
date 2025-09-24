from PySide6.QtWidgets import QStackedWidget, QGraphicsOpacityEffect
from PySide6.QtCore import QPropertyAnimation, QEasingCurve

class PageStack(QStackedWidget):
    def __init__(self):
        super().__init__()
        # remove self.setGraphicsEffect(...) from here
        self.anim = None

    def fade_to_index(self, index: int, duration=600):
        # create an effect on the CURRENT page only
        current_page = self.currentWidget()
        effect = QGraphicsOpacityEffect(current_page)
        current_page.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", current_page)
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(lambda: self._switch_and_fade_in(index, duration))
        anim.start()
        self.anim = anim

    def _switch_and_fade_in(self, index, duration):
        self.setCurrentIndex(index)
        page = self.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)

        anim = QPropertyAnimation(effect, b"opacity", page)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self.anim = anim

