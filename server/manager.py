import json
import time
from typing import Dict, List
from ollama import Client
import config
from agent import Agent
from prompts import TASK_SPLIT_PROMPT


class Manager:
    def __init__(self, agents: Dict[str, Agent], agents_lock, tasks: List[str]):
        self.agents = agents
        self.lock = agents_lock
        self.tasks = tasks

        api_key = config.OLLAMA_API_KEY
        self.ai = Client(host="https://ollama.com", headers={"Authorization": f"Bearer {api_key}"})

    def activate(self):
        while True:
            self.cleanup()
            self.assign()
            time.sleep(1)

    def cleanup(self):
        with self.lock:
            disconnected = [aid for aid, agent in self.agents.items() if agent.status == "disconnected"]
            for aid in disconnected:
                print(f"[Manager] Removing: {aid}")
                del self.agents[aid]

    def assign(self):
        with self.lock:
            for agent in self.agents.values():
                if agent.status == "idle" and self.tasks:
                    task = self.tasks.pop(0)
                    agent.assign(task)
                    print(f"[Manager] Assigned to {agent.id}")

    def split(self, task: str):
        messages = [
            {"role": "system", "content": TASK_SPLIT_PROMPT},
            {"role": "user", "content": task}
        ]

        try:
            result = self.ai.chat(model="qwen3-vl:235b-instruct-cloud", messages=messages)
            raw = result["message"]["content"].strip()

            start = raw.find("[")
            end = raw.rfind("]") + 1
            if start == -1 or end == 0:
                print("[Manager] No JSON array in response")
                self.tasks.append(task)
                return

            subtasks = json.loads(raw[start:end])
            if not isinstance(subtasks, list) or len(subtasks) == 0:
                print("[Manager] Invalid subtasks format")
                self.tasks.append(task)
                return

            self.tasks.extend(subtasks)
            print(f"[Manager] Split into {len(subtasks)} subtasks")

        except json.JSONDecodeError as e:
            print(f"[Manager] Parse error: {e}")
            self.tasks.append(task)
        except Exception as e:
            print(f"[Manager] Split error: {e}")
            self.tasks.append(task)

    def prompt(self):
        while True:
            no_tasks = len(self.tasks) == 0

            with self.lock:
                all_idle = all(agent.status == "idle" for agent in self.agents.values())

            if no_tasks and all_idle and len(self.agents) > 0:
                print()
                task = input("New task (or Enter to skip): ").strip()
                if task:
                    print("[Manager] Splitting task...")
                    self.split(task)

            time.sleep(1)
