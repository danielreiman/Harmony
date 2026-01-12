import os
import socket
import threading
import uuid
from helpers import broadcast
from agent import Agent
from manager import Manager
from dashboard import init_dashboard, run_dashboard

HOST = "0.0.0.0"
PORT = 1222
DASHBOARD_PORT = 1234
RUNTIME_DIR = "./runtime"
MODEL = "qwen3-vl:235b-instruct-cloud"

DEFAULT_TASKS = []


def main():
    agents = {}
    lock = threading.Lock()
    tasks = list(DEFAULT_TASKS)

    os.makedirs(RUNTIME_DIR, exist_ok=True)

    print("=" * 60)
    print("Harmony Server")
    print("=" * 60)
    print()

    # Start LAN discovery broadcast
    broadcast_thread = threading.Thread(target=broadcast, daemon=True)
    broadcast_thread.start()
    print("[✓] LAN discovery broadcast started (UDP port 3030)")

    # Start task manager
    manager = Manager(agents, lock, tasks)
    manager_thread = threading.Thread(target=manager.activate, daemon=True)
    manager_thread.start()
    print("[✓] Task manager started")

    # Start dashboard with shared state
    init_dashboard(agents, lock, tasks)
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        kwargs={"host": HOST, "port": DASHBOARD_PORT},
        daemon=True
    )
    dashboard_thread.start()
    print(f"[✓] Dashboard started on http://localhost:{DASHBOARD_PORT}")

    # Start TCP server
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
