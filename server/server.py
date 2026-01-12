import os
import socket
import threading
import uuid
from helpers import broadcast
from agent import Agent
from manager import Manager

HOST = "0.0.0.0"
PORT = 1222
RUNTIME_DIR = "./runtime"
MODEL = "qwen3-vl:235b-instruct-cloud"

DEFAULT_TASKS = [
    "Create a 1-page research document about AI with clear structure: "
    "Introduction (what is AI and why it matters), "
    "Brief History (key milestones from 1950s to 2020s), "
    "Current State (how AI is used today with 2-3 specific examples and statistics), "
    "and Conclusion (what this means for the future). "
    "Focus on essential facts with proper citations. Keep it concise and professional. "
    "Use only things from websites, no personal knowledge.",
]


def main():
    agents = {}
    lock = threading.Lock()
    tasks = list(DEFAULT_TASKS)

    os.makedirs(RUNTIME_DIR, exist_ok=True)

    print("=" * 60)
    print("Harmony Server")
    print("=" * 60)
    print()

    broadcast_thread = threading.Thread(target=broadcast, daemon=True)
    broadcast_thread.start()
    print("[✓] LAN discovery broadcast started (UDP port 3030)")

    manager = Manager(agents, lock, tasks)
    manager_thread = threading.Thread(target=manager.activate, daemon=True)
    manager_thread.start()
    print("[✓] Task manager started")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen()

    print(f"[✓] Server listening on {HOST}:{PORT}")
    print()
    print("Waiting for clients...")
    print()

    try:
        while True:
            conn, addr = sock.accept()

            agent_id = f"agent-{uuid.uuid4().hex[:6]}"
            print(f"[Server] Connected: {agent_id} from {addr[0]}")

            agent = Agent(id=agent_id, model=MODEL, conn=conn)

            agent_thread = threading.Thread(target=agent.activate, daemon=True)
            agent_thread.start()

            with lock:
                agents[agent_id] = agent

    except KeyboardInterrupt:
        print()
        print("[Server] Shutting down...")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
