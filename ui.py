import sys
import os
import re
import time
import csv
from datetime import datetime

import numpy as np
import pandas as pd
import pyqtgraph as pg

from PySide6.QtGui import QPixmap, QColor
from PySide6.QtCore import (
    QTimer,
    Qt,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtWidgets import QScrollArea
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QGraphicsOpacityEffect,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)

from services import (
    AS_COLS,
    CSV_PATH,
    AppState,
    ensure_csv_schema,
    SerialReader,
    AS_LABELS,
    CHANNEL_COLORS,
    evaluate_against_baseline,
    append_row,
    compute_all_indices,
    apply_session_name,
    load_records_df,
    pkt_to_rgb,
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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1200, 800)
        self.setMinimumSize(900,700)

        self.setWindowTitle("Real-Time Algae Biosensor")
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.state = AppState()
        ensure_csv_schema(CSV_PATH)

        self.reader = SerialReader()
        self.reader.packet.connect(self.on_packet)
        self.reader.status.connect(self.on_status)

        try:
            self.reader.start()
        except Exception:
            self.reader.stop()
            raise

        self.drag_pos = None
        self._animations = []
        self._name_prompt_anims = []
        self._name_prompt_hide_anims = []
        self.swatch_anim = None

        self.live_history_limit = 100
        self.last_snapshot_time = 0
        self.snapshot_interval = 30  # seconds

        self.setup_ui()
        self.setup_animations()

        self.live_tab = QWidget()
        self.records_tab = QWidget()
        self.tabs.addTab(self.live_tab, "Live / Record")
        self.tabs.addTab(self.records_tab, "Past Records")

        self.build_live_tab()
        self.build_records_tab()

        self.ui_timer = QTimer()
        self.ui_timer.setInterval(80)
        self.ui_timer.timeout.connect(self.tick_ui)
        self.ui_timer.start()

        self.refresh_ports()
        self.refresh_sessions()
        self.animate_window_open()

    def setup_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.title_bar = self.build_title_bar()
        root_layout.addWidget(self.title_bar)

        self.content_wrapper = QWidget()
        self.content_wrapper.setStyleSheet("""
            QWidget {
                background-color: #281C59;
                color: white;
            }
        """)
        content_layout = QVBoxLayout(self.content_wrapper)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #4a3f8a;
                background: #1e1650;
                border-radius: 10px;
            }
            QTabBar::tab {
                background: #3d2f8f;
                color: white;
                padding: 10px 16px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background: #0f172a;
                color: white;
            }
        """)
        content_layout.addWidget(self.tabs)

        root_layout.addWidget(self.content_wrapper)
        self.setCentralWidget(root)

    def setup_animations(self):
        self.setWindowOpacity(0.0)

    def animate_window_open(self):
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(650)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
        self._animations.append(anim)

    def build_title_bar(self):
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet("""
            background-color: #0f172a;
            border-bottom: 1px solid #1e293b;
        """)

        layout = QHBoxLayout(bar)
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

        btn_min.clicked.connect(self.showMinimized)
        btn_close.clicked.connect(self.close)

        layout.addWidget(logo)
        layout.addLayout(title_text)
        layout.addStretch()
        layout.addWidget(btn_min)
        layout.addWidget(btn_close)

        bar.mousePressEvent = self.title_bar_mouse_press
        bar.mouseMoveEvent = self.title_bar_mouse_move

        return bar

    def title_bar_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def title_bar_mouse_move(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def _make_legend(self, plot_widget: pg.PlotWidget):
        leg = plot_widget.addLegend(offset=(10, 10))
        if leg is None:
            leg = pg.LegendItem(offset=(10, 10))
            leg.setParentItem(plot_widget.getPlotItem())
        return leg

    def _colored_label(self, text: str, color_hex: str) -> str:
        return f'<span style="color:{color_hex}; font-weight:700;">{text}</span>'

    def build_metric_card(self, title: str, formula: str):
        card = QWidget()
        card.setMinimumHeight(160)
        card.setStyleSheet("""
            QWidget {
                background-color: #052e16;
                border: 1px solid #166534;
                border-radius: 0px;
            }
        """)

        layout = QVBoxLayout(card)
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

        value_label = QLabel("—")
        value_label.setStyleSheet("""
            color: #ffffff;
            font-size: 30px;
            font-weight: 900;
        """)

        badge_label = QLabel("—")
        badge_label.setAlignment(Qt.AlignCenter)
        badge_label.setStyleSheet("""
            padding: 4px 12px;
            border: 1px solid #166534;
            border-radius: 8px;
            color: #86efac;
            background-color: transparent;
            font-size: 14px;
            font-weight: 700;
        """)
        badge_label.setFixedHeight(30)

        value_row.addWidget(value_label, 0, Qt.AlignBottom)
        value_row.addWidget(badge_label, 0, Qt.AlignVCenter)
        value_row.addStretch()

        baseline_label = QLabel("Baseline: —")
        baseline_label.setStyleSheet("""
            color: #a7f3d0;
            font-size: 13px;
            font-weight: 500;
        """)

        delta_label = QLabel("— from baseline")
        delta_label.setStyleSheet("""
            color: #86efac;
            font-size: 13px;
            font-weight: 700;
        """)

        formula_label = QLabel(formula)
        formula_label.setStyleSheet("""
            color: #c4b5fd;
            font-size: 12px;
            font-family: Consolas, monospace;
        """)
        formula_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addLayout(value_row)
        layout.addWidget(baseline_label)
        layout.addWidget(delta_label)
        layout.addStretch()
        layout.addWidget(formula_label)

        return {
            "card": card,
            "title": title_label,
            "value": value_label,
            "badge": badge_label,
            "baseline": baseline_label,
            "delta": delta_label,
            "formula": formula_label,
        }

    def metric_badge_style(self, status: str) -> str:
        status = str(status or "").strip().upper()

        if status == "HEALTHY":
            return """
                padding: 4px 12px;
                border: 1px solid #166534;
                border-radius: 8px;
                color: #86efac;
                background-color: transparent;
                font-size: 14px;
                font-weight: 700;
            """
        elif status in {"WARNING", "MODERATE"}:
            return """
                padding: 4px 12px;
                border: 1px solid #a16207;
                border-radius: 8px;
                color: #facc15;
                background-color: transparent;
                font-size: 14px;
                font-weight: 700;
            """
        elif status in {"CRITICAL", "HIGH", "STRESS"}:
            return """
                padding: 4px 12px;
                border: 1px solid #991b1b;
                border-radius: 8px;
                color: #fca5a5;
                background-color: transparent;
                font-size: 14px;
                font-weight: 700;
            """
        else:
            return """
                padding: 4px 12px;
                border: 1px solid #374151;
                border-radius: 8px;
                color: #d1d5db;
                background-color: transparent;
                font-size: 14px;
                font-weight: 700;
            """

    def build_history_table(self):
        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
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
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.NoFocus)
        table.setSortingEnabled(False)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)

        table.setColumnWidth(0, 220)  # TIMESTAMP
        table.setColumnWidth(1, 140)  # STATUS
        table.setColumnWidth(2, 120)  # CHL INDEX
        table.setColumnWidth(3, 90)   # Δ
        table.setColumnWidth(4, 120)  # CAR:CHL
        table.setColumnWidth(5, 90)   # Δ
        table.setColumnWidth(6, 120)  # YELLOW
        table.setColumnWidth(7, 90)   # Δ
        table.setColumnWidth(8, 140)  # STRESS RATIO
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        table.setStyleSheet("""
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
        return table

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

    def add_live_history_row(self, timestamp_str, overall, cur, delta):
        table = self.live_history_table
        table.insertRow(0)

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
            table.setItem(0, col, item)

        if table.rowCount() > self.live_history_limit:
            table.removeRow(table.rowCount() - 1)

        self.live_history_count.setText(f"{table.rowCount()} snaps recorded")

    def populate_records_history_table(self, sdf: pd.DataFrame):
        table = self.records_history_table
        table.setRowCount(0)

        if sdf.empty:
            self.records_history_count.setText("0 snaps recorded")
            return

        for _, row in sdf.sort_values("time", ascending=False).iterrows():
            r = table.rowCount()
            table.insertRow(r)

            overall = str(row.get("overall_status", "—")).upper()
            fg, bg = self.status_cell_style(overall)
            row_bg = "#1e1650"

            ts = row["time"]
            if pd.notna(ts):
                ts_text = pd.to_datetime(ts).strftime("%Y-%m-%d %I:%M:%S %p")
            else:
                ts_text = "—"

            table.setItem(r, 0, self.make_table_item(ts_text, "#c4b5fd", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            table.setItem(r, 1, self.make_table_item(f"● {overall}", fg, True, Qt.AlignCenter, bg))
            table.setItem(r, 2, self.make_table_item(f"{float(row.get('chlorophyll_index', np.nan)):.3f}" if pd.notna(row.get("chlorophyll_index", np.nan)) else "—", "#6ee7b7", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            table.setItem(r, 3, self.make_table_item(self.format_delta(row.get("chlorophyll_index_delta_pct", np.nan)), self.delta_color(row.get("chlorophyll_index_delta_pct", np.nan)), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            table.setItem(r, 4, self.make_table_item(f"{float(row.get('car_chl_ratio', np.nan)):.3f}" if pd.notna(row.get("car_chl_ratio", np.nan)) else "—", "#6ee7b7", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            table.setItem(r, 5, self.make_table_item(self.format_delta(row.get("car_chl_ratio_delta_pct", np.nan)), self.delta_color(row.get("car_chl_ratio_delta_pct", np.nan)), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            table.setItem(r, 6, self.make_table_item(f"{float(row.get('yellow_index', np.nan)):.3f}" if pd.notna(row.get("yellow_index", np.nan)) else "—", "#fcd34d", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            table.setItem(r, 7, self.make_table_item(self.format_delta(row.get("yellow_index_delta_pct", np.nan)), self.delta_color(row.get("yellow_index_delta_pct", np.nan)), True, Qt.AlignLeft | Qt.AlignVCenter, row_bg))
            table.setItem(r, 8, self.make_table_item(f"{float(row.get('stress_ratio', np.nan)):.3f}" if pd.notna(row.get("stress_ratio", np.nan)) else "—", "#f87171", False, Qt.AlignLeft | Qt.AlignVCenter, row_bg))

        self.records_history_count.setText(f"{len(sdf)} snaps recorded")

    def build_live_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        root = QVBoxLayout(container)

        scroll.setWidget(container)

        layout = QVBoxLayout(self.live_tab)
        layout.addWidget(scroll)

        top = QHBoxLayout()
        root.addLayout(top)

        self.port_combo = QComboBox()
        self.btn_refresh_ports = QPushButton("Refresh Ports")
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #c4b5fd; font-weight:600;")

        top.addWidget(QLabel("Port:"))
        top.addWidget(self.port_combo, 2)
        top.addWidget(self.btn_refresh_ports)
        top.addWidget(self.btn_connect)
        top.addWidget(self.btn_disconnect)
        top.addWidget(self.status_label, 3)

        self.btn_refresh_ports.clicked.connect(self.refresh_ports)
        self.btn_connect.clicked.connect(self.handle_connect)
        self.btn_disconnect.clicked.connect(self.handle_disconnect)

        grid = QGridLayout()
        root.addLayout(grid)

        self.btn_capture_base = QPushButton("Capture Baseline")
        self.btn_clear_base = QPushButton("Clear Baseline")
        self.base_info = QLabel("Baseline: not set (capture a healthy algae reference first)")
        self.base_info.setStyleSheet("color: #fbbf24; font-weight:600;")

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 3600)
        self.duration_spin.setValue(30)
        self.btn_start_record = QPushButton("Start Timed Recording")
        self.btn_stop_record = QPushButton("Stop Recording")
        self.timer_label = QLabel("Remaining: —")
        self.timer_label.setStyleSheet("font-weight:700; color: white;")

        self.btn_reset_live = QPushButton("Reset Live History")

        grid.addWidget(self.btn_capture_base, 0, 0)
        grid.addWidget(self.btn_clear_base, 0, 1)
        grid.addWidget(self.base_info, 0, 2, 1, 4)

        grid.addWidget(QLabel("Duration (s):"), 1, 0)
        grid.addWidget(self.duration_spin, 1, 1)
        grid.addWidget(self.btn_start_record, 1, 2)
        grid.addWidget(self.btn_stop_record, 1, 3)
        grid.addWidget(self.timer_label, 1, 4)
        grid.addWidget(self.btn_reset_live, 1, 5)

        self.btn_capture_base.clicked.connect(self.capture_baseline)
        self.btn_clear_base.clicked.connect(self.clear_baseline)
        self.btn_start_record.clicked.connect(self.start_recording)
        self.btn_stop_record.clicked.connect(self.stop_recording)
        self.btn_reset_live.clicked.connect(self.reset_live_buffers)

        self.overall_banner = QLabel("●  Overall Status: —")
        self.overall_banner.setFixedHeight(44)
        self.overall_banner.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.overall_banner.setStyleSheet("""
            background-color: #052e16;
            border: 1px solid #166534;
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
            color: #86efac;
            font-size: 18px;
            font-weight: 800;
            padding-left: 20px;
        """)
        root.addWidget(self.overall_banner)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(0)
        root.addLayout(cards_row)

        self.card_chl = self.build_metric_card("CHLOROPHYLL INDEX", "F8(680nm) / F2(445nm)")
        self.card_car = self.build_metric_card("CAR:CHL RATIO", "F3(480nm) / F8(680nm)")
        self.card_yellow = self.build_metric_card("YELLOW INDEX", "F6(590nm) / F3(480nm)")
        self.card_stress = self.build_metric_card("STRESS RATIO", "(F5+F6) / (F2+F8) normalized by Clear")

        cards_row.addWidget(self.card_chl["card"])
        cards_row.addWidget(self.card_car["card"])
        cards_row.addWidget(self.card_yellow["card"])
        cards_row.addWidget(self.card_stress["card"])

        viz = QHBoxLayout()
        root.addLayout(viz)

        self.color_swatch = QLabel("")
        self.color_swatch.setFixedHeight(70)
        self.color_swatch.setFixedWidth(220)
        self.color_swatch.setAlignment(Qt.AlignCenter)
        self.color_swatch.setStyleSheet(
            "background:#000000;border:2px solid #3d2f8f;border-radius:14px;"
        )

        self.swatch_effect = QGraphicsOpacityEffect(self.color_swatch)
        self.swatch_effect.setOpacity(1.0)
        self.color_swatch.setGraphicsEffect(self.swatch_effect)

        swatch_info = QVBoxLayout()
        self.rgb_text = QLabel("RGB: —")
        self.hex_text = QLabel("HEX: —")
        self.rgb_text.setStyleSheet("font-weight:900;font-size:16px;color:white;")
        self.hex_text.setStyleSheet("font-weight:800;color:#c4b5fd;")
        swatch_info.addWidget(self.rgb_text)
        swatch_info.addWidget(self.hex_text)

        self.viz_hint = QLabel(
            "Tip: capture a healthy baseline first, then monitor the index history table below."
        )
        self.viz_hint.setStyleSheet("color:#c4b5fd;font-weight:600;")

        # Live history header
        history_header = QHBoxLayout()
        root.addLayout(history_header)

        history_title = QLabel("📋  Snap History")
        history_title.setStyleSheet("font-size: 18px; font-weight: 800; color: white;")
        self.live_history_count = QLabel("0 snaps recorded")
        self.live_history_count.setStyleSheet("color: #c4b5fd; font-weight:600;")

        history_header.addWidget(history_title)
        history_header.addStretch()
        history_header.addWidget(self.live_history_count)

        self.live_history_table = self.build_history_table()
        self.live_history_table.setMinimumHeight(180)
        root.addWidget(self.live_history_table, 1)

        name_row = QHBoxLayout()
        root.addLayout(name_row)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name last session (optional)")
        self.btn_save_name = QPushButton("Save Name")
        self.btn_skip_name = QPushButton("Skip")
        self.name_hint = QLabel("")
        self.name_hint.setStyleSheet("color: #c4b5fd;")

        name_row.addWidget(self.name_input, 3)
        name_row.addWidget(self.btn_save_name)
        name_row.addWidget(self.btn_skip_name)
        name_row.addWidget(self.name_hint, 3)

        self.btn_save_name.clicked.connect(self.save_last_session_name)
        self.btn_skip_name.clicked.connect(self.skip_last_session_name)

        self.name_prompt_widgets = [
            self.name_input,
            self.btn_save_name,
            self.btn_skip_name,
            self.name_hint,
        ]
        self.name_prompt_effects = []
        for w in self.name_prompt_widgets:
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(0.0)
            w.setGraphicsEffect(eff)
            self.name_prompt_effects.append(eff)

        self.hide_name_prompt(immediate=True)

    def hide_name_prompt(self, immediate=False):
        if immediate:
            for w, eff in zip(self.name_prompt_widgets, self.name_prompt_effects):
                eff.setOpacity(0.0)
                w.hide()
            return

        self._name_prompt_hide_anims = []
        for w, eff in zip(self.name_prompt_widgets, self.name_prompt_effects):
            anim = QPropertyAnimation(eff, b"opacity")
            anim.setDuration(180)
            anim.setStartValue(eff.opacity())
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.InCubic)

            def hide_widget(widget=w):
                widget.hide()

            anim.finished.connect(hide_widget)
            anim.start()
            self._name_prompt_hide_anims.append(anim)

    def show_name_prompt(self, sid: str):
        self.state.last_session_needs_name = sid
        self.name_input.setText(f"Sample {datetime.now():%Y-%m-%d %I:%M %p}")
        self.name_hint.setText(f"Session ID: {sid}")

        for w in self.name_prompt_widgets:
            w.show()

        self._name_prompt_anims = []
        for eff in self.name_prompt_effects:
            anim = QPropertyAnimation(eff, b"opacity")
            anim.setDuration(320)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._name_prompt_anims.append(anim)

    def build_records_tab(self):
        root = QVBoxLayout()
        self.records_tab.setLayout(root)

        top = QHBoxLayout()
        root.addLayout(top)

        self.session_combo = QComboBox()
        self.btn_refresh_sessions = QPushButton("Refresh Sessions")
        self.btn_delete_session = QPushButton("Delete Session")

        top.addWidget(QLabel("Session:"))
        top.addWidget(self.session_combo, 4)
        top.addWidget(self.btn_refresh_sessions)
        top.addWidget(self.btn_delete_session)

        self.btn_refresh_sessions.clicked.connect(self.refresh_sessions)
        self.session_combo.currentIndexChanged.connect(self.load_selected_session_plot)
        self.btn_delete_session.clicked.connect(self.delete_selected_session)

        self.session_info = QLabel("—")
        self.session_info.setStyleSheet("color: white;")
        root.addWidget(self.session_info)

        self.session_indices_info = QLabel("—")
        self.session_indices_info.setStyleSheet("color: white; font-weight:600;")
        root.addWidget(self.session_indices_info)

        # Index graph for past records
        self.plot_hist = pg.PlotWidget()
        self.plot_hist.showGrid(x=True, y=True)
        self.plot_hist.setLabel("left", "Index Value")
        self.plot_hist.setLabel("bottom", "Samples (session)")
        self.plot_hist.setBackground("#1e1650")
        root.addWidget(self.plot_hist, 1)

        self.hist_legend = self._make_legend(self.plot_hist)

        self.curves_hist = {}
        index_cfg = {
            "chlorophyll_index": ("Chlorophyll Index", "#10b981"),
            "car_chl_ratio": ("Car:Chl Ratio", "#3b82f6"),
            "yellow_index": ("Yellow Index", "#f59e0b"),
            "stress_ratio": ("Stress Ratio", "#ef4444"),
        }

        for key, (label, color) in index_cfg.items():
            pen = pg.mkPen(color=color, width=3)
            curve = pg.PlotDataItem([], [], pen=pen)
            self.plot_hist.addItem(curve)
            self.curves_hist[key] = curve
            self.hist_legend.addItem(curve, self._colored_label(label, color))

        records_header = QHBoxLayout()
        root.addLayout(records_header)

        records_title = QLabel("📋  Session History")
        records_title.setStyleSheet("font-size:18px;font-weight:800;color:white;")
        self.records_history_count = QLabel("0 snaps recorded")
        self.records_history_count.setStyleSheet("color:#c4b5fd;font-weight:600;")

        records_header.addWidget(records_title)
        records_header.addStretch()
        records_header.addWidget(self.records_history_count)

        self.records_history_table = self.build_history_table()
        self.records_history_table.setMinimumHeight(180)
        root.addWidget(self.records_history_table, 1)

    def refresh_ports(self):
        ports = self.reader.list_ports()
        self.port_combo.clear()
        if not ports:
            self.port_combo.addItem("No ports detected")
        else:
            for p in ports:
                self.port_combo.addItem(p)

    def handle_connect(self):
        port = self.port_combo.currentText().strip()
        if not port or port.lower().startswith("no ports"):
            QMessageBox.warning(self, "No Port", "No serial ports detected.")
            return

        ok = self.reader.connect_port(port, baud=115200)
        if ok:
            self.reader.flush_buffer(0.6)
            self.reader.clear_pending()

    def handle_disconnect(self):
        self.reader.disconnect_port()

    def on_status(self, msg: str):
        self.status_label.setText(msg)

    def reset_live_buffers(self):
        self.state.t.clear()
        for ch in AS_COLS:
            self.state.channels[ch].clear()
        self.state.last_pkt = None

        self.overall_banner.setText("●  Overall Status: —")
        self.overall_banner.setStyleSheet("""
            background-color: #052e16;
            border: 1px solid #166534;
            border-top-left-radius: 14px;
            border-top-right-radius: 14px;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
            color: #86efac;
            font-size: 18px;
            font-weight: 800;
            padding-left: 20px;
        """)

        for card in [self.card_chl, self.card_car, self.card_yellow, self.card_stress]:
            card["value"].setText("—")
            card["badge"].setText("—")
            card["baseline"].setText("Baseline: —")
            card["delta"].setText("— from baseline")
            card["badge"].setStyleSheet(self.metric_badge_style("UNKNOWN"))

        self.live_history_table.setRowCount(0)
        self.live_history_count.setText("0 snaps recorded")

        self.color_swatch.setStyleSheet(
            "background:#000000;border:2px solid #3d2f8f;border-radius:14px;"
        )
        self.rgb_text.setText("RGB: —")
        self.hex_text.setText("HEX: —")

    def animate_swatch_pulse(self):
        if self.swatch_anim and self.swatch_anim.state() == QPropertyAnimation.Running:
            self.swatch_anim.stop()

        self.swatch_anim = QPropertyAnimation(self.swatch_effect, b"opacity")
        self.swatch_anim.setDuration(180)
        self.swatch_anim.setStartValue(0.72)
        self.swatch_anim.setEndValue(1.0)
        self.swatch_anim.setEasingCurve(QEasingCurve.OutCubic)
        self.swatch_anim.start()

    def on_packet(self, pkt: dict):
        self.state.last_pkt = pkt

        self.state.t.append(len(self.state.t))
        for ch in AS_COLS:
            self.state.channels[ch].append(pkt.get(ch, 0))

        if len(self.state.t) > self.state.max_points:
            self.state.t = self.state.t[-self.state.max_points:]
            for ch in AS_COLS:
                self.state.channels[ch] = self.state.channels[ch][-self.state.max_points:]

        eval_result = evaluate_against_baseline(pkt, self.state.baseline_pkt)
        cur = eval_result["current"]
        delta = eval_result["delta_pct"]

        now = time.time()

        if now - self.last_snapshot_time >= self.snapshot_interval:
            self.last_snapshot_time = now

            self.add_live_history_row(
                datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
                eval_result["overall_status"],
                cur,
                delta,
            )

        if self.state.recording and self.state.session_id:
            st = eval_result["status_per_index"]
            row = {
                "time": datetime.now(),
                **pkt,
                "session_id": self.state.session_id,
                "session_name": "",
                "chlorophyll_index": cur["chlorophyll_index"],
                "chlorophyll_index_delta_pct": np.nan if delta["chlorophyll_index"] is None else delta["chlorophyll_index"],
                "chlorophyll_index_status": st["chlorophyll_index"],
                "car_chl_ratio": cur["car_chl_ratio"],
                "car_chl_ratio_delta_pct": np.nan if delta["car_chl_ratio"] is None else delta["car_chl_ratio"],
                "car_chl_ratio_status": st["car_chl_ratio"],
                "yellow_index": cur["yellow_index"],
                "yellow_index_delta_pct": np.nan if delta["yellow_index"] is None else delta["yellow_index"],
                "yellow_index_status": st["yellow_index"],
                "stress_ratio": cur["stress_ratio"],
                "stress_ratio_delta_pct": np.nan if delta["stress_ratio"] is None else delta["stress_ratio"],
                "stress_ratio_status": st["stress_ratio"],
                "overall_status": eval_result["overall_status"],
            }
            append_row(row, CSV_PATH)

    def capture_baseline(self):
        if not self.state.last_pkt:
            QMessageBox.information(self, "No Data", "No packet received yet. Check Arduino streaming.")
            return

        self.state.baseline_pkt = dict(self.state.last_pkt)
        self.state.baseline_indices = compute_all_indices(self.state.last_pkt)
        self.state.baseline_time = datetime.now()

        bi = self.state.baseline_indices
        self.base_info.setText(
            f"Baseline set @ {self.state.baseline_time:%Y-%m-%d %H:%M:%S} | "
            f"Chl={bi['chlorophyll_index']:.4f} | "
            f"Car:Chl={bi['car_chl_ratio']:.4f} | "
            f"Yellow={bi['yellow_index']:.4f} | "
            f"Stress={bi['stress_ratio']:.4f}"
        )
        self.base_info.setStyleSheet("color:#6ee7b7;font-weight:700;")

    def clear_baseline(self):
        self.state.baseline_pkt = None
        self.state.baseline_indices = None
        self.state.baseline_time = None
        self.base_info.setText("Baseline: not set (capture a healthy algae reference first)")
        self.base_info.setStyleSheet("color: #fbbf24; font-weight:600;")

    def start_recording(self):
        if not self.reader._ser:
            QMessageBox.warning(self, "Not Connected", "Connect to Arduino first.")
            return

        self.reader.flush_buffer(0.6)
        self.reader.clear_pending()
        self.reset_live_buffers()

        self.state.recording = True
        dur = int(self.duration_spin.value())
        self.state.record_end_ts = time.time() + max(1, dur)
        self.state.session_id = datetime.now().isoformat()
        self.hide_name_prompt()

        self.timer_label.setText(f"Remaining: {dur}s (recording)")
        self.timer_label.setStyleSheet("font-weight:900;color:white;")

    def stop_recording(self):
        if not self.state.recording:
            return
        self.finish_recording()

    def finish_recording(self):
        self.state.recording = False
        self.state.record_end_ts = None

        sid = self.state.session_id
        self.state.session_id = None

        self.timer_label.setText("Remaining: —")
        self.timer_label.setStyleSheet("font-weight:700; color: white;")

        if sid:
            self.show_name_prompt(sid)
            self.refresh_sessions()
            self.tabs.setCurrentWidget(self.records_tab)

    def save_last_session_name(self):
        sid = self.state.last_session_needs_name
        if not sid:
            return

        name = self.name_input.text().strip()
        apply_session_name(sid, name, CSV_PATH)
        self.state.last_session_needs_name = None
        self.hide_name_prompt()
        self.refresh_sessions()

    def skip_last_session_name(self):
        self.state.last_session_needs_name = None
        self.hide_name_prompt()
        self.refresh_sessions()

    def refresh_sessions(self):
        df = load_records_df(CSV_PATH)
        if df.empty:
            self.session_combo.clear()
            self.session_combo.addItem("No sessions")
            self.session_info.setText("—")
            self.session_indices_info.setText("—")
            self.clear_hist_plot()
            self.records_history_table.setRowCount(0)
            self.records_history_count.setText("0 snaps recorded")
            return

        sessions = (
            df.groupby("session_id")
            .agg(
                start=("time", "min"),
                end=("time", "max"),
                count=("time", "count"),
                session_name=("session_name", "last"),
                overall_status=("overall_status", "last"),
            )
            .sort_values("end", ascending=False)
            .reset_index()
        )

        def label_row(r):
            nm = str(r["session_name"]).strip()
            status = str(r["overall_status"]).strip()
            if not nm:
                nm = "Unnamed"
            return f"{nm} [{status}] ({r['end']:%Y-%m-%d %I:%M %p})"

        self._sessions_df = sessions
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        for _, r in sessions.iterrows():
            self.session_combo.addItem(label_row(r), userData=str(r["session_id"]))
        self.session_combo.blockSignals(False)

        self.load_selected_session_plot()

    def clear_hist_plot(self):
        for key in self.curves_hist:
            self.curves_hist[key].setData([], [])

    def load_selected_session_plot(self):
        sid = self.session_combo.currentData()
        if not sid or str(sid).lower().startswith("no sessions"):
            self.session_info.setText("—")
            self.session_indices_info.setText("—")
            self.clear_hist_plot()
            self.records_history_table.setRowCount(0)
            self.records_history_count.setText("0 snaps recorded")
            return

        df = load_records_df(CSV_PATH)
        sdf = df[df["session_id"].astype(str) == str(sid)].sort_values("time").copy()
        if sdf.empty:
            self.session_info.setText("Session empty.")
            self.session_indices_info.setText("—")
            self.clear_hist_plot()
            self.records_history_table.setRowCount(0)
            self.records_history_count.setText("0 snaps recorded")
            return

        start = sdf["time"].iloc[0]
        end = sdf["time"].iloc[-1]
        count = len(sdf)
        name = str(sdf["session_name"].iloc[-1]).strip() or "Unnamed"
        overall = str(sdf["overall_status"].iloc[-1]).strip() or "—"

        self.session_info.setText(
            f"Session: {name} | {start:%Y-%m-%d %I:%M:%S %p} → {end:%I:%M:%S %p} | "
            f"Samples: {count} | Overall: {overall} | ID: {sid}"
        )

        try:
            last = sdf.iloc[-1]
            self.session_indices_info.setText(
                f"Chl={float(last['chlorophyll_index']):.4f} "
                f"(Δ {float(last['chlorophyll_index_delta_pct']):.2f}% | {last['chlorophyll_index_status']})   |   "
                f"Car:Chl={float(last['car_chl_ratio']):.4f} "
                f"(Δ {float(last['car_chl_ratio_delta_pct']):.2f}% | {last['car_chl_ratio_status']})   |   "
                f"Yellow={float(last['yellow_index']):.4f} "
                f"(Δ {float(last['yellow_index_delta_pct']):.2f}% | {last['yellow_index_status']})   |   "
                f"Stress={float(last['stress_ratio']):.4f} "
                f"(Δ {float(last['stress_ratio_delta_pct']):.2f}% | {last['stress_ratio_status']})"
            )
        except Exception:
            self.session_indices_info.setText("Index summary unavailable.")

        x = np.arange(count)

        for key in self.curves_hist:
            if key in sdf.columns:
                y = pd.to_numeric(sdf[key], errors="coerce").to_numpy()
                self.curves_hist[key].setData(x, y)
            else:
                self.curves_hist[key].setData([], [])

        self.populate_records_history_table(sdf)

    def delete_selected_session(self):
        sid = self.session_combo.currentData()
        if not sid:
            return

        reply = QMessageBox.question(
            self,
            "Delete Session",
            "Delete this entire session from the CSV? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        df = load_records_df(CSV_PATH)
        new_df = df[df["session_id"].astype(str) != str(sid)].copy()
        new_df2 = new_df.copy()
        new_df2["time"] = new_df2["time"].dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        new_df2.to_csv(CSV_PATH, index=False)

        self.refresh_sessions()

    def tick_ui(self):
        if self.state.recording and self.state.record_end_ts:
            rem = int(max(0, self.state.record_end_ts - time.time()))
            self.timer_label.setText(f"Remaining: {rem}s (recording)")
            if rem <= 0:
                self.finish_recording()

        pkt = self.state.last_pkt
        if not pkt:
            return

        eval_result = evaluate_against_baseline(pkt, self.state.baseline_pkt)
        cur = eval_result["current"]
        delta = eval_result["delta_pct"]
        st = eval_result["status_per_index"]
        overall = eval_result["overall_status"]

        baseline = self.state.baseline_indices or {}

        def fmt_value(v):
            return "—" if v is None or pd.isna(v) else f"{v:.3f}"

        def fmt_base(v):
            return "—" if v is None or pd.isna(v) else f"{v:.3f}"

        def fmt_delta_line(v):
            if v is None or pd.isna(v):
                return "— from baseline"
            sign = "+" if v >= 0 else ""
            return f"{sign}{v:.1f}% from baseline"

        def update_metric_card(card, value, baseline_value, delta_value, status):
            card["value"].setText(fmt_value(value))
            card["badge"].setText(str(status).upper())
            card["badge"].setStyleSheet(self.metric_badge_style(status))
            card["baseline"].setText(f"Baseline: {fmt_base(baseline_value)}")
            card["delta"].setText(fmt_delta_line(delta_value))

            if delta_value is None or pd.isna(delta_value):
                card["delta"].setStyleSheet("""
                    color: #9ca3af;
                    font-size: 13px;
                    font-weight: 700;
                """)
            else:
                card["delta"].setStyleSheet("""
                    color: #86efac;
                    font-size: 13px;
                    font-weight: 700;
                """)

        overall_text = str(overall).upper()
        self.overall_banner.setText(f"●  Overall Status: {overall_text}")

        if overall_text == "HEALTHY":
            self.overall_banner.setStyleSheet("""
                background-color: #052e16;
                border: 1px solid #166534;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                color: #86efac;
                font-size: 18px;
                font-weight: 800;
                padding-left: 20px;
            """)
        elif overall_text in {"WARNING", "MODERATE"}:
            self.overall_banner.setStyleSheet("""
                background-color: #3f2a06;
                border: 1px solid #a16207;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                color: #fde047;
                font-size: 18px;
                font-weight: 800;
                padding-left: 20px;
            """)
        else:
            self.overall_banner.setStyleSheet("""
                background-color: #3f1113;
                border: 1px solid #991b1b;
                border-top-left-radius: 14px;
                border-top-right-radius: 14px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
                color: #fca5a5;
                font-size: 18px;
                font-weight: 800;
                padding-left: 20px;
            """)

        update_metric_card(
            self.card_chl,
            cur["chlorophyll_index"],
            baseline.get("chlorophyll_index"),
            delta["chlorophyll_index"],
            st["chlorophyll_index"],
        )
        update_metric_card(
            self.card_car,
            cur["car_chl_ratio"],
            baseline.get("car_chl_ratio"),
            delta["car_chl_ratio"],
            st["car_chl_ratio"],
        )
        update_metric_card(
            self.card_yellow,
            cur["yellow_index"],
            baseline.get("yellow_index"),
            delta["yellow_index"],
            st["yellow_index"],
        )
        update_metric_card(
            self.card_stress,
            cur["stress_ratio"],
            baseline.get("stress_ratio"),
            delta["stress_ratio"],
            st["stress_ratio"],
        )

        (r, g, b), hexv = pkt_to_rgb(pkt)
        self.color_swatch.setStyleSheet(
            f"background:{hexv};border:2px solid #3d2f8f;border-radius:14px;"
        )
        self.animate_swatch_pulse()

        self.rgb_text.setText(f"RGB: {r}, {g}, {b}")
        self.hex_text.setText(f"HEX: {hexv}   |   CLR: {pkt.get('CLR', '—')}")

    def closeEvent(self, event):
        try:
            self.reader.stop()
        except Exception:
            pass
        event.accept()