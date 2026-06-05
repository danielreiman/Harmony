"""Open, close, and position the floating task/activity panels."""


class FloatingPanelsMixin:
    """Controls the dashboard's floating panels."""

    def _hide_logs_panel(self):
        """Hide the Activity panel."""
        self.logs_panel.place_forget()
        self.logs_panel.lower()
        self.is_logs_panel_open = False

    # Hide the floating Tasks pop-up.
    def _hide_tasks_panel(self):
        """Hide the Tasks panel."""
        self.tasks_panel.place_forget()
        self.tasks_panel.lower()
        self.is_tasks_panel_open = False

    # Float a pop-up just above a chosen button so it points at it.
    def _place_panel_above(self, panel, anchor_widget):
        """Place a floating panel above its toolbar trigger."""
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
        """Toggle the Activity panel."""
        if self.is_logs_panel_open:
            self._hide_logs_panel()
        else:
            self._place_panel_above(self.logs_panel, self.logs_toggle_button)
            self.logs_panel.lift()
            self.is_logs_panel_open = True

    # Open the Tasks pop-up if it is closed, or close it if it is open.
    def _toggle_tasks_panel(self):
        """Toggle the Tasks panel."""
        if self.is_tasks_panel_open:
            self._hide_tasks_panel()
        else:
            self._refresh_task_list()
            self._place_panel_above(self.tasks_panel, self.tasks_toggle_button)
            self.tasks_panel.lift()
            self.is_tasks_panel_open = True
