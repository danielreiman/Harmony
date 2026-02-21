import os
import socket
import pyautogui
from helpers import discover, act, send_json, recv_json, send_file

SERVER_PORT = 1222
RUNTIME_DIR = "./runtime"
SCREENSHOT_PATH = os.path.join(RUNTIME_DIR, "screenshot.png")


def handle_screenshot_request(sock: socket.socket):
    screenshot = pyautogui.screenshot()
    screenshot.save(SCREENSHOT_PATH)
    send_file(sock, SCREENSHOT_PATH)


def handle_action_request(sock: socket.socket, message: dict):
    step = message.get("step")
    action_succeeded = act(step)

    error_message = None
    if not action_succeeded:
        action_name = step.get("Next Action", "unknown")
        error_message = f"Action '{action_name}' failed to execute"
        print(f"[Client] Action failed: {action_name}")

    send_json(sock, {
        "type": "execution_result",
        "success": action_succeeded,
        "error": error_message
    })


def main():
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    print("[Client] Searching for Harmony server...")
    server_ip = discover(timeout=30)
    print(f"[Client] Found server at {server_ip}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, SERVER_PORT))
    print("[Client] Connected to server")

    try:
        while True:
            message = recv_json(sock)
            if message is None:
                break

            message_type = message.get("type")

            if message_type == "request_screenshot":
                handle_screenshot_request(sock)

            elif message_type == "execute_step":
                handle_action_request(sock, message)

    finally:
        sock.close()
        print("[Client] Disconnected")


if __name__ == "__main__":
    main()
