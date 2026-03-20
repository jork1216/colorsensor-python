from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QGraphicsOpacityEffect,
)


class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None, hover_bg=None):
        super().__init__(text, parent)
        self.hover_bg = hover_bg

        self.setFixedSize(34, 30)
        self.setCursor(Qt.PointingHandCursor)

        base_style = """
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                font-size: 16px;
                font-weight: 700;
                border-radius: 6px;
            }
        """

        if hover_bg:
            base_style += f"""
                QPushButton:hover {{
                    background-color: {hover_bg};
                }}
            """

        self.setStyleSheet(base_style)

        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(0.82)
        self.setGraphicsEffect(self.effect)

        self.fade_anim = QPropertyAnimation(self.effect, b"opacity", self)
        self.fade_anim.setDuration(140)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

    def enterEvent(self, event):
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.effect.opacity())
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.fade_anim.stop()
        self.fade_anim.setStartValue(self.effect.opacity())
        self.fade_anim.setEndValue(0.82)
        self.fade_anim.start()
        super().leaveEvent(event)


class TitleBar(QWidget):
    def __init__(self, parent_window=None):
        super().__init__()
        self.parent_window = parent_window
        self.drag_pos = None

        self.setFixedHeight(44)
        self.setStyleSheet("""
            background-color: #0f172a;
            border-bottom: 1px solid #1e293b;
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        logo = QLabel()
        pixmap = QPixmap("logo.png")
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setFixedSize(24, 24)

        title = QLabel("Real-Time Algae Biosensor")
        title.setStyleSheet("color: white; font-size: 14px; font-weight: 700;")

        title_text = QVBoxLayout()
        title_text.setContentsMargins(0, 0, 0, 0)
        title_text.setSpacing(0)
        title_text.addWidget(title)

        btn_min = AnimatedButton("—")
        btn_close = AnimatedButton("✕", hover_bg="#dc2626")

        if parent_window:
            btn_min.clicked.connect(parent_window.showMinimized)
            btn_close.clicked.connect(parent_window.close)

        layout.addWidget(logo)
        layout.addLayout(title_text)
        layout.addStretch()
        layout.addWidget(btn_min)
        layout.addWidget(btn_close)

        self.mousePressEvent = self.title_bar_mouse_press
        self.mouseMoveEvent = self.title_bar_mouse_move

    def title_bar_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            if self.parent_window:
                self.drag_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            if self.parent_window:
                self.parent_window.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
