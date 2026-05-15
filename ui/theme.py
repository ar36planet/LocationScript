import customtkinter as ctk

# --- Appearance ---
APPEARANCE_MODE = "system"
COLOR_THEME = "blue"

# --- Colors ---
PRIMARY      = "#007AFF"
SUCCESS      = "#28C840"
WARNING      = "#FF9500"
ERROR        = "#FF3B30"
SECONDARY    = "#8E8E93"

BG_DARK      = "#1C1C1E"
BG_LIGHT     = "#F2F2F7"
CARD_DARK    = "#2C2C2E"
CARD_LIGHT   = "#FFFFFF"

TEXT_PRIMARY_DARK  = "#FFFFFF"
TEXT_PRIMARY_LIGHT = "#000000"
TEXT_SECONDARY     = "#8E8E93"

# --- Typography ---
FONT_BODY    = ("SF Pro Display", 13)
FONT_BOLD    = ("SF Pro Display", 13, "bold")
FONT_TITLE   = ("SF Pro Display", 15, "bold")
FONT_SMALL   = ("SF Pro Display", 11)
FONT_MONO    = ("Menlo", 12)

# --- Spacing ---
PAD_XS  = 4
PAD_SM  = 8
PAD_MD  = 16
PAD_LG  = 24

# --- Widget defaults ---
CORNER_RADIUS   = 8
BUTTON_HEIGHT   = 32
ENTRY_HEIGHT    = 32

# secondary button style
BTN_SECONDARY       = ("#C7C7CC", "#545456")   # distinct from card bg
BTN_SECONDARY_HOVER = ("#B0B0B5", "#626265")   # subtle shift, not too dark
BTN_TEXT            = ("gray10", "gray90")


def apply():
    ctk.set_appearance_mode(APPEARANCE_MODE)
    ctk.set_default_color_theme(COLOR_THEME)
