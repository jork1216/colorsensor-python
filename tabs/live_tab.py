import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
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
    QDialog,
)

from config import LIVE_HISTORY_LIMIT, SNAPSHOT_INTERVAL_SECONDS, DEFAULT_RECORDING_DURATION, CSV_PATH, SETTINGS_PATH
from models import AS_COLS
from storage import apply_session_name
from color_utils import pkt_to_rgb
from theme import (
    banner_style_healthy, banner_style_mild_stress, banner_style_stressed,
    btn_connect, btn_disconnect, btn_capture_baseline, btn_clear_baseline,
    btn_start_recording, btn_stop_recording, btn_save_name, btn_skip, btn_neutral
)
from widgets.metric_card import MetricCard, metric_badge_style
from widgets.history_table import HistoryTable


class LiveTab(QWidget):
    class AutoRefreshComboBox(QComboBox):
        def __init__(self, refresh_callback: callable, parent=None):
            super().__init__(parent)
            self._refresh_callback = refresh_callback

        def showPopup(self):
            self._refresh_callback()
            super().showPopup()

    def __init__(self, state, reader, controller, refresh_sessions_callback):
        super().__init__()
        self.state = state
        self.reader = reader
        self.controller = controller
        self.refresh_sessions_callback = refresh_sessions_callback

        self.live_history_limit = LIVE_HISTORY_LIMIT
        self.last_snapshot_time = 0
        self.snapshot_interval = SNAPSHOT_INTERVAL_SECONDS

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

        self.port_combo = self.AutoRefreshComboBox(refresh_callback=self._populate_ports)
        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #c4b5fd; font-weight:600;")

        top.addWidget(QLabel("Port:"))
        top.addWidget(self.port_combo, 2)
        top.addWidget(self.btn_connect)
        top.addWidget(self.btn_disconnect)
        top.addWidget(self.status_label, 3)

        self.btn_connect.clicked.connect(self.handle_connect)
        self.btn_disconnect.clicked.connect(self.handle_disconnect)

        grid = QGridLayout()
        root.addLayout(grid)

        self.btn_capture_base = QPushButton("Capture Baseline")
        self.btn_clear_base = QPushButton("Clear Baseline")
        self.base_info = QLabel("Baseline: not set (capture a healthy algae reference first)")
        self.base_info.setStyleSheet("color: #fbbf24; font-weight:600;")

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 60)
        self.duration_spin.setValue(DEFAULT_RECORDING_DURATION // 60 if DEFAULT_RECORDING_DURATION >= 60 else 1)
        
        self.snapshot_spin = QSpinBox()
        self.snapshot_spin.setRange(1, 300)
        self.snapshot_spin.setValue(SNAPSHOT_INTERVAL_SECONDS)
        
        self.btn_start_record = QPushButton("Start Timed Recording")
        self.btn_stop_record = QPushButton("Stop Recording")
        self.timer_label = QLabel("Remaining: —")
        self.timer_label.setStyleSheet("font-weight:700; color: white;")

        self._rec_blink_timer = QTimer(self)
        self._rec_blink_timer.setInterval(600)
        self._rec_blink_timer.timeout.connect(self._on_rec_blink)

        self.btn_reset_live = QPushButton("Reset Live History")

        # Initialize capture and recording buttons as disabled until connected
        self.btn_capture_base.setEnabled(False)
        self.btn_start_record.setEnabled(False)
        self.btn_stop_record.setEnabled(False)

        grid.addWidget(self.btn_capture_base, 0, 0)
        grid.addWidget(self.btn_clear_base, 0, 1)
        grid.addWidget(self.base_info, 0, 2, 1, 4)

        grid.addWidget(QLabel("Duration (minutes):"), 1, 0)
        grid.addWidget(self.duration_spin, 1, 1)
        grid.addWidget(QLabel("Snap every (s):"), 1, 2)
        grid.addWidget(self.snapshot_spin, 1, 3)
        grid.addWidget(self.btn_start_record, 1, 4)
        grid.addWidget(self.btn_stop_record, 1, 5)
        grid.addWidget(self.timer_label, 1, 6)
        grid.addWidget(self.btn_reset_live, 1, 7)

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

        # Create a container widget with green styling
        cards_container = QWidget()
        cards_container.setStyleSheet("""
            background-color: #052e16;
            border: 1px solid #166534;
            border-radius: 8px;
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
        
        # Vertical separator line
        sep1 = QWidget()
        sep1.setFixedWidth(1)
        sep1.setStyleSheet("background-color: #166534;")
        cards_row.addWidget(sep1)
        
        cards_row.addWidget(self.card_car)
        
        # Vertical separator line
        sep2 = QWidget()
        sep2.setFixedWidth(1)
        sep2.setStyleSheet("background-color: #166534;")
        cards_row.addWidget(sep2)
        
        cards_row.addWidget(self.card_yellow)
        
        # Vertical separator line
        sep3 = QWidget()
        sep3.setFixedWidth(1)
        sep3.setStyleSheet("background-color: #166534;")
        cards_row.addWidget(sep3)
        
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
        
        self.rec_indicator = QLabel("● REC")
        self.rec_indicator.setStyleSheet("color: white; font-size: 14px; font-weight: 700; background-color: transparent; padding: 4px 8px;")
        self.rec_indicator.hide()
        self._rec_blink_state = False
        
        self.live_history_count = QLabel("0 snaps recorded")
        self.live_history_count.setStyleSheet("color: #c4b5fd; font-weight:600;")

        history_header.addWidget(history_title)
        history_header.addWidget(self.rec_indicator)
        history_header.addStretch()
        history_header.addWidget(self.live_history_count)

        self.live_history_table = HistoryTable()
        self.live_history_table.setMinimumHeight(180)
        root.addWidget(self.live_history_table, 1)

        # Apply button stylesheets
        self.btn_connect.setStyleSheet(btn_connect())
        self.btn_disconnect.setStyleSheet(btn_disconnect())
        self.btn_capture_base.setStyleSheet(btn_capture_baseline())
        self.btn_clear_base.setStyleSheet(btn_clear_baseline())
        self.btn_start_record.setStyleSheet(btn_start_recording())
        self.btn_stop_record.setStyleSheet(btn_stop_recording())
        self.btn_reset_live.setStyleSheet(btn_neutral())

    def _on_rec_blink(self):
        self._rec_blink_state = not self._rec_blink_state
        if self._rec_blink_state:
            self.rec_indicator.setStyleSheet("color: white; font-size: 14px; font-weight: 700; background-color: #ef4444; padding: 4px 8px;")
        else:
            self.rec_indicator.setStyleSheet("color: white; font-size: 14px; font-weight: 700; background-color: transparent; padding: 4px 8px;")

    def _save_last_port(self, port: str):
        with open(SETTINGS_PATH, "w") as f:
            json.dump({"last_port": port}, f)

    def _load_last_port(self) -> str | None:
        try:
            with open(SETTINGS_PATH, "r") as f:
                settings = json.load(f)
            return settings["last_port"]
        except Exception:
            return None

    def _populate_ports(self):
        ports = self.reader.list_ports()
        self.port_combo.clear()
        if not ports:
            self.port_combo.addItem("No ports detected")
        else:
            for p in ports:
                self.port_combo.addItem(p)
        last = self._load_last_port()
        if last is not None:
            idx = self.port_combo.findText(last)
            if idx != -1:
                self.port_combo.setCurrentIndex(idx)

    def refresh_ports(self):
        self._populate_ports()

    def on_status(self, msg: str):
        self.status_label.setText(msg)
        
        # Wire connection state to button enable/disable logic
        connected = self.reader._ser is not None
        self.btn_capture_base.setEnabled(connected)
        self.btn_start_record.setEnabled(connected)
        self.btn_stop_record.setEnabled(connected and self.state.recording)

    def handle_connect(self):
        port = self.port_combo.currentText().strip()
        if not port or port.lower().startswith("no ports"):
            QMessageBox.warning(self, "No Port", "No serial ports detected.")
            return

        ok = self.reader.connect_port(port, baud=115200)
        if ok:
            self._save_last_port(port)
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
        dur_minutes = int(self.duration_spin.value())
        dur_seconds = dur_minutes * 60
        snapshot_interval = int(self.snapshot_spin.value())
        self.reset_live_buffers()
        self.controller.start_recording(dur_seconds, snapshot_interval)

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
        dur_minutes = int(self.duration_spin.value())
        self.timer_label.setText(f"Remaining: {dur_minutes}m 0s (recording)")
        self.timer_label.setStyleSheet("font-weight:900;color:white;")
        self.btn_stop_record.setEnabled(True)
        self.rec_indicator.show()
        self._rec_blink_timer.start()

    def on_recording_stopped(self, session_id):
        self._rec_blink_timer.stop()
        self.rec_indicator.hide()
        self.timer_label.setText("Remaining: —")
        self.timer_label.setStyleSheet("font-weight:700; color: white;")
        self.btn_stop_record.setEnabled(False)
        
        if session_id:
            self.show_name_prompt(session_id)
            self.refresh_sessions_callback()

    def on_recording_aborted(self, msg: str):
        self.on_recording_stopped(session_id=None)
        QMessageBox.warning(self, "Recording Aborted", msg)

    def on_tick(self, remaining_seconds):
        minutes = remaining_seconds // 60
        seconds = remaining_seconds % 60
        self.timer_label.setText(f"Remaining: {minutes}m {seconds}s (recording)")

    def on_snapshot_ready(self, timestamp, overall, cur, delta):
        # Signal is only emitted from session_controller.on_packet() when self.state.recording is True.
        # This is the only code path to add_live_history_row() - ensuring snapshots only record during active sessions.
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
                card.delta.setStyleSheet("""
                    color: #9ca3af;
                    font-size: 13px;
                    font-weight: 700;
                """)
            else:
                card.delta.setStyleSheet("""
                    color: #86efac;
                    font-size: 13px;
                    font-weight: 700;
                """)

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

    def show_name_prompt(self, sid: str):
        dialog = QDialog(self)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setWindowTitle("Name This Recording")

        layout = QVBoxLayout()

        label = QLabel("Name this recording")
        layout.addWidget(label)

        name_input = QLineEdit()
        name_input.setText(datetime.now().strftime("%Y-%m-%d %I:%M %p"))
        layout.addWidget(name_input)

        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        skip_button = QPushButton("Skip")
        button_layout.addWidget(save_button)
        button_layout.addWidget(skip_button)
        layout.addLayout(button_layout)

        def on_save():
            name = name_input.text()
            apply_session_name(sid, name, CSV_PATH)
            self.state.last_session_needs_name = None
            self.refresh_sessions_callback()
            dialog.accept()

        def on_skip():
            self.state.last_session_needs_name = None
            self.refresh_sessions_callback()
            dialog.reject()

        save_button.clicked.connect(on_save)
        skip_button.clicked.connect(on_skip)

        save_button.setStyleSheet(btn_save_name())
        skip_button.setStyleSheet(btn_skip())

        dialog.setLayout(layout)
        dialog.resize(500, 150)
        dialog.exec()

    def tick_ui(self):
        # Call controller's tick_recording to update timer and check if recording is finished
        self.controller.tick_recording()
