import json
import socket
import subprocess
import time
import pyautogui

BROADCAST_PORT = 3030

def discover(timeout=30, server_port=1222):
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

# Performance Constants
MOUSE_MOVE_DURATION = 0.15
TYPE_INTERVAL = 0.01
HOTKEY_INTERVAL = 0.02
DOUBLE_CLICK_PAUSE = 0.05
SCROLL_AMOUNT = 500
WAIT_DURATION = 0.15

ACTIONS_REQUIRING_COORDINATES = {"left_click", "double_click", "right_click", "click", "drag"}

def _normalize_coordinate(coordinate, screen_width, screen_height):
    if not coordinate or len(coordinate) != 2:
        raise ValueError("Invalid coordinate")
    raw_x, raw_y = coordinate
    nx, ny = max(0, min(1000, raw_x)), max(0, min(1000, raw_y))
    return int((nx / 1000.0) * screen_width), int((ny / 1000.0) * screen_height)

def act(step):
    action = step.get("Next Action")
    value = step.get("Value")
    coord = step.get("Coordinate")
    
    screen_width, screen_height = pyautogui.size()
    
    try:
        # 1. Handle coordinates if needed
        if action in ACTIONS_REQUIRING_COORDINATES:
            nx, ny = _normalize_coordinate(coord, screen_width, screen_height)
            pyautogui.moveTo(nx, ny, duration=MOUSE_MOVE_DURATION)

        # 2. Action Handlers
        if action in ("click", "left_click"):
            pyautogui.click(button="left")
            
        elif action == "double_click":
            pyautogui.click()
            time.sleep(DOUBLE_CLICK_PAUSE)
            pyautogui.click()
            
        elif action == "right_click":
            pyautogui.click(button="right")
            
        elif action == "drag":
            end_coord = step.get("EndCoordinate") or step.get("End Coordinate") or step.get("end_coordinate")
            if not end_coord:
                return {"success": False, "output": "drag requires EndCoordinate"}
            ex, ey = _normalize_coordinate(end_coord, screen_width, screen_height)

            # Ensure cursor is settled at start before pressing.
            pyautogui.moveTo(nx, ny, duration=MOUSE_MOVE_DURATION)
            time.sleep(0.15)
            pyautogui.mouseDown(button="left")
            time.sleep(0.25)

            # Stepped move — OS drag detection needs intermediate motion events.
            steps = 30
            for i in range(1, steps + 1):
                ix = nx + (ex - nx) * i / steps
                iy = ny + (ey - ny) * i / steps
                pyautogui.moveTo(ix, iy, duration=0.02)
            time.sleep(0.25)
            pyautogui.mouseUp(button="left")

        elif action == "type":
            pyautogui.write(value, interval=TYPE_INTERVAL)

        elif action == "press_key":
            pyautogui.press(value, interval=TYPE_INTERVAL)

        elif action == "hotkey":
            keys = json.loads(value) if isinstance(value, str) else value
            pyautogui.hotkey(*keys, interval=HOTKEY_INTERVAL)

        elif action == "scroll_up":
            pyautogui.scroll(SCROLL_AMOUNT)

        elif action == "scroll_down":
            pyautogui.scroll(-SCROLL_AMOUNT)

        elif action == "run_command":
            res = subprocess.run(value, shell=True, capture_output=True, text=True, timeout=30)
            output = (res.stdout + res.stderr).strip()
            if len(output) > 2000: output = output[:2000] + "\n... (truncated)"
            return {"success": True, "output": output}

        elif action == "wait":
            time.sleep(float(value or WAIT_DURATION))

        elif action in (None, "None"):
            return {"success": True, "output": None}

        return {"success": True, "output": None}

    except Exception as e:
        print(f"[Client] Action '{action}' failed: {e}")
        return {"success": False, "output": str(e)}

