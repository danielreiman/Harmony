import json, time, pyautogui
from ollama import Client
import config
from getpass import getpass

from agent.prompts import VERIFY_PROMPT

class Operator:
    def __init__(self, model_name, vision):
        api_key = config.OLLAMA_API_KEY
        if not api_key:
            api_key = getpass(prompt="Enter Ollama API Key: ")

        self.client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )
        self.model_name = model_name
        self.vision = vision


    def think(self, messages):
        result = self.client.chat(model=self.model_name, messages=messages)
        raw = result["message"]["content"].strip()

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            step = json.loads(raw[start:end])
        except Exception:
            step = {}

        return step, raw

    def verify(self, goal, detected_element, step):
        payload = {
            "goal": goal,
            "detected_element": detected_element,
            "proposed_step": step
        }

        messages = [
            {"role": "system", "content": VERIFY_PROMPT},
            {"role": "user", "content": json.dumps(payload)}
        ]

        result = self.client.chat(model=self.model_name, messages=messages)
        raw = result["message"]["content"].strip()

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            verdict = json.loads(raw[start:end])
        except Exception:
            verdict = {"verdict": "reject", "reason": "Cannot parse verifier output"}

        return verdict

    def act(self, step: dict[str, str], elements):
        action = step.get("Next Action")
        box_id = step.get("Target_Box_ID")
        value = step.get("Value")

        x1, y1, x2, y2 = self.vision.locate(box_id, elements)
        coords = ((x1 + x2) // 2, (y1 + y2) // 2)

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