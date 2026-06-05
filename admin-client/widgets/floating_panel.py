import customtkinter as ctk

from theme import BORDER, DIM, ELEVATED, FONT, MUTED, TEXT


"""Reusable floating panel widget builder."""


def build_panel(app, title, width, height, on_close, count_label_attr=None):
    """Build a floating panel with a title, close button, and scroll body."""
    # Outer frame is manually placed by the caller.
    panel = ctk.CTkFrame(app, fg_color="#242424", corner_radius=18,
                         border_width=1, border_color=BORDER,
                         width=width, height=height)
    panel.pack_propagate(False)

    # Header contains title, optional count, and close button.
    header = ctk.CTkFrame(panel, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(14, 4))
    ctk.CTkLabel(header, text=title, font=(FONT, 14, "bold"),
                 text_color=TEXT).pack(side="left")

    # Some panels expose a count label back to the app instance.
    if count_label_attr:
        count_label = ctk.CTkLabel(header, text="", font=(FONT, 11), text_color=MUTED)
        count_label.pack(side="left", padx=(10, 0))
        setattr(app, count_label_attr, count_label)

    ctk.CTkButton(header, text="✕", width=28, height=28, corner_radius=8,
                  fg_color="transparent", hover_color=ELEVATED, text_color=DIM,
                  font=(FONT, 13), command=on_close).pack(side="right")

    # Scroll frame holds the caller's panel-specific rows.
    scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent",
                                    scrollbar_button_color=BORDER,
                                    scrollbar_button_hover_color=MUTED)
    scroll.pack(fill="both", expand=True, padx=8, pady=(2, 10))
    return panel, scroll
