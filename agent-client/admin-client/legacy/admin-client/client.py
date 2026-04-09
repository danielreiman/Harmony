import sys
import threading
import base64
import hashlib
from io import BytesIO

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from bridge import request
from ui_functions import build_overlay_section, create_log_window, append_log_entry

ctk.set_appearance_mode("dark")

# Palette & Constants
COLOR_BG = "#1C1C1C"
COLOR_FIELD = "#2A2A2A"
COLOR_MUTED = "#888888"
COLOR_DANGER = "#dc2626"
TASK_STATUS_DOTS = {"running": "#3b82f6", "completed": "#22c55e", "failed": "#ef4444", "queued": "#d1d5db"}

class HarmonyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Harmony")
        self.configure(fg_color=COLOR_BG)
        self.resizable(True, True)
        
        self.user_id = None
        self.selected_agent = None
        self.agent_is_running = False
        self.tasks_panel_visible = False
        self._agents_list = []
        self._screenshot_ref = None
        self._last_step_hash = None
        self._last_log_hash = None

        self._setup_window()
        self._build_ui()
        self._start_polling()

    def _setup_window(self):
        try:
            icon = ImageTk.PhotoImage(Image.open("icon.png"))
            self.wm_iconphoto(False, icon)
        except Exception:
            pass

        if sys.platform == "darwin":
            self.after(0, lambda: self.attributes("-fullscreen", True))
        elif sys.platform == "win32":
            self.after(0, lambda: self.state("zoomed"))
        else:
            self.after(0, lambda: self.attributes("-zoomed", True))

    def _thread(self, target, *args):
        threading.Thread(target=target, args=args, daemon=True).start()

    def _show_frame(self, frame):
        for f in [self.login_view_frame, self.main_view_frame]:
            try: f.pack_forget()
            except Exception: pass
        frame.pack(fill="both", expand=True)

    # UI Construct
    def _build_ui(self):
        self._build_login_view()
        self._build_main_view()
        self._show_frame(self.login_view_frame)

    def _build_login_view(self):
        self.login_view_frame = ctk.CTkFrame(self, fg_color=COLOR_BG)
        center_f = ctk.CTkFrame(self.login_view_frame, fg_color="transparent")
        center_f.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(center_f, text="Log in to your Account", font=("Arial", 28, "bold"), text_color="#ffffff").pack(pady=(14, 0))
        ctk.CTkLabel(center_f, text="Welcome back - enter your credentials to continue", font=("Arial", 12), text_color="#888888").pack(pady=(4, 0))

        fields_f = ctk.CTkFrame(center_f, fg_color="transparent")
        fields_f.pack(pady=(32, 0))

        style = dict(width=380, height=50, corner_radius=25, border_width=0, fg_color=COLOR_FIELD, text_color="#ffffff", placeholder_text_color="#666666", font=("Arial", 15))
        
        ctk.CTkLabel(fields_f, text="Username", font=("Arial", 11), text_color="#888888").pack(anchor="w", pady=(0, 5))
        self.login_user_entry = ctk.CTkEntry(fields_f, placeholder_text="Enter your username", **style)
        self.login_user_entry.pack()

        ctk.CTkLabel(fields_f, text="Password", font=("Arial", 11), text_color="#888888").pack(anchor="w", pady=(18, 5))
        self.login_pass_entry = ctk.CTkEntry(fields_f, placeholder_text="Enter your password", show="*", **style)
        self.login_pass_entry.pack()

        actions_f = ctk.CTkFrame(center_f, fg_color="transparent")
        actions_f.pack(pady=(28, 0), fill="x", padx=30)
        
        self.login_error_label = ctk.CTkLabel(actions_f, text="", text_color=COLOR_DANGER, font=("Arial", 12))
        self.login_error_label.pack(pady=(0, 8))

        btn = ctk.CTkButton(actions_f, text="Sign In", height=52, corner_radius=26, fg_color="#ffffff", hover_color="#e0e0e0", text_color=COLOR_BG, font=("Arial", 15, "bold"), command=lambda: self._authenticate("auth_login"))
        btn.pack(fill="x")

        signup_f = ctk.CTkFrame(actions_f, fg_color="transparent")
        signup_f.pack(pady=(18, 0))
        ctk.CTkLabel(signup_f, text="Don't have an account?", font=("Arial", 12), text_color="#888888").pack(side="left")
        su_lbl = ctk.CTkLabel(signup_f, text="  Sign up", font=("Arial", 12, "underline"), text_color="#ffffff", cursor="hand2")
        su_lbl.pack(side="left")
        su_lbl.bind("<Button-1>", lambda e: self._authenticate("auth_signup"))

        for w in (self.login_view_frame, self.login_user_entry, self.login_pass_entry):
            w.bind("<Return>", lambda e: self._authenticate("auth_login"))

    def _build_main_view(self):
        self.main_view_frame = ctk.CTkFrame(self, fg_color=COLOR_BG)

        # Top Bar
        top_f = ctk.CTkFrame(self.main_view_frame, fg_color=COLOR_BG, height=72)
        top_f.pack(fill="x", padx=60, pady=(10, 0))
        top_f.pack_propagate(False)
        ctk.CTkLabel(top_f, text="Harmony", font=("Arial", 16, "bold"), text_color="#ffffff").place(relx=0.5, rely=0.5, anchor="center")

        btns_f = ctk.CTkFrame(top_f, fg_color="transparent")
        btns_f.place(relx=1.0, rely=0.5, anchor="e")

        ctk.CTkButton(btns_f, text="Log out", width=90, height=36, corner_radius=32, fg_color=COLOR_FIELD, hover_color="#363636", text_color="#888888", font=("Arial", 13, "bold"), border_width=1, border_color="#888888", command=lambda: self._show_frame(self.login_view_frame)).pack(side="left", padx=(0, 8))
        
        self.disconnect_btn = ctk.CTkButton(btns_f, text="Disconnect Agent", width=140, height=36, corner_radius=32, fg_color="#3a2f15", hover_color="#4a3d1f", text_color="#ffb86b", font=("Arial", 13, "bold"), border_width=1, border_color="#ffb86b", command=self._disconnect_agent)
        # Disconnect button is hidden initially
        
        ctk.CTkButton(btns_f, text="Shutdown", width=100, height=36, corner_radius=32, fg_color="#3a1515", hover_color="#4a1f1f", text_color="#ff6b6b", font=("Arial", 13, "bold"), border_width=1, border_color="#ff6b6b", command=lambda: [request({"action": "stop_server"}), self.quit()]).pack(side="left", padx=(8, 0))

        # Content Area
        screen_f = ctk.CTkFrame(self.main_view_frame, fg_color=COLOR_BG)
        screen_f.pack(fill="both", expand=True, padx=60, pady=(6, 20))

        self.center_screen_f = ctk.CTkFrame(screen_f, fg_color=COLOR_BG)
        self.center_screen_f.place(relx=0.5, rely=0.5, anchor="center")

        left_side = ctk.CTkFrame(self.center_screen_f, fg_color=COLOR_BG)
        left_side.pack(side="left", fill="y")
        self.screenshot_lbl = ctk.CTkLabel(left_side, text="", text_color=COLOR_MUTED, font=("Arial", 13))
        self.screenshot_lbl.pack(expand=True)

        self.right_side = ctk.CTkFrame(self.center_screen_f, fg_color=COLOR_BG, width=320)
        self.right_side.pack(side="left", fill="both", expand=True, padx=(16, 0))

        self.panels_inner_f = ctk.CTkFrame(self.right_side, fg_color=COLOR_BG, width=320)
        self.panels_inner_f.pack(fill="both", expand=True)

        task_card = ctk.CTkFrame(self.panels_inner_f, fg_color=COLOR_FIELD, corner_radius=32)
        task_card.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(task_card, text="CURRENT TASK", font=("Arial", 10, "bold"), text_color="#666666").pack(padx=16, pady=(14, 3), anchor="w")
        self.current_task_lbl = ctk.CTkLabel(task_card, text="—", font=("Arial", 13), text_color="#ffffff", anchor="w", justify="left", wraplength=280)
        self.current_task_lbl.pack(padx=16, pady=(0, 14), anchor="w")

        status_card = ctk.CTkFrame(self.panels_inner_f, fg_color=COLOR_FIELD, corner_radius=32)
        status_card.pack(fill="x", pady=(0, 10))
        self.reasoning_lbl = build_overlay_section(status_card, "REASONING", 13)
        ctk.CTkFrame(status_card, fg_color="#3a3a3a", height=1).pack(fill="x", padx=16)
        self.action_lbl = build_overlay_section(status_card, "ACTION", 14, bold=True, pad_top=12, pad_bottom=16)

        self.log_card, self.log_scroll = create_log_window(self.panels_inner_f, COLOR_BG, COLOR_FIELD)
        self.log_card.pack(fill="both", expand=True)

        # Empty State
        self.empty_state_f = ctk.CTkFrame(screen_f, fg_color=COLOR_BG)
        inner_empty = ctk.CTkFrame(self.empty_state_f, fg_color="transparent")
        inner_empty.place(relx=0.5, rely=0.45, anchor="center")
        ctk.CTkLabel(inner_empty, text="🖥", font=("Arial", 64)).pack(pady=(0, 12))
        self.empty_title = ctk.CTkLabel(inner_empty, text="No agent connected", font=("Arial", 22, "bold"), text_color="#ffffff")
        self.empty_title.pack(pady=(0, 6))
        self.empty_sub = ctk.CTkLabel(inner_empty, text="Connect an agent to see its live screen here", font=("Arial", 14), text_color="#555555")
        self.empty_sub.pack()

        # Bottom Bar
        bot_f = ctk.CTkFrame(self.main_view_frame, fg_color=COLOR_BG, height=62)
        bot_f.pack(fill="x", padx=60, pady=(0, 44))
        bot_f.pack_propagate(False)

        self.agent_dropdown = ctk.CTkOptionMenu(bot_f, values=["No agents"], width=200, height=62, corner_radius=32, fg_color=COLOR_FIELD, text_color="#ffffff", button_color=COLOR_FIELD, button_hover_color="#363636", dropdown_fg_color=COLOR_FIELD, font=("Arial", 14), command=self._on_agent_change)
        self.agent_dropdown.place(relx=0.0, rely=0.5, anchor="w")
        self.agent_dropdown.set("No agents")

        inp_container = ctk.CTkFrame(bot_f, fg_color=COLOR_BG, width=460 + 8 + 62 + 24 + 62 + 24, height=62)
        inp_container.place(relx=0.5, rely=0.5, anchor="center")
        inp_container.pack_propagate(False)

        pill_f = ctk.CTkFrame(inp_container, fg_color=COLOR_FIELD, corner_radius=32, width=460, height=62)
        pill_f.place(x=0, y=0)
        pill_f.pack_propagate(False)
        
        self.task_entry = ctk.CTkEntry(pill_f, placeholder_text="Give the agent a task...", height=58, width=420, corner_radius=0, border_width=0, fg_color="transparent", text_color="#ffffff", font=("Arial", 15))
        self.task_entry.place(x=24, y=2)
        self.task_entry.bind("<Return>", lambda e: self._send_or_stop())

        self.action_btn = ctk.CTkButton(inp_container, text="▶", width=62, height=62, corner_radius=32, fg_color="#ffffff", hover_color="#e0e0e0", text_color="#1C1C1C", font=("Arial", 18), command=self._send_or_stop)
        self.action_btn.place(x=468, y=0)

        self.reset_btn = ctk.CTkButton(inp_container, text="↻", width=62, height=62, corner_radius=32, fg_color="#ef4444", hover_color="#dc2626", text_color="#ffffff", font=("Arial", 22, "bold"), command=self._reset_agent)
        self.reset_btn.place(x=468 + 62 + 24, y=0)

        tasks_f = ctk.CTkFrame(bot_f, fg_color="transparent")
        tasks_f.place(relx=1.0, rely=0.5, anchor="e")
        ctk.CTkButton(tasks_f, text="Tasks", width=100, height=62, corner_radius=32, fg_color=COLOR_FIELD, hover_color="#363636", text_color="#ffffff", font=("Arial", 14), command=self._toggle_tasks_panel).pack(side="left")

        # Tasks Panel
        self._build_tasks_panel()

    def _build_tasks_panel(self):
        self.tasks_panel = ctk.CTkFrame(self.main_view_frame, fg_color=COLOR_FIELD, corner_radius=32, width=360, height=480, bg_color=COLOR_BG)
        self.tasks_panel.pack_propagate(False)

        head = ctk.CTkFrame(self.tasks_panel, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(head, text="Tasks", font=("Arial", 16, "bold"), text_color="#ffffff").pack(side="left")
        self.tasks_cnt_lbl = ctk.CTkLabel(head, text="", font=("Arial", 12), text_color="#aaaaaa")
        self.tasks_cnt_lbl.pack(side="left", padx=(8, 0))
        ctk.CTkButton(head, text="✕", width=28, height=28, corner_radius=14, fg_color="#3a3a3a", text_color="#888888", command=self._toggle_tasks_panel).pack(side="right")

        self.tasks_list_scroll = ctk.CTkScrollableFrame(self.tasks_panel, fg_color="transparent")
        self.tasks_list_scroll.pack(fill="both", expand=True, padx=12, pady=(12, 12))
        self.tasks_empty_lbl = ctk.CTkLabel(self.tasks_list_scroll, text="No tasks yet", text_color=COLOR_MUTED)

    # Workflows
    def _authenticate(self, action):
        u, p = self.login_user_entry.get(), self.login_pass_entry.get()
        self.login_error_label.configure(text="Authenticating...")
        
        def _bg():
            res = request({"action": action, "username": u, "password": p})
            def _cb():
                if "user_id" in res:
                    self.login_error_label.configure(text="")
                    self.user_id = res["user_id"]
                    self._show_frame(self.main_view_frame)
                    self._thread(self._fetch_agents)
                else:
                    self.login_error_label.configure(text=res.get("error", "Failed"))
            self.after(0, _cb)
        self._thread(_bg)

    def _disconnect_agent(self):
        if self.selected_agent:
            ag = self.selected_agent
            self._thread(lambda: request({"action": "disconnect_agent", "agent_id": ag}))
            self.agent_dropdown.set("No agents")
            self._on_agent_change(None)

    def _reset_agent(self):
        if self.selected_agent:
            ag = self.selected_agent
            self._thread(lambda: request({"action": "clear_agent", "agent_id": ag}))
            for w in self.log_scroll.winfo_children(): w.destroy()
            self.action_lbl.configure(text="—")
            self.reasoning_lbl.configure(text="—")
            self.current_task_lbl.configure(text="—")

    def _on_agent_change(self, choice):
        if choice and choice in self._agents_list:
            self.selected_agent = choice
        else:
            self.selected_agent = None

        self._screenshot_ref = None
        self.screenshot_lbl.configure(image="", text="")
        
        # Clear log panel on switch
        for w in self.log_scroll.winfo_children(): w.destroy()
        self._last_step_hash = None
        self._last_log_hash = None
        
        self._update_ui_state()

    def _fetch_agents(self):
        new_ids = [a["id"] for a in request({"action": "get_agents"}).get("agents", [])]
        if new_ids == self._agents_list: return
        self._agents_list = new_ids
        
        def _cb():
            self.agent_dropdown.configure(values=self._agents_list or ["No agents"])
            if not self.selected_agent and self._agents_list:
                self.agent_dropdown.set(self._agents_list[0])
                self._on_agent_change(self._agents_list[0])
            elif self.selected_agent and self.selected_agent not in self._agents_list:
                self.agent_dropdown.set(self._agents_list[0] if self._agents_list else "No agents")
                self._on_agent_change(self._agents_list[0] if self._agents_list else None)
        self.after(0, _cb)

    def _send_or_stop(self):
        if self.agent_is_running:
            if self.selected_agent:
                self._thread(lambda: request({"action": "stop_agent", "agent_id": self.selected_agent}))
        else:
            t = self.task_entry.get().strip()
            if not t or not self.selected_agent: return
            self.task_entry.delete(0, "end")
            self.task_entry.configure(placeholder_text="Sending task...")
            
            def _bg():
                request({"action": "send_task", "task": t, "agent_id": self.selected_agent, "user_id": self.user_id})
                self.after(0, lambda: self.task_entry.configure(placeholder_text="Task sent!"))
                self.after(1200, lambda: self.task_entry.configure(placeholder_text="Give the agent a task..."))
            self._thread(_bg)

    def _update_ui_state(self):
        btn_active = self.selected_agent is not None

        if not self.selected_agent:
            self.empty_title.configure(text="No agent connected")
            self.empty_sub.configure(text="Connect an agent to see its live screen here")
            self.empty_state_f.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
            self.empty_state_f.lift()
            self.center_screen_f.place_forget()
            self.disconnect_btn.pack_forget()
        elif not self._screenshot_ref:
            self.empty_title.configure(text="Waiting for screen")
            self.empty_sub.configure(text="The agent hasn't sent a screenshot yet")
            self.empty_state_f.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
            self.empty_state_f.lift()
            self.center_screen_f.place_forget()
            self.disconnect_btn.pack(side="left", padx=(0, 8))
        else:
            self.empty_state_f.place_forget()
            self.center_screen_f.place(relx=0.5, rely=0.5, anchor="center")
            self.disconnect_btn.pack(side="left", padx=(0, 8))
            
            self.right_side.update_idletasks()
            self.panels_inner_f.place(x=0, y=0, relwidth=1.0)

    # Background Pollers
    def _poll_snapshot(self):
        if self.selected_agent:
            def _bg(w, h):
                data = request({"action": "get_screen", "agent_id": self.selected_agent}).get("data")
                if not data:
                    self.after(0, self._update_ui_state)
                    return
                img = Image.open(BytesIO(base64.b64decode(data))).convert("RGBA")
                scale = min(w / img.width, h / img.height) * 0.95
                fw, fh = int(img.width * scale), int(img.height * scale)
                img = img.resize((fw, fh), Image.LANCZOS)
                mask = Image.new("L", (fw, fh), 0)
                ImageDraw.Draw(mask).rounded_rectangle([(0, 0), (fw - 1, fh - 1)], radius=32, fill=255)
                img.putalpha(mask)
                def _cb():
                    self._screenshot_ref = ctk.CTkImage(light_image=img, dark_image=img, size=(fw, fh))
                    self.screenshot_lbl.configure(image=self._screenshot_ref)
                    self._update_ui_state()
                self.after(0, _cb)

            self.update_idletasks()
            max_h = max(self.main_view_frame.winfo_height() - 200, 200)
            max_w = max(self.main_view_frame.winfo_width() - 440, 200)
            self._thread(_bg, max_w, max_h)
        else:
            self.after(0, self._update_ui_state)
        
        self.after(1000, self._poll_snapshot)

    def _poll_status(self):
        if self.selected_agent:
            def _bg(ag):
                data = request({"action": "get_agent", "agent_id": ag})
                step = data.get("step") or {}
                a, r = step.get("action", "").strip(), step.get("reasoning", "").strip()
                tt = data.get("current_task") or data.get("task") or ""
                st = data.get("status", "")
                
                rn = st == "working"
                if rn != self.agent_is_running:
                    self.agent_is_running = rn
                    
                    def _update_btn_ui(is_running=rn):
                        if is_running:
                            self.action_btn.configure(text="||", fg_color="#eab308", hover_color="#ca8a04", text_color="#1C1C1C")
                        else:
                            self.action_btn.configure(text="▶", fg_color="#ffffff", hover_color="#e0e0e0", text_color="#1C1C1C")
                    self.after(0, _update_btn_ui)

                fp = hashlib.md5(f"{a}|{r}|{tt}|{st}".encode()).hexdigest()
                log_fp = hashlib.md5(f"{a}|{r}".encode()).hexdigest()

                if fp != self._last_step_hash:
                    self._last_step_hash = fp
                    at = a if a and a.lower() != "none" else "—"
                    rt = r or "—"
                    td = tt[:120] + "…" if len(tt) > 120 else tt or "—"
                    
                    self.after(0, lambda: self.action_lbl.configure(text=at))
                    self.after(0, lambda: self.reasoning_lbl.configure(text=rt))
                    self.after(0, lambda: self.current_task_lbl.configure(text=td))

                if log_fp != self._last_log_hash and (a or r or step.get("cmd_output")):
                    self._last_log_hash = log_fp
                    log_data = step.copy() # pass full step data over
                    self.after(0, lambda: append_log_entry(self.log_scroll, log_data))
            self._thread(_bg, self.selected_agent)
        
        self.after(500, self._poll_status)

    def _poll_agents(self):
        if self.user_id: self._thread(self._fetch_agents)
        self.after(3000, self._poll_agents)

    def _start_polling(self):
        self._poll_agents()
        self._poll_status()
        self._poll_snapshot()

    # Tasks Overlay
    def _toggle_tasks_panel(self):
        if self.tasks_panel_visible:
            self.tasks_panel.place_forget()
            self.tasks_panel_visible = False
        else:
            self._fetch_tasks()
            self.tasks_panel.place(relx=1.0, rely=1.0, x=-60, y=-116, anchor="se")
            self.tasks_panel.lift()
            self.tasks_panel_visible = True

    def _fetch_tasks(self):
        for w in self.tasks_list_scroll.winfo_children(): w.destroy()
        self.tasks_empty_lbl.pack(pady=(40, 0))
        self.tasks_empty_lbl.configure(text="Loading tasks...")
        def _bg():
            tasks = request({"action": "get_tasks", "user_id": self.user_id}).get("tasks", [])
            self.after(0, lambda: self._render_tasks(tasks))
        self._thread(_bg)

    def _render_tasks(self, tasks):
        self.tasks_cnt_lbl.configure(text=f"({len(tasks)})" if tasks else "")
        if not tasks:
            self.tasks_empty_lbl.configure(text="No tasks yet")
            self.tasks_empty_lbl.pack(pady=(40, 0))
            return
        self.tasks_empty_lbl.pack_forget()

        for task in tasks:
            rf = ctk.CTkFrame(self.tasks_list_scroll, fg_color="transparent")
            rf.pack(fill="x", pady=(0, 2))
            lf = ctk.CTkFrame(rf, fg_color="transparent")
            lf.pack(fill="x", padx=4, pady=6)
            
            c = TASK_STATUS_DOTS.get(task.get("status", "queued"), "#d1d5db")
            ctk.CTkLabel(lf, text="●", font=("Arial", 8), text_color=c, width=16).pack(side="left", padx=(0, 6))
            
            raw = task.get("task", "")
            d = raw[:42] + "…" if len(raw) > 42 else raw
            tf = ctk.CTkFrame(lf, fg_color="transparent")
            tf.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(tf, text=d, anchor="w", font=("Arial", 13), text_color="#ffffff").pack(side="left")
            ctk.CTkLabel(tf, text=f"  ({task.get('assigned_agent') or 'unassigned'})", anchor="w", font=("Arial", 11), text_color="#aaaaaa").pack(side="left")
            
            tid = task["id"]
            def _del(t_id=tid):
                def _d(): 
                    request({"action": "delete_task", "task_id": t_id, "user_id": self.user_id})
                    self.after(0, self._fetch_tasks)
                self._thread(_d)
                
            ctk.CTkButton(lf, text="✕", width=20, height=20, corner_radius=10, fg_color="transparent", hover_color="#3a3a3a", text_color="#555555", font=("Arial", 10), command=_del).pack(side="right")
            ctk.CTkFrame(rf, fg_color="#3a3a3a", height=1).pack(fill="x", padx=26)

if __name__ == "__main__":
    app = HarmonyApp()
    app.mainloop()
