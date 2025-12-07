import pyautogui, json, time

def normalize_coordinate(coordinate, viewport):
    if coordinate is None or len(coordinate) != 2:
        raise ValueError("Invalid Coordinate")

    x, y = coordinate

    x = max(0, min(1000, x))
    y = max(0, min(1000, y))

    norm_x = x / 1000.0
    norm_y = y / 1000.0

    left = viewport["monitor_left"]
    top = viewport["monitor_top"]
    width = viewport["display_width"]
    height = viewport["display_height"]

    abs_x = left + int(norm_x * width)
    abs_y = top + int(norm_y * height)

    return abs_x, abs_y

def act(step):
    action = step.get("Next Action")
    value = step.get("Value")
    coordinate = step.get("Coordinate")

    viewport = {
        "monitor_left": 0,
        "monitor_top": 0,
        "display_width": pyautogui.size().width,
        "display_height": pyautogui.size().height,
    }

    coords = None
    if action in ["mouse_move", "left_click", "double_click", "right_click"]:
        coords = normalize_coordinate(coordinate, viewport)

    try:
        if coords and action in {"mouse_move", "left_click", "double_click", "right_click"}:
            pyautogui.moveTo(coords[0], coords[1], duration=0.35)

        if action == "mouse_move":
            pass

        elif action == "left_click":
            pyautogui.click(button="left")

        elif action == "double_click":
            pyautogui.click()
            time.sleep(0.12)
            pyautogui.click()

        elif action == "right_click":
            pyautogui.click(button="right")

        elif action == "type":
            pyautogui.typewrite(value, interval=0.04)

        elif action == "press_key":
            pyautogui.press(value)

        elif action == "hotkey":
            if isinstance(value, str):
                value = json.loads(value)
            pyautogui.hotkey(*value, interval=0.04)

        elif action == "scroll_up":
            pyautogui.scroll(360)

        elif action == "scroll_down":
            pyautogui.scroll(-360)

        elif action == "wait":
            time.sleep(0.35)

        elif action in [None, "None"]:
            return True

        else:
            print("Unknown action:", action)
            return False

        return True

    except Exception as e:
        print("Execution error:", e)
        return False


def send_json(sock, obj):
    sock.sendall(json.dumps(obj).encode())

def recv_json(sock):
    data = sock.recv(4096)
    return json.loads(data.decode()) if data else None

def send_file(sock, path):
    with open(path, "rb") as f:
        data = f.read()

    sock.sendall(len(data).to_bytes(8, "big"))
    sock.sendall(data)
