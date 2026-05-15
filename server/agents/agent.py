import base64, json, os, threading, time, traceback
import config, database as db
from ollama import Client
from PIL import Image, ImageOps
from config import RUNTIME_DIR
from prompts import TASK_PROMPT


MAX_HISTORY_LENGTH = 150
MAX_STEPS_PER_TASK = 100


def prepare_screenshot_for_ai(src, dst):
    try:
        img = Image.open(src)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((1000, 1000))
        img = img.convert("RGB")
        img.save(dst, "JPEG", quality=60, optimize=True)
        return dst
    except Exception:
        return src


def extract_json(text):
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


class Agent:
    def __init__(self, id, model, conn, security):
        self.id = id
        self.model = model
        self.conn = conn
        self.security = security

        self.agent_state = "idle"
        self.agent_activity_message = "Idle"

        self.task = None
        self.task_id = None

        self.step = {}
        self.history = []

        self.task_ready = threading.Event()

        self.screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}.png")
        self.ai_screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}_ai.jpg")
        os.makedirs(RUNTIME_DIR, exist_ok=True)

        self.ai = Client(
            host="https://ollama.com",
            headers={"Authorization": "Bearer " + (os.environ.get("OLLAMA_API_KEY") or "")}
        )

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
                    self.agent_activity_message = f"Recovered from error: {type(e).__name__}"
                    self.agent_state = "idle"
                    self.task = None
                    self.save()
                    continue

                if not keep:
                    break

                self.agent_state, self.agent_activity_message = "idle", "Idle"
                self.save()

        except Exception as e:
            print(f"[Agent {self.id}] Fatal: {e}\n{traceback.format_exc()}")

        finally:
            self.agent_state = "disconnected"
            print(f"[Agent {self.id}] Disconnected")
            try:
                self.conn.close()
            except Exception:
                pass


    def assign(self, task, task_id=None):
        self.task, self.task_id = task, task_id

        if not self.history:
            self.history = [
                {"role": "system", "content": TASK_PROMPT},
                {"role": "user", "content": f"Execute this task directly: {task}"}
            ]
        else:
            self.history.append({"role": "user", "content": f"New instruction: {task}"})

        self.agent_state, self.agent_activity_message = "working", "Starting..."
        self.save()

        self.task_ready.set()


    def run(self):
        steps = 0
        while self.task and self.agent_state not in ("stop_requested", "disconnect_requested", "idle", "clear_requested"):
            if steps >= MAX_STEPS_PER_TASK:
                print(f"[Agent {self.id}] Step limit reached ({MAX_STEPS_PER_TASK})")
                self.agent_state, self.agent_activity_message = "idle", "Step limit reached"
                self.task = None
                self.save()
                return True
            steps += 1

            # 1. Look
            self.agent_activity_message = "Looking..."
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
                "content": "Current screen:",
                "images": [b64]
            })


            # 2. Think
            self.agent_activity_message = "Thinking..."
            self.save()

            head = self.history[:2] if len(self.history) >= 2 else list(self.history)
            tail = self.history[2:][-MAX_HISTORY_LENGTH:] if len(self.history) > 2 else []
            messages = head + tail

            try:
                raw_text = ""
                for chunk in self.ai.chat(self.model, messages=messages, stream=True):
                    raw_text += chunk["message"]["content"] or ""
                    self.agent_activity_message = raw_text.replace("\n", " ")[:80]
                    self.save()
                raw_text = raw_text.strip()
            except Exception as e:
                print(f"[Agent {self.id}] AI error: {e}")
                self.agent_state = "idle"
                self.agent_activity_message = f"AI error: {type(e).__name__}"
                self.task = None
                self.save()
                return True

            response = extract_json(raw_text)
            print(response)
            if not isinstance(response, dict):
                print(f"[Agent {self.id}] Bad JSON, retrying...")
                self.history.append({"role": "assistant", "content": raw_text})
                self.history.append({"role": "user", "content": "Your response was not valid JSON. Reply with valid JSON only."})
                for _ in range(2):
                    try:
                        retry_text = ""
                        for chunk in self.ai.chat(self.model, messages=self.history, stream=True):
                            retry_text += chunk["message"]["content"] or ""
                            self.agent_activity_message = retry_text.replace("\n", " ")[:80]
                            self.save()
                        raw_text = retry_text.strip()
                        response = extract_json(raw_text)
                        if isinstance(response, dict):
                            break
                    except Exception:
                        break
                else:
                    response = {}

            self.step = {
                "agent_activity_message_short": str(response.get("Status", "Working..."))[:40],
                "reasoning": response.get("Reasoning", "") or "",
                "action": response.get("Next Action"),
                "coordinate": response.get("Coordinate"),
                "value": response.get("Value")
            }

            # Drop the screenshot image from the last user message to save memory
            self.history[-1] = {"role": "user", "content": "Current screen removed to save space"}

            self.history.append({"role": "assistant", "content": raw_text})


            # 3. Done check
            if self.step["action"] in (None, "None"):
                self.agent_state, self.agent_activity_message = "idle", "Done"
                self._finish_current_task()
                self.save()
                return True


            # 4. Act
            self.agent_activity_message = self.step["agent_activity_message_short"]
            self.save()

            cmd_step = {
                "Next Action": self.step["action"],
                "Coordinate": self.step["coordinate"],
                "Value": self.step["value"],
                "EndCoordinate": response.get("EndCoordinate")
            }

            execute_request = self.security.send(self.conn, {"type": "execute_step", "step": cmd_step})
            if not execute_request:
                return False

            data = self.security.recv(self.conn)
            result = json.loads(data) if data else {}

            if result.get("output"):
                self.history.append({"role": "user", "content": f"[Command output]:\n{result['output']}"})
                self.step["cmd_output"] = result["output"]

            self.save()
            time.sleep(0.1)


        if self.agent_state == "disconnect_requested":
            return False

        if self.agent_state != "stop_requested":
            self.task = None
            self.task_id = None

        if self.agent_state not in ("clear_requested", "stop_requested"):
            self.agent_state = "idle"
        elif self.agent_state == "stop_requested":
            self.agent_state = "idle"

        self.save()
        return True


    def save(self):
        try:
            db.update_agent(
                self.id,
                agent_state=self.agent_state,
                task=self.task,
                agent_activity_message=self.agent_activity_message,
                step_json=json.dumps(self.step, ensure_ascii=False))
        except Exception as error:
            print(f"[Agent {self.id}] Save error: {error}")


    def _finish_current_task(self):
        if not self.task_id:
            return

        try:
            db.mark_task_done(self.task_id)
        except Exception as error:
            print(f"[Agent {self.id}] Task finish error: {error}")
