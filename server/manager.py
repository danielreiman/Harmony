import json
import time

from ollama import Client

import config
import database as db
from google_docs import DocManager
from prompts import TASK_SPLIT_PROMPT

# Tracks which parent tasks have already had their summary written so we don't repeat it.
_summary_written = set()


class Manager:
    def __init__(self, agents, agents_lock, model):
        """Holds the shared agent registry, AI client, and doc manager for task assignment and coordination."""
        self.agents = agents
        self.lock = agents_lock
        self.model = model
        self.ai = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {config.OLLAMA_API_KEY}"}
        )

        try:
            self.docs = DocManager(config.GOOGLE_SERVICE_ACCOUNT_FILE)
        except Exception as error:
            print(f"[Manager] DocManager unavailable: {error}")
            self.docs = None

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
        """Splits parent research tasks across idle agents when possible, then assigns tasks one per idle agent."""
        with self.lock:
            idle_agents = [a for a in self.agents.values() if a.status == "idle"]
            idle_count = len(idle_agents)

            if idle_count >= 1 and self.docs is not None:
                self._maybe_split_research_tasks(idle_count)

            self._check_research_complete()

            for agent in self.agents.values():
                if agent.status != "idle":
                    continue

                task_row = self._next_task_for(agent.id)
                if task_row is None:
                    continue

                task_text = task_row["task"]
                research_mode = bool(task_row["research_mode"])
                doc_id = task_row.get("doc_id")
                task_id = task_row["id"]
                section_label = task_row.get("section_label")

                db.assign_task(task_id, agent.id)
                agent.assign(task_text, research_mode=research_mode, doc_id=doc_id, section_label=section_label, task_id=task_id)

                if research_mode and doc_id and section_label and self.docs is not None:
                    try:
                        self.docs.update_placeholder(doc_id, section_label, f"⏳ In progress — {agent.id}")
                    except Exception as error:
                        print(f"[Manager] Placeholder update failed: {error}")

                mode_label = "research" if research_mode else "task"
                print(f"[Manager] Assigned to {agent.id} ({mode_label})")

    def _next_task_for(self, agent_id):
        """Selects the highest-priority queued task for an agent — prefers tasks targeted directly at it."""
        targeted_tasks = db.get_queued_tasks(agent_id=agent_id)
        if targeted_tasks:
            return targeted_tasks[0]

        general_tasks = db.get_queued_tasks()
        if general_tasks:
            return general_tasks[0]

        return None

    def _maybe_split_research_tasks(self, idle_count):
        """Checks for any unsplit parent research tasks and splits the first one found."""
        general_tasks = db.get_queued_tasks()
        for task_row in general_tasks:
            if not task_row.get("research_mode"):
                continue
            if task_row.get("parent_task_id"):
                continue  # Already a sub-task
            if not task_row.get("doc_id"):
                continue  # No doc to write to — skip splitting

            self._split_research_task(task_row, idle_count)
            break  # Only split one parent task per tick

    def _split_research_task(self, task_row, idle_count):
        """Splits a parent research task into per-agent subtopics and pre-structures the doc outline."""
        try:
            result = self.ai.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": TASK_SPLIT_PROMPT},
                    {"role": "user", "content": task_row["task"]}
                ]
            )
            raw = result["message"]["content"].strip()
            subtopics = self._parse_json_array(raw)

            if not subtopics:
                print("[Manager] Task split returned no subtopics — skipping split")
                return
            doc_id = task_row["doc_id"]
            user_id = task_row.get("user_id")
            parent_id = task_row["id"]

            try:
                self.docs.create_outline(doc_id, task_row["task"], subtopics)
            except Exception as error:
                print(f"[Manager] create_outline failed: {error}")

            for subtopic in subtopics:
                db.add_task(
                    subtopic,
                    research_mode=True,
                    doc_id=doc_id,
                    user_id=user_id,
                    section_label=subtopic,
                    parent_task_id=parent_id
                )

            db.mark_task_split(parent_id)
            print(f"[Manager] Split research task into {len(subtopics)} subtasks")

        except Exception as error:
            print(f"[Manager] Task splitting failed: {error}")

    def _parse_json_array(self, text):
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

    def _check_research_complete(self):
        """Checks if all subtasks for any split research task are done and writes the summary if so."""
        if self.docs is None:
            return

        split_tasks = db.get_split_tasks()
        for parent in split_tasks:
            parent_id = parent["id"]
            doc_id = parent.get("doc_id")

            if parent_id in _summary_written or not doc_id:
                continue

            subtasks = db.get_subtasks(parent_id)
            if not subtasks:
                continue

            all_complete = all(t["status"] == "complete" for t in subtasks)
            if not all_complete:
                continue

            _summary_written.add(parent_id)
            self._write_final_summary(doc_id, parent)

    def _write_final_summary(self, doc_id, parent_task):
        """Reads the completed doc and writes a summary and bibliography to the final sections."""
        try:
            doc_text = self.docs.read(doc_id).get("text", "")

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
                    {"role": "user", "content": f"Research findings:\n\n{doc_text}"}
                ]
            )
            summary_text = result["message"]["content"].strip()
            self.docs.write_summary(doc_id, summary_text)
            print(f"[Manager] Wrote summary for research task: {parent_task['task'][:60]}")

            # Aggregate bibliography from all completed subtasks
            subtasks = db.get_subtasks(parent_task["id"])
            all_bib_entries = []
            seen_urls = set()
            for subtask in subtasks:
                result_json_str = subtask.get("result_json")
                if not result_json_str:
                    continue
                try:
                    data = json.loads(result_json_str)
                    for entry in data.get("bibliography", []):
                        url = entry.get("url", "")
                        if url not in seen_urls:
                            seen_urls.add(url)
                            all_bib_entries.append(entry)
                except Exception:
                    pass

            if all_bib_entries:
                self.docs.write_bibliography(doc_id, all_bib_entries)
                print(f"[Manager] Wrote bibliography ({len(all_bib_entries)} entries)")

        except Exception as error:
            print(f"[Manager] Final summary write failed: {error}")

    def notify_research_complete(self, doc_id, parent_task_id):
        """Called when a sub-task finishes — checks if all sibling subtasks are done and writes the summary."""
        if self.docs is None:
            return
        if parent_task_id is None:
            return

        subtasks = db.get_subtasks(parent_task_id)
        all_done = all(t["status"] in ("complete", "assigned") for t in subtasks)

        if not all_done:
            return

        # Check that all are actually complete (not just assigned)
        truly_done = all(t["status"] == "complete" for t in subtasks)
        if not truly_done:
            return

        try:
            parent = db.get_task_by_id(parent_task_id)
            if parent is None:
                return

            doc_text = self.docs.read(doc_id).get("text", "")

            result = self.ai.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are writing the summary section of a research report. "
                            "Read the findings below and write a 2-3 sentence executive summary. "
                            "Be concise and professional. Return plain text only."
                        )
                    },
                    {"role": "user", "content": f"Research findings:\n\n{doc_text}"}
                ]
            )
            summary_text = result["message"]["content"].strip()
            self.docs.write_summary(doc_id, summary_text)
            print(f"[Manager] Wrote summary for parent task {parent_task_id}")

        except Exception as error:
            print(f"[Manager] Summary write failed: {error}")
