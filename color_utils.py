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
