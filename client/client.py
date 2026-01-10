import socket, os
from helpers import *

SERVER_HOST = discover()
SERVER_PORT = 1222

def main():
    os.makedirs("./runtime", exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))
    print("[CLIENT] Connected to server")
    try:
        while True:
            msg = recv_json(sock)
            if not msg:
                break

            msg_type = msg.get("type")

            # ======== SEND SCREENSHOT ========
            if msg_type == "request_screenshot":
                screenshot = pyautogui.screenshot()
                screenshot.save("./runtime/screenshot.png")

                send_file(sock, "./runtime/screenshot.png")

            # ======== EXECUTE STEP ========
            elif msg_type == "execute_step":
                step = msg.get("step")
                success = act(step)
                error_msg = None
                
                if not success:
                    action = step.get("Next Action", "unknown")
                    error_msg = f"Action '{action}' failed to execute"
                    print(f"[CLIENT] Action failed: {action}")

                send_json(sock, {
                    "type": "execution_result",
                    "success": success,
                    "error": error_msg
                })

    finally:
        sock.close()
        print("[CLIENT] Disconnected")

if __name__ == "__main__":
    main()
