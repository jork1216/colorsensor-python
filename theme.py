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
