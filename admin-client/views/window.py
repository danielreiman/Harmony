import os
import threading

import customtkinter as ctk
from PIL import Image, ImageTk

from theme import AUTH_WINDOW_SIZE, BG
from widgets import build_panel
from .login import _build_login


"""Window-level helpers and top-level dashboard composition."""


RESOURCE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")


class WindowMixin:
    """Owns window setup, frame switching, image loading, and main layout."""

    def _setup_window(self):
        """Set icon and initial centered login size."""
        try:
            app_icon = ImageTk.PhotoImage(Image.open(os.path.join(RESOURCE_DIR, "icon.png")))
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
        """Switch the Admin dashboard into fullscreen mode."""
        try:
            self.state("normal")
        except Exception:
            pass
        self.attributes("-fullscreen", True)

    # Run a slow piece of work on the side so the app stays smooth.
    def _run_in_background(self, fn, *args):
        """Run blocking work without freezing the UI thread."""
        threading.Thread(target=fn, args=args, daemon=True).start()

    # Load small UI images once and keep them alive for CustomTkinter labels.
    def _resource_image(self, filename, size):
        """Load and cache a resource image at the requested display size."""
        if not hasattr(self, "_resource_image_cache"):
            self._resource_image_cache = {}

        key = (filename, size)
        if key not in self._resource_image_cache:
            path = os.path.join(RESOURCE_DIR, filename)
            image = Image.open(path)
            self._resource_image_cache[key] = ctk.CTkImage(
                light_image=image, dark_image=image, size=size)
        return self._resource_image_cache[key]

    # Hide every screen and then show only the one we want.
    def _show_frame(self, frame):
        """Replace the visible root frame."""
        for f in (self.login_frame, self.main_frame):
            try:
                f.pack_forget()
            except Exception:
                pass
        frame.pack(fill="both", expand=True)

    # Switch back to the sign-in screen.
    def _show_login_view(self):
        """Show the compact login screen."""
        self._set_centered_window(*AUTH_WINDOW_SIZE)
        self._show_frame(self.login_frame)

    # Switch to the big main screen after someone signs in.
    def _show_main_view(self):
        """Show the fullscreen dashboard."""
        self._enter_main_fullscreen()
        self._show_frame(self.main_frame)

    # Build both the sign-in screen and the main screen, then show sign-in first.
    def _build_all_views(self):
        """Create all persistent top-level UI frames."""
        self.login_frame = _build_login(self)
        self._build_main_view()
        self._show_login_view()

    # Build the whole main screen piece by piece: top bar, middle area,
    # bottom bar, and the two pop-ups for Tasks and Activity.
    def _build_main_view(self):
        """Build the dashboard shell and its floating panels."""
        self.main_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._build_top_bar()
        self._build_content_area()
        self._build_empty_state()
        self._build_bottom_bar()
        self.tasks_panel, self.tasks_scroll = build_panel(
            self, "Tasks", 310, 380, self._hide_tasks_panel, "tasks_cnt")
        self.logs_panel, self.log_scroll = build_panel(
            self, "Activity", 350, 430, self._hide_logs_panel, "logs_agent_lbl")
