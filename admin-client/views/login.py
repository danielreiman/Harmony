import customtkinter as ctk

from theme import (
    ACCENT, ACCENT_HOVER, BG, BORDER, FONT, MUTED, RED, SOFT, TEXT,
)


"""Login/signup screen builder."""


def _build_login(app):
    """Build the compact authentication screen."""
    # Full-frame background for the login screen.
    frame = ctk.CTkFrame(app, fg_color=BG, corner_radius=0)

    # Centered card that holds all auth controls.
    auth_card = ctk.CTkFrame(frame, fg_color="#242424", corner_radius=22,
                             border_width=1, border_color="#343434",
                             width=390, height=430)
    auth_card.place(relx=0.5, rely=0.5, anchor="center")
    auth_card.pack_propagate(False)

    ctk.CTkLabel(auth_card, text="Harmony", font=(FONT, 28, "bold"),
                 text_color=TEXT).pack(pady=(38, 4))
    ctk.CTkLabel(auth_card, text="Sign in to continue", font=(FONT, 13),
                 text_color=MUTED).pack(pady=(0, 28))

    def field(placeholder, show=None):
        """Create a consistently styled auth input."""
        entry_options = dict(width=316, height=44, corner_radius=10,
                             border_width=1, border_color=BORDER, fg_color=SOFT,
                             text_color=TEXT, placeholder_text_color=MUTED,
                             font=(FONT, 13))
        if show:
            entry_options["show"] = show
        entry = ctk.CTkEntry(auth_card, placeholder_text=placeholder, **entry_options)
        entry.pack(pady=(0, 12))
        return entry

    # Store entries on the app so the controller can read them.
    app.login_user = field("Username")
    app.login_pass = field("Password", show="•")

    # Error/status label updated during authentication.
    app.login_err = ctk.CTkLabel(auth_card, text="", text_color=RED, font=(FONT, 11),
                                 height=22, wraplength=300)
    app.login_err.pack(pady=(2, 10))

    # Primary login action.
    ctk.CTkButton(auth_card, text="Sign in", width=316, height=44, corner_radius=10,
                  fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=BG,
                  font=(FONT, 13, "bold"),
                  command=lambda: app._authenticate("auth_login")).pack()

    # Secondary signup action.
    signup = ctk.CTkLabel(auth_card, text="Create account", font=(FONT, 12, "bold"),
                          text_color=MUTED, cursor="hand2")
    signup.pack(pady=(20, 0))
    signup.bind("<Button-1>", lambda e: app._authenticate("auth_signup"))

    # Let Enter submit from anywhere in the login form.
    for widget in (frame, auth_card, app.login_user, app.login_pass):
        widget.bind("<Return>", lambda e: app._authenticate("auth_login"))
    return frame
