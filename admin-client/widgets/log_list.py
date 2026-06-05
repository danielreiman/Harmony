from datetime import datetime

import customtkinter as ctk

from theme import ACCENT, DIM, FONT, FONT_MONO, GREEN, MUTED, TEXT


"""Activity log row rendering helpers."""


_MAX_LOG = 120
_LOG_KIND = {"cmd": ("$", GREEN), "action": ("▸", ACCENT), "idle": ("·", MUTED)}


# Keep only the most recent items so the list does not grow forever.
def _trim_scroll(scroll):
    """Remove old log rows when the log grows too large."""
    kids = scroll.winfo_children()
    if len(kids) >= _MAX_LOG:
        for w in kids[:len(kids) - _MAX_LOG + 1]:
            w.destroy()

# Jump the view all the way down so the newest item is showing.
def _scroll_end(scroll):
    """Scroll the log to the newest row after layout settles."""
    def _go():
        """Move the underlying canvas to the bottom."""
        try:
            scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    scroll.after(50, _go)


# Add one new card to the activity list, showing what the helper just did
# and why it chose to do it.
def append_log_entry(scroll, step):
    """Append an agent action row to the activity panel."""
    if not step:
        return

    action  = step.get("action", "") or ""
    reason  = step.get("reasoning", "") or ""
    coord, val, cmd_out = step.get("coordinate"), step.get("value"), step.get("cmd_output")
    if action in (None, "None", "") and not reason and not cmd_out:
        return

    _trim_scroll(scroll)
    ts = datetime.now().strftime("%H:%M:%S")
    _, color = _LOG_KIND["cmd"] if cmd_out else \
               _LOG_KIND["action"] if action and action != "None" else _LOG_KIND["idle"]

    # Card container for one activity item.
    entry = ctk.CTkFrame(scroll, fg_color="#282828", corner_radius=12,
                         border_width=0)
    entry.pack(fill="x", padx=4, pady=(0, 6))

    head = ctk.CTkFrame(entry, fg_color="transparent")
    head.pack(fill="x", padx=14, pady=(11, 0))

    # Small colored dot shows action type.
    ctk.CTkFrame(head, fg_color=color, width=6, height=6,
                 corner_radius=3).pack(side="left", pady=(6, 0))
    title = (action if action and action != "None" else "—") \
          + (f'  "{val}"' if val else "") + (f"  @ {coord}" if coord else "")
    ctk.CTkLabel(head, text=title, font=(FONT, 12, "bold"), text_color=TEXT,
                 anchor="w").pack(side="left", padx=(10, 0), fill="x", expand=True)
    ctk.CTkLabel(head, text=ts, font=(FONT_MONO, 9),
                 text_color=MUTED).pack(side="right")

    # Optional reasoning text from the agent.
    if reason:
        ctk.CTkLabel(entry, text=reason, font=(FONT, 11), text_color=DIM,
                     anchor="w", justify="left", wraplength=340).pack(
                         padx=14, pady=(4, 0), fill="x", anchor="w")

    # Optional command output block.
    if cmd_out:
        blk = ctk.CTkFrame(entry, fg_color="#303030", corner_radius=8)
        blk.pack(fill="x", padx=12, pady=(8, 0))
        ctk.CTkLabel(blk, text=str(cmd_out), font=(FONT_MONO, 10),
                     text_color=GREEN, anchor="w", justify="left",
                     wraplength=310).pack(padx=10, pady=7, fill="x", anchor="w")

    ctk.CTkFrame(entry, fg_color="transparent", height=10).pack()
    _scroll_end(scroll)


# Add a short note from the app itself (not the helper) to the activity list.
def append_system_log(scroll, text, color=None):
    """Append a lightweight system status row."""
    if not text:
        return

    _trim_scroll(scroll)
    row = ctk.CTkFrame(scroll, fg_color="transparent")
    row.pack(fill="x", padx=6, pady=1)
    ctk.CTkLabel(row, text=datetime.now().strftime("%H:%M:%S"), font=(FONT_MONO, 9),
                 text_color=MUTED, width=56, anchor="w").pack(side="left")
    ctk.CTkLabel(row, text=text, font=(FONT, 11), text_color=color or DIM,
                 anchor="w", wraplength=300).pack(side="left", fill="x", expand=True)
