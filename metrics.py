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
