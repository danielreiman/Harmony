import sys
import threading
import base64
import hashlib
from io import BytesIO

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from bridge import request
from ui import (
    BG, SURFACE, ELEVATED, BORDER, TEXT, DIM, MUTED, ACCENT, GREEN, RED, AMBER, CYAN,
    FONT, FONT_MONO, CORNER_RADIUS, AGENT_STATUS_LABELS,
    card, ghost_btn,
    build_login, build_tasks_panel, build_logs_panel, build_overlay_section,
    append_log_entry, append_system_log,
)

ctk.set_appearance_mode("light")


class HarmonyApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Harmony")
        self.configure(fg_color=BG)
        self.resizable(True, True)

        self.user_id              = None
        self.selected_agent       = None
        self.is_agent_working     = False
        self.is_tasks_panel_open  = False
        self.is_logs_panel_open   = False

        self._known_agent_ids     = []
        self._known_agents        = []
        self._current_screenshot  = None
        self._prev_step_hash      = None
        self._prev_log_hash       = None
        self._prev_plan_text      = ""
        self._prev_status_message = ""
        self._prev_agent_status   = ""
        self._is_server_connected = True

        self._setup_window()
        self._build_all_views()
        self._start_polling_loops()


    # ------------------------------------------------------------------
    #  Window
    # ------------------------------------------------------------------

    def _setup_window(self):
        try:
            app_icon = ImageTk.PhotoImage(Image.open("icon.png"))
            self.wm_iconphoto(False, app_icon)
        except Exception:
            pass
        if sys.platform == "darwin":
            self.overrideredirect(True)
            self.after(0, lambda: self.attributes("-fullscreen", True))
        elif sys.platform == "win32":
            self.after(0, lambda: self.state("zoomed"))
        else:
            self.after(0, lambda: self.attributes("-zoomed", True))

    def _run_in_background(self, fn, *args):
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _switch_to_frame(self, frame):
        for f in (self.login_frame, self.main_frame):
            try: f.pack_forget()
            except Exception: pass
        frame.pack(fill="both", expand=True)


    # ------------------------------------------------------------------
    #  Building the interface
    # ------------------------------------------------------------------

    def _build_all_views(self):
        self.login_frame = build_login(self)
        self._build_main_view()
        self._switch_to_frame(self.login_frame)

    def _build_main_view(self):
        self.main_frame = ctk.CTkFrame(self, fg_color=BG)
        self._build_top_bar()
        self._build_content_area()
        self._build_empty_state()
        self._build_bottom_bar()
        self.tasks_panel = build_tasks_panel(self)
        self.logs_panel  = build_logs_panel(self)

    def _build_top_bar(self):
        bar = ctk.CTkFrame(self.main_frame, fg_color=SURFACE, height=60,
                           corner_radius=0, border_width=1, border_color=BORDER)
        bar.pack(fill="x"); bar.pack_propagate(False)

        # Left: logo + connection status
        left = ctk.CTkFrame(bar, fg_color="transparent"); left.pack(side="left", padx=24)
        ctk.CTkLabel(left, text="Harmony", font=(FONT, 15, "bold"), text_color=TEXT).pack(side="left")
        ctk.CTkFrame(left, fg_color=BORDER, width=1, height=20).pack(side="left", padx=14)
        self.connection_dot = ctk.CTkFrame(left, fg_color=GREEN, width=7, height=7, corner_radius=4)
        self.connection_dot.pack(side="left")
        self.connection_label = ctk.CTkLabel(left, text="Connected", font=(FONT, 12), text_color=DIM)
        self.connection_label.pack(side="left", padx=(6, 0))

        # Right: action buttons
        btns = ctk.CTkFrame(bar, fg_color="transparent"); btns.pack(side="right", padx=24)
        S = 6
        ghost_btn(btns, "Log out", width=84,
                  command=lambda: self._switch_to_frame(self.login_frame)).pack(side="left", padx=(0, S))
        self.disconnect_button = ghost_btn(btns, "Disconnect", width=104,
            text_color=AMBER, border="#fef3c7", hover="#fffbeb",
            command=self._disconnect_current_agent)
        self.disconnect_button.pack(side="left", padx=(0, S))
        self._is_disconnect_visible = False; self._hide_disconnect_button()
        self.reset_memory_button = ghost_btn(btns, "Reset", width=76,
            text_color=CYAN, border="#cffafe", hover="#ecfeff",
            command=self._reset_current_agent)
        self.reset_memory_button.pack(side="left", padx=(0, S))
        self._is_reset_visible = False; self._hide_reset_button()
        ghost_btn(btns, "Shutdown", width=90, text_color=RED, border="#fee2e2", hover="#fff1f2",
                  command=lambda: [request({"action": "stop_server"}), self.quit()]).pack(side="left")

    def _build_content_area(self):
        self.content_area = ctk.CTkFrame(self.main_frame, fg_color=BG)
        self.content_area.pack(fill="both", expand=True, padx=28, pady=20)

        self.screenshot_and_panels = ctk.CTkFrame(self.content_area, fg_color=BG)
        self.screenshot_and_panels.place(relx=0.5, rely=0.5, anchor="center")

        shot_frame = ctk.CTkFrame(self.screenshot_and_panels, fg_color=BG)
        shot_frame.pack(side="left", fill="y")
        self.screenshot_label = ctk.CTkLabel(shot_frame, text="", text_color=DIM, font=(FONT, 13))
        self.screenshot_label.pack(expand=True)

        info_col = ctk.CTkFrame(self.screenshot_and_panels, fg_color=BG, width=300)
        info_col.pack(side="left", fill="both", expand=True, padx=(22, 0))
        self.info_cards_container = ctk.CTkFrame(info_col, fg_color=BG, width=300)
        self.info_cards_container.pack(fill="both", expand=True)

        # Task card
        tc = card(self.info_cards_container); tc.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(tc, text="TASK", font=(FONT_MONO, 8, "bold"),
                     text_color=MUTED, anchor="w").pack(padx=14, pady=(12, 0), anchor="w")
        self.current_task_label = ctk.CTkLabel(tc, text="No active task", font=(FONT, 13),
            text_color=TEXT, anchor="w", justify="left", wraplength=268)
        self.current_task_label.pack(padx=14, pady=(4, 14), anchor="w")

        # Plan card (hidden initially)
        self.plan_card = card(self.info_cards_container)
        ctk.CTkLabel(self.plan_card, text="PLAN", font=(FONT_MONO, 8, "bold"),
                     text_color=MUTED, anchor="w").pack(padx=14, pady=(12, 0), anchor="w")
        self.plan_text_label = ctk.CTkLabel(self.plan_card, text="", font=(FONT, 11),
            text_color=DIM, anchor="w", justify="left", wraplength=268)
        self.plan_text_label.pack(padx=14, pady=(4, 14), anchor="w")

        # Status card
        sc = card(self.info_cards_container); sc.pack(fill="x", pady=(0, 8))
        self.reasoning_textbox = build_overlay_section(sc, "REASONING", 11)
        ctk.CTkFrame(sc, fg_color=BORDER, height=1).pack(fill="x")
        self.action_textbox = build_overlay_section(sc, "ACTION", 12, bold=True, pad_top=10, pad_bottom=12)

    def _build_empty_state(self):
        self.empty_state_overlay = ctk.CTkFrame(self.content_area, fg_color=BG)
        ctr = ctk.CTkFrame(self.empty_state_overlay, fg_color="transparent")
        ctr.place(relx=0.5, rely=0.44, anchor="center")
        ctk.CTkFrame(ctr, fg_color="transparent", width=56, height=56,
                     corner_radius=28, border_width=2, border_color=BORDER).pack(pady=(0, 18))
        self.empty_state_title = ctk.CTkLabel(ctr, text="No agent connected",
                                              font=(FONT, 20, "bold"), text_color=TEXT)
        self.empty_state_title.pack(pady=(0, 6))
        self.empty_state_subtitle = ctk.CTkLabel(ctr, text="Connect an agent to see its screen here",
                                                 font=(FONT, 13), text_color=DIM)
        self.empty_state_subtitle.pack()

    def _build_bottom_bar(self):
        H = 46
        bar = ctk.CTkFrame(self.main_frame, fg_color=SURFACE, height=76,
                           corner_radius=0, border_width=1, border_color=BORDER)
        bar.pack(fill="x"); bar.pack_propagate(False)

        # Agent selector
        self.agent_dropdown = ctk.CTkOptionMenu(
            bar, values=["No agents"], width=196, height=H, corner_radius=CORNER_RADIUS,
            fg_color=BG, text_color=TEXT, button_color=BG, button_hover_color=ELEVATED,
            dropdown_fg_color=SURFACE, font=(FONT, 13),
            command=self._on_agent_selection_changed)
        self.agent_dropdown.place(relx=0.0, x=24, rely=0.5, anchor="w")
        self.agent_dropdown.set("No agents")

        # Task input
        PW = 460
        pill = ctk.CTkFrame(bar, fg_color=BG, corner_radius=CORNER_RADIUS,
                            border_width=1, border_color=BORDER, width=PW, height=H)
        pill.place(relx=0.5, rely=0.5, anchor="center"); pill.pack_propagate(False)
        self.task_input = ctk.CTkEntry(pill, placeholder_text="What should the agent do?",
            height=H - 4, width=PW - 48, corner_radius=0, border_width=0,
            fg_color="transparent", text_color=TEXT, placeholder_text_color=MUTED, font=(FONT, 14))
        self.task_input.place(x=16, rely=0.5, anchor="w")
        self.task_input.bind("<Return>", lambda e: self._send_task_or_stop_agent())
        self.send_stop_button = ctk.CTkButton(pill, text="▶", width=30, height=30,
            corner_radius=CORNER_RADIUS, fg_color=ACCENT, hover_color="#1d4ed8",
            text_color="#fff", font=(FONT, 13), command=self._send_task_or_stop_agent, border_width=0)
        self.send_stop_button.place(relx=1.0, x=-10, rely=0.5, anchor="e")

        # Panel toggles
        right = ctk.CTkFrame(bar, fg_color="transparent"); right.place(relx=1.0, x=-24, rely=0.5, anchor="e")
        _tb = dict(height=H, corner_radius=CORNER_RADIUS, fg_color=BG, hover_color=ELEVATED,
                   text_color=DIM, font=(FONT, 12), border_width=1, border_color=BORDER)
        self.logs_toggle_button = ctk.CTkButton(right, text="Logs", width=72,
            command=self._toggle_logs_panel, **_tb); self.logs_toggle_button.pack(side="left", padx=(0, 6))
        self.tasks_toggle_button = ctk.CTkButton(right, text="Tasks", width=72,
            command=self._toggle_tasks_panel, **_tb); self.tasks_toggle_button.pack(side="left")


    # ------------------------------------------------------------------
    #  Authentication
    # ------------------------------------------------------------------

    def _authenticate(self, action):
        username = self.login_user.get()
        password = self.login_pass.get()
        self.login_err.configure(text="Authenticating...")

        def background():
            response = request({"action": action, "username": username, "password": password})

            def on_result():
                if "user_id" in response:
                    self.login_err.configure(text="")
                    self.user_id = response["user_id"]
                    self._switch_to_frame(self.main_frame)
                    self._run_in_background(self._fetch_agents_from_server)
                else:
                    self.login_err.configure(text=response.get("error", "Failed"))

            self.after(0, on_result)

        self._run_in_background(background)


    # ------------------------------------------------------------------
    #  Agent actions
    # ------------------------------------------------------------------

    def _disconnect_current_agent(self):
        if not self.selected_agent:
            return
        agent_id = self.selected_agent
        self._write_system_log(f"Disconnecting {agent_id}")
        self._run_in_background(
            lambda: request({"action": "disconnect_agent", "agent_id": agent_id}))
        self.agent_dropdown.set("No agents")
        self._on_agent_selection_changed(None)

    def _reset_current_agent(self):
        if not self.selected_agent:
            return
        agent_id = self.selected_agent
        self._write_system_log(f"Clearing {agent_id}")
        self._run_in_background(
            lambda: request({"action": "clear_agent", "agent_id": agent_id}))
        for widget in self.log_scroll.winfo_children():
            widget.destroy()
        self.action_textbox.configure(text="—")
        self.reasoning_textbox.configure(text="—")
        self.current_task_label.configure(text="No active task")
        self._show_or_hide_plan("")

    def _on_agent_selection_changed(self, chosen_value):
        previous_agent = self.selected_agent
        if chosen_value and chosen_value != "No agents":
            self.selected_agent = chosen_value.split("  ")[0]
        else:
            self.selected_agent = None

        if self._current_screenshot:
            self._current_screenshot = None
            self.screenshot_label.configure(text=" ")
            blank = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            self.screenshot_label.configure(
                image=ctk.CTkImage(light_image=blank, dark_image=blank, size=(1, 1)))

        for widget in self.log_scroll.winfo_children():
            widget.destroy()

        self._prev_step_hash = self._prev_log_hash = None
        self._prev_plan_text = self._prev_status_message = self._prev_agent_status = ""
        self._show_or_hide_plan("")
        self._refresh_view_for_current_agent()

        if self.selected_agent and self.selected_agent != previous_agent:
            self._write_system_log(f"Switched to {self.selected_agent}")
            self.logs_agent_lbl.configure(text=self.selected_agent)

    def _show_or_hide_plan(self, plan_text):
        self.plan_text_label.configure(text=plan_text or "")
        if plan_text:
            self.plan_card.pack(fill="x", pady=(0, 8),
                after=self.info_cards_container.winfo_children()[0])
        else:
            self.plan_card.pack_forget()


    # ------------------------------------------------------------------
    #  Connection status
    # ------------------------------------------------------------------

    def _update_connection_status(self, is_connected):
        if is_connected == self._is_server_connected:
            return
        self._is_server_connected = is_connected
        if is_connected:
            self.connection_dot.configure(fg_color=GREEN)
            self.connection_label.configure(text="Connected")
            self._write_system_log("Server connection restored", GREEN)
        else:
            self.connection_dot.configure(fg_color=RED)
            self.connection_label.configure(text="Unreachable")
            self._write_system_log("Lost server connection", RED)

    def _write_system_log(self, message, color=None):
        self.after(0, lambda: append_system_log(self.log_scroll, message, color))


    # ------------------------------------------------------------------
    #  Server data
    # ------------------------------------------------------------------

    def _fetch_agents_from_server(self):
        response = request({"action": "get_agents"})
        self.after(0, lambda: self._update_connection_status("agents" in response))

        agents = response.get("agents", [])
        agent_ids = [a["id"] for a in agents]
        if agent_ids == self._known_agent_ids and agents == self._known_agents:
            return
        self._known_agent_ids = agent_ids
        self._known_agents = agents

        def update_dropdown():
            display_values = [
                f"{a['id']}  [{AGENT_STATUS_LABELS.get(a.get('status', 'idle'), a.get('status', 'idle'))}]"
                for a in agents
            ] or ["No agents"]
            self.agent_dropdown.configure(values=display_values)
            if not self.selected_agent and agent_ids:
                self.agent_dropdown.set(display_values[0])
                self._on_agent_selection_changed(display_values[0])
            elif self.selected_agent:
                if self.selected_agent in agent_ids:
                    self.agent_dropdown.set(display_values[agent_ids.index(self.selected_agent)])
                else:
                    fallback = display_values[0] if agent_ids else "No agents"
                    self.agent_dropdown.set(fallback)
                    self._on_agent_selection_changed(fallback if agent_ids else None)

        self.after(0, update_dropdown)

    def _send_task_or_stop_agent(self):
        if self.is_agent_working:
            if self.selected_agent:
                self._write_system_log(f"Stop requested for {self.selected_agent}", AMBER)
                self._run_in_background(lambda: request(
                    {"action": "stop_agent", "agent_id": self.selected_agent}))
            return

        task_text = self.task_input.get().strip()
        if not task_text or not self.selected_agent:
            return

        self.task_input.delete(0, "end")
        self.task_input.configure(placeholder_text="Sending...")
        self._show_or_hide_plan("")
        self._prev_plan_text = ""
        self._write_system_log(f"Task dispatched to {self.selected_agent}", CYAN)

        def background():
            request({"action": "send_task", "task": task_text,
                     "agent_id": self.selected_agent, "user_id": self.user_id})
            self.after(0, lambda: self.task_input.configure(placeholder_text="Sent!"))
            self.after(1200, lambda: self.task_input.configure(
                placeholder_text="What should the agent do?"))

        self._run_in_background(background)


    # ------------------------------------------------------------------
    #  Disconnect / Reset button visibility
    # ------------------------------------------------------------------

    def _hide_disconnect_button(self):
        if self._is_disconnect_visible:
            self.disconnect_button.configure(
                text_color=SURFACE, border_color=SURFACE, fg_color=SURFACE,
                hover_color=SURFACE, state="disabled")
            self._is_disconnect_visible = False

    def _show_disconnect_button(self):
        if not self._is_disconnect_visible:
            self.disconnect_button.configure(
                text_color=AMBER, border_color="#fef3c7",
                fg_color="transparent", hover_color="#fffbeb", state="normal")
            self._is_disconnect_visible = True

    def _hide_reset_button(self):
        if self._is_reset_visible:
            self.reset_memory_button.configure(
                text_color=SURFACE, border_color=SURFACE, fg_color=SURFACE,
                hover_color=SURFACE, state="disabled")
            self._is_reset_visible = False

    def _show_reset_button(self):
        if not self._is_reset_visible:
            self.reset_memory_button.configure(
                text_color=CYAN, border_color="#cffafe",
                fg_color="transparent", hover_color="#ecfeff", state="normal")
            self._is_reset_visible = True


    # ------------------------------------------------------------------
    #  View refresh
    # ------------------------------------------------------------------

    def _refresh_view_for_current_agent(self):
        if not self.selected_agent:
            self.empty_state_title.configure(text="No agent connected")
            self.empty_state_subtitle.configure(text="Connect an agent to see its screen here")
            self.empty_state_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.empty_state_overlay.lift()
            self.screenshot_and_panels.place_forget()
            self._hide_disconnect_button(); self._hide_reset_button()
        elif not self._current_screenshot:
            self.empty_state_title.configure(text="Waiting for screen")
            self.empty_state_subtitle.configure(text="The agent hasn't sent a screenshot yet")
            self.empty_state_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.empty_state_overlay.lift()
            self.screenshot_and_panels.place_forget()
            self._show_disconnect_button(); self._show_reset_button()
        else:
            self.empty_state_overlay.place_forget()
            self.screenshot_and_panels.place(relx=0.5, rely=0.5, anchor="center")
            self._show_disconnect_button(); self._show_reset_button()
            info_column = self.screenshot_and_panels.winfo_children()[1]
            info_column.update_idletasks()
            self.info_cards_container.place(x=0, y=0, relwidth=1.0)


    # ------------------------------------------------------------------
    #  Polling loops
    # ------------------------------------------------------------------

    def _start_polling_loops(self):
        self._poll_agents_loop()
        self._poll_agent_status_loop()
        self._poll_screenshot_loop()

    def _poll_agents_loop(self):
        if self.user_id:
            self._run_in_background(self._fetch_agents_from_server)
        self.after(3000, self._poll_agents_loop)

    def _poll_screenshot_loop(self):
        if self.selected_agent:
            def background(max_w, max_h):
                raw_data = request({"action": "get_screen",
                                    "agent_id": self.selected_agent}).get("data")
                if not raw_data:
                    self.after(0, self._refresh_view_for_current_agent); return

                screenshot = Image.open(BytesIO(base64.b64decode(raw_data))).convert("RGBA")
                scale = min(max_w / screenshot.width, max_h / screenshot.height) * 0.95
                fw, fh = int(screenshot.width * scale), int(screenshot.height * scale)
                screenshot = screenshot.resize((fw, fh), Image.LANCZOS)
                mask = Image.new("L", (fw, fh), 0)
                ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (fw - 1, fh - 1)], radius=12, fill=255)
                screenshot.putalpha(mask)

                def apply():
                    self._current_screenshot = ctk.CTkImage(
                        light_image=screenshot, dark_image=screenshot, size=(fw, fh))
                    self.screenshot_label.configure(image=self._current_screenshot)
                    self._refresh_view_for_current_agent()
                self.after(0, apply)

            self.update_idletasks()
            self._run_in_background(background,
                max(self.main_frame.winfo_width() - 440, 200),
                max(self.main_frame.winfo_height() - 180, 200))
        else:
            self.after(0, self._refresh_view_for_current_agent)

        self.after(800 if self.is_agent_working else 2000, self._poll_screenshot_loop)

    def _poll_agent_status_loop(self):
        if self.selected_agent:
            def background(agent_id):
                data           = request({"action": "get_agent", "agent_id": agent_id})
                step_data      = data.get("step") or {}
                action_text    = step_data.get("action", "").strip()
                reasoning_text = step_data.get("reasoning", "").strip()
                current_task   = data.get("current_task") or data.get("task") or ""
                agent_status   = data.get("status", "")
                plan_text      = step_data.get("plan", "")
                status_message = data.get("status_text", "") or ""

                if agent_status != self._prev_agent_status:
                    old = self._prev_agent_status
                    self._prev_agent_status = agent_status
                    if old:
                        self._write_system_log(f"Agent status: {AGENT_STATUS_LABELS.get(agent_status, agent_status)}")

                if status_message and status_message != self._prev_status_message:
                    self._prev_status_message = status_message
                    self._write_system_log(status_message)

                is_working = agent_status == "working"
                if is_working != self.is_agent_working:
                    self.is_agent_working = is_working
                    def update_btn(w=is_working):
                        self.send_stop_button.configure(
                            text="■" if w else "▶",
                            fg_color=RED if w else ACCENT,
                            hover_color="#dc2626" if w else "#1d4ed8")
                    self.after(0, update_btn)

                fp = hashlib.md5(f"{action_text}|{reasoning_text}|{current_task}|{agent_status}".encode()).hexdigest()
                if fp != self._prev_step_hash:
                    self._prev_step_hash = fp
                    disp_action    = action_text if action_text and action_text.lower() != "none" else "—"
                    disp_reasoning = reasoning_text or "—"
                    disp_task      = ((current_task[:110] + "...") if len(current_task) > 110 else current_task) or "No active task"
                    self.after(0, lambda: self.action_textbox.configure(text=disp_action))
                    self.after(0, lambda: self.reasoning_textbox.configure(text=disp_reasoning))
                    self.after(0, lambda: self.current_task_label.configure(text=disp_task))

                if plan_text and plan_text != self._prev_plan_text:
                    self._prev_plan_text = plan_text
                    self._write_system_log("Plan generated")
                    self.after(0, lambda p=plan_text: self._show_or_hide_plan(p))

                lf = hashlib.md5(f"{action_text}|{reasoning_text}".encode()).hexdigest()
                if lf != self._prev_log_hash and (action_text or reasoning_text or step_data.get("cmd_output")):
                    self._prev_log_hash = lf
                    self.after(0, lambda: append_log_entry(self.log_scroll, step_data.copy()))

            self._run_in_background(background, self.selected_agent)

        self.after(500, self._poll_agent_status_loop)


    # ------------------------------------------------------------------
    #  Floating panels
    # ------------------------------------------------------------------

    def _hide_logs_panel(self):
        self.logs_panel.place_forget(); self.logs_panel.lower()
        self.is_logs_panel_open = False

    def _hide_tasks_panel(self):
        self.tasks_panel.place_forget(); self.tasks_panel.lower()
        self.is_tasks_panel_open = False

    def _toggle_logs_panel(self):
        if self.is_logs_panel_open: self._hide_logs_panel()
        else:
            self.logs_panel.place(relx=1.0, rely=1.0, x=-28, y=-100, anchor="se")
            self.logs_panel.lift(); self.is_logs_panel_open = True

    def _toggle_tasks_panel(self):
        if self.is_tasks_panel_open: self._hide_tasks_panel()
        else:
            self._refresh_task_list()
            self.tasks_panel.place(relx=1.0, rely=1.0, x=-28, y=-100, anchor="se")
            self.tasks_panel.lift(); self.is_tasks_panel_open = True

    def _refresh_task_list(self):
        for w in self.tasks_scroll.winfo_children(): w.destroy()
        ctk.CTkLabel(self.tasks_scroll, text="Loading…", text_color=DIM,
                     font=(FONT, 12)).pack(pady=(40, 0))
        def background():
            tasks = request({"action": "get_tasks", "user_id": self.user_id}).get("tasks", [])
            self.after(0, lambda: self._render_task_rows(tasks))
        self._run_in_background(background)

    def _render_task_rows(self, tasks):
        for w in self.tasks_scroll.winfo_children(): w.destroy()
        self.tasks_cnt.configure(text=f"({len(tasks)})" if tasks else "")
        if not tasks:
            ctk.CTkLabel(self.tasks_scroll, text="No tasks yet",
                         text_color=DIM, font=(FONT, 12)).pack(pady=(40, 0))
            return
        for task in tasks:
            row = ctk.CTkFrame(self.tasks_scroll, fg_color="transparent"); row.pack(fill="x", pady=(0, 2))
            content = ctk.CTkFrame(row, fg_color="transparent"); content.pack(fill="x", padx=6, pady=7)
            full = task.get("task", "")
            short = full[:42] + "…" if len(full) > 42 else full
            txt = ctk.CTkFrame(content, fg_color="transparent"); txt.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(txt, text=short, anchor="w", font=(FONT, 12), text_color=TEXT).pack(side="left")
            ctk.CTkLabel(txt, text=f"  {task.get('assigned_agent') or 'unassigned'}",
                         anchor="w", font=(FONT, 10), text_color=MUTED).pack(side="left")
            task_id = task["id"]
            def on_delete(tid=task_id):
                self._run_in_background(lambda: [
                    request({"action": "delete_task", "task_id": tid, "user_id": self.user_id}),
                    self.after(0, self._refresh_task_list)])
            ctk.CTkButton(content, text="✕", width=20, height=20, corner_radius=5,
                fg_color="transparent", hover_color=ELEVATED,
                text_color=MUTED, font=(FONT, 10), command=on_delete).pack(side="right")
            ctk.CTkFrame(row, fg_color=BORDER, height=1).pack(fill="x", padx=16)


if __name__ == "__main__":
    HarmonyApp().mainloop()
