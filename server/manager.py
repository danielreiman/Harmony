import json
import time

from ollama import Client

import config
import database as db
from prompts import TASK_SPLIT_PROMPT

# Tracks which parent tasks have already had their summary written so we don't repeat it.
summary_written = set()


class Manager:
    def __init__(self, agents, agents_lock, model):
        """Holds the shared agent registry and AI client for task assignment and coordination."""
        self.agents = agents
        self.lock = agents_lock
        self.model = model
        self.ai = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"}
        )

    def activate(self):
        """Runs the manager loop, polling for disconnections, commands, messages, and new tasks every second."""
        while True:
            self.drop_disconnected()
            self.process_commands()
            self.forward_messages()
            self.dispatch_tasks()
            time.sleep(1)

    def drop_disconnected(self):
        """Removes agents that have disconnected from the registry and database so they stop appearing in the dashboard."""
        with self.lock:
            disconnected_ids = []
            for agent_id, agent in self.agents.items():
                if agent.status == "disconnected":
                    disconnected_ids.append(agent_id)
            for agent_id in disconnected_ids:
                print(f"[Manager] Removing: {agent_id}")
                db.remove_agent(agent_id)
                del self.agents[agent_id]

    def process_commands(self):
        """Checks the database for stop or disconnect commands and applies them to the live agent objects."""
        with self.lock:
            for agent_id, agent in list(self.agents.items()):
                db_agent = db.get_agent(agent_id)
                if db_agent is None:
                    continue

                db_status = db_agent["status"]
                agent_is_working = agent.status == "working"

                if db_status == "stop_requested" and agent_is_working:
                    agent.status = "idle"
                    agent.task = None
                    agent.status_msg = "Stopped"
                    agent.save()
                    print(f"[Manager] Stopped: {agent_id}")

                elif db_status == "disconnect_requested":
                    agent.status = "disconnected"
                    try:
                        agent.conn.close()
                    except Exception:
                        pass
                    print(f"[Manager] Disconnect requested: {agent_id}")

    def forward_messages(self):
        """Injects any pending database messages into the conversation history of working agents."""
        with self.lock:
            for agent_id, agent in self.agents.items():
                if agent.status != "working":
                    continue

                pending_messages = db.consume_agent_messages(agent_id)
                for message in pending_messages:
                    agent.history.append({"role": "user", "content": message})
                    print(f"[Manager] Delivered message to {agent_id}: {message[:60]}...")

    def dispatch_tasks(self):
        """Splits parent research tasks when an agent is idle, then assigns tasks one per idle agent."""
        with self.lock:
            idle_agents = [a for a in self.agents.values() if a.status == "idle"]
            idle_count = len(idle_agents)

            if idle_count >= 1:
                self.maybesplit_research_tasks()

            self.check_research_complete()

            for agent in self.agents.values():
                if agent.status != "idle":
                    continue

                task_row = self.next_task_for(agent.id)
                if task_row is None:
                    continue

                task_text = task_row["task"]
                research_mode = bool(task_row["research_mode"])
                task_id = task_row["id"]
                section_label = task_row.get("section_label")

                db.assign_task(task_id, agent.id)
                agent.assign(task_text, research_mode=research_mode, section_label=section_label, task_id=task_id)

                mode_label = "research" if research_mode else "task"
                print(f"[Manager] Assigned to {agent.id} ({mode_label}): {task_text[:50]}...")

    def next_task_for(self, agent_id):
        """Selects the highest-priority queued task for an agent — prefers tasks targeted directly at it."""
        targeted_tasks = db.get_queued_tasks(agent_id=agent_id)
        if targeted_tasks:
            return targeted_tasks[0]

        general_tasks = db.get_queued_tasks()
        if general_tasks:
            return general_tasks[0]

        return None

    def maybesplit_research_tasks(self):
        """Checks for any unsplit parent research tasks and splits the first one found."""
        general_tasks = db.get_queued_tasks()
        for task_row in general_tasks:
            if not task_row.get("research_mode"):
                continue
            if task_row.get("parent_task_id"):
                continue  # Already a subtask

            self.split_research_task(task_row)
            break  # Only split one parent task per tick

    def split_research_task(self, task_row):
        """Splits a parent research task into subtopics and queues each as a separate task."""
        try:
            result = self.ai.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": TASK_SPLIT_PROMPT},
                    {"role": "user", "content": task_row["task"]}
                ]
            )
            raw = result["message"]["content"].strip()
            subtopics = self.parse_json_array(raw)

            if not subtopics:
                print("[Manager] Task split returned no subtopics — skipping split")
                return

            user_id = task_row.get("user_id")
            parent_id = task_row["id"]

            for subtopic in subtopics:
                db.add_task(
                    subtopic,
                    research_mode=True,
                    user_id=user_id,
                    section_label=subtopic,
                    parent_task_id=parent_id
                )

            db.mark_task_split(parent_id)
            print(f"[Manager] Split '{task_row['task'][:50]}' into {len(subtopics)} subtasks")

        except Exception as error:
            print(f"[Manager] Task splitting failed: {error}")

    def parse_json_array(self, text):
        """Extracts a JSON array from the AI response text, returning None if parsing fails."""
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return None
        try:
            result = json.loads(text[start:end + 1])
            if isinstance(result, list):
                return result
            return None
        except json.JSONDecodeError:
            return None

    def check_research_complete(self):
        """Checks if all subtasks for any split research task are done and writes the summary if so."""
        split_tasks = db.get_split_tasks()
        for parent in split_tasks:
            parent_id = parent["id"]

            if parent_id in summary_written:
                continue

            subtasks = db.get_subtasks(parent_id)
            if not subtasks:
                continue

            all_complete = all(t["status"] == "complete" for t in subtasks)
            if not all_complete:
                continue

            summary_written.add(parent_id)
            self.finalize_research(parent)

    def finalize_research(self, parent_task):
        """Collects all subtask findings and writes a summary into the parent task's result."""
        try:
            subtasks = db.get_subtasks(parent_task["id"])

            # Collect all body texts from completed subtasks
            findings_parts = []
            for subtask in subtasks:
                result_json_str = subtask.get("result_json")
                if not result_json_str:
                    continue
                try:
                    data = json.loads(result_json_str)
                    body = data.get("body", "")
                    label = subtask.get("section_label") or subtask.get("task", "")
                    if body:
                        findings_parts.append(f"{label}:\n{body}")
                except Exception:
                    pass

            if not findings_parts:
                print(f"[Manager] No findings to summarize for task {parent_task['id']}")
                return

            findings_text = "\n\n".join(findings_parts)

            result = self.ai.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are writing the summary section of a research report. "
                            "Read the research findings below and write a 2-3 sentence executive summary. "
                            "Be concise and professional. Return plain text only — no JSON, no markdown."
                        )
                    },
                    {"role": "user", "content": f"Research findings:\n\n{findings_text}"}
                ]
            )
            summary_text = result["message"]["content"].strip()

            db.set_task_result(parent_task["id"], {"summary": summary_text})
            print(f"[Manager] Wrote summary for: {parent_task['task'][:60]}")

        except Exception as error:
            print(f"[Manager] Finalize research failed: {error}")
