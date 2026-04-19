import time
import database as db


POLL_INTERVAL_SECONDS = 0.2


class Manager:
    def __init__(self, agents, agents_lock):
        self.agents = agents
        self.lock = agents_lock

    def activate(self):
        while True:
            self.tick()
            time.sleep(POLL_INTERVAL_SECONDS)

    def tick(self):
        db_agents = {row["agent_id"]: row for row in db.get_all_agents()}

        with self.lock:
            self._remove_stale_db_agents(db_agents)

            for agent_id, agent in list(self.agents.items()):
                if self._remove_if_disconnected(agent_id, agent):
                    continue

                self._handle_requested_status(agent_id, agent, db_agents.get(agent_id))
                self._assign_next_task_if_idle(agent_id, agent)

    def _remove_stale_db_agents(self, db_agents):
        """Drop DB rows for agents that are not connected in this process."""
        for agent_id in set(db_agents) - set(self.agents):
            db.remove_agent(agent_id)

    def _remove_if_disconnected(self, agent_id, agent):
        if agent.status != "disconnected":
            return False

        del self.agents[agent_id]
        db.remove_agent(agent_id)
        return True

    def _handle_requested_status(self, agent_id, agent, db_row):
        if not db_row:
            return

        status = db_row.get("status")
        if status == "stop_requested":
            if agent.status == "working":
                agent.status = "idle"
                agent.task = None
                agent.status_msg = "Stopped"
                agent.save()

        elif status == "clear_requested":
            agent.status = "idle"
            agent.task = None
            agent.history = []
            agent.status_msg = "Memory cleared"
            agent.save()
            db.set_agent_status(agent_id, "idle")

        elif status == "disconnect_requested":
            agent.status = "disconnected"
            try:
                agent.conn.close()
            except Exception:
                pass

    def _assign_next_task_if_idle(self, agent_id, agent):
        if agent.status != "idle":
            return

        queued_tasks = db.get_queued_tasks(agent_id=agent_id)
        if not queued_tasks:
            return

        task = queued_tasks[0]
        db.assign_task(task["id"], agent_id)
        agent.assign(task["task"], task_id=task["id"])
