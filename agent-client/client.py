import os
import socket
import sys
import threading
import tkinter as tk
from PIL import Image, ImageTk

import pyautogui

from helpers import discover, act, send_message, receive_message, send_file

SERVER_PORT = 1222
RUNTIME_DIR = "./runtime"
SCREENSHOT_PATH = os.path.join(RUNTIME_DIR, "screenshot.png")


def show_overlay(agent_id):
    """Shows a compact bar pinned to the top center, always above everything."""
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)

    try:
        root.tk.call("::tk::unsupported::MacWindowStyle", "style", root._w, "borderless", "")
    except Exception:
        pass

    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.92)

    BG = "black"
    root.configure(bg=BG)
    if sys.platform == "darwin":
        root.attributes("-transparent", True)
    elif sys.platform == "win32":
        root.attributes("-transparentcolor", BG)

    # Size the window first so we can draw the rounded pill on a canvas
    root.update_idletasks()
    screen_w = root.winfo_screenwidth()
    w, h, r = 460, 72, 36
    x = (screen_w - w) // 2
    root.geometry(f"{w}x{h}+{x}+0")

    canvas = tk.Canvas(root, width=w, height=h, bg=BG, highlightthickness=0)
    canvas.place(x=0, y=0)

    canvas.create_rectangle(0, 0, w, h, fill="#1a1a1a", outline="#2a2a2a", width=1)

    # Icon
    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    icon_img = ImageTk.PhotoImage(Image.open(icon_path).resize((36, 36), Image.LANCZOS))
    icon_lbl = tk.Label(canvas, image=icon_img, bg="#1a1a1a")
    icon_lbl.image = icon_img
    canvas.create_window(20 + 18, h // 2, window=icon_lbl)

    # Text
    cx = 20 + 36 + 16
    canvas.create_text(cx, h // 2 - 11, text=f"Harmony ({agent_id})",
                       fill="#ffffff", font=("Helvetica", 13), anchor="w")
    canvas.create_text(cx, h // 2 + 11, text="This computer is being controlled by Harmony Agent",
                       fill="#999999", font=("Helvetica", 11), anchor="w")

    root.deiconify()
    root.mainloop()


def take_and_send_screenshot(sock):
    """Takes a screenshot and sends it to the server over the given socket."""
    screenshot = pyautogui.screenshot()
    screenshot.save(SCREENSHOT_PATH)
    send_file(sock, SCREENSHOT_PATH)


def run_and_report_action(sock, message):
    """Executes the action step from the message and sends the result back to the server."""
    step = message.get("step")
    action_succeeded = act(step)

    error_message = None
    if not action_succeeded:
        action_name = step.get("Next Action", "unknown")
        error_message = f"Action '{action_name}' failed to execute"
        print(f"[Client] Action failed: {action_name}")

    send_message(sock, {
        "type": "execution_result",
        "success": action_succeeded,
        "error": error_message
    })


def message_loop(sock):
    """Handles incoming messages from the server in a background thread."""
    try:
        while True:
            message = receive_message(sock)
            if message is None:
                break

            message_type = message.get("type")

            if message_type == "request_screenshot":
                take_and_send_screenshot(sock)

            elif message_type == "execute_step":
                run_and_report_action(sock, message)

    finally:
        sock.close()
        print("[Client] Disconnected")


def main():
    """Discovers the server, connects, reads the agent ID, then runs the overlay on the main thread."""
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    print("[Client] Searching for Harmony server...")
    server_ip = discover(timeout=30)
    print(f"[Client] Found server at {server_ip}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, SERVER_PORT))
    print("[Client] Connected to server")

    # First message is always the agent ID
    first_message = receive_message(sock)
    agent_id = "unknown"
    if first_message and first_message.get("type") == "connected":
        agent_id = first_message.get("agent_id", "unknown")
        print(f"[Client] Assigned ID: {agent_id}")

    # Run message loop in background, overlay on main thread
    threading.Thread(target=message_loop, args=(sock,), daemon=True).start()
    show_overlay(agent_id)


if __name__ == "__main__":
    main()
