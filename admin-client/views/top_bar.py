import customtkinter as ctk

import gateway_requests
from theme import BG, FONT


"""Top navigation bar for the Admin dashboard."""


class TopBarMixin:
    """Builds the welcome, title, logout, and shutdown controls."""

    def _build_top_bar(self):
        """Create the fixed top bar."""
        # Outer bar keeps the top spacing stable.
        bar = ctk.CTkFrame(self.main_frame, fg_color="transparent", height=82,
                           corner_radius=0, border_width=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Single row containing left greeting, centered title, and right actions.
        top_row = ctk.CTkFrame(bar, fg_color="transparent", height=42)
        top_row.pack(fill="x", padx=22, pady=(20, 0))
        top_row.pack_propagate(False)

        # Shared capsule styling for top bar groups.
        capsule_style = dict(fg_color="#282828", corner_radius=21,
                             height=42, border_width=1, border_color="#343434",
                             bg_color=BG)

        # Greeting capsule updates after login.
        welcome_capsule = ctk.CTkFrame(top_row, width=224, **capsule_style)
        welcome_capsule.pack(side="left")
        welcome_capsule.pack_propagate(False)

        self.welcome_label = ctk.CTkLabel(welcome_capsule,
            text="  Good to see you",
            image=self._resource_image("wave_emoji.png", (24, 19)),
            compound="left", font=(FONT, 13, "bold"),
            text_color="#f4f4f4", height=24)
        self.welcome_label.place(relx=0.5, rely=0.5, anchor="center")

        # Center product title.
        title_capsule = ctk.CTkFrame(top_row, width=110, **capsule_style)
        title_capsule.place(relx=0.5, rely=0.5, anchor="center")
        title_capsule.pack_propagate(False)
        ctk.CTkLabel(title_capsule, text="Harmony", font=(FONT, 13, "bold"),
                     text_color="#f4f4f4").place(relx=0.5, rely=0.5, anchor="center")

        # Right-side account/server actions.
        actions_capsule = ctk.CTkFrame(top_row, width=206, **capsule_style)
        actions_capsule.pack(side="right")
        actions_capsule.pack_propagate(False)

        actions_row = ctk.CTkFrame(actions_capsule, fg_color="transparent")
        actions_row.place(relx=0.5, rely=0.5, anchor="center")

        def nav_item(text, width, text_color, weight="normal", hover="#343434", command=None):
            """Create one compact top-bar button."""
            return ctk.CTkButton(
                actions_row, text=text, width=width, height=30, corner_radius=15,
                fg_color="transparent", hover_color=hover,
                text_color=text_color, font=(FONT, 13, weight), border_width=0,
                command=command or (lambda: None))

        nav_item("Log out", 78, "#a8a8a8", command=self._show_login_view).pack(
            side="left", padx=4)

        def shutdown():
            """Stop the server, then close the Admin window."""
            gateway_requests.stop_server()
            self.quit()

        self.shutdown_button = nav_item(
            "Shutdown", 92, "#ff7a7a", hover="#3a2929",
            command=shutdown)
        self.shutdown_button.pack(side="left", padx=4)
