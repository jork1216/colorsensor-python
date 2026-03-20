import time
from datetime import datetime

import numpy as np
import pandas as pd

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import (
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
    QScrollArea,
    QGraphicsOpacityEffect,
)

from config import LIVE_HISTORY_LIMIT, SNAPSHOT_INTERVAL_SECONDS, DEFAULT_RECORDING_DURATION, CSV_PATH
from models import AS_COLS
from storage import apply_session_name
from color_utils import pkt_to_rgb
from theme import banner_style_healthy, banner_style_mild_stress, banner_style_stressed
from theme import delta_box_style_active, delta_box_style_muted
from widgets.metric_card import MetricCard, metric_badge_style
from widgets.history_table import HistoryTable


class LiveTab(QWidget):
    def __init__(self, state, reader, controller, refresh_sessions_callback):
        super().__init__()
        self.state = state
        self.reader = reader
        self.controller = controller
        self.refresh_sessions_callback = refresh_sessions_callback

        self.live_history_limit = LIVE_HISTORY_LIMIT
        self.last_snapshot_time = 0
        self.snapshot_interval = SNAPSHOT_INTERVAL_SECONDS

        self._name_prompt_anims = []
        self._name_prompt_hide_anims = []
        self.swatch_anim = None

        # Build the live tab UI
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        root = QVBoxLayout(container)

        scroll.setWidget(container)

        layout = QVBoxLayout(self)
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
        self.duration_spin.setValue(DEFAULT_RECORDING_DURATION)
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

        self.btn_capture_base.clicked.connect(lambda: self.controller.capture_baseline())
        self.btn_clear_base.clicked.connect(lambda: self.controller.clear_baseline())
        self.btn_start_record.clicked.connect(lambda: self.on_start_recording_clicked())
        self.btn_stop_record.clicked.connect(lambda: self.controller.stop_recording())
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

        cards_container = QWidget()
        cards_container.setObjectName("cards_container")
        cards_container.setStyleSheet("""
            QWidget#cards_container {
                background-color: #0a3d1f;
                border-left: 1px solid #166534;
                border-right: 1px solid #166534;
                border-bottom: 1px solid #166534;
                border-top: none;
                border-bottom-left-radius: 14px;
                border-bottom-right-radius: 14px;
            }
        """)

        cards_row = QHBoxLayout(cards_container)
        cards_row.setSpacing(0)
        cards_row.setContentsMargins(0, 0, 0, 0)
        root.addWidget(cards_container)

        self.card_chl = MetricCard("CHLOROPHYLL INDEX", "F8(680nm) / F2(445nm)")
        self.card_car = MetricCard("CAR:CHL RATIO", "F3(480nm) / F8(680nm)")
        self.card_yellow = MetricCard("YELLOW INDEX", "F6(590nm) / F3(480nm)")
        self.card_stress = MetricCard("STRESS RATIO", "(F5+F6) / (F2+F8) normalized by Clear")

        cards_row.addWidget(self.card_chl)
        cards_row.addWidget(self.card_car)
        cards_row.addWidget(self.card_yellow)
        cards_row.addWidget(self.card_stress)

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

        self.live_history_table = HistoryTable()
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

    def refresh_ports(self):
        ports = self.reader.list_ports()
        self.port_combo.clear()
        if not ports:
            self.port_combo.addItem("No ports detected")
        else:
            for p in ports:
                self.port_combo.addItem(p)

    def on_status(self, msg: str):
        self.status_label.setText(msg)

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
            card.value.setText("—")
            card.badge.setText("—")
            card.baseline.setText("Baseline: —")
            card.delta.setText("— from baseline")
            card.badge.setStyleSheet(metric_badge_style("UNKNOWN"))
            card.delta.setStyleSheet(delta_box_style_muted())

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

    def on_start_recording_clicked(self):
        if not self.reader._ser:
            QMessageBox.warning(self, "Not Connected", "Connect to Arduino first.")
            return
        dur = int(self.duration_spin.value())
        self.reset_live_buffers()
        self.controller.start_recording(dur)

    def on_baseline_captured(self, indices, timestamp_str):
        bi = indices
        self.base_info.setText(
            f"Baseline set @ {timestamp_str} | "
            f"Chl={bi['chlorophyll_index']:.4f} | "
            f"Car:Chl={bi['car_chl_ratio']:.4f} | "
            f"Yellow={bi['yellow_index']:.4f} | "
            f"Stress={bi['stress_ratio']:.4f}"
        )
        self.base_info.setStyleSheet("color:#6ee7b7;font-weight:700;")

    def on_baseline_cleared(self):
        self.base_info.setText("Baseline: not set (capture a healthy algae reference first)")
        self.base_info.setStyleSheet("color: #fbbf24; font-weight:600;")

    def on_recording_started(self):
        self.hide_name_prompt()
        dur = int(self.duration_spin.value())
        self.timer_label.setText(f"Remaining: {dur}s (recording)")
        self.timer_label.setStyleSheet("font-weight:900;color:white;")

    def on_recording_stopped(self, session_id):
        self.timer_label.setText("Remaining: —")
        self.timer_label.setStyleSheet("font-weight:700; color: white;")
        
        if session_id:
            self.show_name_prompt(session_id)
            self.refresh_sessions_callback()

    def on_tick(self, remaining_seconds):
        self.timer_label.setText(f"Remaining: {remaining_seconds}s (recording)")

    def on_snapshot_ready(self, timestamp, overall, cur, delta):
        self.live_history_table.add_live_history_row(
            timestamp,
            overall,
            cur,
            delta,
            self.live_history_count,
        )

    def on_packet_evaluated(self, eval_result):
        pkt = self.state.last_pkt
        if not pkt:
            return
        
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
            card.value.setText(fmt_value(value))
            card.badge.setText(str(status).upper())
            card.badge.setStyleSheet(metric_badge_style(status))
            card.baseline.setText(f"Baseline: {fmt_base(baseline_value)}")
            card.delta.setText(fmt_delta_line(delta_value))

            if delta_value is None or pd.isna(delta_value):
                card.delta.setStyleSheet(delta_box_style_muted())
            else:
                card.delta.setStyleSheet(delta_box_style_active())

        overall_text = str(overall).upper()
        self.overall_banner.setText(f"●  Overall Status: {overall_text}")

        if overall_text == "HEALTHY":
            self.overall_banner.setStyleSheet(banner_style_healthy())
        elif overall_text in {"WARNING", "MODERATE"}:
            self.overall_banner.setStyleSheet(banner_style_mild_stress())
        else:
            self.overall_banner.setStyleSheet(banner_style_stressed())

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

    def save_last_session_name(self):
        sid = self.state.last_session_needs_name
        if not sid:
            return

        name = self.name_input.text().strip()
        apply_session_name(sid, name, CSV_PATH)
        self.state.last_session_needs_name = None
        self.hide_name_prompt()
        self.refresh_sessions_callback()

    def skip_last_session_name(self):
        self.state.last_session_needs_name = None
        self.hide_name_prompt()
        self.refresh_sessions_callback()

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

    def tick_ui(self):
        # Call controller's tick_recording to update timer and check if recording is finished
        self.controller.tick_recording()
