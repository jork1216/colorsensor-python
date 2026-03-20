import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)


class HistoryTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(9)
        self.setHorizontalHeaderLabels([
            "TIMESTAMP",
            "STATUS",
            "CHL INDEX",
            "Δ",
            "CAR:CHL",
            "Δ",
            "YELLOW",
            "Δ",
            "STRESS RATIO",
        ])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.NoSelection)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSortingEnabled(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

        self.setColumnWidth(0, 220)  # TIMESTAMP
        self.setColumnWidth(1, 140)  # STATUS
        self.setColumnWidth(2, 120)  # CHL INDEX
        self.setColumnWidth(3, 90)   # Δ
        self.setColumnWidth(4, 120)  # CAR:CHL
        self.setColumnWidth(5, 90)   # Δ
        self.setColumnWidth(6, 120)  # YELLOW
        self.setColumnWidth(7, 90)   # Δ
        self.setColumnWidth(8, 140)  # STRESS RATIO
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.setStyleSheet("""
            QTableWidget {
                background-color: #1e1650;
                color: #ffffff;
                border: 1px solid #3d2f8f;
                border-radius: 14px;
                gridline-color: transparent;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #1e1650;
                color: #c4b5fd;
                border: none;
                border-bottom: 1px solid #3d2f8f;
                padding: 14px 10px;
                font-size: 12px;
                font-weight: 800;
            }
            QTableWidget::item {
                border-bottom: 1px solid #2d2070;
                padding: 10px;
            }
        """)

    def make_table_item(self, text, color="#e5e7eb", bold=False, align=None, bg=None):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        if bg:
            item.setBackground(QColor(bg))
        font = item.font()
        font.setBold(bold)
        item.setFont(font)
        if align is not None:
            item.setTextAlignment(align)
        return item

    def format_delta(self, value):
        if value is None or pd.isna(value):
            return "—"
        sign = "+" if float(value) >= 0 else ""
        return f"{sign}{float(value):.1f}%"

    def status_cell_style(self, status):
        s = str(status or "").upper()
        if s == "HEALTHY":
            return "#86efac", "#052e16"
        if s in {"WARNING", "MODERATE"}:
            return "#fde047", "#3f2a06"
        return "#f87171", "#3f1113"

    def delta_color(self, value):
        if value is None or pd.isna(value):
            return "#9ca3af"
        return "#6ee7b7" if float(value) >= 0 else "#f87171"

    def add_live_history_row(self, timestamp_str, overall, cur, delta, count_label):
        self.insertRow(0)

        fg, bg = self.status_cell_style(overall)

        row_bg = "#2d2070"

        values = [
            self.make_table_item(timestamp_str, "#c4b5fd", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
            self.make_table_item(f"● {str(overall).upper()}", fg, True, Qt.AlignCenter, bg),
            self.make_table_item(f"{cur['chlorophyll_index']:.3f}", "#6ee7b7", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
            self.make_table_item(self.format_delta(delta["chlorophyll_index"]), self.delta_color(delta["chlorophyll_index"]), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
            self.make_table_item(f"{cur['car_chl_ratio']:.3f}", "#6ee7b7", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
            self.make_table_item(self.format_delta(delta["car_chl_ratio"]), self.delta_color(delta["car_chl_ratio"]), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
            self.make_table_item(f"{cur['yellow_index']:.3f}", "#fcd34d", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
            self.make_table_item(self.format_delta(delta["yellow_index"]), self.delta_color(delta["yellow_index"]), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
            self.make_table_item(f"{cur['stress_ratio']:.3f}", "#f87171", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg),
        ]

        for col, item in enumerate(values):
            self.setItem(0, col, item)

        if self.rowCount() > 100:  # Default limit, can be made configurable if needed
            self.removeRow(self.rowCount() - 1)

        count_label.setText(f"{self.rowCount()} snaps recorded")

    def populate_records_history_table(self, sdf: pd.DataFrame, count_label):
        self.setRowCount(0)

        if sdf.empty:
            count_label.setText("0 snaps recorded")
            return

        for _, row in sdf.sort_values("time", ascending=False).iterrows():
            r = self.rowCount()
            self.insertRow(r)

            overall = str(row.get("overall_status", "—")).upper()
            fg, bg = self.status_cell_style(overall)
            row_bg = "#1e1650"

            ts = row["time"]
            if pd.notna(ts):
                ts_text = pd.to_datetime(ts).strftime("%Y-%m-%d %I:%M:%S %p")
            else:
                ts_text = "—"

            self.setItem(r, 0, self.make_table_item(ts_text, "#c4b5fd", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            self.setItem(r, 1, self.make_table_item(f"● {overall}", fg, True, Qt.AlignCenter, bg))
            self.setItem(r, 2, self.make_table_item(f"{float(row.get('chlorophyll_index', np.nan)):.3f}" if pd.notna(row.get("chlorophyll_index", np.nan)) else "—", "#6ee7b7", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            self.setItem(r, 3, self.make_table_item(self.format_delta(row.get("chlorophyll_index_delta_pct", np.nan)), self.delta_color(row.get("chlorophyll_index_delta_pct", np.nan)), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            self.setItem(r, 4, self.make_table_item(f"{float(row.get('car_chl_ratio', np.nan)):.3f}" if pd.notna(row.get("car_chl_ratio", np.nan)) else "—", "#6ee7b7", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            self.setItem(r, 5, self.make_table_item(self.format_delta(row.get("car_chl_ratio_delta_pct", np.nan)), self.delta_color(row.get("car_chl_ratio_delta_pct", np.nan)), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            self.setItem(r, 6, self.make_table_item(f"{float(row.get('yellow_index', np.nan)):.3f}" if pd.notna(row.get("yellow_index", np.nan)) else "—", "#fcd34d", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            self.setItem(r, 7, self.make_table_item(self.format_delta(row.get("yellow_index_delta_pct", np.nan)), self.delta_color(row.get("yellow_index_delta_pct", np.nan)), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            self.setItem(r, 8, self.make_table_item(f"{float(row.get('stress_ratio', np.nan)):.3f}" if pd.notna(row.get("stress_ratio", np.nan)) else "—", "#f87171", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))

        count_label.setText(f"{len(sdf)} snaps recorded")
