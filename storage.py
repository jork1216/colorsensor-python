import os
import csv
from datetime import datetime

import pandas as pd
import numpy as np

from models import CSV_PATH, EXPECTED_COLS


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
