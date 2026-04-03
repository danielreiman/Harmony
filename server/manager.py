import time

import database as db


class Manager:
    def __init__(self, agents, agents_lock):
        self.agents = agents
        self.lock = agents_lock

    def activate(self):
        while True:
            self.remove_dead_agents()
            self.handle_commands()
            self.assign_tasks()
            time.sleep(1)

    def remove_dead_agents(self):
        with self.lock:
            for id, agent in list(self.agents.items()):
                if agent.status == "disconnected":
                    print(f"[Manager] Removing: {id}")
                    db.remove_agent(id)
                    del self.agents[id]

    def handle_commands(self):
        with self.lock:
            for id, agent in list(self.agents.items()):
                row = db.get_agent(id)
                if row is None:
                    continue

                if row["status"] == "stop_requested" and agent.status == "working":
                    agent.status = "idle"
                    agent.task = None
                    agent.status_msg = "Stopped"
                    agent.save()
                    print(f"[Manager] Stopped: {id}")

                elif row["status"] == "disconnect_requested":
                    agent.status = "disconnected"
                    try:
                        agent.conn.close()
                    except Exception:
                        pass
                    print(f"[Manager] Disconnect requested: {id}")

    def assign_tasks(self):
        with self.lock:
            for agent in self.agents.values():
                if agent.status != "idle":
                    continue

                task = self.find_task(agent.id)
                if task is None:
                    continue

                db.assign_task(task["id"], agent.id)
                agent.assign(task["task"], task_id=task["id"])
                print(f"[Manager] Assigned to {agent.id}: {task['task'][:50]}...")

    def find_task(self, agent_id):
        targeted = db.get_queued_tasks(agent_id=agent_id)
        if targeted:
            return targeted[0]

        general = db.get_queued_tasks()
        if general:
            return general[0]

        return None
