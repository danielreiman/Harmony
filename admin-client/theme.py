import customtkinter as ctk


"""Shared colors, fonts, labels, and sizing constants for the Admin UI."""


# Base surface colors.
BG         = "#171717"
ELEVATED   = "#303030"
BORDER     = "#343434"
SOFT       = "#282828"

# Text colors.
TEXT   = "#f4f4f4"
DIM    = "#a8a8a8"
MUTED  = "#777777"

# Feedback and action colors.
ACCENT       = "#f5f5f5"
ACCENT_HOVER = "#e8e8e8"
GREEN        = "#35d399"
RED          = "#ff6467"
AMBER        = "#d6b16a"
CYAN         = "#a8a8a8"

# Fonts used by normal text and compact metadata.
FONT, FONT_MONO  = "Helvetica Neue", "Menlo"

# Friendly display names for raw agent states.
AGENT_STATUS_LABELS = {
    "working": "working", "idle": "idle",
    "stop_requested": "stopping", "clear_requested": "clearing",
    "disconnect_requested": "disconnecting",
}

# Screenshot preview scale inside the dashboard.
SCREEN_PREVIEW_SCALE = 0.88

# Configure CustomTkinter once when the theme module loads.
ctk.set_appearance_mode("dark")

# Login window and prompt defaults.
AUTH_WINDOW_SIZE = (520, 620)
TASK_PLACEHOLDER = "What can I do for you?"

ctk.set_appearance_mode("dark")
