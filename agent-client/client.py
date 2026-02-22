import os
import socket

import pyautogui

from helpers import discover, act, send_message, receive_message, send_file

SERVER_PORT = 1222
RUNTIME_DIR = "./runtime"
SCREENSHOT_PATH = os.path.join(RUNTIME_DIR, "screenshot.png")


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


def main():
    """Discovers the server, connects, and handles incoming messages in a loop until disconnected."""
    os.makedirs(RUNTIME_DIR, exist_ok=True)

    print("[Client] Searching for Harmony server...")
    server_ip = discover(timeout=30)
    print(f"[Client] Found server at {server_ip}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((server_ip, SERVER_PORT))
    print("[Client] Connected to server")

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


if __name__ == "__main__":
    main()
