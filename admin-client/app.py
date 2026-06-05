import customtkinter as ctk

from controllers import ControllerMixin
from views import ViewMixin
from theme import BG


"""Application entry point for the Admin desktop UI."""


class HarmonyApp(ControllerMixin, ViewMixin, ctk.CTk):
    """Main window object composed from controller and view mixins."""

    def __init__(self):
        # Initialize the native CustomTkinter window.
        super().__init__()
        self.title("Harmony")
        self.configure(fg_color=BG)
        self.resizable(True, True)

        # User/session state.
        self.user_id              = None
        self.current_username     = ""
        self.selected_agent       = None

        # Current task and panel state.
        self.is_agent_working     = False
        self.is_task_send_pending = False
        self.is_tasks_panel_open  = False
        self.is_logs_panel_open   = False

        # Cached server data used to avoid unnecessary UI redraws.
        self._known_agent_ids     = []
        self._known_agents        = []
        self._current_screenshot  = None

        # Previous values used to detect meaningful status/log changes.
        self._prev_step_hash      = None
        self._prev_log_hash       = None
        self._prev_status_message = ""
        self._prev_agent_status   = ""
        self._is_server_connected = True

        # Build the UI and start the background refresh loops.
        self._setup_window()
        self._build_all_views()
        self._start_polling_loops()



if __name__ == "__main__":
    HarmonyApp().mainloop()
