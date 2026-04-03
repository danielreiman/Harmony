import json
import socket
import time

import pyautogui


BROADCAST_PORT = 3030


def discover(timeout=30, server_port=1222):
    # Try localhost first in case client and server are on the same machine
    try:
        test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test.settimeout(1)
        test.connect(("127.0.0.1", server_port))
        test.close()
        return "127.0.0.1"
    except OSError:
        pass

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", BROADCAST_PORT))
    sock.settimeout(timeout)
    try:
        while True:
            packet, sender_address = sock.recvfrom(1024)
            if packet == b"HARMONY_SERVER":
                return sender_address[0]
    except socket.timeout:
        raise RuntimeError(f"No Harmony server found within {timeout}s")
    finally:
        sock.close()



MOUSE_MOVE_DURATION = 0.35
TYPE_INTERVAL = 0.02
HOTKEY_INTERVAL = 0.04
DOUBLE_CLICK_PAUSE = 0.12
SCROLL_AMOUNT = 360
WAIT_DURATION = 0.35

ACTIONS_REQUIRING_COORDINATES = {"left_click", "double_click", "right_click", "click"}


def _normalize_coordinate(coordinate, screen_width, screen_height):
    if coordinate is None or len(coordinate) != 2:
        raise ValueError("Invalid coordinate")

    raw_x, raw_y = coordinate
    clamped_x = max(0, min(1000, raw_x))
    clamped_y = max(0, min(1000, raw_y))

    absolute_x = int((clamped_x / 1000.0) * screen_width)
    absolute_y = int((clamped_y / 1000.0) * screen_height)

    return absolute_x, absolute_y


def act(step):
    action = step.get("Next Action")
    value = step.get("Value")
    coordinate = step.get("Coordinate")

    screen_size = pyautogui.size()
    screen_coords = None

    if action in ACTIONS_REQUIRING_COORDINATES:
        screen_coords = _normalize_coordinate(coordinate, screen_size.width, screen_size.height)

    try:
        if screen_coords:
            pyautogui.moveTo(screen_coords[0], screen_coords[1], duration=MOUSE_MOVE_DURATION)

        if action in ("left_click", "click"):
            pyautogui.click(button="left")

        elif action == "double_click":
            pyautogui.click()
            time.sleep(DOUBLE_CLICK_PAUSE)
            pyautogui.click()

        elif action == "right_click":
            pyautogui.click(button="right")

        elif action == "type":
            pyautogui.write(value, interval=TYPE_INTERVAL)

        elif action == "press_key":
            pyautogui.press(value)

        elif action == "hotkey":
            if isinstance(value, str):
                key_combination = json.loads(value)
            else:
                key_combination = value
            pyautogui.hotkey(*key_combination, interval=HOTKEY_INTERVAL)

        elif action == "scroll_up":
            pyautogui.scroll(SCROLL_AMOUNT)

        elif action == "scroll_down":
            pyautogui.scroll(-SCROLL_AMOUNT)

        elif action == "wait":
            time.sleep(WAIT_DURATION)

        elif action in (None, "None"):
            return True

        else:
            print(f"[Client] Unknown action: {action}")
            return False

        return True

    except Exception as error:
        print(f"[Client] Action '{action}' failed: {error}")
        return False


def _read_exact(sock, size):
    received = b""
    while len(received) < size:
        chunk = sock.recv(size - len(received))
        if not chunk:
            return None
        received += chunk
    return received


def send_message(sock, obj):
    encoded = json.dumps(obj).encode()
    length_prefix = len(encoded).to_bytes(8, "big")
    sock.sendall(length_prefix)
    sock.sendall(encoded)


def receive_message(sock):
    """Reads a length-prefixed JSON message from the socket and returns it as a dict."""
    size_bytes = _read_exact(sock, 8)
    if size_bytes is None:
        return None

    message_size = int.from_bytes(size_bytes, "big")
    if message_size <= 0:
        return None

    data = _read_exact(sock, message_size)
    if data is None:
        return None

    return json.loads(data.decode())


def send_file(sock, path):
    """Reads a file from disk and sends its bytes with an 8-byte length prefix over the socket."""
    with open(path, "rb") as f:
        file_bytes = f.read()
    length_prefix = len(file_bytes).to_bytes(8, "big")
    sock.sendall(length_prefix)
    sock.sendall(file_bytes)
