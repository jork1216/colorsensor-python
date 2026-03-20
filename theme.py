# Background colors for UI elements
BG_DARK = "#0f172a"
BG_MEDIUM = "#1e1650"
BG_CARD = "#281C59"
BG_GREEN_DARK = "#052e16"
BG_YELLOW_DARK = "#3f2a06"
BG_RED_DARK = "#3f1113"

# Border colors for different status states
BORDER_GREEN = "#166534"
BORDER_YELLOW = "#a16207"
BORDER_RED = "#991b1b"
BORDER_PURPLE = "#3d2f8f"

# Text colors for different status states
TEXT_WHITE = "#ffffff"
TEXT_GREEN = "#86efac"
TEXT_YELLOW = "#fde047"
TEXT_RED = "#fca5a5"
TEXT_PURPLE = "#c4b5fd"
TEXT_MUTED = "#9ca3af"


def badge_style_healthy() -> str:
    """Returns the green badge style for healthy status"""
    return """
        padding: 4px 12px;
        border: 1px solid {border};
        border-radius: 8px;
        color: {text};
        background-color: transparent;
        font-size: 14px;
        font-weight: 700;
    """.replace("{border}", BORDER_GREEN).replace("{text}", TEXT_GREEN)


def badge_style_mild_stress() -> str:
    """Returns the yellow badge style for mild stress / warning status"""
    return """
        padding: 4px 12px;
        border: 1px solid {border};
        border-radius: 8px;
        color: {text};
        background-color: transparent;
        font-size: 14px;
        font-weight: 700;
    """.replace("{border}", BORDER_YELLOW).replace("{text}", TEXT_YELLOW)


def badge_style_stressed() -> str:
    """Returns the red badge style for stressed / critical status"""
    return """
        padding: 4px 12px;
        border: 1px solid {border};
        border-radius: 8px;
        color: {text};
        background-color: transparent;
        font-size: 14px;
        font-weight: 700;
    """.replace("{border}", BORDER_RED).replace("{text}", TEXT_RED)


def badge_style_unknown() -> str:
    """Returns the grey badge style for unknown status"""
    return """
        padding: 4px 12px;
        border: 1px solid #374151;
        border-radius: 8px;
        color: #d1d5db;
        background-color: transparent;
        font-size: 14px;
        font-weight: 700;
    """


def banner_style_healthy() -> str:
    """Returns the green overall status banner style for healthy status"""
    return """
        background-color: {bg};
        border: 1px solid {border};
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
        color: {text};
        font-size: 18px;
        font-weight: 800;
        padding-left: 20px;
    """.replace("{bg}", BG_GREEN_DARK).replace("{border}", BORDER_GREEN).replace("{text}", TEXT_GREEN)


def banner_style_mild_stress() -> str:
    """Returns the yellow overall status banner style for mild stress / warning status"""
    return """
        background-color: {bg};
        border: 1px solid {border};
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
        color: {text};
        font-size: 18px;
        font-weight: 800;
        padding-left: 20px;
    """.replace("{bg}", BG_YELLOW_DARK).replace("{border}", BORDER_YELLOW).replace("{text}", TEXT_YELLOW)


def banner_style_stressed() -> str:
    """Returns the red overall status banner style for stressed / critical status"""
    return """
        background-color: {bg};
        border: 1px solid {border};
        border-top-left-radius: 14px;
        border-top-right-radius: 14px;
        border-bottom-left-radius: 0px;
        border-bottom-right-radius: 0px;
        color: {text};
        font-size: 18px;
        font-weight: 800;
        padding-left: 20px;
    """.replace("{bg}", BG_RED_DARK).replace("{border}", BORDER_RED).replace("{text}", TEXT_RED)


def btn_style(bg, border, text, hover_bg=None):
    hover_bg = hover_bg or bg
    return f"""
        QPushButton {{
            background-color: {bg};
            border: 1px solid {border};
            border-radius: 8px;
            color: {text};
            font-size: 13px;
            font-weight: 700;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
        }}
        QPushButton:disabled {{
            background-color: #1e1b4b;
            border-color: #3730a3;
            color: #6b7280;
        }}
    """

def btn_connect():      return btn_style("#0f766e", "#14b8a6", "#ccfbf1", "#0d9488")
def btn_disconnect():   return btn_style("#7c2d12", "#f97316", "#fed7aa", "#9a3412")
def btn_capture_baseline(): return btn_style("#14532d", "#22c55e", "#bbf7d0", "#166534")
def btn_clear_baseline():   return btn_style("#78350f", "#f59e0b", "#fde68a", "#92400e")
def btn_start_recording():  return btn_style("#1e3a8a", "#3b82f6", "#bfdbfe", "#1d4ed8")
def btn_stop_recording():   return btn_style("#7f1d1d", "#ef4444", "#fecaca", "#991b1b")
def btn_export():       return btn_style("#164e63", "#06b6d4", "#cffafe", "#155e75")
def btn_delete():       return btn_style("#450a0a", "#dc2626", "#fca5a5", "#7f1d1d")
def btn_save_name():    return btn_style("#14532d", "#4ade80", "#bbf7d0", "#166534")
def btn_skip():         return btn_style("#1f2937", "#6b7280", "#d1d5db", "#374151")
def btn_neutral():      return btn_style("#2e1065", "#7c3aed", "#ddd6fe", "#3b0764")
