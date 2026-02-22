import time
from ollama import Client
import config
import database as db


class Manager:
    def __init__(self, agents, agents_lock):
        """Holds the shared agent registry and AI client so it can assign tasks and relay messages to agents."""
        self.agents = agents
        self.lock = agents_lock
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
        """Picks the next queued task for each idle agent and assigns it."""
        with self.lock:
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

                db.assign_task(task_id, agent.id)
                agent.assign(task_text, research_mode=research_mode, doc_id=doc_id)

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
