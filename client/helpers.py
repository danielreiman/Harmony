import json
import socket
import time
import pyautogui

BROADCAST_PORT = 3030
MOUSE_MOVE_DURATION = 0.35
TYPE_INTERVAL = 0.02
HOTKEY_INTERVAL = 0.04
DOUBLE_CLICK_PAUSE = 0.12
SCROLL_AMOUNT = 360
WAIT_DURATION = 0.35

ACTIONS_REQUIRING_COORDINATES = {"mouse_move", "left_click", "double_click", "right_click", "click"}


def discover(timeout: int = 30) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", BROADCAST_PORT))
    sock.settimeout(timeout)
    try:
        while True:
            packet, sender_address = sock.recvfrom(1024)
            packet_is_harmony_beacon = packet == b"HARMONY_SERVER"
            if packet_is_harmony_beacon:
                return sender_address[0]
    except socket.timeout:
        raise RuntimeError(f"No Harmony server found within {timeout}s")
    finally:
        sock.close()


def _normalize_coordinate(coordinate: list, screen_width: int, screen_height: int) -> tuple[int, int]:
    if coordinate is None or len(coordinate) != 2:
        raise ValueError("Invalid coordinate")

    raw_x, raw_y = coordinate
    clamped_x = max(0, min(1000, raw_x))
    clamped_y = max(0, min(1000, raw_y))

    absolute_x = int((clamped_x / 1000.0) * screen_width)
    absolute_y = int((clamped_y / 1000.0) * screen_height)

    return absolute_x, absolute_y


def act(step: dict) -> bool:
    action = step.get("Next Action")
    value = step.get("Value")
    coordinate = step.get("Coordinate")

    screen_size = pyautogui.size()
    screen_coords = None

    action_requires_coordinates = action in ACTIONS_REQUIRING_COORDINATES
    if action_requires_coordinates:
        screen_coords = _normalize_coordinate(coordinate, screen_size.width, screen_size.height)

    try:
        if screen_coords:
            pyautogui.moveTo(screen_coords[0], screen_coords[1], duration=MOUSE_MOVE_DURATION)

        if action == "mouse_move":
            pass

        elif action in ("left_click", "click"):
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
            key_combination = json.loads(value) if isinstance(value, str) else value
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


def _recv_exact(sock: socket.socket, size: int) -> bytes | None:
    received = b""
    while len(received) < size:
        chunk = sock.recv(size - len(received))
        if not chunk:
            return None
        received += chunk
    return received


def send_json(sock: socket.socket, obj: dict):
    encoded = json.dumps(obj).encode()
    length_prefix = len(encoded).to_bytes(8, "big")
    sock.sendall(length_prefix)
    sock.sendall(encoded)


def recv_json(sock: socket.socket) -> dict | None:
    size_bytes = _recv_exact(sock, 8)
    if size_bytes is None:
        return None

    message_size = int.from_bytes(size_bytes, "big")
    if message_size <= 0:
        return None

    data = _recv_exact(sock, message_size)
    if data is None:
        return None

    return json.loads(data.decode())


def send_file(sock: socket.socket, path: str):
    with open(path, "rb") as f:
        file_bytes = f.read()
    length_prefix = len(file_bytes).to_bytes(8, "big")
    sock.sendall(length_prefix)
    sock.sendall(file_bytes)
