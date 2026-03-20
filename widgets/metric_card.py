from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
)

from theme import badge_style_healthy, badge_style_mild_stress, badge_style_stressed, badge_style_unknown


def metric_badge_style(status: str) -> str:
    status = str(status or "").strip().upper()

    if status == "HEALTHY":
        return badge_style_healthy()
    elif status in {"WARNING", "MODERATE"}:
        return badge_style_mild_stress()
    elif status in {"CRITICAL", "HIGH", "STRESS"}:
        return badge_style_stressed()
    else:
        return badge_style_unknown()


class MetricCard(QWidget):
    def __init__(self, title: str, formula: str):
        super().__init__()
        
        self.setMinimumHeight(160)
        self.setStyleSheet("""
            QWidget {
                background-color: #052e16;
                border: 1px solid #166534;
                border-radius: 0px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(8)

        title_label = QLabel(f"●  {title}")
        title_label.setStyleSheet("""
            color: #6ee7b7;
            font-size: 16px;
            font-weight: 800;
            letter-spacing: 1px;
        """)

        value_row = QHBoxLayout()
        value_row.setSpacing(12)

        self.value = QLabel("—")
        self.value.setStyleSheet("""
            color: #ffffff;
            font-size: 30px;
            font-weight: 900;
        """)

        self.badge = QLabel("—")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet("""
            padding: 4px 12px;
            border: 1px solid #166534;
            border-radius: 8px;
            color: #86efac;
            background-color: transparent;
            font-size: 14px;
            font-weight: 700;
        """)
        self.badge.setFixedHeight(30)

        value_row.addWidget(self.value, 0, Qt.AlignBottom)
        value_row.addWidget(self.badge, 0, Qt.AlignVCenter)
        value_row.addStretch()

        self.baseline = QLabel("Baseline: —")
        self.baseline.setStyleSheet("""
            color: #a7f3d0;
            font-size: 13px;
            font-weight: 500;
        """)

        self.delta = QLabel("— from baseline")
        self.delta.setStyleSheet("""
            color: #86efac;
            font-size: 13px;
            font-weight: 700;
        """)

        self.formula = QLabel(formula)
        self.formula.setStyleSheet("""
            color: #c4b5fd;
            font-size: 12px;
            font-family: Consolas, monospace;
        """)
        self.formula.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addLayout(value_row)
        layout.addWidget(self.baseline)
        layout.addWidget(self.delta)
        layout.addStretch()
        layout.addWidget(self.formula)
