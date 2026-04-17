import os, threading, json, time
from ollama import Client

import config
from config import RUNTIME_DIR
from prompts import TASK_PROMPT
from helpers import send, recv, receive_file, extract_json
import database as db

MAX_HISTORY_LENGTH = 150

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
        if not api_key: raise RuntimeError("OLLAMA_API_KEY not found")
        self.ai = Client(host="https://ollama.com", headers={"Authorization": f"Bearer {api_key}"})
        self.save()

    def activate(self):
        send({"type": "connected", "agent_id": self.id}, self.conn)
        try:
            while True:
                self.task_ready.wait()
                self.task_ready.clear()
                if not self.run(): break
                self.status, self.status_msg = "idle", "Idle"
                self.save()
        except Exception as e:
            print(f"[Agent {self.id}] Error: {e}")
        finally:
            self.status = "disconnected"
            try: self.conn.close()
            except: pass

    def assign(self, task, task_id=None):
        self.task, self.task_id = task, task_id
        if not self.history:
            self.history = [
                {"role": "system", "content": TASK_PROMPT},
                {"role": "user", "content": f"Execute this task directly: {task}"}
            ]
        else:
            self.history.append({"role": "user", "content": f"New instruction: {task}"})
        
        self.status, self.status_msg = "working", "Starting..."
        self.save()
        self.task_ready.set()

    def run(self):
        while self.task and self.status not in ("stop_requested", "disconnect_requested", "idle", "clear_requested"):
            # 1. Look
            self.status_msg = "Looking..."
            self.save()
            if not send({"type": "request_screenshot"}, self.conn): return False
            if not receive_file(self.screen_path, self.conn): return False
            
            self.history.append({"role": "user", "content": "Current screen:", "images": [self.screen_path]})

            # 2. Think
            self.status_msg = "Thinking..."
            self.save()
            messages = self.history[:2] + self.history[2:][-MAX_HISTORY_LENGTH:]
            try:
                raw_text = self.ai.chat(model=self.model, messages=messages)["message"]["content"].strip()
            except Exception as e:
                print(f"[Agent] AI Error: {e}")
                return False
                
            res = extract_json(raw_text) or {}
            self.step = {
                "status_short": res.get("Status", "Working..."),
                "reasoning": res.get("Reasoning", ""),
                "action": res.get("Next Action"),
                "coordinate": res.get("Coordinate"),
                "value": res.get("Value")
            }

            # Cleanup images from history to save tokens/memory
            if self.history[-1].get("images"): self.history[-1].pop("images")
            self.history.append({"role": "assistant", "content": raw_text})

            # 3. Done check
            if self.step["action"] in (None, "None"):
                self.status, self.status_msg = "idle", "Done"
                self.save()
                return True

            # 4. Act
            self.status_msg = self.step["status_short"]
            self.save()
            cmd_step = {
                "Next Action": self.step["action"], "Coordinate": self.step["coordinate"],
                "Value": self.step["value"], "EndCoordinate": res.get("EndCoordinate")
            }
            if not send({"type": "execute_step", "step": cmd_step}, self.conn): return False
            
            result = recv(self.conn) or {}
            if result.get("output"):
                self.history.append({"role": "user", "content": f"[Command output]:\n{result['output']}"})
                self.step["cmd_output"] = result["output"]

            self.save()
            time.sleep(0.1)
        return False

    def save(self):
        try:
            db.update_agent(self.id, status=self.status, task=self.task, 
                           status_text=self.status_msg, 
                           step_json=json.dumps(self.step, ensure_ascii=False))
        except: pass
