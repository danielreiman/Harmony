import time, json
from ollama import Client
import config
from prompts import MAIN_PROMPT
from helpers import *

BASE_SCREENSHOT_DIR = "server/runtime/"
MAX_HISTORY = 10

class Agent:
    def __init__(self,id, model_name, conn):
        self.id = id
        self.model_name = model_name
        self.conn = conn
        self.status = "ready"
        self.history = [
            {"role": "system", "content": MAIN_PROMPT}
        ]
        self.screenshot_path = f"{BASE_SCREENSHOT_DIR}/screenshot_{self.id}.png"
        self.task = None

        api_key = config.OLLAMA_API_KEY
        if not api_key:
            print("No API key provided")
            exit(1)

        self.client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )

    def assign(self, task: str):
        self.task = task
        self.status = "working"

        self.history.append({
            "role": "user",
            "content": f"Goal: {task}"
        })

        self.run()

    def run(self):
        self.status = "working"

        while self.status == "working" and self.task:
            # ================= VISION =================
            send({"type": "request_screenshot"}, self.conn)
            recv_file(self.screenshot_path, self.conn)

            self.history.append({
                "role": "user",
                "content": "Current view",
                "images": [self.screenshot_path]
            })

            # ================= AI =================
            step, raw_ai_message = self.think(self.history)

            if self.history and "images" in self.history[-1]:
                self.history[-1].pop("images", None)

            self.history.append({"role": "assistant", "content": raw_ai_message})

            if step.get("Next Action") in [None, "None"]:
                self.status = "idle"
                break

            # ================= EXECUTION AND FEEDBACK =================
            send({
                "type": "execute_step",
                "step": step
            })

            response = recv(self.conn)
            success = response.get("success", False)
            self.history.append({
                "role": "user",
                "content": f"System feedback: {success}"
            })

            time.sleep(1)

        print("[LOG] Program finished.")

    def think(self, messages):
        trimmed = [messages[:2]] + messages[-MAX_HISTORY:]

        result = self.client.chat(model=self.model_name, messages=trimmed)
        raw = result["message"]["content"].strip()

        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            step = json.loads(raw[start:end])
        except Exception:
            step = {}

        return step, raw
