import customtkinter as ctk
from ui.theme import *


def _panel(app, title, w, h, close_fn, sub_attr=None):
    p = ctk.CTkFrame(app, fg_color=SURFACE, corner_radius=CORNER_RADIUS,
                     border_width=1, border_color=BORDER, width=w, height=h)
    p.pack_propagate(False)

    head = ctk.CTkFrame(p, fg_color="transparent"); head.pack(fill="x", padx=16, pady=(14, 0))
    ctk.CTkLabel(head, text=title, font=(FONT, 14, "bold"), text_color=TEXT).pack(side="left")
    if sub_attr:
        lbl = ctk.CTkLabel(head, text="", font=(FONT, 11), text_color=MUTED)
        lbl.pack(side="left", padx=(8, 0)); setattr(app, sub_attr, lbl)
    ctk.CTkButton(head, text="✕", width=26, height=26, corner_radius=6,
                  fg_color="transparent", hover_color=ELEVATED, text_color=MUTED,
                  font=(FONT, 12), command=close_fn).pack(side="right")

    ctk.CTkFrame(p, fg_color=BORDER, height=1).pack(fill="x", pady=(12, 0))
    scroll = ctk.CTkScrollableFrame(p, fg_color="transparent", scrollbar_button_color=BORDER,
                                    scrollbar_button_hover_color=MUTED)
    scroll.pack(fill="both", expand=True, padx=4, pady=(2, 6))
    return p, scroll


def build_tasks_panel(app):
    p, app.tasks_scroll = _panel(app, "Tasks", 360, 440, app._hide_tasks_panel, "tasks_cnt")
    return p


def build_logs_panel(app):
    p, app.log_scroll = _panel(app, "Activity Log", 400, 480, app._hide_logs_panel, "logs_agent_lbl")
    return p


class _ROText(ctk.CTkTextbox):
    def configure(self, require_redraw=False, **kwargs):
        if "text" in kwargs:
            txt = kwargs.pop("text")
            super().configure(state="normal"); self.delete("1.0", "end")
            self.insert("1.0", str(txt)); super().configure(state="disabled")
        super().configure(require_redraw=require_redraw, **kwargs)


def build_overlay_section(parent, title, font_size, bold=False,
                          pad_top=12, pad_bottom=10, font_name=FONT):
    ctk.CTkLabel(parent, text=title, font=(FONT_MONO, 8, "bold"),
                 text_color=MUTED, anchor="w").pack(padx=12, pady=(pad_top, 2), anchor="w")
    font = (font_name, font_size, "bold") if bold else (font_name, font_size)
    tb = _ROText(parent, font=font, text_color=TEXT if bold else DIM,
                 fg_color="transparent", wrap="word", height=64, spacing3=3, border_width=0)
    tb.configure(text="—"); tb.pack(padx=8, pady=(0, pad_bottom), fill="x")
    return tb
