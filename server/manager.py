import json
import time
from ollama import Client
import config
from prompts import TASK_SPLIT_PROMPT
import database as db


class Manager:
    def __init__(self, agents: dict, agents_lock):
        self.agents = agents
        self.lock = agents_lock
        self.ai = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"}
        )

    def activate(self):
        while True:
            self.cleanup_disconnected_agents()
            self.poll_commands()
            self.deliver_pending_messages()
            self.assign_queued_tasks()
            time.sleep(1)

    def cleanup_disconnected_agents(self):
        with self.lock:
            disconnected_ids = [
                agent_id
                for agent_id, agent in self.agents.items()
                if agent.status == "disconnected"
            ]
            for agent_id in disconnected_ids:
                print(f"[Manager] Removing: {agent_id}")
                db.remove_agent(agent_id)
                del self.agents[agent_id]

    def poll_commands(self):
        with self.lock:
            for agent_id, agent in list(self.agents.items()):
                db_agent = db.get_agent(agent_id)
                if db_agent is None:
                    continue

                db_status = db_agent["status"]
                agent_is_working = agent.status == "working"
                stop_was_requested = db_status == "stop_requested" and agent_is_working
                disconnect_was_requested = db_status == "disconnect_requested"

                if stop_was_requested:
                    agent.status = "idle"
                    agent.task = None
                    agent.status_msg = "Stopped"
                    agent.save()
                    print(f"[Manager] Stopped: {agent_id}")

                elif disconnect_was_requested:
                    agent.status = "disconnected"
                    try:
                        agent.conn.close()
                    except Exception:
                        pass
                    print(f"[Manager] Disconnect requested: {agent_id}")

    def deliver_pending_messages(self):
        with self.lock:
            for agent_id, agent in self.agents.items():
                agent_is_not_working = agent.status != "working"
                if agent_is_not_working:
                    continue

                pending_messages = db.consume_agent_messages(agent_id)
                for message in pending_messages:
                    agent.history.append({"role": "user", "content": message})
                    print(f"[Manager] Delivered message to {agent_id}: {message[:60]}...")

    def assign_queued_tasks(self):
        with self.lock:
            for agent in self.agents.values():
                agent_is_not_idle = agent.status != "idle"
                if agent_is_not_idle:
                    continue

                task_row = self._pick_next_task_for_agent(agent.id)
                if task_row is None:
                    continue

                task_text = task_row["task"]
                research_mode = bool(task_row["research_mode"])
                doc_id = task_row.get("doc_id")
                task_id = task_row["id"]

                db.assign_task(task_id, agent.id)
                agent.assign(task_text, research_mode=research_mode, doc_id=doc_id)

                mode_label = "research" if research_mode else "task"
                print(f"[Manager] Assigned to {agent.id} ({mode_label})")

    def _pick_next_task_for_agent(self, agent_id: str) -> dict | None:
        targeted_tasks = db.get_queued_tasks(agent_id=agent_id)
        if targeted_tasks:
            return targeted_tasks[0]

        general_tasks = db.get_queued_tasks()
        if general_tasks:
            return general_tasks[0]

        return None

    def split(self, task: str):
        messages = [
            {"role": "system", "content": TASK_SPLIT_PROMPT},
            {"role": "user", "content": task}
        ]
        try:
            result = self.ai.chat(model="qwen3-vl:235b-instruct-cloud", messages=messages)
            raw_response = result["message"]["content"].strip()

            array_start = raw_response.find("[")
            array_end = raw_response.rfind("]") + 1
            json_array_not_found = array_start == -1 or array_end == 0

            if json_array_not_found:
                print("[Manager] No JSON array in split response")
                db.add_task(task)
                return

            subtasks = json.loads(raw_response[array_start:array_end])
            subtasks_are_valid = isinstance(subtasks, list) and len(subtasks) > 0

            if not subtasks_are_valid:
                print("[Manager] Invalid subtask format in split response")
                db.add_task(task)
                return

            for subtask in subtasks:
                db.add_task(subtask)
            print(f"[Manager] Split into {len(subtasks)} subtasks")

        except json.JSONDecodeError as error:
            print(f"[Manager] JSON parse error: {error}")
            db.add_task(task)
        except Exception as error:
            print(f"[Manager] Split error: {error}")
            db.add_task(task)
