import tkinter as tk
import threading
import queue
import time
import math
import random

ui_queue = queue.Queue()
working_queue = queue.Queue()

MOUSE_ICON = "🖱"
KEY_ICON = "⌨"

TRANSPARENT = "#ff00ff"

PILL_BG = "#1b1e27"
PILL_BORDER = "#2f3442"

TEXT_MAIN = "#f4f5f9"
ICON_COLOR = "#9aa3bb"

REASON_BASE = "#cfd5e6"
REASON_PULSE = "#ffffff"

SCREEN_BORDER_BASE = "#2a2f3b"
SCREEN_BORDER_PULSE = "#aab4ff"
SCREEN_BORDER_SOFT = "#3a4160"

agent_running = True


def draw_round_rect(canvas, x, y, w, h, r, **kwargs):
    points = [
        x+r, y, x+w-r, y, x+w, y,
        x+w, y+r, x+w, y+h-r, x+w, y+h,
        x+w-r, y+h, x+r, y+h, x, y+h,
        x, y+h-r, x, y+r, x, y
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def create_screen_borders(root, color, thickness=2):
    root.update_idletasks()
    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()

    def make(wi, hi, xi, yi):
        t = tk.Toplevel(root)
        t.overrideredirect(True)
        t.attributes("-topmost", True)
        t.configure(bg=color)
        t.geometry(f"{wi}x{hi}+{xi}+{yi}")
        return t

    return {
        "top": make(w, thickness, 0, 0),
        "bottom": make(w, thickness, 0, h - thickness),
        "left": make(thickness, h, 0, 0),
        "right": make(thickness, h, w - thickness, 0),
    }


def mix_color(root, c1, c2, t):
    a = root.winfo_rgb(c1)
    b = root.winfo_rgb(c2)
    r = int(a[0] + (b[0] - a[0]) * t) // 256
    g = int(a[1] + (b[1] - a[1]) * t) // 256
    b = int(a[2] + (b[2] - a[2]) * t) // 256
    return f"#{r:02x}{g:02x}{b:02x}"


def start_overlay(demo=True):
    global agent_running

    root = tk.Tk()
    root.attributes("-topmost", True)
    root.overrideredirect(True)
    root.configure(bg=TRANSPARENT)
    root.attributes("-transparentcolor", TRANSPARENT)

    # Dimensions
    pill_width = 520
    height = 64
    gap = 2
    total_width = pill_width + height + gap

    screen_w = root.winfo_screenwidth()
    x = (screen_w // 2) - (total_width // 2)
    y = 20

    # Position BOTH as one centered stack
    root.geometry(f"{pill_width}x{height}+{x}+{y}")

    # ===== MAIN PILL =====
    canvas = tk.Canvas(root, width=pill_width, height=height,
                       bg=TRANSPARENT, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    radius = 26
    pad = 5

    draw_round_rect(canvas, pad + 2, pad + 2,
                    pill_width - pad * 2, height - pad * 2, radius,
                    fill="#0f1118", outline="")
    draw_round_rect(canvas, pad, pad,
                    pill_width - pad * 2 - 2, height - pad * 2 - 2,
                    radius, fill=PILL_BG, outline=PILL_BORDER, width=1)

    content = tk.Frame(canvas, bg=PILL_BG)
    content.place(x=18, y=8, width=pill_width - 36, height=height - 16)

    title_label = tk.Label(content, text="Harmony Agent",
                           fg=TEXT_MAIN, bg=PILL_BG,
                           font=("Segoe UI Semibold", 11))
    title_label.pack(side="left")

    right = tk.Frame(content, bg=PILL_BG)
    right.pack(side="right", fill="both")

    right_inner = tk.Frame(right, bg=PILL_BG)
    right_inner.pack(expand=True)

    action_row = tk.Frame(right_inner, bg=PILL_BG)
    action_row.pack()

    icon_label = tk.Label(action_row, text=KEY_ICON,
                          fg=ICON_COLOR, bg=PILL_BG,
                          font=("Segoe UI", 12))
    icon_label.pack(side="left", padx=(0, 6))

    reasoning_label = tk.Label(action_row, text="Awaiting instructions",
                               fg=REASON_BASE, bg=PILL_BG,
                               font=("Segoe UI", 10, "italic"))
    reasoning_label.pack(side="left")

    # ===== MINI X BUTTON (SAME HEIGHT, SAME STYLE, CENTERED AS STACK) =====
    cancel_btn = tk.Toplevel(root)
    cancel_btn.overrideredirect(True)
    cancel_btn.attributes("-topmost", True)
    cancel_btn.configure(bg=TRANSPARENT)
    cancel_btn.attributes("-transparentcolor", TRANSPARENT)

    cx = x + pill_width + gap
    cancel_btn.geometry(f"{height}x{height}+{cx}+{y}")

    btn_canvas = tk.Canvas(cancel_btn, width=height, height=height,
                           bg=TRANSPARENT, highlightthickness=0)
    btn_canvas.pack(fill="both", expand=True)

    draw_round_rect(btn_canvas, pad + 2, pad + 2,
                    height - pad * 2, height - pad * 2,
                    radius, fill="#0f1118", outline="")
    draw_round_rect(btn_canvas, pad, pad,
                    height - pad * 2 - 2, height - pad * 2 - 2,
                    radius, fill=PILL_BG, outline=PILL_BORDER, width=1)

    btn_canvas.create_text(height // 2, height // 2,
                           text="✕", fill=REASON_BASE,
                           font=("Segoe UI", 12, "bold"))

    def cancel_agent(event=None):
        global agent_running
        agent_running = False
        working_queue.put(False)
        ui_queue.put({"reasoning": "Agent paused by user", "mode": "keyboard"})

    btn_canvas.bind("<Button-1>", cancel_agent)

    # ===== CONTINUOUS SCREEN BORDER PULSE (NEVER DISAPPEARS) =====
    outer = create_screen_borders(root, SCREEN_BORDER_SOFT, thickness=5)
    inner = create_screen_borders(root, SCREEN_BORDER_BASE, thickness=2)

    pulsing = False
    phase = 0
    reason_phase = 0

    def animate_pulse():
        nonlocal phase, reason_phase

        # Always pulse. If idle, pulse softly.
        base_intensity = 0.25 if not pulsing else 1.0
        t = (math.sin(phase) + 1) / 2
        t *= base_intensity

        outer_c = mix_color(root, SCREEN_BORDER_SOFT, SCREEN_BORDER_PULSE, t * 0.6)
        inner_c = mix_color(root, SCREEN_BORDER_BASE, SCREEN_BORDER_PULSE, t)

        for b in outer.values():
            b.configure(bg=outer_c)
        for b in inner.values():
            b.configure(bg=inner_c)

        phase += 0.05

        # Reasoning still pulses only when working
        if pulsing:
            tr = (math.sin(reason_phase) + 1) / 2
            reason_c = mix_color(root, REASON_BASE, REASON_PULSE, tr)
            reasoning_label.config(fg=reason_c)
            reason_phase += 0.12
        else:
            reasoning_label.config(fg=REASON_BASE)

        root.after(40, animate_pulse)

    animate_pulse()

    def update_overlay():
        nonlocal pulsing

        while not ui_queue.empty():
            payload = ui_queue.get()
            reasoning_label.config(text=payload["reasoning"])
            icon_label.config(text=MOUSE_ICON if payload["mode"] == "mouse" else KEY_ICON)

        if not working_queue.empty():
            pulsing = working_queue.get()

        root.after(60, update_overlay)

    # ===== DEMO =====
    if demo:
        def run_demo():
            global agent_running
            while True:
                agent_running = True
                working_queue.put(True)

                for step, mode in [
                    ("Initializing system context", "keyboard"),
                    ("Resolving active window", "mouse"),
                    ("Validating operation target", "keyboard"),
                    ("Executing task sequence", "mouse"),
                    ("Finalizing response", "keyboard")
                ]:
                    if not agent_running:
                        break
                    ui_queue.put({"reasoning": step, "mode": mode})
                    time.sleep(random.uniform(1.0, 2.0))

                working_queue.put(False)
                time.sleep(3)

        threading.Thread(target=run_demo, daemon=True).start()

    update_overlay()
    root.mainloop()


if __name__ == "__main__":
    start_overlay(demo=True)
