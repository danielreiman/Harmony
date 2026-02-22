import os
import socket
import threading
import uuid
from networking import broadcast, local_ip
from agent import Agent
from manager import Manager
from api import run_api
from database import init_db, register_agent

HOST = "0.0.0.0"
AGENT_PORT = 1222
API_PORT = 1223
RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")
AI_MODEL = "qwen3-vl:235b-instruct-cloud"


def main():
    """Initializes all server subsystems and accepts incoming agent connections in a loop."""
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    init_db()

    agents = {}
    agents_lock = threading.Lock()

    print("=" * 60)
    print("Harmony Server")
    print("=" * 60)
    print()

    broadcast_thread = threading.Thread(target=broadcast, daemon=True)
    broadcast_thread.start()
    print("[✓] LAN discovery broadcast started (UDP port 3030)")

    manager = Manager(agents, agents_lock)
    manager_thread = threading.Thread(target=manager.activate, daemon=True)
    manager_thread.start()
    print("[✓] Task manager started")

    api_thread = threading.Thread(
        target=run_api,
        kwargs={"host": HOST, "port": API_PORT},
        daemon=True
    )
    api_thread.start()

    lan_ip = local_ip()
    print(f"[✓] API started on http://localhost:{API_PORT}")
    print(f"[✓] API LAN URL: http://{lan_ip}:{API_PORT}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, AGENT_PORT))
    server_socket.listen()
    print(f"[✓] Server listening on {HOST}:{AGENT_PORT}")
    print()
    print("Waiting for clients...")
    print()

    try:
        while True:
            client_conn, client_addr = server_socket.accept()
            agent_id = f"agent-{uuid.uuid4().hex[:6]}"
            print(f"[Server] Connected: {agent_id} from {client_addr[0]}")

            agent = Agent(id=agent_id, model=AI_MODEL, conn=client_conn)

            with agents_lock:
                agents[agent_id] = agent

            register_agent(agent_id)  # no user binding — all agents are shared

            agent_thread = threading.Thread(target=agent.activate, daemon=True)
            agent_thread.start()

    except KeyboardInterrupt:
        print()
        print("[Server] Shutting down...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
