import time
import database as db


class Manager:
    def __init__(self, agents, agents_lock):
        self.agents = agents
        self.lock = agents_lock

    def activate(self):
        while True:
            self.tick()
            time.sleep(0.2)

    def tick(self):
        states = {}
        for row in db.get_all_agents():
            states[row["agent_id"]] = row

        with self.lock:
            for id in list(self.agents.keys()):
                agent = self.agents[id]
                row = states.get(id)

                if agent.status == "disconnected":
                    del self.agents[id]
                    db.remove_agent(id)
                    continue

                if row:
                    status = row.get("status")

                    if status == "stop_requested":
                        if agent.status == "working":
                            agent.status = "idle"
                            agent.task = None
                            agent.status_msg = "Stopped"
                            agent.save()

                    if status == "clear_requested":
                        agent.status = "idle"
                        agent.task = None
                        agent.history = []
                        agent.status_msg = "Memory cleared"
                        agent.save()
                        db.set_agent_status(id, "idle")

                    if status == "disconnect_requested":
                        agent.status = "disconnected"
                        try:
                            agent.conn.close()
                        except Exception:
                            pass

                if agent.status == "idle":
                    task = self.get_next_task(id)
                    
                    if task:
                        db.assign_task(task["id"], id)
                        agent.assign(task["task"], task_id=task["id"])

    def get_next_task(self, id):
        targeted = db.get_queued_tasks(agent_id=id)
        
        if targeted:
            return targeted[0]

        return None
