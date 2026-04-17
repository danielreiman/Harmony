import customtkinter as ctk
from datetime import datetime
from ui.theme import FONT, FONT_MONO, SURFACE, BORDER, BG, ELEVATED, TEXT, DIM, MUTED, ACCENT, GREEN

MAX_ENTRIES = 120
_SYM = {"action": ("▸", ACCENT), "cmd": ("$", GREEN), "idle": ("·", MUTED)}


def append_log_entry(scroll, step):
    if not step:
        return
    action = step.get("action", "") or ""
    reason = step.get("reasoning", "") or ""
    coord, val, cmd_out = step.get("coordinate"), step.get("value"), step.get("cmd_output")
    if action in (None, "None", "") and not reason and not cmd_out:
        return

    _trim(scroll)
    ts = datetime.now().strftime("%H:%M:%S")
    sym, color = _SYM["cmd"] if cmd_out else _SYM["action"] if action and action != "None" else _SYM["idle"]

    entry = ctk.CTkFrame(scroll, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
    entry.pack(fill="x", padx=4, pady=(0, 5))

    head = ctk.CTkFrame(entry, fg_color="transparent"); head.pack(fill="x", padx=12, pady=(10, 0))
    ctk.CTkLabel(head, text=sym, font=(FONT_MONO, 12, "bold"), text_color=color,
                 width=16, anchor="w").pack(side="left")
    label = (action if action and action != "None" else "—") + (f'  "{val}"' if val else "") + (f"  @ {coord}" if coord else "")
    ctk.CTkLabel(head, text=label, font=(FONT, 11, "bold"), text_color=TEXT,
                 anchor="w").pack(side="left", fill="x", expand=True)
    ctk.CTkLabel(head, text=ts, font=(FONT_MONO, 8), text_color=MUTED).pack(side="right")

    if reason:
        ctk.CTkFrame(entry, fg_color=BORDER, height=1).pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(entry, text=reason, font=(FONT, 10), text_color=DIM,
                     anchor="w", justify="left", wraplength=320).pack(padx=12, fill="x")
    if cmd_out:
        ctk.CTkFrame(entry, fg_color=BORDER, height=1).pack(fill="x", padx=8, pady=(8, 4))
        blk = ctk.CTkFrame(entry, fg_color=ELEVATED, corner_radius=6); blk.pack(fill="x", padx=8)
        ctk.CTkLabel(blk, text=str(cmd_out), font=(FONT_MONO, 9), text_color=GREEN,
                     anchor="w", justify="left", wraplength=290).pack(padx=8, pady=6, fill="x")

    ctk.CTkFrame(entry, fg_color="transparent", height=6).pack()
    _scroll_to_end(scroll)


def append_system_log(scroll, text, color=None):
    if not text:
        return
    _trim(scroll)
    row = ctk.CTkFrame(scroll, fg_color="transparent"); row.pack(fill="x", padx=4, pady=(0, 1))
    ctk.CTkLabel(row, text=datetime.now().strftime("%H:%M:%S"), font=(FONT_MONO, 8),
                 text_color=MUTED, width=52, anchor="w").pack(side="left")
    ctk.CTkLabel(row, text=text, font=(FONT, 10), text_color=color or DIM,
                 anchor="w", wraplength=290).pack(side="left", fill="x", expand=True)
    _scroll_to_end(scroll)


def _trim(scroll):
    kids = scroll.winfo_children()
    if len(kids) >= MAX_ENTRIES:
        for w in kids[:len(kids) - MAX_ENTRIES + 1]:
            w.destroy()


def _scroll_to_end(scroll):
    def _go():
        try: scroll._parent_canvas.yview_moveto(1.0)
        except Exception: pass
    scroll.after(50, _go)
