import os, socket, threading
from config import RUNTIME_DIR
from helpers import broadcast, pick_agent_name, load_keys, server_secure
from agent import Agent
from manager import Manager
from gateway import run_gateway
from database import init_db, register_agent, get_all_agents

HOST = "0.0.0.0"
AGENT_PORT = 1222
GATEWAY_PORT = 1223
AI_MODEL = "holo3-35b-a3b"


def main():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    init_db()
    our_key, open_key = load_keys()
    print("[✓] Locks loaded")

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

    gateway_thread = threading.Thread(
        target=run_gateway,
        kwargs={"host": HOST, "port": GATEWAY_PORT},
        daemon=True
    )
    gateway_thread.start()

    print(f"[✓] Gateway started on http://localhost:{GATEWAY_PORT}")
    print(f"[✓] Gateway LAN URL")

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

            security = server_secure(client_conn, our_key, open_key)
            if security is None:
                print(f"[Server] Handshake failed from {client_addr[0]}")
                client_conn.close()
                continue

            with agents_lock:
                taken = set(agents.keys())
            taken.update(row["agent_id"] for row in get_all_agents())
            agent_id = pick_agent_name(taken)
            print(f"[Server] Connected: {agent_id} from {client_addr[0]}")

            agent = Agent(id=agent_id, model=AI_MODEL, conn=client_conn, security=security)

            with agents_lock:
                agents[agent_id] = agent

            register_agent(agent_id)

            agent_thread = threading.Thread(target=agent.activate, daemon=True)
            agent_thread.start()

    except KeyboardInterrupt:
        print()
        print("[Server] Shutting down...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
