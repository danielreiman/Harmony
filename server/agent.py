import time, json, threading, os
from ollama import Client

import config
from prompts import MAIN_PROMPT
from helpers import *

BASE_SCREENSHOT_DIR = "./runtime/"
MAX_HISTORY = 10

class Agent:
    def __init__(self, id, model_name, conn, cleanup_callback=None):
        self.id = id
        self.model_name = model_name
        self.conn = conn
        self.cleanup_callback = cleanup_callback

        self.status = "idle"
        self.task = None
        self.history = []

        self.status_text = "Idle"
        self.step = {}

        self.screenshot_path = f"{BASE_SCREENSHOT_DIR}/screenshot_{self.id}.png"
        self.event = threading.Event()

        os.makedirs(BASE_SCREENSHOT_DIR, exist_ok=True)
        self.state_path = f"{BASE_SCREENSHOT_DIR}/{self.id}.soul"

        api_key = config.OLLAMA_API_KEY
        if not api_key:
            print("No API key provided")
            exit(1)

        self.client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )

        self.broadcast("Idle")

    def activate(self):
        while True:
            try:
                self.event.wait()
                self.event.clear()
                if not self.run(): break
                self.status = "idle"
            except: break
        self.cleanup()

    def assign(self, task: str):
        self.task = task
        self.status = "working"
        self.history = [
            {"role": "system", "content": MAIN_PROMPT},
            {"role": "user", "content": f"Goal: {task}"}
        ]
        self.broadcast("Task assigned")
        self.event.set()

    def run(self):
        while self.status == "working" and self.task:
            # =========== Vision ===========
            self.broadcast("Looking...")
            request_sent = send({"type": "request_screenshot"}, self.conn)
            if not request_sent:
                return False

            screenshot_received = recv_file(self.screenshot_path, self.conn)
            if not screenshot_received:
                return False

            self.history.append({"role": "user", "content": "Current view", "images": [self.screenshot_path]})

            # =========== Brain ===========
            self.broadcast("Thinking...")
            step, raw_ai_message = self.think(self.history)
            
            if self.history and "images" in self.history[-1]:
                self.history[-1].pop("images", None)
            self.history.append({"role": "assistant", "content": raw_ai_message})

            self.step = {"reasoning": step.get("Reasoning"), "action": step.get("Next Action"), "coordinate": step.get("Coordinate"), "value": step.get("Value")}

            if self.step["action"] in [None, "None"]:
                self.status = "idle"
                self.broadcast("Done")
                return True

            # =========== Execution ===========
            self.broadcast("Executing...")
            step_sent = send({"type": "execute_step", "step": step}, self.conn)
            if not step_sent:
                return False

            response = recv(self.conn)
            if not response: return False

            self.step["success"] = response.get("success", False)
            self.broadcast(self.status_text)
            time.sleep(1)
        
        self.broadcast("Program finished")
        return True

    def think(self, messages):
        trimmed = messages[:2] + messages[-MAX_HISTORY:]
        result = self.client.chat(model=self.model_name, messages=trimmed)
        raw = result["message"]["content"].strip()

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            step = json.loads(raw[start:end])
        except Exception:
            step = {}

        return step, raw

    def broadcast(self, status_text=None):
        if status_text is not None:
            self.status_text = status_text

        data = {
            "id": self.id,
            "status": self.status,
            "task": self.task,
            "status_text": self.status_text,
            "step": self.step,
            "ts": time.time()
        }

        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        os.replace(tmp, self.state_path)


    def cleanup(self):
        try:
            if os.path.exists(self.state_path):
                os.remove(self.state_path)
            if os.path.exists(self.screenshot_path):
                os.remove(self.screenshot_path)
        except Exception as e:
            print(f"[Agent {self.id}] Cleanup error: {e}")
        
        if self.cleanup_callback:
            self.cleanup_callback(self.id)

