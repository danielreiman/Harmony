import os, threading, json, time
from ollama import Client

import config
from config import RUNTIME_DIR
from prompts import TASK_PROMPT
from helpers import send, recv, receive_file, extract_json
import database as db

MAX_HISTORY_LENGTH = 30

class Agent:
    def __init__(self, id, model, conn):
        self.id = id
        self.model = model
        self.conn = conn

        self.status = "idle"
        self.task = None
        self.task_id = None

        self.status_msg = "Idle"

        self.step = {}
        self.history = []

        self.task_ready = threading.Event()

        self.screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}.png")
        os.makedirs(RUNTIME_DIR, exist_ok=True)

        api_key = config.OLLAMA_API_KEY
        if not api_key:
            raise RuntimeError("OLLAMA_API_KEY not found")

        self.ai = Client(host="https://ollama.com", headers={"Authorization": f"Bearer {api_key}"})
        self.save()

    def activate(self):
        send({"type": "connected", "agent_id": self.id}, self.conn)

        try:
            while True:
                self.task_ready.wait()
                self.task_ready.clear()

                if not self.run(): break

                self.status = "idle"
                self.status_msg = "Idle"
                self.save()

        except Exception as error:
            print(f"[Agent {self.id}] Fatal error: {error}")
        finally:
            self.status = "disconnected"
            print(f"[Agent {self.id}] Disconnected")
            try:
                self.conn.close()
            except OSError:
                pass

    def assign(self, task, task_id=None):
        self.task = task
        self.task_id = task_id

        self.history = [
            {"role": "system", "content": TASK_PROMPT},
            {"role": "user", "content": f"Execute this task directly: {task}"}
        ]
        self.status = "working"
        self.status_msg = "Starting..."
        self.save()

        self.task_ready.set()

        print(f"[Agent {self.id}] Assigned: {task[:60]}...")

    def run(self):
        while self.task and self.status not in ("stop_requested", "disconnect_requested", "idle"):
            self.status = "working"
            if not self.look():
                return False

            ai_response = self.think()
            self.parse(ai_response)

            if self.done():
                print(f"[Agent {self.id}] Completed")
                return True

            if not self.act(ai_response):
                return False

            time.sleep(1)

        return False

    def look(self):
        self.status = "Looking..."
        self.save()

        if not send({"type": "request_screenshot"}, self.conn):
            print(f"[Agent {self.id}] Failed to request screenshot")
            return False

        if not receive_file(self.screen_path, self.conn):
            print(f"[Agent {self.id}] Failed to receive screenshot")
            return False

        self.history.append({
            "role": "user",
            "content": "Current screen:",
            "images": [self.screen_path]
        })

        return True

    def think(self):
        self.status = "Thinking..."
        self.save()

        initial_messages = self.history[:2]
        recent_messages = self.history[2:][-MAX_HISTORY_LENGTH:]
        messages = initial_messages + recent_messages

        try:
            result = self.ai.chat(model=self.model, messages=messages)
            raw_text = result["message"]["content"].strip()
        except Exception as e:
            print(f"[Agent {self.id}] AI call failed: {e}")
            return {}

        json_response_as_dict = extract_json(raw_text) or {}

        last_message = self.history[-1]
        if last_message and "images" in last_message:
            last_message.pop("images")

        self.history.append({"role": "assistant", "content": raw_text})

        return json_response_as_dict

    def parse(self, ai_response):
        self.step = {
            "phase": ai_response.get("Step", ""),
            "status_short": ai_response.get("Status", "Working..."),
            "reasoning": ai_response.get("Reasoning", ""),
            "action": ai_response.get("Next Action"),
            "coordinate": ai_response.get("Coordinate"),
            "value": ai_response.get("Value")
        }

    def done(self):
        is_done = self.step.get("action") in (None, "None")

        if is_done:
            self.status = "idle"
            self.status_msg = "Done"
            self.save()
            return True

        return False

    def act(self, ai_response):
        self.status_msg = self.step.get("status_short", "Acting...")
        self.save()

        action = ai_response.get("Next Action")
        value = ai_response.get("Value")
        coordinate = ai_response.get("Coordinate")

        command_step = {"Next Action": action, "Coordinate": coordinate, "Value": value}
        if not send({"type": "execute_step", "step": command_step}, self.conn):
            print(f"[Agent {self.id}] Failed to send action")
            return False

        recv(self.conn)
        self.save()

        return True

    def save(self):
        step_json = json.dumps(self.step, ensure_ascii=False) if self.step else None
        try:
            db.update_agent(
                self.id,
                status=self.status,
                task=self.task,
                status_text=self.status_msg,
                step_json=step_json,
            )
        except Exception as error:
            print(f"[Agent {self.id}] Database update failed: {error}")
