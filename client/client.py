import socket
from pathlib import Path
from helpers import *

SERVER_HOST = "harmony-server.duckdns.org"
SERVER_PORT = 8080

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))
    print("[CLIENT] Connected to server")

    screenshot_path = Path("client/runtime/screenshot.png")
    screenshot_path.parent.mkdir(exist_ok=True)

    try:
        while True:
            msg = recv_json(sock)
            if not msg:
                break

            msg_type = msg.get("type")

            # ======== SEND SCREENSHOT ========
            if msg_type == "request_screenshot":
                pyautogui.screenshot(str(screenshot_path))
                send_file(sock, screenshot_path)

            # ======== EXECUTE STEP ========
            elif msg_type == "execute_step":
                step = msg.get("step")
                success = act(step)

                send_json(sock, {
                    "type": "execution_result",
                    "success": success
                })

    finally:
        sock.close()
        print("[CLIENT] Disconnected")

if __name__ == "__main__":
    main()
