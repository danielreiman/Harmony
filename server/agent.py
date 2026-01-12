import json
import os
import threading
import time
from ollama import Client
import config
from prompts import MAIN_PROMPT
from helpers import send, recv, recv_file

RUNTIME_DIR = "./runtime/"
MAX_HISTORY = 12
MAX_PHASE_STUCK = 5


class Agent:
    def __init__(self, id: str, model: str, conn):
        # Identity
        self.id = id
        self.model = model
        self.conn = conn

        # State
        self.status = "idle"
        self.task = None
        self.status_msg = "Idle"

        # Execution tracking
        self.cycles = 0
        self.phase = None
        self.phase_count = 0
        self.step = {}

        # AI conversation
        self.history = []

        # File paths
        self.screen_path = f"{RUNTIME_DIR}screenshot_{self.id}.png"
        self.state_path = f"{RUNTIME_DIR}{self.id}.soul"

        # Threading
        self.event = threading.Event()

        # Setup
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        api_key = config.OLLAMA_API_KEY
        if not api_key:
            raise RuntimeError("OLLAMA_API_KEY not found")
        self.ai = Client(host="https://ollama.com", headers={"Authorization": f"Bearer {api_key}"})
        self.save()

    def activate(self):
        try:
            while True:
                self.event.wait()
                self.event.clear()

                success = self.run()
                if not success:
                    break

                self.status = "idle"
                self.status_msg = "Idle"
                self.save()

        except Exception as e:
            print(f"[Agent {self.id}] Fatal error: {e}")
        finally:
            self.status = "disconnected"
            print(f"[Agent {self.id}] Disconnected")

    def assign(self, task: str):
        self.task = task
        self.status = "working"
        self.cycles = 0
        self.phase = None
        self.phase_count = 0

        self.history = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": f"Research this topic: {task}"}
        ]

        self.status_msg = "Starting..."
        self.save()
        self.event.set()
        print(f"[Agent {self.id}] Assigned: {task[:60]}...")

    def run(self) -> bool:
        while self.status == "working" and self.task:
            self.cycles += 1

            if not self.look():
                return False

            response = self.think()
            self.parse(response)

            if self.done():
                print(f"[Agent {self.id}] Completed in {self.cycles} cycles")
                return True

            if not self.act(response):
                return False

        return True

    def look(self) -> bool:
        self.status_msg = "Looking..."
        self.save()

        if not send({"type": "request_screenshot"}, self.conn):
            print(f"[Agent {self.id}] Failed to request screenshot")
            return False

        if not recv_file(self.screen_path, self.conn):
            print(f"[Agent {self.id}] Failed to receive screenshot")
            return False

        self.history.append({
            "role": "user",
            "content": "Current screen:",
            "images": [self.screen_path]
        })
        return True

    def think(self) -> dict:
        self.status_msg = "Thinking..."
        self.save()

        try:
            trimmed = self.history[:2] + self.history[-MAX_HISTORY:]
            result = self.ai.chat(model=self.model, messages=trimmed)
            raw = result["message"]["content"].strip()

            try:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start == -1 or end == 0:
                    raise ValueError("No JSON found")

                parsed = json.loads(raw[start:end])
                parsed["raw"] = raw

                if self.history and "images" in self.history[-1]:
                    self.history[-1].pop("images", None)

                self.history.append({"role": "assistant", "content": raw})
                return parsed

            except (json.JSONDecodeError, ValueError) as e:
                print(f"[Agent {self.id}] Parse error: {e}")
                return {
                    "Step": "SEARCH",
                    "Status": "Parse Error",
                    "Next Action": "None",
                    "Reasoning": str(e),
                    "raw": raw
                }
        except Exception as e:
            print(f"[Agent {self.id}] AI error: {e}")
            return {
                "Step": "SEARCH",
                "Status": "API Error",
                "Next Action": "None",
                "Reasoning": str(e),
                "raw": str(e)
            }

    def parse(self, response: dict):
        current_phase = response.get("Step", "SEARCH")

        self.step = {
            "phase": current_phase,
            "status_short": response.get("Status", "Working..."),
            "reasoning": response.get("Reasoning", ""),
            "action": response.get("Next Action"),
            "coordinate": response.get("Coordinate"),
            "value": response.get("Value")
        }

        if current_phase == self.phase:
            self.phase_count += 1
        else:
            self.phase = current_phase
            self.phase_count = 1

        if self.phase_count > MAX_PHASE_STUCK:
            hint = f"You've been on {current_phase} for {self.phase_count} actions. Move to next step. SEARCH→READ→WRITE→SEARCH."
            self.history.append({"role": "user", "content": hint})
            print(f"[Agent {self.id}] Stuck on {current_phase} for {self.phase_count} actions")

    def done(self) -> bool:
        action = self.step.get("action")
        if action in [None, "None"]:
            self.status = "idle"
            self.status_msg = "Done"
            self.save()
            return True
        return False

    def act(self, response: dict) -> bool:
        self.status_msg = self.step.get("status_short", "Acting...")
        self.save()

        cmd = {
            "Next Action": response.get("Next Action"),
            "Coordinate": response.get("Coordinate"),
            "Value": response.get("Value")
        }

        if not send({"type": "execute_step", "step": cmd}, self.conn):
            print(f"[Agent {self.id}] Failed to send action")
            return False

        result = recv(self.conn)
        if not result:
            print(f"[Agent {self.id}] Failed to receive result")
            return False

        success = result.get("success", False)
        self.step["success"] = success

        if not success:
            action = self.step.get("action", "unknown")
            print(f"[Agent {self.id}] Failed: {action}")
            self.history.append({
                "role": "user",
                "content": "Action failed. Tips: 1) Click text field BEFORE typing 2) Use correct coordinates 3) Maximize windows. Try again."
            })

        self.save()
        return True

    def save(self):
        data = {
            "id": self.id,
            "status": self.status,
            "task": self.task,
            "status_text": self.status_msg,
            "step": self.step,
            "cycle": self.cycles,
            "phase": self.phase,
            "phase_count": self.phase_count,
            "ts": time.time()
        }

        temp = self.state_path + ".tmp"
        try:
            with open(temp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(temp, self.state_path)
        except Exception as e:
            print(f"[Agent {self.id}] Save failed: {e}")
