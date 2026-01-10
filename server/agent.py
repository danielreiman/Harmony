import time, json, threading, os
from ollama import Client

import config
from prompts import MAIN_PROMPT
from helpers import send, recv, recv_file

BASE_SCREENSHOT_DIR = "./runtime/"
MAX_HISTORY = 12


class Agent:
    def __init__(self, id, model_name, conn):
        self.id = id
        self.model_name = model_name
        self.conn = conn

        self.status = "idle"
        self.task = None
        self.history = []

        self.status_text = "Idle"
        self.step = {}
        self.cycle_count = 0

        self.screenshot_path = f"{BASE_SCREENSHOT_DIR}screenshot_{self.id}.png"
        self.event = threading.Event()

        os.makedirs(BASE_SCREENSHOT_DIR, exist_ok=True)
        self.state_path = f"{BASE_SCREENSHOT_DIR}{self.id}.soul"

        api_key = config.OLLAMA_API_KEY
        if not api_key:
            raise RuntimeError("No OLLAMA_API_KEY provided")

        self.client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        self.broadcast()

    def activate(self):
        try:
            while True:
                self.event.wait()
                self.event.clear()
                if not self.run():
                    break
                self.status = "idle"
                self.status_text = "Idle"
                self.broadcast()
        except Exception as e:
            print(f"[Agent {self.id}] Error: {e}")
        finally:
            self.status = "disconnected"

    def assign(self, task: str):
        self.task = task
        self.status = "working"
        self.cycle_count = 0
        self.history = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": f"Research task: {task}"}
        ]
        self.status_text = "Starting..."
        self.broadcast()
        self.event.set()
        print(f"[Agent {self.id}] Task: {task[:60]}...")

    def run(self):
        while self.status == "working" and self.task:
            self.cycle_count += 1

            # ===== Capture Screen =====
            self.status_text = "Looking..."
            self.broadcast()

            if not send({"type": "request_screenshot"}, self.conn):
                return False

            if not recv_file(self.screenshot_path, self.conn):
                return False

            self.history.append({
                "role": "user",
                "content": "Current screen:",
                "images": [self.screenshot_path]
            })

            # ===== Think =====
            self.status_text = "Thinking..."
            self.broadcast()

            ai_response = self.think()

            # Remove image from history to save context
            if self.history and "images" in self.history[-1]:
                self.history[-1].pop("images", None)
            self.history.append({"role": "assistant", "content": ai_response["raw"]})

            # Parse response
            self.step = {
                "status_short": ai_response.get("Status", "Working..."),
                "reasoning": ai_response.get("Reasoning", ""),
                "action": ai_response.get("Next Action"),
                "coordinate": ai_response.get("Coordinate"),
                "value": ai_response.get("Value")
            }

            # Check completion
            if self.step["action"] in [None, "None"]:
                self.status_text = "Done"
                self.status = "idle"
                self.broadcast()
                print(f"[Agent {self.id}] Completed after {self.cycle_count} cycles")
                return True

            # ===== Execute =====
            self.status_text = self.step.get("status_short", "Executing...")
            self.broadcast()

            # Send only fields client expects
            client_step = {
                "Next Action": ai_response.get("Next Action"),
                "Coordinate": ai_response.get("Coordinate"),
                "Value": ai_response.get("Value")
            }

            if not send({"type": "execute_step", "step": client_step}, self.conn):
                return False

            response = recv(self.conn)
            if not response:
                return False

            success = response.get("success", False)
            self.step["success"] = success

            # Provide feedback on failure
            if not success:
                action = self.step.get("action", "")
                print(f"[Agent {self.id}] Action failed: {action}")
                self.history.append({
                    "role": "user",
                    "content": f"The action failed. If you tried to type, make sure you clicked on a text field first. Try again."
                })

            self.broadcast()

        return True

    def think(self):
        try:
            # Keep system prompt + task + recent history
            trimmed = self.history[:2] + self.history[-MAX_HISTORY:]

            result = self.client.chat(model=self.model_name, messages=trimmed)
            raw = result["message"]["content"].strip()

            # Parse JSON
            try:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                parsed = json.loads(raw[start:end])
                parsed["raw"] = raw
                return parsed
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[Agent {self.id}] Parse error: {e}")
                return {
                    "Status": "Parse error",
                    "Next Action": "None",
                    "Reasoning": str(e),
                    "raw": raw
                }

        except Exception as e:
            print(f"[Agent {self.id}] API error: {e}")
            return {
                "Status": "API error",
                "Next Action": "None",
                "Reasoning": str(e),
                "raw": str(e)
            }

    def broadcast(self):
        data = {
            "id": self.id,
            "status": self.status,
            "task": self.task,
            "status_text": self.status_text,
            "step": self.step,
            "cycle": self.cycle_count,
            "ts": time.time()
        }

        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, self.state_path)
