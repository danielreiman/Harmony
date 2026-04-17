import customtkinter as ctk
from ui.theme import *

F = dict(width=320, height=44, corner_radius=CORNER_RADIUS, border_width=1,
         border_color=BORDER, fg_color=ELEVATED, text_color=TEXT,
         placeholder_text_color=MUTED, font=(FONT, 14))


def build_login(app):
    frame = ctk.CTkFrame(app, fg_color=BG)
    c = ctk.CTkFrame(frame, fg_color="transparent")
    c.place(relx=0.5, rely=0.5, anchor="center")

    # Logo mark
    mark = ctk.CTkFrame(c, fg_color=ACCENT, corner_radius=12, width=48, height=48)
    mark.pack(); mark.pack_propagate(False)
    ctk.CTkLabel(mark, text="H", font=(FONT, 22, "bold"), text_color="#fff").place(relx=.5, rely=.5, anchor="center")

    ctk.CTkLabel(c, text="Harmony", font=(FONT, 22, "bold"), text_color=TEXT).pack(pady=(12, 2))
    ctk.CTkLabel(c, text="Sign in to your account", font=(FONT, 13), text_color=DIM).pack(pady=(0, 24))

    box = card(c); box.pack()
    inner = ctk.CTkFrame(box, fg_color="transparent"); inner.pack(padx=36, pady=32)

    ctk.CTkLabel(inner, text="Username", font=(FONT, 12, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 6))
    app.login_user = ctk.CTkEntry(inner, placeholder_text="Enter your username", **F); app.login_user.pack()

    ctk.CTkLabel(inner, text="Password", font=(FONT, 12, "bold"), text_color=TEXT).pack(anchor="w", pady=(18, 6))
    app.login_pass = ctk.CTkEntry(inner, placeholder_text="Enter your password", show="•", **F); app.login_pass.pack()

    app.login_err = ctk.CTkLabel(inner, text="", text_color=RED, font=(FONT, 12))
    app.login_err.pack(pady=(10, 0))

    ctk.CTkButton(inner, text="Sign In", height=44, corner_radius=CORNER_RADIUS,
                  fg_color=ACCENT, hover_color="#1d4ed8", text_color="#fff",
                  font=(FONT, 14, "bold"),
                  command=lambda: app._authenticate("auth_login")).pack(fill="x", pady=(10, 0))

    signup = ctk.CTkLabel(inner, text="No account?  Sign up", font=(FONT, 12),
                          text_color=ACCENT, cursor="hand2")
    signup.pack(pady=(16, 0))
    signup.bind("<Button-1>", lambda e: app._authenticate("auth_signup"))

    for w in (frame, app.login_user, app.login_pass):
        w.bind("<Return>", lambda e: app._authenticate("auth_login"))

    return frame
