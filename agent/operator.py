import json, time, pyautogui
from ollama import Client
import config
from getpass import getpass

class Operator:
    def __init__(self, model_name, verify_model_name):
        api_key = config.OLLAMA_API_KEY
        if not api_key:
            api_key = getpass(prompt="Enter Ollama API Key: ")

        self.client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        self.model_name = model_name
        self.verify_model_name = verify_model_name


    def think(self, messages):
        MAX_HISTORY = 10
        trimmed = [messages[0]] + messages[-MAX_HISTORY:]

        result = self.client.chat(model=self.model_name, messages=trimmed)
        raw = result["message"]["content"].strip()

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            step = json.loads(raw[start:end])
        except Exception:
            step = {}

        return step, raw

    def act(self, step: dict[str, str]):
        action = step.get("Next Action")
        coordinate = step.get("Coordinate")
        value = step.get("Value")

        coordinate = step.get("Coordinate")

        viewport = {
            "monitor_left": 0,
            "monitor_top": 0,
            "display_width": 1920,
            "display_height": 1080,
        }

        coords = None

        if action in ["mouse_move", "left_click", "double_click", "right_click"]:
            coords = normalize_coordinate(coordinate, viewport)

        try:
            if action == "mouse_move" and coords:
                pyautogui.moveTo(*coords)
            elif action == "left_click" and coords:
                pyautogui.click(*coords)
            elif action == "double_click" and coords:
                pyautogui.doubleClick(*coords)
            elif action == "right_click" and coords:
                pyautogui.click(*coords, button="right")
            elif action == "type":
                pyautogui.typewrite(value)
            elif action == "press_key":
                pyautogui.press(value)
            elif action == "hotkey":
                if isinstance(value, str):
                    value = json.loads(value)
                pyautogui.hotkey(*value)
            elif action == "scroll_up":
                pyautogui.scroll(500)
            elif action == "scroll_down":
                pyautogui.scroll(-500)
            elif action == "wait":
                time.sleep(1)
            elif action in [None, "None"]:
                return "Task complete."
            else:
                return f"Unknown action: {action}"

            return f"Action done: {action}"
        except Exception as e:
            return f"Failed: {action} -> {e}"

def normalize_coordinate(coordinate, viewport):
    """
    Convert normalized 0–1000 coordinates to absolute screen coordinates.

    coordinate: [x, y] from model (0–1000 space)
    viewport: dict with monitor + screen info
    """

    if coordinate is None or len(coordinate) != 2:
        raise ValueError("Invalid Coordinate")

    x, y = coordinate

    # Clamp to valid range
    x = max(0, min(1000, x))
    y = max(0, min(1000, y))

    # Normalize
    norm_x = x / 1000.0
    norm_y = y / 1000.0

    # Extract viewport info
    left = viewport["monitor_left"]
    top = viewport["monitor_top"]
    width = viewport["display_width"]
    height = viewport["display_height"]

    # Convert to absolute screen position
    abs_x = left + int(norm_x * width)
    abs_y = top + int(norm_y * height)

    return abs_x, abs_y
