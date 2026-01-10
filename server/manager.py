import time, config, json
from ollama import Client
from agent import Agent
from typing import Dict, List
from prompts import TASK_SPLIT_PROMPT

class Manager:
    def __init__(self, agents: Dict[str, Agent], agents_lock, tasks: List[str]):
        self.agents = agents
        self.agents_lock = agents_lock
        self.tasks = tasks

        api_key = config.OLLAMA_API_KEY
        self.client = Client(
            host="https://ollama.com",
            headers={"Authorization": f"Bearer {api_key}"}
        )

    def activate(self):
        while True:
            with self.agents_lock:
                # Remove disconnected agents
                disconnected = [agent_id for agent_id, agent in self.agents.items() if agent.status == "disconnected"]
                for agent_id in disconnected:
                    print(f"[Manager] Removing disconnected agent: {agent_id}")
                    del self.agents[agent_id]
                
                # Assign tasks to idle agents
                for agent in self.agents.values():
                    if agent.status == "idle" and self.tasks:
                        task = self.tasks.pop(0)
                        agent.assign(task)

            time.sleep(1)

    def decompress(self, task):
        messages = [
            {"role": "system", "content": TASK_SPLIT_PROMPT},
            {"role": "user", "content": task}
        ]

        result = self.client.chat(
            model="qwen3-vl:235b-instruct-cloud",
            messages=messages
        )

        raw = result["message"]["content"].strip()

        try:
            start = raw.find("[")
            end = raw.rfind("]") + 1
            json_text = raw[start:end]
            subtasks = json.loads(json_text)
        except Exception as e:
            print("[Manager] Failed to parse subtasks:", e, raw)
            subtasks = [task]

        self.tasks.extend(subtasks)

    def ask(self):
        while True:
            no_tasks_left = len(self.tasks) == 0

            with self.agents_lock:
                agents_idle = all(agent.status == "idle" for agent in self.agents.values())

            if no_tasks_left and agents_idle:
                new_task = input("\nEnter new main task: ").strip()
                if new_task:
                    self.decompress(new_task)

            time.sleep(1)



