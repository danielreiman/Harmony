import customtkinter as ctk

from theme import BG, DIM, FONT, MUTED, TEXT


"""Central screen preview and empty-state UI."""


class ScreenViewMixin:
    """Builds the area that shows the selected agent's screen."""

    def _build_content_area(self):
        """Create the main dashboard content area."""
        # Leave room at the bottom for the prompt composer.
        self.content_area = ctk.CTkFrame(self.main_frame, fg_color=BG)
        self.content_area.pack(fill="both", expand=True, padx=22, pady=(22, 236))

        # Shared layer for the screenshot and right-side cards.
        self.screenshot_and_panels = ctk.CTkFrame(self.content_area, fg_color="transparent")
        self.screenshot_and_panels.pack(fill="both", expand=True)
        self._build_screen_stage()
        self._build_floating_state_panel()

    # Set up the area in the middle where the helper's screen picture appears.
    def _build_screen_stage(self):
        """Create the label that displays screenshots."""
        self.screen_meta = ctk.CTkLabel(self.screenshot_and_panels, text="")
        self.screen_area = ctk.CTkFrame(self.screenshot_and_panels, fg_color="transparent")
        self.screen_area.place(relx=0.5, rely=0.5, anchor="center",
                               relwidth=1.0, relheight=1.0)
        self.screenshot_label = ctk.CTkLabel(self.screen_area, text="",
            text_color=MUTED, font=(FONT, 13))
        self.screenshot_label.place(relx=0.5, rely=0.5, anchor="center")

    # Clear the screen picture while we are waiting for a new one.
    # We never pass image=None to a CTkLabel — CustomTkinter doesn't fully
    # clear the inner tk.Label's image option, which leaves a dangling
    # pyimage reference and crashes on the next configure(). Instead we
    # tell the label to display only the text, leaving the image option
    # untouched (the empty-state overlay covers anything still drawn).
    def _show_waiting_screenshot(self):
        """Switch the screenshot label to a harmless waiting state."""
        try:
            self.screenshot_label.configure(text=" ")
        except Exception:
            pass

    def _build_empty_state(self):
        """Create the overlay shown before a screenshot is available."""
        self.empty_state_overlay = ctk.CTkFrame(self.screenshot_and_panels, fg_color="transparent")
        ctr = ctk.CTkFrame(self.empty_state_overlay, fg_color="transparent")
        ctr.place(relx=0.5, rely=0.44, anchor="center")
        self.empty_state_title = ctk.CTkLabel(ctr, text="No agent connected",
                                              font=(FONT, 20, "bold"), text_color=TEXT)
        self.empty_state_title.pack(pady=(0, 6))
        self.empty_state_subtitle = ctk.CTkLabel(ctr,
            text="Connect an agent to see its screen here",
            font=(FONT, 13), text_color=DIM)
        self.empty_state_subtitle.pack()
