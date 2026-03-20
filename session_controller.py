import time
from datetime import datetime

import numpy as np
from PySide6.QtCore import QObject, Signal

from config import SNAPSHOT_INTERVAL_SECONDS, SERIAL_FLUSH_SECONDS, CSV_PATH
from models import AS_COLS
from metrics import compute_all_indices, evaluate_against_baseline
from storage import append_row


class SessionController(QObject):
    recording_started = Signal()
    recording_stopped = Signal(str)
    tick = Signal(int)
    snapshot_ready = Signal(str, str, dict, dict)
    packet_evaluated = Signal(dict)
    baseline_captured = Signal(dict, str)
    baseline_cleared = Signal()

    def __init__(self, state, reader):
        super().__init__()
        self.state = state
        self.reader = reader
        self.last_snapshot_time = 0
        self.snapshot_interval = SNAPSHOT_INTERVAL_SECONDS

    def capture_baseline(self):
        if not self.state.last_pkt:
            return

        self.state.baseline_pkt = dict(self.state.last_pkt)
        self.state.baseline_indices = compute_all_indices(self.state.last_pkt)
        self.state.baseline_time = datetime.now()

        timestamp_string = self.state.baseline_time.strftime("%Y-%m-%d %H:%M:%S")
        self.baseline_captured.emit(self.state.baseline_indices, timestamp_string)

    def clear_baseline(self):
        self.state.baseline_pkt = None
        self.state.baseline_indices = None
        self.state.baseline_time = None
        self.baseline_cleared.emit()

    def start_recording(self, duration_seconds, snapshot_interval_seconds=None):
        self.reader.flush_buffer(SERIAL_FLUSH_SECONDS)
        self.reader.clear_pending()

        self.state.recording = True
        dur = int(duration_seconds)
        self.state.record_end_ts = time.time() + max(1, dur)
        self.state.session_id = datetime.now().isoformat()
        
        if snapshot_interval_seconds is not None:
            self.snapshot_interval = int(snapshot_interval_seconds)

        self.last_snapshot_time = time.time()
        self.recording_started.emit()

    def stop_recording(self):
        if not self.state.recording:
            return
        self.finish_recording()

    def finish_recording(self):
        self.state.recording = False
        self.last_snapshot_time = 0
        self.state.record_end_ts = None

        sid = self.state.session_id
        self.state.session_id = None

        if sid:
            self.recording_stopped.emit(sid)

    def tick_recording(self):
        if not self.state.recording or self.state.record_end_ts is None:
            return

        remaining = max(0, self.state.record_end_ts - time.time())
        self.tick.emit(int(remaining))

        if remaining <= 0:
            self.finish_recording()

        # Re-evaluate packet against baseline to keep UI updated
        if self.state.last_pkt:
            eval_result = evaluate_against_baseline(self.state.last_pkt, self.state.baseline_pkt)
            self.packet_evaluated.emit(eval_result)

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

        if self.state.recording and (now - self.last_snapshot_time >= self.snapshot_interval):
            self.last_snapshot_time = now
            timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            overall = eval_result["overall_status"]
            self.snapshot_ready.emit(timestamp, overall, cur, delta)

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

        self.packet_evaluated.emit(eval_result)
