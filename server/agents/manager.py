import time, database as db


POLL_INTERVAL_SECONDS = 0.2


class Manager:
    def __init__(self, connected_agents, connected_agents_lock):
        self.connected_agents = connected_agents
        self.connected_agents_lock = connected_agents_lock


    def activate(self):
        while True:
            self.manage_connected_agents_once()
            time.sleep(POLL_INTERVAL_SECONDS)


    def manage_connected_agents_once(self):
        saved_agents_by_id = {}

        for saved_agent in db.get_all_agents():
            agent_id = saved_agent["agent_id"]
            saved_agents_by_id[agent_id] = saved_agent

        with self.connected_agents_lock:
            saved_agent_ids = set(saved_agents_by_id)
            connected_agent_ids = set(self.connected_agents)

            for stale_agent_id in saved_agent_ids - connected_agent_ids:
                db.remove_agent(stale_agent_id)

            for agent_id, agent in list(self.connected_agents.items()):
                saved_agent = saved_agents_by_id.get(agent_id)
                requested_state = saved_agent.get("agent_state") if saved_agent else None


                # Disconnect handling
                if agent.agent_state == "disconnect_requested" or requested_state == "disconnect_requested":
                    try:
                        agent.conn.close()
                    except Exception:
                        pass

                    del self.connected_agents[agent_id]
                    db.remove_agent(agent_id)
                    continue


                # Stop handling
                if requested_state == "stop_requested":
                    if agent.agent_state == "working":
                        agent.agent_state = "idle"
                        agent.task = None
                        agent.agent_activity_message = "Stopped"
                        agent.save()


                # Clear memory handling
                elif requested_state == "clear_requested":
                    agent.agent_state = "idle"
                    agent.task = None
                    agent.history = []
                    agent.agent_activity_message = "Memory cleared"
                    agent.save()
                    db.set_agent_state(agent_id, "idle")


                # Task assignment
                if agent.agent_state != "idle":
                    continue

                queued_tasks_for_this_agent = db.get_queued_tasks(agent_id=agent_id)
                if not queued_tasks_for_this_agent:
                    continue

                next_task = queued_tasks_for_this_agent[0]
                db.assign_task(next_task["id"], agent_id)
                agent.assign(next_task["task"], task_id=next_task["id"])
