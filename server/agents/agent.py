import base64, json, os, threading, time, traceback

from openai import OpenAI
from PIL import Image, ImageOps

import database as db
from config import HAI_API_KEY, RUNTIME_DIR
from prompts import TASK_PROMPT
from tools import STEP_SCHEMA, Step, build_cmd_step


MAX_HISTORY_LENGTH = 150
MAX_STEPS_PER_TASK = 100
MAX_SCREENSHOTS = 3
MAX_OUTPUT_TOKENS = 2500
MAX_TOOL_OUTPUT_CHARS = 1500

ACTION_WAIT_SECONDS = {
    "left_click": 0.8,
    "double_click": 0.9,
    "right_click": 0.5,
    "drag": 0.7,
    "hotkey": 0.6,
    "press_key": 0.7,
    "type": 0.2,
    "scroll_down": 0.4,
    "scroll_up": 0.4,
    "wait": 0.0,
    "run_command": 0.0,
}
DEFAULT_WAIT_SECONDS = 0.3


SCHEMA_BLOCK = f"\n\n<output_format>\n```json\n{json.dumps(STEP_SCHEMA, indent=2)}\n```\n</output_format>"
SYSTEM_CONTENT = TASK_PROMPT + SCHEMA_BLOCK


def prepare_screenshot_for_ai(src_path, dst_path):
    try:
        image = Image.open(src_path)
        image = ImageOps.exif_transpose(image)
        image.thumbnail((1600, 1600))
        image = image.convert("RGB")
        image.save(dst_path, "JPEG", quality=85, optimize=True)
        return dst_path
    except Exception:
        return src_path


def delete_old_screenshots(messages, keep=MAX_SCREENSHOTS):
    images = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for chunk in content:
                if chunk.get("type") == "image_url":
                    images.append(chunk)

    total = len(images)
    old_images = images[: total - keep]
    for chunk in old_images:
        chunk.clear()
        chunk["type"] = "text"
        chunk["text"] = "[screenshot deleted]"


def action_fingerprint(tool_call) -> str:
    # element is a description of what the model is targeting
    return str(tool_call.model_dump(exclude={"element"}))


def truncate_tool_output(text: str, limit=MAX_TOOL_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text

    keep = limit // 2
    removed = len(text) - limit

    start = text[:keep]
    end = text[-keep:]

    return f"{start}\n... [truncated {removed} chars] ...\n{end}"


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

        self.recent_actions = []

        self.task_ready = threading.Event()
        self.screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}.png")
        self.ai_screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{self.id}_ai.jpg")
        os.makedirs(RUNTIME_DIR, exist_ok=True)

        self.ai = OpenAI(
            base_url="https://api.hcompany.ai/v1/",
            api_key=HAI_API_KEY,
        )

        self.save()


    def save(self):
        try:
            db.update_agent(
                self.id,
                agent_state=self.agent_state,
                task=self.task,
                agent_activity_message=self.agent_activity_message,
                step_json=json.dumps(self.step, ensure_ascii=False),
            )
        except Exception as error:
            print(f"[Agent {self.id}] Save error: {error}")


    def activate(self):
        self.security.send(self.conn, {"type": "connected", "agent_id": self.id})
        print(f"[Agent {self.id}] Ready")

        try:
            while True:
                self.task_ready.wait()
                self.task_ready.clear()

                try:
                    should_keep_running = self.run()
                except Exception as error:
                    print(f"[Agent {self.id}] Step error: {error}")
                    self.agent_activity_message = f"Recovered from error: {type(error).__name__}"
                    self.agent_state = "idle"
                    self.task = None
                    self.save()
                    continue

                if not should_keep_running:
                    break

                self.agent_state = "idle"
                self.agent_activity_message = "Idle"
                self.save()

        except Exception as error:
            print(f"[Agent {self.id}] Fatal: {error}\n{traceback.format_exc()}")

        finally:
            self.agent_state = "disconnected"
            print(f"[Agent {self.id}] Disconnected")
            try:
                self.conn.close()
            except Exception:
                pass


    def assign(self, task, task_id=None):
        # Give the agent a new task and wake its loop (task_ready event).
        self.task = task
        self.task_id = task_id

        if not self.history:  # first task: seed the system prompt
            self.history = [
                {"role": "system", "content": SYSTEM_CONTENT},
                {"role": "user", "content": f"<observation>\nExecute this task: {task}\n</observation>"},
            ]
        else:
            self.history.append({
                "role": "user",
                "content": f"<observation>\nNew instruction: {task}\n</observation>",
            })

        self.agent_state = "working"
        self.agent_activity_message = "Starting..."
        self.save()
        self.task_ready.set()


    def run(self):
        # One task = repeat look → think → act until the model says "done".
        cancel_states = ("stop_requested", "disconnect_requested", "idle", "clear_requested")
        steps_taken = 0

        while self.task and self.agent_state not in cancel_states:
            if steps_taken >= MAX_STEPS_PER_TASK:
                print(f"[Agent {self.id}] Step limit reached ({MAX_STEPS_PER_TASK})")
                self.agent_state = "idle"
                self.agent_activity_message = f"Aborted: Step limit reached ({MAX_STEPS_PER_TASK})"
                self.task = None
                self.save()
                return True
            steps_taken += 1


            # Look
            self.agent_activity_message = "Looking..."
            self.save()

            if not self.security.send(self.conn, {"type": "request_screenshot"}):
                return False  # agent gone

            screen_bytes = self.security.recv(self.conn)  # the agent's screen
            if not screen_bytes:
                return False

            with open(self.screen_path, "wb") as f:
                f.write(screen_bytes)

            ai_path = prepare_screenshot_for_ai(self.screen_path, self.ai_screen_path)  # shrink for the model
            with open(ai_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("ascii")

            self.history.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": "<observation>\n"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": "\n</observation>"},
                ],
            })


            # Think
            self.agent_activity_message = "Thinking..."
            self.save()

            # Send the system prompt + the most recent history (older screenshots dropped to save tokens).
            head = self.history[:2]
            tail = self.history[2:][-MAX_HISTORY_LENGTH:]
            delete_old_screenshots(tail)

            try:
                response = self.ai.chat.completions.create(
                    model=self.model,
                    messages=head + tail,
                    temperature=0.3,
                    max_tokens=MAX_OUTPUT_TOKENS,
                    extra_body={"structured_outputs": {"json": STEP_SCHEMA}},
                )
            except Exception as error:
                print(f"[Agent {self.id}] AI transport error: {type(error).__name__}: {error}")
                self.agent_state = "idle"
                self.agent_activity_message = f"Aborted: AI transport error"
                self.task = None
                self.save()
                return True

            message = response.choices[0].message if response.choices else None


            # Read
            try:
                step = Step.model_validate_json(message.content or "")
            except Exception as error:
                print(f"[Agent {self.id}] Bad model response: {error}")
                delete_old_screenshots(self.history)
                self.history.append({
                    "role": "user",
                    "content": "Your previous response was not valid JSON. Output a single "
                               "valid JSON object matching the schema, including the required "
                               "`note` field (min 15 chars).",
                })
                continue

            self.history.append({"role": "assistant", "content": step.model_dump_json()})

            self.step = {
                "reasoning": step.thought,
                "note": step.note,
                "action": step.tool_call.tool_name,
            }
            cmd_step = build_cmd_step(step.tool_call)
            self.step.update({
                "coordinate": cmd_step.get("Coordinate"),
                "end_coordinate": cmd_step.get("EndCoordinate"),
                "value": cmd_step.get("Value"),
            })

            # Loop check
            fp = action_fingerprint(step.tool_call)
            self.recent_actions = (self.recent_actions + [fp])[-5:]
            if self.recent_actions.count(fp) >= 3:
                self.recent_actions = []
                self.history.append({
                    "role": "user",
                    "content": f"<observation>You repeated `{step.tool_call.tool_name}` too many times with no progress. Try something different.</observation>",
                })

            # Forget old screenshot
            delete_old_screenshots(self.history)


            # Done
            if step.tool_call.tool_name == "done":
                self.agent_state = "idle"
                self.agent_activity_message = "Done"
                if self.task_id:
                    try:
                        db.mark_task_done(self.task_id)
                    except Exception as error:
                        print(f"[Agent {self.id}] Task finish error: {error}")
                self.save()
                return True


            # Act
            self.agent_activity_message = f"Acting: {step.tool_call.tool_name}"
            self.save()

            if not self.security.send(self.conn, {"type": "execute_step", "step": cmd_step}):
                return False  # tell the agent to perform the action

            raw_reply = self.security.recv(self.conn)  # agent reports back success/output
            result = json.loads(raw_reply) if raw_reply else {}

            if result.get("output"):
                output_text = result["output"]
                self.step["cmd_output"] = result["output"]
            elif result.get("success", True):
                output_text = "ok"
            else:
                output_text = "failed"

            output_text = truncate_tool_output(output_text)
            self.history.append({
                "role": "user",
                "content": f'<tool_output tool="{step.tool_call.tool_name}">\n{output_text}\n</tool_output>',
            })


            # Let UI catch up
            delay = ACTION_WAIT_SECONDS.get(step.tool_call.tool_name, DEFAULT_WAIT_SECONDS)
            self.save()
            time.sleep(delay)


        if self.agent_state == "disconnect_requested":
            return False

        if self.agent_state != "stop_requested":
            self.task = None
            self.task_id = None

        if self.agent_state in ("clear_requested", "stop_requested"):
            self.agent_state = "idle"

        self.save()
        return True
