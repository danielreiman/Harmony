import json
import os
import threading
import time
from ollama import Client
import config
from google_docs import DocManager
from prompts import RESEARCH_PROMPT, TASK_PROMPT
from helpers import send, recv, recv_file
import database as db

RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")
MAX_HISTORY_LENGTH = 30
MAX_CYCLES_IN_SAME_PHASE = 2


class Agent:
    def __init__(self, id: str, model: str, conn):
        self.id = id
        self.model = model
        self.conn = conn

        self.status = "idle"
        self.task = None
        self.status_msg = "Idle"

        self.cycles = 0
        self.phase = None
        self.phase_count = 0
        self.step = {}
        self.history = []

        self.research_mode = False
        self.doc_id = None
        self.doc_read = False

        self.screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}.png")
        self.state_path = os.path.join(RUNTIME_DIR, f"{self.id}.soul")
        self.task_ready = threading.Event()

        os.makedirs(RUNTIME_DIR, exist_ok=True)

        api_key = config.OLLAMA_API_KEY
        if not api_key:
            raise RuntimeError("OLLAMA_API_KEY not found")

        self.ai = Client(host="https://ollama.com", headers={"Authorization": f"Bearer {api_key}"})
        self.docs = DocManager(config.GOOGLE_SERVICE_ACCOUNT_FILE)
        self.save()

    def activate(self):
        try:
            while True:
                self.task_ready.wait()
                self.task_ready.clear()

                task_completed_successfully = self.run()
                if not task_completed_successfully:
                    break

                self.status = "idle"
                self.status_msg = "Idle"
                self.save()

        except Exception as error:
            print(f"[Agent {self.id}] Fatal error: {error}")
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
        self.doc_read = False

        if research_mode:
            system_prompt = RESEARCH_PROMPT
            user_message = (
                f"Research this topic and document findings with proper structure: {task}\n"
                "Use read_doc/write_doc actions"
            )
        else:
            system_prompt = TASK_PROMPT
            user_message = f"Execute this task directly (no research needed): {task}"

        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        mode_label = "research" if research_mode else "task"
        self.status_msg = "Starting..."
        self.save()
        self.task_ready.set()
        print(f"[Agent {self.id}] Assigned ({mode_label}): {task[:60]}...")

    def run(self) -> bool:
        while self.status == "working" and self.task:
            self.cycles += 1

            screenshot_received = self.look()
            if not screenshot_received:
                return False

            ai_response = self.think()
            self.parse(ai_response)

            if self.done():
                print(f"[Agent {self.id}] Completed in {self.cycles} cycles")
                return True

            action_succeeded = self.act(ai_response)
            if not action_succeeded:
                return False

            time.sleep(1)

        return True

    def look(self) -> bool:
        self.status_msg = "Looking..."
        self.save()

        screenshot_requested = send({"type": "request_screenshot"}, self.conn)
        if not screenshot_requested:
            print(f"[Agent {self.id}] Failed to request screenshot")
            return False

        screenshot_received = recv_file(self.screen_path, self.conn)
        if not screenshot_received:
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
            return self._call_ai()
        except Exception as error:
            print(f"[Agent {self.id}] AI error: {error}")
            return self._fallback_response(str(error))

    def _call_ai(self) -> dict:
        initial_messages = self.history[:2]
        recent_messages = self.history[2:][-MAX_HISTORY_LENGTH:]
        messages = initial_messages + recent_messages

        result = self.ai.chat(model=self.model, messages=messages)
        raw_text = result["message"]["content"].strip()

        print(f"[Agent {self.id}] AI response: {raw_text}")

        parsed = self._extract_json(raw_text)
        if parsed is None:
            return self._fallback_response("No valid JSON found in AI response")

        parsed["raw"] = raw_text
        self._append_ai_response_to_history(raw_text)
        return parsed

    def _extract_json(self, text: str) -> dict | None:
        json_start = text.find("{")
        json_end = text.rfind("}") + 1

        no_json_found = json_start == -1 or json_end == 0
        if no_json_found:
            return None

        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            return None

    def _append_ai_response_to_history(self, raw_text: str):
        last_message = self.history[-1] if self.history else None
        last_message_has_images = last_message and "images" in last_message
        if last_message_has_images:
            last_message.pop("images")
        self.history.append({"role": "assistant", "content": raw_text})

    def _fallback_response(self, error_detail: str) -> dict:
        current_phase = self.phase or "EXECUTE"
        return {
            "Step": current_phase,
            "Status": "Error",
            "Next Action": "None",
            "Reasoning": error_detail,
            "raw": error_detail
        }

    def parse(self, ai_response: dict):
        current_phase = ai_response.get("Step", "SEARCH")

        self.step = {
            "phase": current_phase,
            "status_short": ai_response.get("Status", "Working..."),
            "reasoning": ai_response.get("Reasoning", ""),
            "action": ai_response.get("Next Action"),
            "coordinate": ai_response.get("Coordinate"),
            "value": ai_response.get("Value")
        }

        phase_changed = current_phase != self.phase
        if phase_changed:
            self.phase = current_phase
            self.phase_count = 1
        else:
            self.phase_count += 1

        agent_is_stuck = self.phase_count > MAX_CYCLES_IN_SAME_PHASE
        if agent_is_stuck:
            stuck_hint = (
                f"You've been on {current_phase} for {self.phase_count} actions. "
                "Stop repeating the same action; switch phases (SEARCH→READ→WRITE→SEARCH). "
                "Do not repeat identical searches—move to notes and write_doc."
            )
            self.history.append({"role": "user", "content": stuck_hint})
            print(f"[Agent {self.id}] Stuck on {current_phase} for {self.phase_count} actions")

    def done(self) -> bool:
        action_name = self.step.get("action")
        is_done = action_name in (None, "None")

        if is_done:
            self.status = "idle"
            self.status_msg = "Done"
            self.save()

        return is_done

    def act(self, ai_response: dict) -> bool:
        self.status_msg = self.step.get("status_short", "Acting...")
        self.save()

        action = ai_response.get("Next Action")
        value = ai_response.get("Value")
        coordinate = ai_response.get("Coordinate")

        is_doc_action = action in {"read_doc", "write_doc"}
        if is_doc_action:
            return self._handle_doc_action(action, value)

        return self._send_action_to_client(action, coordinate, value)

    def _send_action_to_client(self, action: str, coordinate, value) -> bool:
        command = {"Next Action": action, "Coordinate": coordinate, "Value": value}
        sent = send({"type": "execute_step", "step": command}, self.conn)
        if not sent:
            print(f"[Agent {self.id}] Failed to send action")
            return False

        result = recv(self.conn)
        if not result:
            print(f"[Agent {self.id}] Failed to receive result")
            return False

        self.step["success"] = result.get("success", False)
        self.save()
        return True

    def _handle_doc_action(self, action: str, value) -> bool:
        if not self.research_mode or not self.doc_id:
            return True

        try:
            if action == "read_doc":
                return self._read_doc()
            else:
                return self._write_doc(value)
        except Exception as error:
            self.history.append({"role": "user", "content": f"DOC_ACTION_ERROR: {error}"})
            self.step["success"] = False
            self.status_msg = "Doc action failed"
            self.save()
            return True

    def _read_doc(self) -> bool:
        snapshot = self.docs.read(self.doc_id)
        doc_text = snapshot.get("text", "")
        self.history.append({"role": "user", "content": f"DOC_READ_RESULT ({self.doc_id}):\n{doc_text}"})
        self.status_msg = "Doc read complete"
        self.doc_read = True
        self.step["success"] = True
        self.save()
        return True

    def _write_doc(self, payload) -> bool:
        if not self.doc_read:
            self._auto_read_doc_before_write()

        insert_index = None
        dedupe = None
        if isinstance(payload, dict):
            insert_index = payload.get("index")
            dedupe = payload.get("dedupe")

        write_result = self.docs.write(self.doc_id, payload, index=insert_index, dedupe=dedupe)

        skipped = write_result.get("skipped")
        chars_written = write_result.get("written", 0)
        updates_applied = write_result.get("replies") or []

        if skipped:
            write_summary = "skipped duplicate"
        elif chars_written:
            write_summary = f"wrote {chars_written} chars"
        elif updates_applied:
            write_summary = f"applied {len(updates_applied)} updates"
        else:
            write_summary = "write complete"

        self.history.append({"role": "user", "content": f"DOC_WRITE_RESULT ({self.doc_id}): {write_summary}."})
        self.status_msg = "Doc write complete"
        self.step["success"] = True
        self.save()
        return True

    def _auto_read_doc_before_write(self):
        snapshot = self.docs.read(self.doc_id)
        doc_text = snapshot.get("text", "")
        self.history.append({"role": "user", "content": f"DOC_AUTO_READ ({self.doc_id}):\n{doc_text}"})
        self.doc_read = True

    def save(self):
        state = {
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
        self._write_soul_file(state)
        self._update_database(state)

    def _write_soul_file(self, state: dict):
        temp_path = self.state_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(temp_path, self.state_path)
        except Exception as error:
            print(f"[Agent {self.id}] Soul file write failed: {error}")

    def _update_database(self, state: dict):
        step_json = json.dumps(state["step"], ensure_ascii=False) if state["step"] else None
        try:
            db.update_agent(
                self.id,
                status=state["status"],
                task=state["task"],
                status_text=state["status_text"],
                research_mode=int(state["research_mode"]),
                doc_id=state["doc_id"],
                step_json=step_json,
                cycle=state["cycle"],
                phase=state["phase"],
                phase_count=state["phase_count"]
            )
        except Exception as error:
            print(f"[Agent {self.id}] Database update failed: {error}")
