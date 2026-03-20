import re
from dataclasses import dataclass, field
from datetime import datetime

from config import CSV_PATH, MAX_BUFFER_POINTS

# CONFIG
AS_COLS = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "CLR"]
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


# APP STATE
@dataclass
class AppState:
    baseline_pkt: dict | None = None
    baseline_indices: dict | None = None
    baseline_time: datetime | None = None

    recording: bool = False
    record_end_ts: float | None = None
    session_id: str | None = None
    last_session_needs_name: str | None = None

    max_points: int = MAX_BUFFER_POINTS
    t: list = field(default_factory=list)
    channels: dict = field(default_factory=lambda: {k: [] for k in AS_COLS})

    last_pkt: dict | None = None
