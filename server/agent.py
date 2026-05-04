import base64, json, os, threading, time, traceback, config, database as db
from openai import OpenAI
from config import RUNTIME_DIR
from prompts import TASK_PROMPT
from helpers import extract_json, prepare_screenshot_for_ai

MAX_HISTORY_LENGTH = 150


class Agent:
    def __init__(self, id, model, conn, security):
        self.id = id
        self.model = model
        self.conn = conn
        self.security = security
        self.status = "idle"
        self.task = None
        self.task_id = None
        self.status_msg = "Idle"
        self.step = {}
        self.history = []
        self.task_ready = threading.Event()
        self.screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}.png")
        self.ai_screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}_ai.jpg")
        os.makedirs(RUNTIME_DIR, exist_ok=True)

        api_key = config.HAI_API_KEY
        if not api_key: raise RuntimeError("HAI_API_KEY not found")
        self.ai = OpenAI(api_key=api_key, base_url="https://api.hcompany.ai/v1/")
        self.save()

    def activate(self):
        self.security.send(self.conn, {"type": "connected", "agent_id": self.id})
        print(f"[Agent {self.id}] Ready")
        try:
            while True:
                self.task_ready.wait()
                self.task_ready.clear()
                try:
                    keep = self.run()
                except Exception as e:
                    print(f"[Agent {self.id}] Step error: {e}")
                    self.status_msg = f"Recovered from error: {type(e).__name__}"
                    self.status = "idle"
                    self.task = None
                    self.save()
                    continue
                if not keep: break
                self.status, self.status_msg = "idle", "Idle"
                self.save()
        except Exception as e:
            print(f"[Agent {self.id}] Fatal: {e}\n{traceback.format_exc()}")
        finally:
            self.status = "disconnected"
            print(f"[Agent {self.id}] Disconnected")
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

            request_screenshot = self.security.send(self.conn, {"type": "request_screenshot"})
            if not request_screenshot:
                return False

            screen_bytes = self.security.recv(self.conn)
            if not screen_bytes:
                return False

            with open(self.screen_path, "wb") as f:
                f.write(screen_bytes)

            ai_screen_path = prepare_screenshot_for_ai(self.screen_path, self.ai_screen_path)
            with open(ai_screen_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")

            self.history.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "Current screen:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            })

            # 2. Think
            self.status_msg = "Thinking..."
            self.save()
            head = self.history[:2] if len(self.history) >= 2 else list(self.history)
            tail = self.history[2:][-MAX_HISTORY_LENGTH:] if len(self.history) > 2 else []
            messages = head + tail

            try:
                response = self.ai.chat.completions.create(model=self.model, messages=messages)
                raw_text = (response.choices[0].message.content or "").strip()
            except Exception as e:
                print(f"[Agent {self.id}] AI error: {e}")
                self.status = "idle"
                self.status_msg = f"AI error: {type(e).__name__}"
                self.task = None
                self.save()
                return True

            response = extract_json(raw_text)
            if not isinstance(response, dict):
                response = {}
            self.step = {
                "status_short": str(response.get("Status", "Working..."))[:40],
                "reasoning": response.get("Reasoning", "") or "",
                "action": response.get("Next Action"),
                "coordinate": response.get("Coordinate"),
                "value": response.get("Value")
            }

            # Drop the screenshot image from the last user message to save memory
            if self.history and isinstance(self.history[-1]["content"], list):
                self.history[-1]["content"] = "Current screen removed to save space"

            self.history.append({"role": "assistant", "content": raw_text})

            # 3. Done check
            if self.step["action"] in (None, "None"):
                self.status, self.status_msg = "idle", "Done"
                self._finish_current_task()
                self.save()
                return True

            # 4. Act
            self.status_msg = self.step["status_short"]
            self.save()
            cmd_step = {
                "Next Action": self.step["action"], "Coordinate": self.step["coordinate"],
                "Value": self.step["value"], "EndCoordinate": response.get("EndCoordinate")
            }

            execute_request = self.security.send(self.conn, {"type": "execute_step", "step": cmd_step})
            if not execute_request: return False

            data = self.security.recv(self.conn)
            result = json.loads(data) if data else {}
            if result.get("output"):
                self.history.append({"role": "user", "content": f"[Command output]:\n{result['output']}"})
                self.step["cmd_output"] = result["output"]

            self.save()
            time.sleep(0.1)
        if self.status == "disconnect_requested":
            return False

        self.task = None
        self.task_id = None
        if self.status != "clear_requested":
            self.status = "idle"
        self.save()
        return True

    def save(self):
        try:
            db.update_agent(self.id, status=self.status, task=self.task,
                           status_text=self.status_msg,
                           step_json=json.dumps(self.step, ensure_ascii=False))
        except: pass

    def _finish_current_task(self):
        if not self.task_id:
            return
        try:
            db.mark_task_done(self.task_id)
        except Exception as error:
            print(f"[Agent {self.id}] Task finish error: {error}")
