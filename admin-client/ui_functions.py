import customtkinter as ctk

def create_log_window(parent, bg_color, field_color):
    """Creates a scrollable log window."""
    frame = ctk.CTkFrame(parent, fg_color=field_color, corner_radius=32)
    
    header = ctk.CTkLabel(frame, text="AGENT LOGS", font=("Arial", 10, "bold"), text_color="#666666")
    header.pack(anchor="w", padx=16, pady=(14, 3))
    
    log_scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
    log_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 14))
    
    return frame, log_scroll

def append_log_entry(log_scroll, step_data):
    """Appends a single logging entry to the scrollable frame."""
    if not step_data:
        return
        
    action = step_data.get("action", "None") or step_data.get("a", "None")
    reasoning = step_data.get("reasoning", "") or step_data.get("r", "")
    status_short = step_data.get("status_short", "")
    coord = step_data.get("coordinate")
    val = step_data.get("value")
    cmd_output = step_data.get("cmd_output")
    
    if action in (None, "None", "") and not reasoning and not cmd_output:
        return
        
    entry_frame = ctk.CTkFrame(log_scroll, fg_color="transparent")
    entry_frame.pack(fill="x", pady=4)
    
    header_text = ""
    if status_short:
        header_text = f"[{status_short}]"
        ctk.CTkLabel(entry_frame, text=header_text, font=("Arial", 10, "bold"), text_color="#aaaaaa", anchor="w").pack(fill="x", pady=(0, 2))
    
    if action and action != "None":
        act_text = f"Action: {action}"
        if val:
            act_text += f"\nValue: {val}"
        if coord:
            act_text += f"\nCoord: {coord}"
            
        lbl_action = ctk.CTkLabel(entry_frame, text=act_text, font=("Arial", 12, "bold"), text_color="#3b82f6", anchor="w", justify="left", wraplength=260)
        lbl_action.pack(fill="x")
    
    if reasoning:
        lbl_reason = ctk.CTkLabel(entry_frame, text=reasoning, font=("Arial", 12), text_color="#cccccc", anchor="w", justify="left", wraplength=260)
        lbl_reason.pack(fill="x", pady=(4,0))
        
    if cmd_output:
        out_f = ctk.CTkFrame(entry_frame, fg_color="#181818", corner_radius=6)
        out_f.pack(fill="x", pady=(6, 2))
        lbl_out = ctk.CTkLabel(out_f, text=str(cmd_output), font=("Courier", 10), text_color="#22c55e", anchor="w", justify="left", wraplength=240)
        lbl_out.pack(padx=8, pady=8, fill="x")
    
    ctk.CTkFrame(entry_frame, fg_color="#3a3a3a", height=1).pack(fill="x", pady=(8, 4))
    
    def scroll_bottom():
        log_scroll._parent_canvas.yview_moveto(1.0)
    log_scroll.after(50, scroll_bottom)

def build_overlay_section(parent, title, font_size, bold=False, pad_top=14, pad_bottom=12):
    """Builds a readonly text section."""
    ctk.CTkLabel(
        parent, text=title, font=("Arial", 10, "bold"),
        text_color="#666666", anchor="w",
    ).pack(padx=16, pady=(pad_top, 3), anchor="w")

    class SpacedLabel(ctk.CTkTextbox):
        def configure(self, require_redraw=False, **kwargs):
            if "text" in kwargs:
                text = kwargs.pop("text")
                super().configure(state="normal")
                self.delete("1.0", "end")
                self.insert("1.0", str(text))
                super().configure(state="disabled")
            super().configure(require_redraw=require_redraw, **kwargs)

    font = ("Arial", font_size, "bold") if bold else ("Arial", font_size)
    label = SpacedLabel(
        parent, font=font, text_color="#ffffff" if bold else "#cccccc",
        fg_color="transparent", wrap="word", height=80,
        spacing3=5, border_width=0,
    )
    label.configure(text="—")
    label.pack(padx=12, pady=(0, pad_bottom), fill="x", expand=False)
    return label
