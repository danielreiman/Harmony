import os
import socket
import sys
import threading
import tkinter as tk
from PIL import Image, ImageTk
import pyautogui

from helpers import discover, act, send_message, receive_message, send_file

RUNTIME_DIR = "./runtime"
SCREENSHOT_PATH = os.path.join(RUNTIME_DIR, "screenshot.png")
SERVER_PORT = 1222

def main():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    
    print("[Client] Searching for Harmony server...")
    server_ip = discover(timeout=30)
    if not server_ip:
        print("[Client] No server found.")
        return
        
    print(f"[Client] Found server at {server_ip}")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, SERVER_PORT))
    print("[Client] Connected to server")
    
    first_msg = receive_message(sock) or {}
    agent_id = first_msg.get("agent_id", "unknown")
    print(f"[Client] Assigned ID: {agent_id}")

    def _loop():
        try:
            while True:
                message = receive_message(sock)
                if not message:
                    break
                    
                m_type = message.get("type", "")
                
                if m_type == "request_screenshot":
                    try:
                        screenshot = pyautogui.screenshot()
                        screenshot.save(SCREENSHOT_PATH)
                    except Exception as e:
                        print(f"[Client] Screenshot failed: {e}")
                        screenshot = Image.new("RGB", (1280, 720), (30, 30, 30))
                        screenshot.save(SCREENSHOT_PATH)
                    send_file(sock, SCREENSHOT_PATH)
                    
                elif m_type == "execute_step":
                    step = message.get("step", {})
                    result = act(step)
                    send_message(sock, {
                        "type": "execution_result",
                        "success": result["success"],
                        "output": result.get("output"),
                        "error": None if result["success"] else f"Action '{step.get('Next Action', 'unknown')}' failed"
                    })
        finally:
            sock.close()
            print("[Client] Disconnected")
            try:
                root.after(0, root.destroy)
            except Exception:
                pass

    # Overlay Window setup
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes("-topmost", True, "-alpha", 0.92)

    # Start network socket listener in the background
    threading.Thread(target=_loop, daemon=True).start()
    
    bg_color = "black"
    root.configure(bg=bg_color)
    if sys.platform == "darwin":
        root.attributes("-transparent", True)
    elif sys.platform == "win32":
        root.attributes("-transparentcolor", bg_color)

    root.update_idletasks()
    w, h = 460, 72
    root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+0")

    canvas = tk.Canvas(root, width=w, height=h, bg=bg_color, highlightthickness=0)
    canvas.place(x=0, y=0)
    canvas.create_rectangle(0, 0, w, h, fill="#1a1a1a", outline="#2a2a2a", width=1)

    icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
    try:
        icon_img = ImageTk.PhotoImage(Image.open(icon_path).resize((36, 36), Image.LANCZOS))
        icon_lbl = tk.Label(canvas, image=icon_img, bg="#1a1a1a")
        icon_lbl.image = icon_img
        canvas.create_window(38, h // 2, window=icon_lbl)
    except Exception:
        pass

    canvas.create_text(72, h // 2 - 11, text=f"Harmony ({agent_id})", fill="#ffffff", font=("Helvetica", 13), anchor="w")
    canvas.create_text(72, h // 2 + 11, text="This computer is being controlled by Harmony Agent", fill="#999999", font=("Helvetica", 11), anchor="w")
    
    root.deiconify()
    root.mainloop()

if __name__ == "__main__":
    main()
