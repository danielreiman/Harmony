import customtkinter as ctk

from theme import AMBER, CYAN, ELEVATED, FONT, TASK_PLACEHOLDER


"""Bottom prompt composer, toolbar, and agent action controls."""


class BottomBarMixin:
    """Builds the bottom command area."""

    def _build_bottom_bar(self):
        """Create the toolbar, task strip, prompt field, and send button."""
        # Fixed-width wrapper keeps the composer centered.
        wrap = ctk.CTkFrame(self.main_frame, fg_color="transparent", width=884)
        wrap.place(relx=0.5, rely=1.0, y=-20, anchor="s")

        # Footer toolbar
        footer = ctk.CTkFrame(wrap, fg_color="transparent", width=884, height=28)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        def toolbar_item(parent, icon, label, command, width):
            """Build one hoverable toolbar item."""
            item = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=8,
                                width=width, height=28, cursor="hand2")
            item.pack_propagate(False)
            icon_lbl = ctk.CTkLabel(item, text=icon, font=(FONT, 14, "bold"), text_color="#b5b5b5")
            icon_lbl.pack(side="left", padx=(9, 7))
            text_lbl = ctk.CTkLabel(item, text=label, font=(FONT, 14, "bold"), text_color="#d8d8d8")
            text_lbl.pack(side="left")

            def enter(_e):
                item.configure(fg_color="#242424")

            def leave(_e):
                item.configure(fg_color="transparent")

            for w in (item, icon_lbl, text_lbl):
                w.bind("<Button-1>", lambda _e, fn=command: fn())
                w.bind("<Enter>", enter)
                w.bind("<Leave>", leave)
            return item

        # Left toolbar opens activity and task panels.
        toolbar = ctk.CTkFrame(footer, fg_color="transparent")
        toolbar.pack(side="left")
        self.logs_toggle_button = toolbar_item(toolbar, "⌘", "Activity",
                                               self._toggle_logs_panel, 104)
        self.logs_toggle_button.pack(side="left", padx=(0, 10))
        self.tasks_toggle_button = toolbar_item(toolbar, "☑", "Tasks",
                                                self._toggle_tasks_panel, 82)
        self.tasks_toggle_button.pack(side="left", padx=(0, 10))

        # Right toolbar holds actions for the selected agent.
        self.footer_actions = ctk.CTkFrame(footer, fg_color="transparent")
        self.footer_actions.pack(side="right")
        self.disconnect_button = ctk.CTkButton(self.footer_actions, text="Disconnect",
            width=88, height=24, corner_radius=6, fg_color="transparent",
            hover_color=ELEVATED, text_color=AMBER, font=(FONT, 12), border_width=0,
            command=self._disconnect_current_agent)
        self.disconnect_button.pack(side="right", padx=(12, 0))
        self._is_disconnect_visible = True
        self._hide_disconnect_button()
        self.reset_memory_button = ctk.CTkButton(self.footer_actions, text="Clear Memory",
            width=112, height=24, corner_radius=6, fg_color="transparent",
            hover_color=ELEVATED, text_color=CYAN, font=(FONT, 12), border_width=0,
            command=self._reset_current_agent)
        self.reset_memory_button.pack(side="right", padx=(12, 0))
        self._is_reset_visible = True
        self._hide_reset_button()

        STRIP_H, PROMPT_H = 36, 114
        COMPOSER_H = STRIP_H + PROMPT_H

        # Composer contains the current-task strip and prompt box.
        composer = ctk.CTkFrame(wrap, fg_color="transparent",
                                width=884, height=COMPOSER_H)
        composer.pack(fill="x", side="bottom", pady=(0, 12))
        composer.pack_propagate(False)

        self.prompt_strip = ctk.CTkFrame(composer, fg_color="#242424",
            corner_radius=18, border_width=1, border_color="#343434",
            width=800, height=STRIP_H)
        self.prompt_strip.place(relx=0.5, y=0, anchor="n")
        self.prompt_strip.pack_propagate(False)

        strip_inner = ctk.CTkFrame(self.prompt_strip, fg_color="transparent")
        strip_inner.place(relx=0, rely=0.5, x=20, anchor="w", relwidth=0.9)

        # Current task display is trimmed to keep the layout fixed.
        ctk.CTkLabel(strip_inner, text="Current Task:", font=(FONT, 13, "bold"),
                     text_color="#8a8a8a", anchor="w").pack(side="left", padx=(0, 10))
        self.strip_task_label = ctk.CTkLabel(strip_inner, text="No active task",
            font=(FONT, 13, "bold"), text_color="#e8e8e8",
            anchor="w", justify="left")
        self.strip_task_label.pack(side="left", fill="x", expand=True)

        # Prompt box is where the user types new requests.
        self.prompt_box = ctk.CTkFrame(composer, fg_color="#282828",
            corner_radius=18, border_width=1, border_color="#343434",
            height=PROMPT_H)
        self.prompt_box.place(x=0, y=STRIP_H, relwidth=1)
        self.prompt_box.pack_propagate(False)
        self.prompt_box.lift()

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

        # Agent dropdown chooses where the next task goes.
        self.agent_dropdown = ctk.CTkOptionMenu(right, values=["No agents"],
            width=142, height=30, corner_radius=9, fg_color="#282828",
            text_color="#a8a8a8", button_color="#282828", button_hover_color="#343434",
            dropdown_fg_color="#2b2b2b", dropdown_text_color="#f4f4f4",
            font=(FONT, 12, "bold"), command=self._on_agent_selection_changed)
        self.agent_dropdown.pack(side="left", padx=(0, 12))
        self.agent_dropdown.set("No agents")

        # Standard button switches between Send and Stop modes.
        self.send_stop_button = ctk.CTkButton(right, text="Send",
            width=72, height=34, corner_radius=10,
            fg_color="#f5f5f5", hover_color="#e8e8e8",
            text_color="#1f1f1f", font=(FONT, 12, "bold"),
            command=self._send_task_or_stop_agent)
        self.send_stop_button.pack(side="left")

        self._set_task_text("No active task")
