import customtkinter as ctk

BG, SURFACE, ELEVATED, BORDER, GLASS = "#f8f9fb", "#ffffff", "#f3f4f6", "#e4e7ec", "#ffffff"
TEXT, DIM, MUTED = "#101828", "#667085", "#98a2b3"
ACCENT, GREEN, RED, AMBER, CYAN = "#2563eb", "#12b76a", "#f04438", "#f79009", "#0ba5ec"

FONT, FONT_MONO, CORNER_RADIUS = "Helvetica Neue", "Menlo", 10

AGENT_STATUS_LABELS = {
    "working": "working", "idle": "idle",
    "stop_requested": "stopping", "clear_requested": "clearing",
}


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=CORNER_RADIUS,
                        border_width=1, border_color=BORDER, **kw)


def ghost_btn(parent, text, command, width=100, height=36,
              text_color=None, border=None, hover=None, **kw):
    return ctk.CTkButton(parent, text=text, width=width, height=height,
                         corner_radius=CORNER_RADIUS, fg_color="transparent",
                         hover_color=hover or ELEVATED, text_color=text_color or DIM,
                         font=(FONT, 13), border_width=1,
                         border_color=border or BORDER, command=command, **kw)
