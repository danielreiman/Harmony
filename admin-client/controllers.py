import gateway_requests
from theme import AGENT_STATUS_LABELS, AMBER, CYAN, GREEN, RED, TEXT
from widgets import append_system_log


"""Controller logic for authentication, agent actions, and task submission."""


class ControllerMixin:
    """Owns user-triggered behavior that is not pure layout."""

    def _set_current_user(self, username):
        """Store and display the signed-in username."""
        self.current_username = username.strip() or "User"
        shown_name = self.current_username
        if len(shown_name) > 15:
            shown_name = shown_name[:14].rstrip() + "…"
        self.welcome_label.configure(text=f"  Good to see you {shown_name}")

    # Try to sign someone in or make a new account using the name and
    # password they typed. Show a friendly message if something is wrong.
    def _authenticate(self, action):
        """Authenticate using either login or signup mode."""
        username = self.login_user.get()
        password = self.login_pass.get()
        if not username.strip() or not password:
            self.login_err.configure(text="Username and password are required")
            return
        self.login_err.configure(text="Authenticating...")

        def background():
            """Run the network request off the UI thread."""
            response = gateway_requests.authenticate(action, username, password)

            def on_result():
                """Apply the auth result on the UI thread."""
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

    # Politely tell the chosen helper to leave, and forget about it.
    def _disconnect_current_agent(self):
        """Disconnect the currently selected agent."""
        if not self.selected_agent:
            return

        agent_id = self.selected_agent
        self._write_system_log(f"Disconnecting {agent_id}")
        self._run_in_background(lambda: gateway_requests.disconnect_agent(agent_id))
        self.agent_dropdown.set("No agents")
        self._on_agent_selection_changed(None)
        self._run_in_background(self._fetch_agents_from_server)

    # Ask the chosen helper to forget what it has been doing and start fresh.
    def _reset_current_agent(self):
        """Clear the selected agent's memory and local activity view."""
        if not self.selected_agent:
            return

        agent_id = self.selected_agent
        self._write_system_log(f"Clearing {agent_id}")
        self._run_in_background(lambda: gateway_requests.clear_agent(agent_id))
        for widget in self.log_scroll.winfo_children():
            widget.destroy()
        self._set_action_display("—")
        self._set_reasoning_text("—")
        self._set_task_text("No active task")

    # Someone picked a different helper from the drop-down. Clear the
    # old picture and notes, and start showing what the new helper is doing.
    def _on_agent_selection_changed(self, chosen_value):
        """Update local state when the selected agent changes."""
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
        self._refresh_view_for_current_agent()

        if self.selected_agent and self.selected_agent != previous_agent:
            self._write_system_log(f"Switched to {self.selected_agent}")
            self.logs_agent_lbl.configure(text=self.selected_agent)

    # Change the words shown in the "Current Task" ribbon.
    def _set_task_text(self, text):
        """Update the current-task strip text."""
        task_text = text or "No active task"
        if len(task_text) > 90:
            task_text = task_text[:89].rstrip() + "…"
        self.strip_task_label.configure(text=task_text)

    # Notice when the link to the server comes back or goes away,
    # and write a short note about it in the activity list.
    def _update_connection_status(self, is_connected):
        """Log connection status changes only when they change."""
        if is_connected == self._is_server_connected:
            return

        self._is_server_connected = is_connected
        if is_connected:
            self._write_system_log("Server connection restored", GREEN)
        else:
            self._write_system_log("Lost server connection", RED)

    # Add a short note from the app into the activity list.
    def _write_system_log(self, message, color=None):
        """Append a system message safely on the UI thread."""
        self.after(0, lambda: append_system_log(self.log_scroll, message, color))

    # Ask the server for the list of helpers and update the drop-down.
    def _fetch_agents_from_server(self):
        """Fetch agents and update the dropdown if anything changed."""
        response = gateway_requests.get_agents()
        self.after(0, lambda: self._update_connection_status("agents" in response))

        hidden_states = {"disconnected", "disconnect_requested"}
        agents = [
            agent for agent in response.get("agents", [])
            if agent.get("agent_state", "idle") not in hidden_states
        ]
        agent_ids = [a["id"] for a in agents]
        if agent_ids == self._known_agent_ids and agents == self._known_agents:
            return

        self._known_agent_ids = agent_ids
        self._known_agents    = agents

        def update_dropdown():
            """Apply agent dropdown changes on the UI thread."""
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
                else:
                    fallback = display_values[0] if agent_ids else "No agents"
                    self.agent_dropdown.set(fallback)
                    self._on_agent_selection_changed(fallback if agent_ids else None)
        self.after(0, update_dropdown)

    # Look up whether a helper is busy, resting, or stopping.
    def _status_for_agent(self, agent_id):
        """Return the cached state for one agent."""
        for agent in self._known_agents:
            if agent.get("id") == agent_id:
                return agent.get("agent_state", "idle")
        return ""

    # Remember whether the helper is busy and update the send/stop button.
    def _set_send_button_working(self, is_working):
        """Remember if the selected agent is currently working."""
        self.is_agent_working = is_working
        self._sync_send_button_visual()

    # Paint the button based on whether it will send a task or stop an agent.
    def _sync_send_button_visual(self):
        """Switch the button between Send and Stop modes."""
        if not hasattr(self, "send_stop_button"):
            return

        has_text = hasattr(self, "task_input") and bool(self.task_input.get().strip())
        stop_mode = self.is_agent_working and not has_text

        if stop_mode:
            self.send_stop_button.configure(
                text="Stop",
                fg_color="#ff6467",
                hover_color="#ff777a",
                text_color="#1f1f1f")
        else:
            self.send_stop_button.configure(
                text="Send",
                fg_color="#f5f5f5",
                hover_color="#e8e8e8",
                text_color="#1f1f1f")

    # Clear an entry and immediately restore its focus + text color, so
    # CustomTkinter's placeholder state machine doesn't paint the next
    # typed characters in the grey placeholder color.
    def _clear_entry(self, entry, text_color=TEXT):
        """Clear a text entry while preserving normal input styling."""
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
        """Show a non-blocking warning around the prompt box."""
        self._write_system_log(message, AMBER)
        try:
            self.prompt_box.configure(border_color=AMBER)
            self.after(900, lambda: self.prompt_box.configure(border_color="#343434"))
        except Exception:
            pass

    # If there is something typed, send it as a new request to the helper.
    # If the box is empty and the helper is busy, ask the helper to stop.
    def _send_task_or_stop_agent(self):
        """Send typed text as a task, or stop the agent when empty."""
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
                self._run_in_background(lambda: gateway_requests.stop_agent(agent_id))
                return
            self._flash_prompt_warning("Describe a command first")
            return

        agent_id = self.selected_agent
        self.is_task_send_pending = True
        self._clear_entry(self.task_input)
        self._sync_send_button_visual()

        def background():
            """Queue the task without blocking the UI."""
            response = gateway_requests.send_task(task_text, agent_id, self.user_id)

            def on_done():
                """Report task queue result on the UI thread."""
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
