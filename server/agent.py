import json
import os
import threading
import time

from ollama import Client

import config
import database as db
from google_docs import DocManager
from networking import send, recv, receive_file
from prompts import RESEARCH_PROMPT, TASK_PROMPT


MAX_HISTORY_LENGTH = 30
MAX_CYCLES_IN_SAME_PHASE = 2
RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")


class Agent:
    def __init__(self, id, model, conn):
        """Sets up the agent with its ID, AI client, doc manager, and all runtime state fields."""
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
        self.task_ready = threading.Event()

        os.makedirs(RUNTIME_DIR, exist_ok=True)

        api_key = config.OLLAMA_API_KEY
        if not api_key:
            raise RuntimeError("OLLAMA_API_KEY not found")

        self.ai = Client(host="https://ollama.com", headers={"Authorization": f"Bearer {api_key}"})
        self.docs = DocManager(config.GOOGLE_SERVICE_ACCOUNT_FILE)
        self.save()

    def activate(self):
        """Waits for task assignments and runs them in a loop — the manager signals this via task_ready."""
        try:
            while True:
                self.task_ready.wait()
                self.task_ready.clear()

                if not self.run():
                    break

                self.status = "idle"
                self.status_msg = "Idle"
                self.save()

        except Exception as error:
            print(f"[Agent {self.id}] Fatal error: {error}")
        finally:
            self.status = "disconnected"
            print(f"[Agent {self.id}] Disconnected")

    def assign(self, task, research_mode=False, doc_id=None):
        """Sets up the agent's task state and signals it to begin — called by the manager."""
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

    def run(self):
        """Runs the think-act loop until the task is done or the connection fails."""
        while self.status == "working" and self.task:
            self.cycles += 1

            if not self.look():
                return False

            ai_response = self.think()
            self.parse(ai_response)

            if self.done():
                print(f"[Agent {self.id}] Completed in {self.cycles} cycles")
                return True

            if not self.act(ai_response):
                return False

            time.sleep(1)

        return True

    def look(self):
        """Requests a screenshot from the client and appends it to history so the AI can see the current screen."""
        self.status_msg = "Looking..."
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

    def parse(self, ai_response):
        """Extracts the current step info from the AI response and nudges the agent if it's stuck in the same phase."""
        current_phase = ai_response.get("Step", "SEARCH")

        self.step = {
            "phase": current_phase,
            "status_short": ai_response.get("Status", "Working..."),
            "reasoning": ai_response.get("Reasoning", ""),
            "action": ai_response.get("Next Action"),
            "coordinate": ai_response.get("Coordinate"),
            "value": ai_response.get("Value")
        }

        if current_phase != self.phase:
            self.phase = current_phase
            self.phase_count = 1
        else:
            self.phase_count += 1

        if self.phase_count > MAX_CYCLES_IN_SAME_PHASE:
            stuck_hint = (
                f"You've been on {current_phase} for {self.phase_count} actions. "
                "Stop repeating the same action; switch phases (SEARCH→READ→WRITE→SEARCH). "
                "Do not repeat identical searches—move to notes and write_doc."
            )
            self.history.append({"role": "user", "content": stuck_hint})
            print(f"[Agent {self.id}] Stuck on {current_phase} for {self.phase_count} actions")

    def done(self):
        """Checks if the AI returned a None action, which signals the task is complete."""
        action_name = self.step.get("action")
        is_done = action_name in (None, "None")

        if is_done:
            self.status = "idle"
            self.status_msg = "Done"
            self.save()

        return is_done

    def act(self, ai_response):
        """Routes the AI's chosen action to either the doc handler or the client machine."""
        self.status_msg = self.step.get("status_short", "Acting...")
        self.save()

        action = ai_response.get("Next Action")
        value = ai_response.get("Value")
        coordinate = ai_response.get("Coordinate")

        if action in {"read_doc", "write_doc"}:
            return self._handle_doc_command(action, value)

        return self._send_to_client(action, coordinate, value)

    def _send_to_client(self, action, coordinate, value):
        """Sends an action command to the client machine and waits for the execution result."""
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

    def think(self):
        """Calls the AI with the current conversation history and returns its next action — falls back to a safe no-op on error."""
        self.status_msg = "Thinking..."
        self.save()

        try:
            return self._query_ai()
        except Exception as error:
            print(f"[Agent {self.id}] AI error: {error}")
            return self._error_step(str(error))

    def _query_ai(self):
        """Sends the trimmed conversation history to the AI model and parses the JSON response."""
        initial_messages = self.history[:2]
        all_recent_messages = self.history[2:]
        recent_messages = all_recent_messages[-MAX_HISTORY_LENGTH:]
        messages = initial_messages + recent_messages

        result = self.ai.chat(model=self.model, messages=messages)
        raw_text = result["message"]["content"].strip()

        print(f"[Agent {self.id}] AI response: {raw_text}")

        parsed = self._parse_json(raw_text)
        if parsed is None:
            return self._error_step("No valid JSON found in AI response")

        parsed["raw"] = raw_text
        self._record_ai_reply(raw_text)
        return parsed

    def _parse_json(self, text):
        """Finds and parses the first JSON object in the AI's raw text output."""
        json_start = text.find("{")
        last_brace = text.rfind("}")

        if json_start == -1 or last_brace == -1:
            return None

        json_end = last_brace + 1

        try:
            return json.loads(text[json_start:json_end])
        except json.JSONDecodeError:
            return None

    def _record_ai_reply(self, raw_text):
        """Strips the image from the last history entry and appends the assistant's reply so the next call includes it."""
        if self.history:
            last_message = self.history[-1]
        else:
            last_message = None
        if last_message and "images" in last_message:
            last_message.pop("images")
        self.history.append({"role": "assistant", "content": raw_text})

    def _error_step(self, error_detail):
        """Builds a safe no-op response when the AI call fails so the agent loop can continue gracefully."""
        current_phase = self.phase or "EXECUTE"
        return {
            "Step": current_phase,
            "Status": "Error",
            "Next Action": "None",
            "Reasoning": error_detail,
            "raw": error_detail
        }

    def _handle_doc_command(self, action, value):
        """Routes read_doc and write_doc actions to the appropriate handler — silently skips if no doc is configured."""
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

    def _read_doc(self):
        """Reads the current document and injects its text into conversation history so the AI knows what's already written."""
        snapshot = self.docs.read(self.doc_id)
        doc_text = snapshot.get("text", "")
        self.history.append({"role": "user", "content": f"DOC_READ_RESULT ({self.doc_id}):\n{doc_text}"})
        self.status_msg = "Doc read complete"
        self.doc_read = True
        self.step["success"] = True
        self.save()
        return True

    def _write_doc(self, payload):
        """Writes content to the document and reports the outcome back into history so the AI knows the write succeeded."""
        if not self.doc_read:
            self._prefetch_doc()

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

    def _prefetch_doc(self):
        """Automatically reads the document before a write so the AI has current context without an explicit read_doc step."""
        snapshot = self.docs.read(self.doc_id)
        doc_text = snapshot.get("text", "")
        self.history.append({"role": "user", "content": f"DOC_AUTO_READ ({self.doc_id}):\n{doc_text}"})
        self.doc_read = True

    def save(self):
        """Saves the agent's current state to the database."""
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
        }
        self._persist_to_db(state)

    def _persist_to_db(self, state):
        """Writes the agent's current state fields to the database so the API can serve them without reading the soul file."""
        if state["step"]:
            step_json = json.dumps(state["step"], ensure_ascii=False)
        else:
            step_json = None
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
