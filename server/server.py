import socket, threading, os
from agent import Agent

def main():
    os.makedirs("server/runtime", exist_ok=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", 8080))
    sock.listen()

    print("Server listening on port 8080")

    while True:
        conn, addr = sock.accept()
        thread = threading.Thread(
            target=handle_client,
            args=(conn, addr),
            daemon=True
        )
        thread.start()

def handle_client(conn, addr):
    print(f"Connected: {addr}")

    agent = Agent(id=str(addr),  model_name="qwen3-vl:235b-instruct-cloud", conn=conn)

    try:
        agent.assign("Open browser and show weather in USA")
    except Exception as e:
        print("Agent crashed:", e)
    finally:
        conn.close()
        print(f"Disconnected: {addr}")


if __name__ == "__main__":
    main()
