import json, os, socket, subprocess, time, pyautogui
from shared import client_secure, Secure

BROADCAST_PORT = 3030


def discover(timeout=30, server_port=1222):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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


def scale_ai_coordinates(coord, screen_w, screen_h):
    if not coord or len(coord) != 2:
        raise ValueError("Invalid coordinate")
    x = int((max(0, min(1000, coord[0])) / 1000.0) * screen_w)
    y = int((max(0, min(1000, coord[1])) / 1000.0) * screen_h)
    return x, y


def act(step):
    action = step.get("Next Action")
    value = step.get("Value")
    coord = step.get("Coordinate")

    sw, sh = pyautogui.size()

    try:
        # Move if needed
        if action in NEEDS_POSITION:
            x, y = scale_ai_coordinates(coord, sw, sh)
            pyautogui.moveTo(x, y, duration=MOVE_SPEED)

        if action in ("click", "left_click"):
            pyautogui.click(button="left")

        elif action == "double_click":
            pyautogui.doubleClick(interval=CLICK_PAUSE)

        elif action == "right_click":
            pyautogui.click(button="right")

        elif action == "type":
            pyautogui.write(value or "", interval=TYPE_SPEED)

        elif action == "press_key":
            pyautogui.press(value)

        elif action == "hotkey":
            keys = json.loads(value) if isinstance(value, str) else value
            pyautogui.hotkey(*keys, interval=HOTKEY_SPEED)

        elif action == "scroll_up":
            pyautogui.scroll(SCROLL_AMOUNT)

        elif action == "scroll_down":
            pyautogui.scroll(-SCROLL_AMOUNT)

        elif action == "drag":
            end = step.get("EndCoordinate")

            if not end:
                return {"success": False, "output": "drag requires EndCoordinate"}

            ex, ey = scale_ai_coordinates(end, sw, sh)
            pyautogui.dragTo(ex, ey, duration=0.7, button="left")

        elif action == "run_command":
            result = subprocess.run(
                value,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            command_output = result.stdout.strip()
            error_output = result.stderr.strip()

            output = command_output + error_output
            if len(output) > 2000:
                output = output[:2000] + "\n... (truncated)"

            return {"success": True, "output": output}

        elif action == "wait":
            time.sleep(float(value or WAIT_DEFAULT))

        elif action in (None, "None"):
            pass

        else:
            return {"success": False, "output": f"unknown action: {action}"}

        return {"success": True, "output": None}

    except Exception as e:
        print(f"[Client] Action '{action}' failed: {e}")
        return {"success": False, "output": str(e)}