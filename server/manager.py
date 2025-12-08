import time
from agent import Agent
from typing import Dict, List

class Manager:
    def __init__(self, agents: Dict[str, Agent], tasks: List[str]):
        self.agents = agents
        self.tasks = tasks

    def activate(self):
        while True:
            for agent in self.agents.values():
                if agent.status == "idle" and self.tasks:
                    task = self.tasks.pop(0)
                    agent.assign(task)

            time.sleep(0.1)
