import sys
import os
import re
import time
import csv
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import pandas as pd
import serial
import serial.tools.list_ports
import json

from PySide6.QtCore import QThread, Signal


# ---------------- CONFIG ----------------
AS_COLS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "CLR"]
CSV_PATH = "records_as7341_algae.csv"
KV_PATTERN = re.compile(r"\b(F1|F2|F3|F4|F5|F6|F7|F8|CLR)\s*=\s*(\d+)\b")
JSON_ALIAS_TO_AS = {
    "415nm": "F1",
    "445nm": "F2",
    "480nm": "F3",
    "515nm": "F4",
    "555nm": "F5",
    "590nm": "F6",
    "630nm": "F7",
    "680nm": "F8",
    "Clear": "CLR",
    "clear": "CLR",
}

EXPECTED_COLS = [
    "time", *AS_COLS, "session_id", "session_name",
    "chlorophyll_index", "chlorophyll_index_delta_pct", "chlorophyll_index_status",
    "car_chl_ratio", "car_chl_ratio_delta_pct", "car_chl_ratio_status",
    "yellow_index", "yellow_index_delta_pct", "yellow_index_status",
    "stress_ratio", "stress_ratio_delta_pct", "stress_ratio_status",
    "overall_status"
]

AS_LABELS = {
    "F1": "415nm",
    "F2": "445nm",
    "F3": "480nm",
    "F4": "515nm",
    "F5": "555nm",
    "F6": "590nm",
    "F7": "630nm",
    "F8": "680nm",
    "CLR": "Clear"
}

CHANNEL_COLORS = {
    "F1":  "#7c3aed",
    "F2":  "#2563eb",
    "F3":  "#06b6d4",
    "F4":  "#10b981",
    "F5":  "#84cc16",
    "F6":  "#f59e0b",
    "F7":  "#f97316",
    "F8":  "#ef4444",
    "CLR": "#6b7280",
}


# ---------------- METRICS ----------------
def safe_div(a, b, default=0.0):
    try:
        b = float(b)
        if abs(b) < 1e-9:
            return default
        return float(a) / b
    except Exception:
        return default


def normalize_by_clear(pkt: dict, key: str) -> float:
    clr = max(float(pkt.get("CLR", 0)), 1.0)
    return safe_div(pkt.get(key, 0), clr, default=0.0)


def compute_chlorophyll_index(pkt: dict) -> float:
    # F8(680nm) / F2(445nm)
    return safe_div(pkt.get("F8", 0), pkt.get("F2", 0), default=0.0)


def compute_car_chl_ratio(pkt: dict) -> float:
    # F3(480nm) / F8(680nm)
    return safe_div(pkt.get("F3", 0), pkt.get("F8", 0), default=0.0)


def compute_yellow_index(pkt: dict) -> float:
    # F6(590nm) / F3(480nm)
    return safe_div(pkt.get("F6", 0), pkt.get("F3", 0), default=0.0)


def compute_stress_ratio(pkt: dict) -> float:
    # (F5+F6) / (F2+F8), normalized by Clear first
    f2 = normalize_by_clear(pkt, "F2")
    f5 = normalize_by_clear(pkt, "F5")
    f6 = normalize_by_clear(pkt, "F6")
    f8 = normalize_by_clear(pkt, "F8")
    return safe_div((f5 + f6), (f2 + f8), default=0.0)


def compute_all_indices(pkt: dict) -> dict:
    return {
        "chlorophyll_index": compute_chlorophyll_index(pkt),
        "car_chl_ratio": compute_car_chl_ratio(pkt),
        "yellow_index": compute_yellow_index(pkt),
        "stress_ratio": compute_stress_ratio(pkt),
    }


def compute_delta_pct(current: float, baseline: float) -> float | None:
    if baseline is None or abs(float(baseline)) < 1e-9:
        return None
    return ((float(current) - float(baseline)) / float(baseline)) * 100.0


def classify_delta(delta_pct: float | None, inverse: bool = False) -> str:
    """
    Normal:
      0–10%   -> Healthy
      10–25%  -> Mild stress
      >25%    -> Stressed

    inverse=True means a negative drop is the danger sign.
    Used for Chlorophyll Index, where falling value is bad.
    """
    if delta_pct is None:
        return "No baseline"

    effective = abs(delta_pct) if not inverse else abs(min(delta_pct, 0.0))

    if effective <= 10:
        return "Healthy"
    if effective <= 25:
        return "Mild stress"
    return "Stressed"


def overall_status_from_index_statuses(statuses: list[str]) -> str:
    if not statuses or any(s == "No baseline" for s in statuses):
        return "No baseline"
    if any(s == "Stressed" for s in statuses):
        return "Stressed"
    if any(s == "Mild stress" for s in statuses):
        return "Mild stress"
    return "Healthy"


def status_badge_style(level: str) -> str:
    level = (level or "").lower()
    if "no baseline" in level:
        return "background:#e5e7eb;color:#111827;"
    if level == "healthy":
        return "background:#dcfce7;color:#065f46;"
    if level == "mild stress":
        return "background:#fef3c7;color:#92400e;"
    if level == "stressed":
        return "background:#fee2e2;color:#991b1b;"
    return "background:#e5e7eb;color:#111827;"


def evaluate_against_baseline(pkt: dict, baseline_pkt: dict | None) -> dict:
    current = compute_all_indices(pkt)

    if not baseline_pkt:
        return {
            "current": current,
            "baseline": None,
            "delta_pct": {
                "chlorophyll_index": None,
                "car_chl_ratio": None,
                "yellow_index": None,
                "stress_ratio": None,
            },
            "status_per_index": {
                "chlorophyll_index": "No baseline",
                "car_chl_ratio": "No baseline",
                "yellow_index": "No baseline",
                "stress_ratio": "No baseline",
            },
            "overall_status": "No baseline",
        }

    baseline = compute_all_indices(baseline_pkt)

    delta = {
        k: compute_delta_pct(current[k], baseline[k])
        for k in current.keys()
    }

    status_per_index = {
        "chlorophyll_index": classify_delta(delta["chlorophyll_index"], inverse=True),
        "car_chl_ratio": classify_delta(delta["car_chl_ratio"], inverse=False),
        "yellow_index": classify_delta(delta["yellow_index"], inverse=False),
        "stress_ratio": classify_delta(delta["stress_ratio"], inverse=False),
    }

    overall = overall_status_from_index_statuses(list(status_per_index.values()))

    return {
        "current": current,
        "baseline": baseline,
        "delta_pct": delta,
        "status_per_index": status_per_index,
        "overall_status": overall,
    }


# ---------------- COLOR VISUALIZATION ----------------
def clamp_int(x, lo=0, hi=255):
    try:
        x = int(round(float(x)))
    except Exception:
        return lo
    return max(lo, min(hi, x))


def pkt_to_rgb(pkt: dict):
    """
    Friendly preview color.
    Normalize by CLR to reduce brightness dominance.
    Use:
      B ~ F2+F3
      G ~ F4+F5
      R ~ F7
    """
    if not pkt:
        return (0, 0, 0), "#000000"

    clr = max(1, int(pkt.get("CLR", 1)))

    b_raw = (int(pkt.get("F2", 0)) + int(pkt.get("F3", 0))) / clr
    g_raw = (int(pkt.get("F4", 0)) + int(pkt.get("F5", 0))) / clr
    r_raw = int(pkt.get("F7", 0)) / clr

    m = max(1e-9, float(max(r_raw, g_raw, b_raw)))
    r = clamp_int((r_raw / m) * 255.0)
    g = clamp_int((g_raw / m) * 255.0)
    b = clamp_int((b_raw / m) * 255.0)

    hexv = "#{:02X}{:02X}{:02X}".format(r, g, b)
    return (r, g, b), hexv


def dominant_color_name(pkt: dict):
    if not pkt:
        return "—"
    clr = max(1, int(pkt.get("CLR", 1)))
    b = (int(pkt.get("F2", 0)) + int(pkt.get("F3", 0))) / clr
    g = (int(pkt.get("F4", 0)) + int(pkt.get("F5", 0))) / clr
    r = int(pkt.get("F7", 0)) / clr
    y = int(pkt.get("F6", 0)) / clr

    dom = max(
        [("Blue", b), ("Green", g), ("Red", r), ("Yellow", y)],
        key=lambda x: x[1]
    )[0]
    return dom


# ---------------- CSV ----------------
def ensure_csv_schema(path=CSV_PATH):
    if not os.path.exists(path):
        pd.DataFrame(columns=EXPECTED_COLS).to_csv(path, index=False)
        return

    try:
        header = pd.read_csv(path, nrows=0).columns.tolist()
    except Exception:
        header = []

    if header != EXPECTED_COLS:
        try:
            df = pd.read_csv(path, on_bad_lines="skip")
        except Exception:
            df = pd.DataFrame()

        if df.empty:
            pd.DataFrame(columns=EXPECTED_COLS).to_csv(path, index=False)
            return

        for c in EXPECTED_COLS:
            if c not in df.columns:
                df[c] = np.nan

        df["session_id"] = df["session_id"].fillna("legacy-session").astype(str)
        df["session_name"] = df["session_name"].fillna("").astype(str)

        df = df[EXPECTED_COLS].copy()
        df.to_csv(path, index=False)


def append_row(row: dict, path=CSV_PATH):
    ensure_csv_schema(path)
    ordered = {c: row.get(c, "") for c in EXPECTED_COLS}
    if isinstance(ordered["time"], (datetime, pd.Timestamp)):
        ordered["time"] = ordered["time"].strftime("%Y-%m-%d %H:%M:%S.%f")

    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EXPECTED_COLS)
        w.writerow(ordered)


def load_records_df(path=CSV_PATH) -> pd.DataFrame:
    ensure_csv_schema(path)
    try:
        df = pd.read_csv(path, on_bad_lines="skip")
    except Exception:
        df = pd.DataFrame(columns=EXPECTED_COLS)

    for c in EXPECTED_COLS:
        if c not in df.columns:
            df[c] = np.nan

    df = df[EXPECTED_COLS].copy()
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    df = df.dropna(subset=["time"])
    df["session_id"] = df["session_id"].fillna("legacy-session").astype(str)
    df["session_name"] = df["session_name"].fillna("").astype(str)
    return df


def apply_session_name(session_id: str, session_name: str, path=CSV_PATH):
    df = load_records_df(path)
    sid = str(session_id).strip()
    df.loc[df["session_id"].astype(str) == sid, "session_name"] = str(session_name).strip()
    df2 = df.copy()
    df2["time"] = df2["time"].dt.strftime("%Y-%m-%d %H:%M:%S.%f")
    df2.to_csv(path, index=False)


# ---------------- SERIAL READER THREAD ----------------
class SerialReader(QThread):
    packet = Signal(dict)
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self._ser = None
        self._running = False
        self._pending = {}

    def list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]

    def connect_port(self, port, baud=115200):
        self.disconnect_port()
        try:
            self._ser = serial.Serial(port, baud, timeout=0.2)
            time.sleep(2.0)
            self.flush_buffer(0.5)
            self.clear_pending()
            self.status.emit(f"Connected: {port} @ {baud}")
            return True
        except Exception as e:
            self._ser = None
            self.status.emit(f"Connect error: {e}")
            return False

    def disconnect_port(self):
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        self._ser = None
        self._pending = {}
        self.status.emit("Disconnected")

    def clear_pending(self):
        self._pending.clear()

    def _coerce_as7341_packet(self, obj: dict) -> dict | None:
        if not isinstance(obj, dict) or not obj:
            return None

        pkt = {}
        for raw_key, value in obj.items():
            key = str(raw_key).strip()
            mapped = JSON_ALIAS_TO_AS.get(key, key)
            if mapped not in AS_COLS:
                continue
            try:
                pkt[mapped] = int(value)
            except Exception:
                try:
                    pkt[mapped] = int(float(value))
                except Exception:
                    continue

        if not pkt:
            return None
        return pkt

    def flush_buffer(self, seconds=0.6):
        if not self._ser:
            return
        try:
            self._ser.reset_input_buffer()
        except Exception:
            pass

        t0 = time.time()
        while time.time() - t0 < seconds:
            try:
                while self._ser.in_waiting > 0:
                    self._ser.readline()
            except Exception:
                break
            time.sleep(0.01)

    def run(self):
        self._running = True
        while self._running:
            if not self._ser:
                time.sleep(0.05)
                continue

            try:
                while self._ser.in_waiting > 0:
                    line = self._ser.readline().decode(errors="ignore").strip()
                    if not line:
                        continue
                    if "OK=" in line or "ERR=" in line:
                        continue

                    if line.startswith("{") and line.endswith("}"):
                        try:
                            parsed = json.loads(line)
                            pkt = self._coerce_as7341_packet(parsed)
                            if pkt:
                                for k, v in pkt.items():
                                    self._pending[k] = v
                        except Exception:
                            pass
                    else:
                        for k, v in KV_PATTERN.findall(line):
                            self._pending[k] = int(v)

                    if all(k in self._pending for k in AS_COLS):
                        pkt = {k: self._pending[k] for k in AS_COLS}
                        self._pending.clear()
                        self.packet.emit(pkt)

            except Exception as e:
                self.status.emit(f"Serial read error: {e}")
                time.sleep(0.2)

            time.sleep(0.005)

    def stop(self):
        self._running = False
        self.wait(800)
        self.disconnect_port()


# ---------------- APP STATE ----------------
@dataclass
class AppState:
    baseline_pkt: dict | None = None
    baseline_indices: dict | None = None
    baseline_time: datetime | None = None

    recording: bool = False
    record_end_ts: float | None = None
    session_id: str | None = None
    last_session_needs_name: str | None = None

    max_points: int = 800
    t: list = field(default_factory=list)
    channels: dict = field(default_factory=lambda: {k: [] for k in AS_COLS})

    last_pkt: dict | None = None

