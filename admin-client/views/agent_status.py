from theme import AGENT_STATUS_LABELS


"""Agent visibility and selected-agent state display helpers."""


class AgentStatusMixin:
    """Controls agent status labels and action button visibility."""

    def _hide_disconnect_button(self):
        """Hide the disconnect action when no agent is selected."""
        if self._is_disconnect_visible:
            self.disconnect_button.pack_forget()
            self._is_disconnect_visible = False

    # Show the "Disconnect" button.
    def _show_disconnect_button(self):
        """Show the disconnect action for a selected agent."""
        if not self._is_disconnect_visible:
            self.disconnect_button.pack(side="right", padx=(12, 0))
            self._is_disconnect_visible = True

    # Hide the "Clear Memory" button.
    def _hide_reset_button(self):
        """Hide the memory reset action when no agent is selected."""
        if self._is_reset_visible:
            self.reset_memory_button.pack_forget()
            self._is_reset_visible = False

    # Show the "Clear Memory" button.
    def _show_reset_button(self):
        """Show the memory reset action for a selected agent."""
        if not self._is_reset_visible:
            self.reset_memory_button.pack(side="right", padx=(12, 0))
            self._is_reset_visible = True

    # Decide what the main area should look like: a friendly empty message,
    # a "waiting" message, or the helper's screen picture.
    def _refresh_view_for_current_agent(self):
        """Refresh empty/waiting/screenshot UI for the selected agent."""
        if not self.selected_agent:
            self._show_waiting_screenshot()
            self.screen_meta.configure(text="No active screen")
            self.empty_state_title.configure(text="No agent connected")
            self.empty_state_subtitle.configure(text="Connect an agent to see its screen here")
            self.empty_state_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.empty_state_overlay.lift()
            self._hide_disconnect_button()
            self._hide_reset_button()
        elif not self._current_screenshot:
            self._show_waiting_screenshot()
            self.screen_meta.configure(text=f"{self.selected_agent} / waiting for screen")
            self.empty_state_title.configure(text="Waiting for screen")
            self.empty_state_subtitle.configure(text="The agent hasn't sent a screenshot yet")
            self.empty_state_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.empty_state_overlay.lift()
            self._show_disconnect_button()
            self._show_reset_button()
        else:
            status = AGENT_STATUS_LABELS.get(self._prev_agent_status, self._prev_agent_status or "idle")
            self.screen_meta.configure(text=f"{self.selected_agent} / {status}")
            self.empty_state_overlay.place_forget()
            self._show_disconnect_button()
            self._show_reset_button()
