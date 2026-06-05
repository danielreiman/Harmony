import customtkinter as ctk

from theme import FONT, FONT_MONO


"""Right-side cards for current action and reasoning."""


class SidePanelMixin:
    """Builds and updates the action/reasoning cards."""

    def _build_floating_state_panel(self):
        """Create the right-side status card stack."""
        # Local sizing constants keep this panel self-contained.
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

        # Done icon is hidden until the agent finishes.
        self.action_done_icon = self._resource_image("confeti_emoji.png", (38, 38))
        self.action_icon_label = ctk.CTkLabel(self.action_row, text="",
            image=self.action_done_icon, width=38, height=38)

        # Main action text and optional metadata sit on one row.
        self.action_textbox = ctk.CTkLabel(self.action_row, text="—",
            font=HEADLINE_FONT, text_color=PANEL_BG, anchor="w",
            justify="left", wraplength=WRAP)
        self.action_textbox.pack(side="left")
        self.action_meta_label = ctk.CTkLabel(self.action_row, text="",
            font=HEADLINE_FONT, text_color="#8a8a90", anchor="w",
            justify="left")
        self.action_meta_label.pack(side="left", padx=(10, 0))

        # Command block appears only for run_command steps.
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

    _ACTION_LABELS = {
        # Display names for raw tool names coming from the server.
        "left_click": "Left Click", "click": "Left Click",
        "double_click": "Double Click", "right_click": "Right Click",
        "drag": "Drag", "type": "Type", "press_key": "Press",
        "hotkey": "Hotkey", "scroll_up": "Scroll Up", "scroll_down": "Scroll Down",
        "run_command": "Run Command", "wait": "Wait",
    }

    # Turn a raw step from the helper into a short, friendly sentence
    # that someone can read at a glance.
    def _format_coord(self, coordinate):
        """Format screen coordinates for display."""
        try:
            x, y = coordinate[0], coordinate[1]
            return f"({int(x)}, {int(y)})"
        except Exception:
            return str(coordinate)

    def _format_key_value(self, value):
        """Format keyboard values for display."""
        if isinstance(value, (list, tuple)):
            return " + ".join(str(v).title() for v in value)
        return str(value).title()

    def _format_action(self, action, coordinate, value, end_coord=None):
        """Convert raw action data into display text."""
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
        """Update the read-only reasoning text box."""
        self.reasoning_textbox.configure(state="normal")
        self.reasoning_textbox.delete("1.0", "end")
        self.reasoning_textbox.insert("1.0", text)
        self.reasoning_textbox.configure(state="disabled")

    def _set_action_display(self, action, meta="", command="", icon=None):
        """Update the visible current-action card."""
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
