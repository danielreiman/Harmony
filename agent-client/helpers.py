import json
import os
import socket
import subprocess
import time
import pyautogui
from nacl.public import PublicKey, SealedBox
from cryptography.fernet import Fernet

BROADCAST_PORT = 3030


def send_frame(sock, data):
    sock.sendall(len(data).to_bytes(8, "big") + data)


def recv_frame(sock):
    size = sock.recv(8)
    if not size:
        return None
    size = int.from_bytes(size, "big")
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def client_secure(sock):
    try:
        public = recv_frame(sock)               # 1 receive public key
        if not public:
            return None
        key = Fernet.generate_key()             # 2 make session key
        sealed_key = SealedBox(PublicKey(public)).encrypt(key)  # 3 seal key
        send_frame(sock, sealed_key)            # 4 send sealed key
        return Secure(key)                      # 5 ready
    except Exception:
        return None


class Secure:
    def __init__(self, key):
        self.cipher = Fernet(key)

    def send(self, sock, data):
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        try:
            encrypted = self.cipher.encrypt(data)   # 1 encrypt
            send_frame(sock, encrypted)             # 2 send
            return True
        except Exception:
            return False

    def recv(self, sock):
        encrypted = recv_frame(sock)                # 1 receive
        if not encrypted:
            return None
        return self.cipher.decrypt(encrypted)       # 2 decrypt


def discover(timeout=30, server_port=1222):
    try:  # check if server is running locally first
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
            packet, (ip, _) = sock.recvfrom(1024)
            if packet == b"HARMONY_SERVER":
                return ip
    except socket.timeout:
        raise RuntimeError(f"No Harmony server found within {timeout}s")
    finally:
        sock.close()


MOVE_SPEED     = 0.15
TYPE_SPEED     = 0.01
HOTKEY_SPEED   = 0.02
CLICK_PAUSE    = 0.05
SCROLL_AMOUNT  = 500
WAIT_DEFAULT   = 0.15

NEEDS_POSITION = {"left_click", "double_click", "right_click", "click", "drag"}


def to_screen_position(coord, screen_w, screen_h):
    if not coord or len(coord) != 2:
        raise ValueError("Invalid coordinate")
    x = int((max(0, min(1000, coord[0])) / 1000.0) * screen_w)
    y = int((max(0, min(1000, coord[1])) / 1000.0) * screen_h)
    return x, y


def act(step):
    action = step.get("Next Action")
    value  = step.get("Value")
    coord  = step.get("Coordinate")
    sw, sh = pyautogui.size()

    try:
        if action in NEEDS_POSITION:
            x, y = to_screen_position(coord, sw, sh)
            pyautogui.moveTo(x, y, duration=MOVE_SPEED)

        if action in ("click", "left_click"):
            pyautogui.click(button="left")

        elif action == "double_click":
            pyautogui.click()
            time.sleep(CLICK_PAUSE)
            pyautogui.click()

        elif action == "right_click":
            pyautogui.click(button="right")

        elif action == "drag":
            end = step.get("EndCoordinate") or step.get("End Coordinate") or step.get("end_coordinate")
            if not end:
                return {"success": False, "output": "drag requires EndCoordinate"}
            ex, ey = to_screen_position(end, sw, sh)
            pyautogui.mouseDown(button="left")
            time.sleep(0.25)
            for i in range(1, 31):
                pyautogui.moveTo(x + (ex - x) * i / 30, y + (ey - y) * i / 30, duration=0.02)
            time.sleep(0.25)
            pyautogui.mouseUp(button="left")

        elif action == "type":
            pyautogui.write(value, interval=TYPE_SPEED)

        elif action == "press_key":
            pyautogui.press(value)

        elif action == "hotkey":
            keys = json.loads(value) if isinstance(value, str) else value
            pyautogui.hotkey(*keys, interval=HOTKEY_SPEED)

        elif action == "scroll_up":
            pyautogui.scroll(SCROLL_AMOUNT)

        elif action == "scroll_down":
            pyautogui.scroll(-SCROLL_AMOUNT)

        elif action == "run_command":
            result = subprocess.run(value, shell=True, capture_output=True, text=True, timeout=30)
            output = (result.stdout + result.stderr).strip()
            if len(output) > 2000:
                output = output[:2000] + "\n... (truncated)"
            return {"success": True, "output": output}

        elif action == "wait":
            time.sleep(float(value or WAIT_DEFAULT))

        elif action in (None, "None"):
            return {"success": True, "output": None}

        return {"success": True, "output": None}

    except Exception as e:
        print(f"[Client] Action '{action}' failed: {e}")
        return {"success": False, "output": str(e)}
