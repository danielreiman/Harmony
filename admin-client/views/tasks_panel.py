import customtkinter as ctk

import gateway_requests
from theme import DIM, FONT, FONT_MONO, MUTED, TEXT


"""Task history panel rendering."""


class TasksPanelMixin:
    """Builds and refreshes the floating task list."""

    def _refresh_task_list(self):
        """Fetch and redraw the current user's tasks."""
        # Clear old rows before showing the loading state.
        for widget in self.tasks_scroll.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.tasks_scroll, text="Loading…", text_color=DIM,
                     font=(FONT, 12)).pack(pady=(40, 0))

        def background():
            tasks = gateway_requests.get_tasks(self.user_id).get("tasks", [])
            self.after(0, lambda: self._render_task_rows(tasks))

        self._run_in_background(background)

    # Draw each saved request as its own read-only card.
    def _render_task_rows(self, tasks):
        """Render task rows after they return from the server."""
        # Replace the loading row with real task rows.
        for widget in self.tasks_scroll.winfo_children():
            widget.destroy()

        # Keep the panel title count in sync.
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
