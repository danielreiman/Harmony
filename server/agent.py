import json
import os
import threading
import time

from ollama import Client

import config
import database as db
from google_docs import DocManager
from networking import send, recv, receive_file
from prompts import RESEARCH_BROWSE_PROMPT, RESEARCH_SUMMARIZE_PROMPT, TASK_PROMPT


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
        self.section_label = None
        self.task_id = None

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

    def assign(self, task, research_mode=False, doc_id=None, section_label=None, task_id=None):
        """Sets up the agent's task state and signals it to begin — called by the manager."""
        self.task = task
        self.status = "working"
        self.cycles = 0
        self.phase = None
        self.phase_count = 0
        self.research_mode = research_mode
        self.doc_id = doc_id
        self.section_label = section_label
        self.task_id = task_id

        if research_mode:
            system_prompt = RESEARCH_BROWSE_PROMPT
            user_message = f"Research this topic by browsing the web: {task}"
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
            if self.research_mode:
                stuck_hint = (
                    f"You've been on {current_phase} for {self.phase_count} steps. "
                    "Try something different: search with new keywords, click a different link, "
                    "or scroll further. When you have gathered info from 2-3 sources, "
                    "set \"Next Action\": \"None\" to finish browsing."
                )
            else:
                stuck_hint = (
                    f"You've been on {current_phase} for {self.phase_count} steps. "
                    "Stop repeating the same action and make progress toward completing the task."
                )
            self.history.append({"role": "user", "content": stuck_hint})
            print(f"[Agent {self.id}] Stuck on {current_phase} for {self.phase_count} steps")

    def done(self):
        """Checks if the AI returned a None action, which signals the task is complete."""
        action_name = self.step.get("action")
        is_done = action_name in (None, "None")

        if is_done:
            self.status = "idle"
            self.status_msg = "Done"
            self.save()
            if self.research_mode and self.doc_id:
                self._extract_and_write()

        return is_done

    def act(self, ai_response):
        """Sends the AI's chosen action to the client machine for execution."""
        self.status_msg = self.step.get("status_short", "Acting...")
        self.save()

        action = ai_response.get("Next Action")
        value = ai_response.get("Value")
        coordinate = ai_response.get("Coordinate")

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

    def _extract_and_write(self):
        """After browsing finishes, asks the AI to summarize findings and writes them to the doc with professional formatting."""
        self.status_msg = "Writing findings to doc..."
        self.save()

        subtopic = self.section_label or self.task
        summarize_prompt = RESEARCH_SUMMARIZE_PROMPT.replace("{subtopic}", subtopic)

        recent_history = self.history[-20:]
        messages = [{"role": "system", "content": summarize_prompt}] + recent_history

        try:
            result = self.ai.chat(model=self.model, messages=messages)
            raw = result["message"]["content"].strip()
            parsed = self._parse_json(raw)

            if parsed:
                body = parsed.get("body", "")
                sources = parsed.get("sources", [])
                bibliography = parsed.get("bibliography", [])
            else:
                body = raw
                sources = []
                bibliography = []

            if body:
                self.docs.write_formatted_section(
                    self.doc_id,
                    subtopic,
                    body,
                    sources,
                    bibliography,
                    self.id
                )
                print(f"[Agent {self.id}] Wrote findings to doc section: {subtopic[:50]}")
            else:
                print(f"[Agent {self.id}] No findings to write")

        except Exception as error:
            print(f"[Agent {self.id}] Extract and write failed: {error}")

        self.status_msg = "Done — section written"
        self.save()

        if self.task_id is not None:
            if bibliography:
                try:
                    db.set_task_result(self.task_id, {"bibliography": bibliography})
                except Exception as error:
                    print(f"[Agent {self.id}] Failed to save bibliography: {error}")
            try:
                db.complete_task(self.task_id)
            except Exception as error:
                print(f"[Agent {self.id}] Failed to mark task complete: {error}")

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
