import socket, threading, os, uuid
from helpers import broadcast
from agent import Agent
from manager import Manager

def main():
    agents = {}
    agents_lock = threading.Lock()
    tasks = [
        "Create a 1-page research document about AI with clear structure: Introduction (what is AI and why it matters), Brief History (key milestones from 1950s to 2020s), Current State (how AI is used today with 2-3 specific examples and statistics), and Conclusion (what this means for the future). Focus on essential facts with proper citations. Keep it concise and professional. Use only things from websites no personal knwoledge",
    ]

    os.makedirs("./runtime", exist_ok=True)


    # Start LAN discovery broadcast
    threading.Thread(target=broadcast, daemon=True).start()

    # Start Manager
    manager = Manager(agents, agents_lock, tasks)
    threading.Thread(target=manager.activate, daemon=True).start()

    # Start agent TCP server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 1222))
    sock.listen()

    print("Server listening on port 1222")

    while True:
        conn, addr = sock.accept()

        agent_id = f"agent-{uuid.uuid4().hex[:6]}"
        print(f"[Server] Agent connected: {agent_id} from {addr[0]}")

        agent = Agent(
            id=agent_id,
            model_name="qwen3-vl:235b-instruct-cloud",
            conn=conn
        )

        threading.Thread(
            target=agent.activate,
            daemon=True
        ).start()
        
        with agents_lock:
            agents[agent_id] = agent

if __name__ == "__main__":
    main()
