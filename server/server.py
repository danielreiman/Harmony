import socket, threading, os, uuid
from agent import Agent
from manager import Manager

agents = {}
tasks = []

def main():
    os.makedirs("server/runtime", exist_ok=True)

    manager = Manager(agents, tasks)

    threading.Thread(target=manager.activate).start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", 8080))
    sock.listen()

    print("Server listening on port 8080")

    while True:
        conn, addr = sock.accept()

        # ================= AGENT REGISTRATION =================
        agent_id = f"agent-{uuid.uuid4().hex[:6]}"

        print(f"[Server] Agent connected: {agent_id}")

        agent = Agent(
            id=agent_id,
            model_name="qwen3-vl:235b-instruct-cloud",
            conn=conn
        )
        agents[agent_id] = agent

        threading.Thread(
            target=agent.activate,
            daemon=True
        ).start()

if __name__ == "__main__":
    main()
