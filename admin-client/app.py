import base64, hashlib, os, threading, tkinter as tk, customtkinter as ctk
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageTk
from connection import request

# ── Theme ─────────────────────────────────────────────────────────────────────
BG         = "#171717"
ELEVATED   = "#303030"
BORDER     = "#343434"
SOFT       = "#282828"

TEXT   = "#f4f4f4"
DIM    = "#a8a8a8"
MUTED  = "#777777"

ACCENT       = "#f5f5f5"
ACCENT_HOVER = "#e8e8e8"
GREEN        = "#35d399"
RED          = "#ff6467"
AMBER        = "#d6b16a"
CYAN         = "#a8a8a8"

FONT, FONT_MONO  = "Helvetica Neue", "Menlo"

AGENT_STATUS_LABELS = {
    "working": "working", "idle": "idle",
    "stop_requested": "stopping", "clear_requested": "clearing",
    "disconnect_requested": "disconnecting",
}

SCREEN_PREVIEW_SCALE = 0.88

ctk.set_appearance_mode("dark")
AUTH_WINDOW_SIZE = (520, 620)
TASK_PLACEHOLDER = "What can I do for you?"


# Small grey heading shown above a group of items.
def _section_label(parent, text, **kw):
    return ctk.CTkLabel(parent, text=text, font=(FONT_MONO, 9, "bold"),
                        text_color=MUTED, anchor="w", **kw)


# ── Log helpers ───────────────────────────────────────────────────────────────
_MAX_LOG = 120
_LOG_KIND = {"cmd": ("$", GREEN), "action": ("▸", ACCENT), "idle": ("·", MUTED)}

# Keep only the most recent items so the list does not grow forever.
def _trim_scroll(scroll):
    kids = scroll.winfo_children()
    if len(kids) >= _MAX_LOG:
        for w in kids[:len(kids) - _MAX_LOG + 1]:
            w.destroy()

# Jump the view all the way down so the newest item is showing.
def _scroll_end(scroll):
    def _go():
        try: scroll._parent_canvas.yview_moveto(1.0)
        except Exception: pass
    scroll.after(50, _go)

# Add one new card to the activity list, showing what the helper just did
# and why it chose to do it.
def append_log_entry(scroll, step):
    if not step: return
    action  = step.get("action", "") or ""
    reason  = step.get("reasoning", "") or ""
    coord, val, cmd_out = step.get("coordinate"), step.get("value"), step.get("cmd_output")
    if action in (None, "None", "") and not reason and not cmd_out: return

    _trim_scroll(scroll)
    ts = datetime.now().strftime("%H:%M:%S")
    sym, color = _LOG_KIND["cmd"] if cmd_out else \
                 _LOG_KIND["action"] if action and action != "None" else _LOG_KIND["idle"]

    entry = ctk.CTkFrame(scroll, fg_color="#282828", corner_radius=12,
                         border_width=0)
    entry.pack(fill="x", padx=4, pady=(0, 6))

    head = ctk.CTkFrame(entry, fg_color="transparent"); head.pack(fill="x", padx=14, pady=(11, 0))
    ctk.CTkFrame(head, fg_color=color, width=6, height=6,
                 corner_radius=3).pack(side="left", pady=(6, 0))
    title = (action if action and action != "None" else "—") \
          + (f'  "{val}"' if val else "") + (f"  @ {coord}" if coord else "")
    ctk.CTkLabel(head, text=title, font=(FONT, 12, "bold"), text_color=TEXT,
                 anchor="w").pack(side="left", padx=(10, 0), fill="x", expand=True)
    ctk.CTkLabel(head, text=ts, font=(FONT_MONO, 9),
                 text_color=MUTED).pack(side="right")

    if reason:
        ctk.CTkLabel(entry, text=reason, font=(FONT, 11), text_color=DIM,
                     anchor="w", justify="left", wraplength=340).pack(
                         padx=14, pady=(4, 0), fill="x", anchor="w")
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
    if not text: return
    _trim_scroll(scroll)
    row = ctk.CTkFrame(scroll, fg_color="transparent"); row.pack(fill="x", padx=6, pady=1)
    ctk.CTkLabel(row, text=datetime.now().strftime("%H:%M:%S"), font=(FONT_MONO, 9),
                 text_color=MUTED, width=56, anchor="w").pack(side="left")
    ctk.CTkLabel(row, text=text, font=(FONT, 11), text_color=color or DIM,
                 anchor="w", wraplength=300).pack(side="left", fill="x", expand=True)
    _scroll_end(scroll)


# ── Read-only textbox ─────────────────────────────────────────────────────────
# A text area people can read but cannot type into.
class _ROText(ctk.CTkTextbox):
    def configure(self, require_redraw=False, **kwargs):
        if "text" in kwargs:
            txt = kwargs.pop("text")
            super().configure(state="normal"); self.delete("1.0", "end")
            self.insert("1.0", str(txt)); super().configure(state="disabled")
        super().configure(require_redraw=require_redraw, **kwargs)


# ── Floating panel builder ────────────────────────────────────────────────────
# Build a small floating box (like the Tasks or Activity pop-up) with a title,
# a close button, and a scrolling area inside.
def _build_panel(app, title, width, height, on_close, count_label_attr=None):
    panel = ctk.CTkFrame(app, fg_color="#242424", corner_radius=18,
                         border_width=1, border_color=BORDER,
                         width=width, height=height)
    panel.pack_propagate(False)

    header = ctk.CTkFrame(panel, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(14, 4))
    ctk.CTkLabel(header, text=title, font=(FONT, 14, "bold"),
                 text_color=TEXT).pack(side="left")
    if count_label_attr:
        count_label = ctk.CTkLabel(header, text="", font=(FONT, 11), text_color=MUTED)
        count_label.pack(side="left", padx=(10, 0))
        setattr(app, count_label_attr, count_label)
    ctk.CTkButton(header, text="✕", width=28, height=28, corner_radius=8,
                  fg_color="transparent", hover_color=ELEVATED, text_color=DIM,
                  font=(FONT, 13), command=on_close).pack(side="right")

    scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent",
                                    scrollbar_button_color=BORDER,
                                    scrollbar_button_hover_color=MUTED)
    scroll.pack(fill="both", expand=True, padx=8, pady=(2, 10))
    return panel, scroll

# ── Login screen ──────────────────────────────────────────────────────────────
# Build the sign-in screen where someone types their name and password
# to enter the app.
def _build_login(app):
    frame = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)

    auth_card = ctk.CTkFrame(frame, fg_color="#242424", corner_radius=22,
                             border_width=1, border_color="#343434",
                             width=390, height=430)
    auth_card.place(relx=0.5, rely=0.5, anchor="center")
    auth_card.pack_propagate(False)

    ctk.CTkLabel(auth_card, text="Harmony", font=(FONT, 28, "bold"),
                 text_color=TEXT).pack(pady=(38, 4))
    ctk.CTkLabel(auth_card, text="Sign in to continue", font=(FONT, 13),
                 text_color=MUTED).pack(pady=(0, 28))

    def field(placeholder, show=None):
        entry_options = dict(width=316, height=44, corner_radius=10,
                             border_width=1, border_color=BORDER, fg_color=SOFT,
                             text_color=TEXT, placeholder_text_color=MUTED,
                             font=(FONT, 13))
        if show:
            entry_options["show"] = show
        entry = ctk.CTkEntry(auth_card, placeholder_text=placeholder, **entry_options)
        entry.pack(pady=(0, 12))
        return entry

    app.login_user = field("Username")
    app.login_pass = field("Password", show="•")

    app.login_err = ctk.CTkLabel(auth_card, text="", text_color=RED, font=(FONT, 11),
                                 height=22, wraplength=300)
    app.login_err.pack(pady=(2, 10))

    ctk.CTkButton(auth_card, text="Sign in", width=316, height=44, corner_radius=10,
                  fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=BG,
                  font=(FONT, 13, "bold"),
                  command=lambda: app._authenticate("auth_login")).pack()

    signup = ctk.CTkLabel(auth_card, text="Create account", font=(FONT, 12, "bold"),
                          text_color=MUTED, cursor="hand2")
    signup.pack(pady=(20, 0))
    signup.bind("<Button-1>", lambda e: app._authenticate("auth_signup"))

    for widget in (frame, auth_card, app.login_user, app.login_pass):
        widget.bind("<Return>", lambda e: app._authenticate("auth_login"))
    return frame


# ── Main application ──────────────────────────────────────────────────────────
# The whole app. This holds every screen and keeps track of who is signed in,
# which helper is chosen, and what is happening right now.
class HarmonyApp(ctk.CTk):

    # Set up the app when it first starts: remember nothing is chosen yet,
    # build all the screens, and begin checking for news from the server.
    def __init__(self):
        super().__init__()
        self.title("Harmony")
        self.configure(fg_color=BG)
        self.resizable(True, True)

        self.user_id              = None
        self.current_username     = ""
        self.selected_agent       = None
        self.is_agent_working     = False
        self.is_task_send_pending = False
        self.is_tasks_panel_open  = False
        self.is_logs_panel_open   = False

        self._known_agent_ids     = []
        self._known_agents        = []
        self._current_screenshot  = None
        self._prev_step_hash      = None
        self._prev_log_hash       = None
        self._prev_status_message = ""
        self._prev_agent_status   = ""
        self._is_server_connected = True

        self._setup_window()
        self._build_all_views()
        self._start_polling_loops()

    # ── Window ────────────────────────────────────────────────────────────────
    # Give the app window its picture in the corner and place it on screen.
    def _setup_window(self):
        try:
            app_icon = ImageTk.PhotoImage(Image.open(os.path.join(os.path.dirname(__file__), "resources", "icon.png")))
            self.wm_iconphoto(False, app_icon)
        except Exception:
            pass
        self._set_centered_window(*AUTH_WINDOW_SIZE)

    # Put a small window right in the middle of the screen.
    def _set_centered_window(self, width, height):
        """Place compact views in the center without hiding the native title bar."""
        self.attributes("-fullscreen", False)
        try:
            self.attributes("-zoomed", False)
        except Exception:
            pass
        try:
            self.state("normal")
        except Exception:
            pass
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # Make the window cover the whole screen for the main view.
    def _enter_main_fullscreen(self):
        try:
            self.state("normal")
        except Exception:
            pass
        self.attributes("-fullscreen", True)

    # Run a slow piece of work on the side so the app stays smooth.
    def _run_in_background(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    # Load small UI images once and keep them alive for CustomTkinter labels.
    def _resource_image(self, filename, size):
        if "_resource_image_cache" not in self.__dict__:
            self._resource_image_cache = {}
        key = (filename, size)
        if key not in self._resource_image_cache:
            path = os.path.join(os.path.dirname(__file__), "resources", filename)
            image = Image.open(path)
            self._resource_image_cache[key] = ctk.CTkImage(
                light_image=image, dark_image=image, size=size)
        return self._resource_image_cache[key]

    # Hide every screen and then show only the one we want.
    def _show_frame(self, frame):
        for f in (self.login_frame, self.main_frame):
            try: f.pack_forget()
            except Exception: pass
        frame.pack(fill="both", expand=True)

    # Switch back to the sign-in screen.
    def _show_login_view(self):
        self._set_centered_window(*AUTH_WINDOW_SIZE)
        self._show_frame(self.login_frame)

    # Switch to the big main screen after someone signs in.
    def _show_main_view(self):
        self._enter_main_fullscreen()
        self._show_frame(self.main_frame)

    # ── Build views ───────────────────────────────────────────────────────────
    # Build both the sign-in screen and the main screen, then show sign-in first.
    def _build_all_views(self):
        self.login_frame = _build_login(self)
        self._build_main_view()
        self._show_login_view()

    # Build the whole main screen piece by piece: top bar, middle area,
    # bottom bar, and the two pop-ups for Tasks and Activity.
    def _build_main_view(self):
        self.main_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._build_top_bar()
        self._build_content_area()
        self._build_empty_state()
        self._build_bottom_bar()
        self.tasks_panel, self.tasks_scroll = _build_panel(
            self, "Tasks", 310, 380, self._hide_tasks_panel, "tasks_cnt")
        self.logs_panel, self.log_scroll = _build_panel(
            self, "Activity", 350, 430, self._hide_logs_panel, "logs_agent_lbl")

    # Build the strip across the top with the welcome message, the name
    # of the app, and the sign-out and shut-down buttons.
    def _build_top_bar(self):
        bar = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=82,
                           corner_radius=0, border_width=0)
        bar.pack(fill="x"); bar.pack_propagate(False)

        top_row = ctk.CTkFrame(bar, fg_color="transparent", height=42)
        top_row.pack(fill="x", padx=22, pady=(20, 0))
        top_row.pack_propagate(False)

        capsule_style = dict(fg_color="#282828", corner_radius=21,
                             height=42, border_width=1, border_color="#343434",
                             bg_color=BG)

        welcome_capsule = ctk.CTkFrame(top_row, width=224, **capsule_style)
        welcome_capsule.pack(side="left")
        welcome_capsule.pack_propagate(False)

        self.welcome_label = ctk.CTkLabel(welcome_capsule,
            text="  Good to see you",
            image=self._resource_image("wave_emoji.png", (24, 19)),
            compound="left", font=(FONT, 13, "bold"),
            text_color="#f4f4f4", height=24)
        self.welcome_label.place(relx=0.5, rely=0.5, anchor="center")

        title_capsule = ctk.CTkFrame(top_row, width=110, **capsule_style)
        title_capsule.place(relx=0.5, rely=0.5, anchor="center")
        title_capsule.pack_propagate(False)
        ctk.CTkLabel(title_capsule, text="Harmony", font=(FONT, 13, "bold"),
                     text_color="#f4f4f4").place(relx=0.5, rely=0.5, anchor="center")

        actions_capsule = ctk.CTkFrame(top_row, width=206, **capsule_style)
        actions_capsule.pack(side="right")
        actions_capsule.pack_propagate(False)

        actions_row = ctk.CTkFrame(actions_capsule, fg_color="transparent")
        actions_row.place(relx=0.5, rely=0.5, anchor="center")

        def nav_item(text, width, text_color, weight="normal", hover="#343434", command=None):
            return ctk.CTkButton(
                actions_row, text=text, width=width, height=30, corner_radius=15,
                fg_color="transparent", hover_color=hover,
                text_color=text_color, font=(FONT, 13, weight), border_width=0,
                command=command or (lambda: None))

        nav_item("Log out", 78, "#a8a8a8", command=self._show_login_view).pack(
            side="left", padx=4)
        self.shutdown_button = nav_item(
            "Shutdown", 92, "#ff7a7a", hover="#3a2929",
            command=lambda: [request({"action": "stop_server"}), self.quit()])
        self.shutdown_button.pack(side="left", padx=4)

    # Build the big middle area that holds the picture of the helper's
    # screen and the side cards with what it is doing.
    def _build_content_area(self):
        self.content_area = ctk.CTkFrame(self.main_frame, fg_color=BG)
        self.content_area.pack(fill="both", expand=True, padx=22, pady=(22, 236))

        self.screenshot_and_panels = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.screenshot_and_panels.pack(fill="both", expand=True)
        self._build_screen_stage()
        self._build_floating_state_panel()

    # Set up the area in the middle where the helper's screen picture appears.
    def _build_screen_stage(self):
        self.screen_meta = ctk.CTkLabel(self.screenshot_and_panels, text="")
        self.screen_area = ctk.CTkFrame(self.screenshot_and_panels, fg_color="transparent")
        self.screen_area.place(relx=0.5, rely=0.5, anchor="center",
                               relwidth=1.0, relheight=1.0)
        self.screenshot_label = ctk.CTkLabel(self.screen_area, text="",
            text_color=MUTED, font=(FONT, 13))
        self.screenshot_label.place(relx=0.5, rely=0.5, anchor="center")

    # Clear the screen picture while we are waiting for a new one.
    # We never pass image=None to a CTkLabel — CustomTkinter doesn't fully
    # clear the inner tk.Label's image option, which leaves a dangling
    # pyimage reference and crashes on the next configure(). Instead we
    # tell the label to display only the text, leaving the image option
    # untouched (the empty-state overlay covers anything still drawn).
    def _show_waiting_screenshot(self):
        try:
            self.screenshot_label.configure(text=" ")
        except Exception:
            pass

    # Build the two cards on the right side that show what the helper
    # is doing right now and the reason it gave for doing it.
    def _build_floating_state_panel(self):
        CARD_W          = 360
        PANEL_BG        = "#282828"
        PANEL_BORDER    = "#3a3a3a"
        ACTION_BG       = "#f1f1f3"
        ACTION_BORDER   = "#d8d8d8"
        CARD_RADIUS     = 18
        CARD_GAP        = 18
        CARD_PAD_X      = 22
        CARD_PAD_Y      = 22
        LABEL_GAP       = 10
        LABEL_FONT      = (FONT_MONO, 13, "bold")
        HEADLINE_FONT   = (FONT, 22, "bold")
        BODY_FONT       = (FONT, 16)
        BODY_COLOR      = "#c9c9ce"
        WRAP            = CARD_W - CARD_PAD_X * 2

        def label(parent, text):
            return ctk.CTkLabel(parent, text=text, font=LABEL_FONT,
                                text_color=LABEL_COLOR, anchor="w")

        # Keep the right column fully on-screen, but reserve more width so the
        # screenshot does not run underneath it.
        self._info_cards_width = CARD_W
        self._screen_right_reserve = CARD_W + 88
        self.info_cards_container = ctk.CTkFrame(self.screenshot_and_panels,
            fg_color="transparent", width=CARD_W)
        self.info_cards_container.place(relx=1.0, rely=0.0, relheight=1.0,
                                        x=-4, anchor="ne")
        self.info_cards_container.pack_propagate(False)

        # Vertical spacer pushes cards to center
        ctk.CTkFrame(self.info_cards_container, fg_color="transparent").pack(
            fill="both", expand=True)

        # ACTION card — white background, dark text
        action_card = ctk.CTkFrame(self.info_cards_container,
            fg_color=ACTION_BG, corner_radius=CARD_RADIUS,
            border_width=1, border_color=ACTION_BORDER)
        action_card.pack(fill="x", pady=(0, CARD_GAP))
        ctk.CTkLabel(action_card, text="ACTION", font=LABEL_FONT,
            text_color="#6a6a70", anchor="w").pack(
            fill="x", padx=CARD_PAD_X, pady=(CARD_PAD_Y, LABEL_GAP), anchor="w")
        self.action_row = ctk.CTkFrame(action_card, fg_color="transparent")
        self.action_row.pack(fill="x", padx=CARD_PAD_X, pady=(0, CARD_PAD_Y))
        self.action_done_icon = self._resource_image("confeti_emoji.png", (38, 38))
        self.action_icon_label = ctk.CTkLabel(self.action_row, text="",
            image=self.action_done_icon, width=38, height=38)
        self.action_textbox = ctk.CTkLabel(self.action_row, text="—",
            font=HEADLINE_FONT, text_color=PANEL_BG, anchor="w",
            justify="left", wraplength=WRAP)
        self.action_textbox.pack(side="left")
        self.action_meta_label = ctk.CTkLabel(self.action_row, text="",
            font=HEADLINE_FONT, text_color="#8a8a90", anchor="w",
            justify="left")
        self.action_meta_label.pack(side="left", padx=(10, 0))

        self.action_command_block = ctk.CTkFrame(action_card, fg_color="#dedee2",
            corner_radius=8)
        self.action_command_label = ctk.CTkLabel(self.action_command_block, text="",
            font=(FONT_MONO, 12), text_color="#313136", anchor="w",
            justify="left", wraplength=WRAP - 20)
        self.action_command_label.pack(fill="x", padx=10, pady=8, anchor="w")

        # REASONING card — dark background
        reason_card = ctk.CTkFrame(self.info_cards_container,
            fg_color=PANEL_BG, corner_radius=CARD_RADIUS,
            border_width=1, border_color=PANEL_BORDER)
        reason_card.pack(fill="x", pady=(0, 0))

        # Bottom spacer mirrors the top one
        ctk.CTkFrame(self.info_cards_container, fg_color="transparent").pack(
            fill="both", expand=True)
        ctk.CTkLabel(reason_card, text="REASONING", font=LABEL_FONT,
            text_color="#7a7a80", anchor="w").pack(
            fill="x", padx=CARD_PAD_X, pady=(CARD_PAD_Y, LABEL_GAP), anchor="w")
        self.reasoning_textbox = ctk.CTkTextbox(reason_card,
            font=BODY_FONT, text_color=BODY_COLOR,
            fg_color=PANEL_BG, border_width=0,
            wrap="word", height=110, activate_scrollbars=True)
        self.reasoning_textbox.pack(fill="x",
            padx=(CARD_PAD_X - 6, CARD_PAD_X), pady=(0, CARD_PAD_Y), anchor="nw")
        self.reasoning_textbox._textbox.configure(spacing2=6, padx=0, pady=0)
        self.reasoning_textbox.insert("1.0", "—")
        self.reasoning_textbox.configure(state="disabled")

        # Removed from this panel — kept as hidden stubs so other code can
        # still call .configure on them without errors.
        self.selected_agent_title = ctk.CTkLabel(self, text="")
        self.status_chip          = ctk.CTkFrame(self, fg_color="transparent")
        self.status_chip_label    = ctk.CTkLabel(self.status_chip, text="")

    _ACTION_LABELS = {
        "left_click": "Left Click", "click": "Left Click",
        "double_click": "Double Click", "right_click": "Right Click",
        "drag": "Drag", "type": "Type", "press_key": "Press",
        "hotkey": "Hotkey", "scroll_up": "Scroll Up", "scroll_down": "Scroll Down",
        "run_command": "Run Command", "wait": "Wait",
    }

    # Turn a raw step from the helper into a short, friendly sentence
    # that someone can read at a glance.
    def _format_coord(self, coordinate):
        try:
            x, y = coordinate[0], coordinate[1]
            return f"({int(x)}, {int(y)})"
        except Exception:
            return str(coordinate)

    def _format_key_value(self, value):
        if isinstance(value, (list, tuple)):
            return " + ".join(str(v).title() for v in value)
        return str(value).title()

    def _format_action(self, action, coordinate, value, end_coord=None):
        if not action or str(action).lower() == "none":
            return "—", "", ""

        action_key = str(action).lower()
        pretty = self._ACTION_LABELS.get(action_key, str(action).replace("_", " ").title())
        meta = ""
        command = ""

        if coordinate:
            meta = self._format_coord(coordinate)
            if end_coord:
                meta = f"{meta} -> {self._format_coord(end_coord)}"
        elif action_key in ("press_key", "hotkey") and value not in (None, ""):
            meta = self._format_key_value(value)
        elif action_key == "wait" and value not in (None, ""):
            meta = f"{value}s"

        if action_key == "run_command" and value not in (None, ""):
            command = str(value)

        return pretty, meta, command

    def _set_reasoning_text(self, text):
        self.reasoning_textbox.configure(state="normal")
        self.reasoning_textbox.delete("1.0", "end")
        self.reasoning_textbox.insert("1.0", text)
        self.reasoning_textbox.configure(state="disabled")

    def _set_action_display(self, action, meta="", command="", icon=None):
        if icon:
            self.action_icon_label.configure(image=icon)
            self.action_icon_label.pack(
                side="left", padx=(0, 10), pady=(0, 0), before=self.action_textbox)
        else:
            self.action_icon_label.pack_forget()
        self.action_textbox.configure(text=action or "—")
        self.action_meta_label.configure(text=meta or "")

        if command:
            self.action_command_label.configure(text=command)
            self.action_row.pack_configure(pady=(0, 10))
            self.action_command_block.pack(
                fill="x", padx=22, pady=(0, 22), after=self.action_row)
        else:
            self.action_command_block.pack_forget()
            self.action_row.pack_configure(pady=(0, 22))

    # Build the friendly message that shows up when no helper is chosen yet.
    def _build_empty_state(self):
        self.empty_state_overlay = ctk.CTkFrame(self.screenshot_and_panels, fg_color="transparent")
        ctr = ctk.CTkFrame(self.empty_state_overlay, fg_color="transparent")
        ctr.place(relx=0.5, rely=0.44, anchor="center")
        self.empty_state_title = ctk.CTkLabel(ctr, text="No agent connected",
                                              font=(FONT, 20, "bold"), text_color=TEXT)
        self.empty_state_title.pack(pady=(0, 6))
        self.empty_state_subtitle = ctk.CTkLabel(ctr,
            text="Connect an agent to see its screen here",
            font=(FONT, 13), text_color=DIM)
        self.empty_state_subtitle.pack()

    # Build the strip across the bottom: the toolbar buttons, the
    # current-task ribbon, and the box for typing a new request.
    def _build_bottom_bar(self):
        wrap = ctk.CTkFrame(self.main_frame, fg_color="transparent", width=884)
        wrap.place(relx=0.5, rely=1.0, y=-20, anchor="s")

        # Footer toolbar
        footer = ctk.CTkFrame(wrap, fg_color="transparent", width=884, height=28)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        def toolbar_item(parent, icon, label, command, width):
            item = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8,
                                width=width, height=28, cursor="hand2")
            item.pack_propagate(False)
            icon_lbl = ctk.CTkLabel(item, text=icon, font=(FONT, 14, "bold"), text_color="#b5b5b5")
            icon_lbl.pack(side="left", padx=(9, 7))
            text_lbl = ctk.CTkLabel(item, text=label, font=(FONT, 14, "bold"), text_color="#d8d8d8")
            text_lbl.pack(side="left")
            def enter(_e): item.configure(fg_color="#242424")
            def leave(_e): item.configure(fg_color="transparent")
            for w in (item, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda _e, fn=command: fn())
                w.bind("<Enter>", enter); w.bind("<Leave>", leave)
            return item

        toolbar = ctk.CTkFrame(footer, fg_color="transparent")
        toolbar.pack(side="left")
        self.logs_toggle_button = toolbar_item(toolbar, "⌘", "Activity",
                                               self._toggle_logs_panel, 104)
        self.logs_toggle_button.pack(side="left", padx=(0, 10))
        self.tasks_toggle_button = toolbar_item(toolbar, "☑", "Tasks",
                                                self._toggle_tasks_panel, 82)
        self.tasks_toggle_button.pack(side="left", padx=(0, 10))

        self.footer_actions = ctk.CTkFrame(footer, fg_color="transparent")
        self.footer_actions.pack(side="right")
        self.disconnect_button = ctk.CTkButton(self.footer_actions, text="Disconnect",
            width=88, height=24, corner_radius=6, fg_color="transparent",
            hover_color=ELEVATED, text_color=AMBER, font=(FONT, 12), border_width=0,
            command=self._disconnect_current_agent)
        self.disconnect_button.pack(side="right", padx=(12, 0))
        self._is_disconnect_visible = True; self._hide_disconnect_button()
        self.reset_memory_button = ctk.CTkButton(self.footer_actions, text="Clear Memory",
            width=112, height=24, corner_radius=6, fg_color="transparent",
            hover_color=ELEVATED, text_color=CYAN, font=(FONT, 12), border_width=0,
            command=self._reset_current_agent)
        self.reset_memory_button.pack(side="right", padx=(12, 0))
        self._is_reset_visible = True; self._hide_reset_button()

        # Layered composer: task strip peeks out above and tucks behind the
        # prompt box. OVERLAP is how much of the strip hides behind the prompt.
        STRIP_MIN_H, STRIP_W, PROMPT_H, OVERLAP = 58, 800, 114, 22
        COMPOSER_H = STRIP_MIN_H - OVERLAP + PROMPT_H

        composer = ctk.CTkFrame(wrap, fg_color="transparent",
                                width=884, height=COMPOSER_H)
        composer.pack(fill="x", side="bottom", pady=(0, 12))
        composer.pack_propagate(False)

        self.prompt_strip = ctk.CTkFrame(composer, fg_color="#242424",
            corner_radius=18, border_width=1, border_color="#343434",
            width=STRIP_W, height=STRIP_MIN_H)
        self.prompt_strip.place(relx=0.5, y=0, anchor="n")
        self.prompt_strip.pack_propagate(False)

        # Visible content sits in the top band (everything below the prompt
        # overlap is hidden behind the prompt box).
        visible_cy = (STRIP_MIN_H - OVERLAP) // 2

        strip_inner = ctk.CTkFrame(self.prompt_strip, fg_color="transparent")
        strip_inner.place(relx=0, y=visible_cy, x=20, anchor="w", relwidth=0.83)
        ctk.CTkLabel(strip_inner, text="Current Task:", font=(FONT, 13, "bold"),
                     text_color="#8a8a8a", anchor="w").pack(side="left", padx=(0, 10))
        self.strip_task_label = ctk.CTkLabel(strip_inner, text="No active task",
            font=(FONT, 13, "bold"), text_color="#e8e8e8",
            anchor="w", justify="left")
        self.strip_task_label.pack(side="left", fill="x", expand=True)

        self.strip_toggle = ctk.CTkButton(self.prompt_strip, text="Show more",
            width=92, height=26, corner_radius=13, fg_color="transparent",
            hover_color="#303030", text_color="#f0f0f0",
            font=(FONT, 11, "bold"), border_width=0,
            command=self._toggle_task_expand)
        self.strip_toggle.place(relx=1.0, y=visible_cy, x=-16, anchor="e")

        self.prompt_box = ctk.CTkFrame(composer, fg_color="#282828",
            corner_radius=18, border_width=1, border_color="#343434",
            height=PROMPT_H)
        self.prompt_box.place(x=0, y=STRIP_MIN_H - OVERLAP, relwidth=1)
        self.prompt_box.pack_propagate(False)
        self.prompt_box.lift()

        self._composer     = composer
        self._strip_min_h  = STRIP_MIN_H
        self._strip_w      = STRIP_W
        self._strip_overlap = OVERLAP
        self._strip_visible_cy = visible_cy
        self._prompt_h     = PROMPT_H

        self.task_input = ctk.CTkEntry(self.prompt_box,
            placeholder_text=TASK_PLACEHOLDER,
            height=36, corner_radius=0, border_width=0, fg_color="#282828",
            text_color="#f4f4f4", placeholder_text_color="#777777",
            font=(FONT, 15, "bold"))
        self.task_input.pack(fill="x", padx=16, pady=(12, 0))
        self.task_input.bind("<Return>", lambda e: self._send_task_or_stop_agent())
        self.task_input.bind("<KeyRelease>", lambda _e: self._sync_send_button_visual())

        tools = ctk.CTkFrame(self.prompt_box, fg_color="transparent", height=42)
        tools.pack(fill="x", padx=16, pady=(12, 0))
        tools.pack_propagate(False)

        right = ctk.CTkFrame(tools, fg_color="transparent")
        right.place(relx=1.0, rely=0.5, x=0, y=0, anchor="e")

        self.agent_dropdown = ctk.CTkOptionMenu(right, values=["No agents"],
            width=142, height=30, corner_radius=9, fg_color="#282828",
            text_color="#a8a8a8", button_color="#282828", button_hover_color="#343434",
            dropdown_fg_color="#2b2b2b", dropdown_text_color="#f4f4f4",
            font=(FONT, 12, "bold"), command=self._on_agent_selection_changed)
        self.agent_dropdown.pack(side="left", padx=(0, 12))
        self.agent_dropdown.set("No agents")

        self.send_stop_button = tk.Canvas(right, width=40, height=40, bd=0,
            highlightthickness=0, bg="#282828", cursor="hand2")
        self.send_stop_bg   = self.send_stop_button.create_oval(1, 1, 39, 39,
                                                                 fill="#f5f5f5", outline="")
        self.send_stop_play = self.send_stop_button.create_polygon(
            15, 13, 15, 27, 28, 20, fill="#2b2b2b", outline="")
        sq = 12
        self.send_stop_square = self.send_stop_button.create_rectangle(
            20 - sq // 2, 20 - sq // 2, 20 + sq // 2, 20 + sq // 2,
            fill="#2b2b2b", outline="", state="hidden")

        def send_enter(_e):
            self._sync_send_button_visual(hover=True)
        def send_leave(_e):
            self._sync_send_button_visual()

        self.send_stop_button.bind("<Button-1>", lambda _e: self._send_task_or_stop_agent())
        self.send_stop_button.bind("<Enter>", send_enter)
        self.send_stop_button.bind("<Leave>", send_leave)
        self.send_stop_button.pack(side="left")

        self._is_task_expanded = False
        self._full_task_text   = "No active task"
        self._apply_task_display()

    # ── Authentication ────────────────────────────────────────────────────────
    # Remember who signed in and put their name in the welcome greeting.
    def _set_current_user(self, username):
        self.current_username = username.strip() or "User"
        shown_name = self.current_username
        if len(shown_name) > 15:
            shown_name = shown_name[:14].rstrip() + "…"
        self.welcome_label.configure(text=f"  Good to see you {shown_name}")

    # Try to sign someone in or make a new account using the name and
    # password they typed. Show a friendly message if something is wrong.
    def _authenticate(self, action):
        username = self.login_user.get()
        password = self.login_pass.get()
        if not username.strip() or not password:
            self.login_err.configure(text="Username and password are required")
            return
        self.login_err.configure(text="Authenticating...")

        def background():
            response = request({"action": action, "username": username, "password": password})
            def on_result():
                if "user_id" in response:
                    self.login_err.configure(text="")
                    self.user_id = response["user_id"]
                    self._set_current_user(username)
                    self._show_main_view()
                    self._run_in_background(self._fetch_agents_from_server)
                else:
                    self.login_err.configure(text=response.get("error", "Failed"))
            self.after(0, on_result)
        self._run_in_background(background)

    # ── Agent actions ─────────────────────────────────────────────────────────
    # Politely tell the chosen helper to leave, and forget about it.
    def _disconnect_current_agent(self):
        if not self.selected_agent: return
        agent_id = self.selected_agent
        self._write_system_log(f"Disconnecting {agent_id}")
        self._run_in_background(
            lambda: request({"action": "disconnect_agent", "agent_id": agent_id}))
        self.agent_dropdown.set("No agents")
        self._on_agent_selection_changed(None)
        self._run_in_background(self._fetch_agents_from_server)

    # Ask the chosen helper to forget what it has been doing and start fresh.
    def _reset_current_agent(self):
        if not self.selected_agent: return
        agent_id = self.selected_agent
        self._write_system_log(f"Clearing {agent_id}")
        self._run_in_background(
            lambda: request({"action": "clear_agent", "agent_id": agent_id}))
        for widget in self.log_scroll.winfo_children(): widget.destroy()
        self._set_action_display("—")
        self._set_reasoning_text("—")
        self._set_task_text("No active task")

    # Someone picked a different helper from the drop-down. Clear the
    # old picture and notes, and start showing what the new helper is doing.
    def _on_agent_selection_changed(self, chosen_value):
        previous_agent = self.selected_agent
        if chosen_value and chosen_value != "No agents":
            self.selected_agent = chosen_value.split("  ")[0]
        else:
            self.selected_agent = None

        if self._current_screenshot:
            self._current_screenshot = None
            self._show_waiting_screenshot()

        for widget in self.log_scroll.winfo_children(): widget.destroy()
        self._set_action_display("—")
        self._set_reasoning_text("—")
        self._prev_step_hash = self._prev_log_hash = None
        self._prev_status_message = self._prev_agent_status = ""
        next_status = self._status_for_agent(self.selected_agent) if self.selected_agent else ""
        self._prev_agent_status = next_status
        self._set_send_button_working(next_status == "working")
        self._sync_agent_summary()
        self._refresh_view_for_current_agent()

        if self.selected_agent and self.selected_agent != previous_agent:
            self._write_system_log(f"Switched to {self.selected_agent}")
            self.logs_agent_lbl.configure(text=self.selected_agent)

    # Change the words shown in the "Current Task" ribbon.
    def _set_task_text(self, text):
        self._full_task_text = text or "No active task"
        self._apply_task_display()

    # Flip between showing a short version and the full version of the
    # current task line when someone clicks "Show more" or "Show less".
    def _toggle_task_expand(self):
        self._is_task_expanded = not self._is_task_expanded
        self._apply_task_display()

    # Actually draw the current task line, either short or full,
    # and grow the ribbon taller if there is more to show.
    def _apply_task_display(self):
        TRUNC = 90
        min_h = self._strip_min_h
        text  = self._full_task_text or "No active task"
        long  = len(text) > TRUNC

        wrap_px = self._strip_w - 220
        if self._is_task_expanded and long:
            self.strip_task_label.configure(text=text, wraplength=wrap_px)
            self.strip_toggle.configure(text="Show less")
            approx_lines = max(1, -(-len(text) // 80))
            target_h = min_h + (approx_lines - 1) * 20
        else:
            disp = text if not long else text[:TRUNC - 1].rstrip() + "…"
            self.strip_task_label.configure(text=disp, wraplength=0)
            self.strip_toggle.configure(text="Show more")
            target_h = min_h

        # Grow the strip. Prompt stays at the same spot so the bottom of the
        # strip tucks behind it (classic "peeking capsule" look).
        self.prompt_strip.configure(height=target_h)
        composer_h = target_h - self._strip_overlap + self._prompt_h
        self._composer.configure(height=composer_h)
        self.prompt_box.place_configure(y=target_h - self._strip_overlap)

        if long:
            self.strip_toggle.place(relx=1.0, y=self._strip_visible_cy,
                                    x=-16, anchor="e")
        else:
            self.strip_toggle.place_forget()

    # ── Connection status ─────────────────────────────────────────────────────
    # Notice when the link to the server comes back or goes away,
    # and write a short note about it in the activity list.
    def _update_connection_status(self, is_connected):
        if is_connected == self._is_server_connected: return
        self._is_server_connected = is_connected
        if is_connected:
            self._write_system_log("Server connection restored", GREEN)
        else:
            self._write_system_log("Lost server connection", RED)

    # Add a short note from the app into the activity list.
    def _write_system_log(self, message, color=None):
        self.after(0, lambda: append_system_log(self.log_scroll, message, color))

    # ── Server data ───────────────────────────────────────────────────────────
    # Ask the server for the list of helpers and update the drop-down.
    def _fetch_agents_from_server(self):
        response = request({"action": "get_agents"})
        self.after(0, lambda: self._update_connection_status("agents" in response))

        hidden_states = {"disconnected", "disconnect_requested"}
        agents = [
            agent for agent in response.get("agents", [])
            if agent.get("agent_state", "idle") not in hidden_states
        ]
        agent_ids = [a["id"] for a in agents]
        if agent_ids == self._known_agent_ids and agents == self._known_agents: return
        self._known_agent_ids = agent_ids
        self._known_agents    = agents

        def update_dropdown():
            display_values = [
                f"{a['id']}  [{AGENT_STATUS_LABELS.get(a.get('agent_state','idle'), a.get('agent_state','idle'))}]"
                for a in agents
            ] or ["No agents"]
            self.agent_dropdown.configure(values=display_values)
            if not self.selected_agent and agent_ids:
                self.agent_dropdown.set(display_values[0])
                self._on_agent_selection_changed(display_values[0])
            elif self.selected_agent:
                if self.selected_agent in agent_ids:
                    self.agent_dropdown.set(display_values[agent_ids.index(self.selected_agent)])
                    agent_state = agents[agent_ids.index(self.selected_agent)].get("agent_state", "idle")
                    self._prev_agent_status = agent_state
                    self._set_send_button_working(agent_state == "working")
                    self._sync_agent_summary()
                else:
                    fallback = display_values[0] if agent_ids else "No agents"
                    self.agent_dropdown.set(fallback)
                    self._on_agent_selection_changed(fallback if agent_ids else None)
        self.after(0, update_dropdown)

    # Look up whether a helper is busy, resting, or stopping.
    def _status_for_agent(self, agent_id):
        for agent in self._known_agents:
            if agent.get("id") == agent_id:
                return agent.get("agent_state", "idle")
        return ""

    # Remember whether the helper is busy and update the round button
    # so it shows either a play arrow or a stop square.
    def _set_send_button_working(self, is_working):
        self.is_agent_working = is_working
        self._sync_send_button_visual()

    # Paint the round button in the right color and shape based on
    # whether the helper is busy and whether the mouse is over it.
    def _sync_send_button_visual(self, hover=False):
        if not hasattr(self, "send_stop_button"):
            return
        has_text = hasattr(self, "task_input") and bool(self.task_input.get().strip())
        stop_mode = self.is_agent_working and not has_text
        fill = "#ff777a" if stop_mode and hover else \
               "#ff6467" if stop_mode else \
               "#e8e8e8" if hover else "#f5f5f5"
        self.send_stop_button.itemconfig(self.send_stop_bg, fill=fill)
        if stop_mode:
            self.send_stop_button.itemconfig(self.send_stop_play, state="hidden")
            self.send_stop_button.itemconfig(self.send_stop_square, state="normal",
                                              fill="#1f1f1f")
        else:
            self.send_stop_button.itemconfig(self.send_stop_square, state="hidden")
            self.send_stop_button.itemconfig(
                self.send_stop_play, state="normal", fill="#1f1f1f")

    # Clear an entry and immediately restore its focus + text color, so
    # CustomTkinter's placeholder state machine doesn't paint the next
    # typed characters in the grey placeholder color.
    def _clear_entry(self, entry, text_color=TEXT):
        try:
            entry.delete(0, "end")
            entry.focus_set()
            entry.configure(text_color=text_color)
        except Exception:
            pass

    # Briefly flash the prompt box's border to signal a problem, without
    # ever mutating the entry's placeholder_text (which is what causes the
    # grey-text-after-stop bug).
    def _flash_prompt_warning(self, message):
        self._write_system_log(message, AMBER)
        try:
            self.prompt_box.configure(border_color=AMBER)
            self.after(900, lambda: self.prompt_box.configure(border_color="#343434"))
        except Exception:
            pass

    # If there is something typed, send it as a new request to the helper.
    # If the box is empty and the helper is busy, ask the helper to stop.
    def _send_task_or_stop_agent(self):
        if self.is_task_send_pending:
            return
        task_text = self.task_input.get().strip()
        if not self.selected_agent:
            self._flash_prompt_warning("Select an agent first")
            return
        if not task_text:
            if self.is_agent_working:
                agent_id = self.selected_agent
                self._write_system_log(f"Stop requested for {agent_id}", AMBER)
                self._run_in_background(lambda: request(
                    {"action": "stop_agent", "agent_id": agent_id}))
                return
            self._flash_prompt_warning("Describe a command first")
            return

        agent_id = self.selected_agent
        self.is_task_send_pending = True
        self._clear_entry(self.task_input)
        self._sync_send_button_visual()

        def background():
            response = request({"action": "send_task", "task": task_text,
                                "agent_id": agent_id, "user_id": self.user_id})

            def on_done():
                self.is_task_send_pending = False
                if response.get("success"):
                    self._write_system_log(
                        response.get("message", f"Task queued for {agent_id}"), CYAN)
                else:
                    self._write_system_log(
                        response.get("error") or "Failed to send task", RED)
                # Keep focus + normal color so the next typing is white.
                self.task_input.focus_set()
                self.task_input.configure(text_color=TEXT)
                self._sync_send_button_visual()

            self.after(0, on_done)
        self._run_in_background(background)

    # ── Button visibility ─────────────────────────────────────────────────────
    # Hide the "Disconnect" button.
    def _hide_disconnect_button(self):
        if self._is_disconnect_visible:
            self.disconnect_button.pack_forget()
            self._is_disconnect_visible = False

    # Show the "Disconnect" button.
    def _show_disconnect_button(self):
        if not self._is_disconnect_visible:
            self.disconnect_button.pack(side="right", padx=(12, 0))
            self._is_disconnect_visible = True

    # Hide the "Clear Memory" button.
    def _hide_reset_button(self):
        if self._is_reset_visible:
            self.reset_memory_button.pack_forget()
            self._is_reset_visible = False

    # Show the "Clear Memory" button.
    def _show_reset_button(self):
        if not self._is_reset_visible:
            self.reset_memory_button.pack(side="right", padx=(12, 0))
            self._is_reset_visible = True

    # ── View refresh ──────────────────────────────────────────────────────────
    # Keep the little name and status tag in step with the chosen helper.
    def _sync_agent_summary(self):
        if not self.selected_agent:
            self.selected_agent_title.configure(text="No agent selected")
            self.status_chip.configure(fg_color="#333333")
            self.status_chip_label.configure(text="offline", text_color="#a3a3a3")
            return
        status = AGENT_STATUS_LABELS.get(self._prev_agent_status, self._prev_agent_status or "idle")
        color  = "#35d399" if status == "idle" else "#ff6467" if status == "working" else "#f4f4f4"
        fill   = "#253b33" if status == "idle" else "#42282b" if status == "working" else "#333333"
        self.selected_agent_title.configure(text=self.selected_agent)
        self.status_chip.configure(fg_color=fill)
        self.status_chip_label.configure(text=status, text_color=color)

    # Decide what the main area should look like: a friendly empty message,
    # a "waiting" message, or the helper's screen picture.
    def _refresh_view_for_current_agent(self):
        if not self.selected_agent:
            self._show_waiting_screenshot()
            self.screen_meta.configure(text="No active screen")
            self.empty_state_title.configure(text="No agent connected")
            self.empty_state_subtitle.configure(text="Connect an agent to see its screen here")
            self.empty_state_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.empty_state_overlay.lift()
            self._hide_disconnect_button(); self._hide_reset_button()
        elif not self._current_screenshot:
            self._show_waiting_screenshot()
            self.screen_meta.configure(text=f"{self.selected_agent} / waiting for screen")
            self.empty_state_title.configure(text="Waiting for screen")
            self.empty_state_subtitle.configure(text="The agent hasn't sent a screenshot yet")
            self.empty_state_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.empty_state_overlay.lift()
            self._show_disconnect_button(); self._show_reset_button()
        else:
            status = AGENT_STATUS_LABELS.get(self._prev_agent_status, self._prev_agent_status or "idle")
            self.screen_meta.configure(text=f"{self.selected_agent} / {status}")
            self.empty_state_overlay.place_forget()
            self._show_disconnect_button(); self._show_reset_button()
        self._sync_agent_summary()

    # ── Polling loops ─────────────────────────────────────────────────────────
    # Begin the three little timers that keep checking the server for
    # the list of helpers, the helper's current status, and the screen picture.
    def _start_polling_loops(self):
        self._poll_agents_loop()
        self._poll_agent_status_loop()
        self._poll_screenshot_loop()

    # Every few seconds, ask the server who is around.
    def _poll_agents_loop(self):
        if self.user_id:
            self._run_in_background(self._fetch_agents_from_server)
        self.after(3000, self._poll_agents_loop)

    # Every short while, ask the helper for a fresh picture of its screen,
    # shrink it to fit, give it rounded corners, and show it.
    def _poll_screenshot_loop(self):
        if self.selected_agent:
            agent_id = self.selected_agent
            def background(max_w, max_h):
                raw_data = request({"action": "get_screen",
                                    "agent_id": agent_id}).get("data")
                if not raw_data:
                    self.after(0, self._refresh_view_for_current_agent); return

                screenshot = Image.open(BytesIO(base64.b64decode(raw_data))).convert("RGBA")
                scale = min(max_w / screenshot.width, max_h / screenshot.height) * SCREEN_PREVIEW_SCALE
                fw, fh = int(screenshot.width * scale), int(screenshot.height * scale)
                screenshot = screenshot.resize((fw, fh), Image.LANCZOS)
                mask = Image.new("L", (fw, fh), 0)
                ImageDraw.Draw(mask).rounded_rectangle([(0,0),(fw-1,fh-1)], radius=22, fill=255)
                screenshot.putalpha(mask)

                def apply():
                    if agent_id != self.selected_agent:
                        return
                    new_image = ctk.CTkImage(
                        light_image=screenshot, dark_image=screenshot, size=(fw, fh))
                    # Keep a few recent images alive so their underlying Tk
                    # pyimages don't get garbage-collected while still in use
                    # by the inner tk.Label.
                    if not hasattr(self, "_screenshot_refs"):
                        self._screenshot_refs = []
                    self._screenshot_refs.append(new_image)
                    if len(self._screenshot_refs) > 4:
                        self._screenshot_refs = self._screenshot_refs[-4:]
                    self._current_screenshot = new_image
                    try:
                        self.screenshot_label.configure(text="", image=new_image)
                    except Exception:
                        return
                    self._refresh_view_for_current_agent()
                self.after(0, apply)

            self.update_idletasks()
            reserve_w = getattr(self, "_screen_right_reserve", 360)
            self._run_in_background(background,
                max(self.content_area.winfo_width() - reserve_w, 280),
                max(self.content_area.winfo_height() - 40, 220))
        else:
            self.after(0, self._refresh_view_for_current_agent)
        self.after(800 if self.is_agent_working else 2000, self._poll_screenshot_loop)

    # Every half second or so, ask the helper what step it is on and what
    # it is thinking, then update the side cards and activity list.
    def _poll_agent_status_loop(self):
        if self.selected_agent:
            def background(agent_id):
                data           = request({"action": "get_agent", "agent_id": agent_id})
                if agent_id != self.selected_agent:
                    return
                step_data      = data.get("step") or {}
                action_text    = (step_data.get("action") or "").strip()
                reasoning_text = (step_data.get("reasoning") or "").strip()
                coordinate     = step_data.get("coordinate") or step_data.get("Coordinate")
                value          = step_data.get("value") or step_data.get("Value")
                cmd_output     = step_data.get("cmd_output")
                current_task   = data.get("current_task") or data.get("task") or ""
                agent_status   = data.get("agent_state", "")
                status_message = data.get("agent_activity_message", "") or ""

                if agent_status != self._prev_agent_status:
                    old = self._prev_agent_status
                    self._prev_agent_status = agent_status
                    self.after(0, self._sync_agent_summary)
                    if old:
                        self._write_system_log(
                            f"Agent status: {AGENT_STATUS_LABELS.get(agent_status, agent_status)}")

                if status_message and status_message != self._prev_status_message:
                    self._prev_status_message = status_message
                    self._write_system_log(status_message)

                is_working = agent_status == "working"
                if is_working != self.is_agent_working:
                    def update_btn(w=is_working):
                        self._set_send_button_working(w)
                    self.after(0, update_btn)

                fp = hashlib.md5(
                    f"{action_text}|{reasoning_text}|{coordinate}|{value}|{cmd_output}|"
                    f"{current_task}|{agent_status}".encode()
                ).hexdigest()
                if fp != self._prev_step_hash:
                    self._prev_step_hash = fp
                    end_coord = step_data.get("end_coordinate") or step_data.get("EndCoordinate")
                    action_key = action_text.lower()
                    is_done = (action_key == "done" or
                               (agent_status == "idle" and action_key in ("none", "")))
                    if is_done:
                        primary, meta, command, icon = "Done!", "", "", self.action_done_icon
                    else:
                        primary, meta, command = self._format_action(
                            action_text, coordinate, value, end_coord)
                        icon = None
                    disp_reasoning = reasoning_text or "—"
                    disp_task = current_task or "No active task"

                    self.after(0, lambda a=primary, m=meta, c=command, i=icon:
                               self._set_action_display(a, m, c, i))
                    self.after(0, lambda r=disp_reasoning: self._set_reasoning_text(r))
                    self.after(0, lambda t=disp_task: self._set_task_text(t))

                lf = hashlib.md5(f"{action_text}|{reasoning_text}".encode()).hexdigest()
                if lf != self._prev_log_hash and (action_text or reasoning_text
                                                   or step_data.get("cmd_output")):
                    self._prev_log_hash = lf
                    self.after(0, lambda: append_log_entry(self.log_scroll, step_data.copy()))

            self._run_in_background(background, self.selected_agent)
        self.after(500, self._poll_agent_status_loop)

    # ── Floating panels ───────────────────────────────────────────────────────
    # Hide the floating Activity pop-up.
    def _hide_logs_panel(self):
        self.logs_panel.place_forget(); self.logs_panel.lower()
        self.is_logs_panel_open = False

    # Hide the floating Tasks pop-up.
    def _hide_tasks_panel(self):
        self.tasks_panel.place_forget(); self.tasks_panel.lower()
        self.is_tasks_panel_open = False

    # Float a pop-up just above a chosen button so it points at it.
    def _place_panel_above(self, panel, anchor_widget):
        self.update_idletasks()
        panel.update_idletasks()
        try:
            panel_w = int(panel.cget("width"))
        except Exception:
            panel_w = panel.winfo_reqwidth()
        x = anchor_widget.winfo_rootx() - self.winfo_rootx()
        y = anchor_widget.winfo_rooty() - self.winfo_rooty() - 10
        x = max(18, min(x, self.winfo_width() - panel_w - 18))
        y = max(82, y)
        panel.place(x=x, y=y, anchor="sw")

    # Open the Activity pop-up if it is closed, or close it if it is open.
    def _toggle_logs_panel(self):
        if self.is_logs_panel_open: self._hide_logs_panel()
        else:
            self._place_panel_above(self.logs_panel, self.logs_toggle_button)
            self.logs_panel.lift(); self.is_logs_panel_open = True

    # Open the Tasks pop-up if it is closed, or close it if it is open.
    def _toggle_tasks_panel(self):
        if self.is_tasks_panel_open: self._hide_tasks_panel()
        else:
            self._refresh_task_list()
            self._place_panel_above(self.tasks_panel, self.tasks_toggle_button)
            self.tasks_panel.lift(); self.is_tasks_panel_open = True

    # Ask the server for the latest list of requests this person has saved,
    # then draw them in the Tasks pop-up.
    def _refresh_task_list(self):
        for w in self.tasks_scroll.winfo_children(): w.destroy()
        ctk.CTkLabel(self.tasks_scroll, text="Loading…", text_color=DIM,
                     font=(FONT, 12)).pack(pady=(40, 0))
        def background():
            tasks = request({"action": "get_tasks",
                             "user_id": self.user_id}).get("tasks", [])
            self.after(0, lambda: self._render_task_rows(tasks))
        self._run_in_background(background)

    # Draw each saved request as its own little card with a delete button.
    def _render_task_rows(self, tasks):
        for w in self.tasks_scroll.winfo_children(): w.destroy()
        self.tasks_cnt.configure(text=f"({len(tasks)})" if tasks else "")
        if not tasks:
            ctk.CTkLabel(self.tasks_scroll, text="No tasks yet",
                         text_color=DIM, font=(FONT, 12)).pack(pady=(40, 0))
            return
        for task in tasks:
            row = ctk.CTkFrame(self.tasks_scroll, fg_color="#282828", corner_radius=12,
                               border_width=0)
            row.pack(fill="x", padx=2, pady=(0, 8))
            content = ctk.CTkFrame(row, fg_color="transparent")
            content.pack(fill="x", padx=12, pady=11)
            full = task.get("task", "")
            txt = ctk.CTkFrame(content, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(txt, text=full, anchor="w", justify="left",
                         font=(FONT, 12, "bold"), text_color=TEXT,
                         wraplength=220).pack(fill="x", anchor="w")
            meta = f"{task.get('status','queued')} / {task.get('assigned_agent') or 'unassigned'}"
            ctk.CTkLabel(txt, text=meta, anchor="w", font=(FONT_MONO, 9),
                         text_color=MUTED).pack(fill="x", anchor="w", pady=(4, 0))
            task_id = task["id"]
            def on_delete(tid=task_id):
                self._run_in_background(lambda: [
                    request({"action": "delete_task", "task_id": tid, "user_id": self.user_id}),
                    self.after(0, self._refresh_task_list)])
            ctk.CTkButton(content, text="✕", width=20, height=20, corner_radius=5,
                fg_color="transparent", hover_color=ELEVATED,
                text_color=MUTED, font=(FONT, 10), command=on_delete).pack(side="right")


if __name__ == "__main__":
    HarmonyApp().mainloop()
