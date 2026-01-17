import json
import os
import threading
import time
from ollama import Client
import config
from google_docs import DocManager
from prompts import RESEARCH_PROMPT, TASK_PROMPT
from helpers import send, recv, recv_file

RUNTIME_DIR = "./runtime/"
MAX_HISTORY = 12
MAX_PHASE_STUCK = 2


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
        self.last_click = None
        self.last_action = None

        # AI conversation
        self.history = []

        # Mode and collaboration target
        self.research_mode = False
        self.doc_id = None

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
        self.docs = DocManager(config.GOOGLE_SERVICE_ACCOUNT_FILE)
        self.save()

    def _handle_doc_action(self, action: str, value, coordinate) -> bool:
        if not self.research_mode:
            return True

        doc_id = self.doc_id
        if not doc_id:
            return True

        try:
            if action == "read_doc":
                doc_snapshot = self.docs.read(doc_id)
                doc_text = doc_snapshot.get("text", "")
                summary = f"DOC_READ_RESULT ({doc_id}):\n{doc_text}"
                self.history.append({"role": "user", "content": summary})
                self.status_msg = "Doc read complete"
            else:
                text_input = ""
                insert_index = None
                if isinstance(value, dict):
                    text_input = value.get("text", "") or ""
                    insert_index = value.get("index")
                else:
                    text_input = "" if value is None else str(value)
                if not text_input.strip():
                    return True
                result = self.docs.write(doc_id, text_input, index=insert_index)
                summary = f"DOC_WRITE_RESULT ({doc_id}): wrote {result['written']} chars."
                self.history.append({"role": "user", "content": summary})
                self.status_msg = "Doc write complete"

            self.step["success"] = True
            self.save()
            return True

        except Exception as e:
            self.history.append({"role": "user", "content": f"DOC_ACTION_ERROR: {e}"})
            self.step["success"] = False
            self.status_msg = "Doc action failed"
            self.save()
            return True

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

    def assign(self, task: str, research_mode: bool = False, doc_id: str = None):
        self.task = task
        self.status = "working"
        self.cycles = 0
        self.phase = None
        self.phase_count = 0
        self.research_mode = research_mode
        self.doc_id = doc_id

        if research_mode:
            prompt = RESEARCH_PROMPT
            user_msg = (
                f"Research this topic and document findings with proper structure: {task}\n"
                "Use read_doc/write_doc actions"
            )
        else:
            prompt = TASK_PROMPT
            user_msg = f"Execute this task directly (no research needed): {task}"

        self.history = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_msg}
        ]

        mode_text = "research" if research_mode else "task"
        self.status_msg = "Starting..."
        self.save()
        self.event.set()
        print(f"[Agent {self.id}] Assigned ({mode_text}): {task[:60]}...")

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

            time.sleep(1)
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
            initial_messages = self.history[:2]
            recent_messages = self.history[-MAX_HISTORY:]
            messages = initial_messages + recent_messages

            chat_result = self.ai.chat(model=self.model, messages=messages)
            raw_text = chat_result["message"]["content"].strip()

            try:
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start == -1 or end == 0:
                    raise ValueError("No JSON found")

                parsed = json.loads(raw_text[start:end])
                parsed["raw"] = raw_text

                print(f"[Agent {self.id}] AI response: {raw_text}")

                if self.history and "images" in self.history[-1]:
                    self.history[-1].pop("images", None)

                self.history.append({"role": "assistant", "content": raw_text})
                return parsed

            except (json.JSONDecodeError, ValueError) as e:
                print(f"[Agent {self.id}] Parse error: {e}")
                return {
                    "Step": "SEARCH",
                    "Status": "Parse Error",
                    "Next Action": "None",
                    "Reasoning": str(e),
                    "raw": raw_text
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
            hint = (
                f"You've been on {current_phase} for {self.phase_count} actions. "
                "Stop repeating the same action; switch phases (SEARCH→READ→WRITE→SEARCH). "
                "Do not repeat identical searches—move to notes and write_doc."
            )
            self.history.append({"role": "user", "content": hint})
            print(f"[Agent {self.id}] Stuck on {current_phase} for {self.phase_count} actions")

    def done(self) -> bool:
        action_name = self.step.get("action")
        if action_name in [None, "None"]:
            self.status = "idle"
            self.status_msg = "Done"
            self.save()
            return True
        return False

    def act(self, response: dict) -> bool:
        self.status_msg = self.step.get("status_short", "Acting...")
        self.save()

        action = response.get("Next Action")
        value = response.get("Value")
        coordinate = response.get("Coordinate")

        if action in {"read_doc", "write_doc"}:
            return self._handle_doc_action(action, value, coordinate)

        command_payload = {
            "Next Action": action,
            "Coordinate": coordinate,
            "Value": value
        }

        if not send({"type": "execute_step", "step": command_payload}, self.conn):
            print(f"[Agent {self.id}] Failed to send action")
            return False

        result = recv(self.conn)
        if not result:
            print(f"[Agent {self.id}] Failed to receive result")
            return False

        success = result.get("success", False)
        self.step["success"] = success

        self.save()
        return True

    def save(self):
        data = {
            "id": self.id,
            "status": self.status,
            "task": self.task,
            "status_text": self.status_msg,
            "research_mode": self.research_mode,
            "doc_id": self.doc_id,
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
