import base64
import json
import os
import re
import signal
import shutil
import socket
import threading
import time
import database as db

RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")
SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(__file__), "service-account.json")
AGENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _agent_id_is_valid(agent_id) -> bool:
    if not agent_id:
        return False
    return bool(AGENT_ID_PATTERN.match(str(agent_id)))


def _recv_exact(sock: socket.socket, byte_count: int) -> bytes | None:
    received = b""
    while len(received) < byte_count:
        chunk = sock.recv(byte_count - len(received))
        if not chunk:
            return None
        received += chunk
    return received


def _recv_request(sock: socket.socket) -> dict | None:
    length_bytes = _recv_exact(sock, 4)
    if length_bytes is None:
        return None
    message_length = int.from_bytes(length_bytes, "big")
    body = _recv_exact(sock, message_length)
    if body is None:
        return None
    return json.loads(body)


def _send_response(sock: socket.socket, response: dict):
    body = json.dumps(response).encode()
    length_prefix = len(body).to_bytes(4, "big")
    sock.sendall(length_prefix + body)


def _handle_get_agents() -> dict:
    active_statuses = {"idle", "working", "stop_requested"}
    all_agents = db.get_all_agents()
    active_agents = [
        {"id": agent["agent_id"]}
        for agent in all_agents
        if agent.get("status") in active_statuses
    ]
    sorted_agents = sorted(active_agents, key=lambda agent: agent["id"])
    return {"agents": sorted_agents}


def _handle_get_agent(agent_id: str) -> dict:
    if not _agent_id_is_valid(agent_id):
        return {"error": "Invalid agent id"}

    soul_file_path = os.path.join(RUNTIME_DIR, f"{agent_id}.soul")
    if not os.path.exists(soul_file_path):
        return {}

    try:
        with open(soul_file_path) as f:
            return json.load(f)
    except Exception:
        return {}


def _handle_get_screen(agent_id: str) -> dict:
    if not _agent_id_is_valid(agent_id):
        return {"error": "Invalid agent id"}

    screenshot_path = os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png")
    if not os.path.exists(screenshot_path):
        return {"error": "No screenshot"}

    with open(screenshot_path, "rb") as f:
        image_bytes = f.read()

    encoded_image = base64.b64encode(image_bytes).decode()
    return {"data": encoded_image}


def _handle_send_task(req: dict) -> dict:
    task_text = req.get("task", "").strip()
    agent_id = req.get("agent_id")
    research_mode = req.get("research_mode", False)
    doc_id = req.get("doc_id")

    if not task_text:
        return {"error": "Task is required"}

    if not agent_id:
        db.add_task(task_text, research_mode=research_mode, doc_id=doc_id)
        return {"success": True, "message": "Task added to queue"}

    agent = db.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent {agent_id} not found"}

    if agent["status"] == "idle":
        db.add_task_for_agent(task_text, agent_id, research_mode=research_mode, doc_id=doc_id)
        return {"success": True, "message": f"Task queued for {agent_id}"}

    if agent["status"] == "working":
        db.send_agent_message(agent_id, task_text)
        return {"success": True, "message": f"Message sent to {agent_id}"}

    return {"error": f"Agent {agent_id} is {agent['status']}"}


def _handle_stop_agent(agent_id: str) -> dict:
    if not _agent_id_is_valid(agent_id):
        return {"error": "Invalid agent id"}
    db.set_command(agent_id, "stop_requested")
    return {"success": True}


def _handle_disconnect_agent(agent_id: str) -> dict:
    if not _agent_id_is_valid(agent_id):
        return {"error": "Invalid agent id"}

    db.set_command(agent_id, "disconnect_requested")

    soul_file_name = f"{agent_id}.soul"
    screenshot_file_name = f"screenshot_{agent_id}.png"
    files_to_remove = [soul_file_name, screenshot_file_name]

    for file_name in files_to_remove:
        file_path = os.path.join(RUNTIME_DIR, file_name)
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass

    return {"success": True}


def _handle_stop_server() -> dict:
    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)

    def _send_sigint_after_delay():
        time.sleep(0.3)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=_send_sigint_after_delay, daemon=True).start()
    return {"success": True}


def _handle_get_service_account() -> dict:
    try:
        with open(SERVICE_ACCOUNT_PATH) as f:
            service_account_data = json.load(f)
        service_account_email = service_account_data.get("client_email", "")
        return {"has_key": True, "email": service_account_email}
    except Exception:
        return {"has_key": False, "email": ""}


def _handle_auth_login(req: dict) -> dict:
    username = req.get("username", "").strip()
    password = req.get("password", "")
    user_id = db.verify_user(username, password)
    if user_id is None:
        return {"error": "Invalid username or password"}
    token = db.create_session(user_id)
    return {"token": token}


def _handle_auth_signup(req: dict) -> dict:
    username = req.get("username", "").strip()
    password = req.get("password", "")
    user_was_created = db.create_user(username, password)
    if not user_was_created:
        return {"error": "Username already taken"}
    user_id = db.verify_user(username, password)
    token = db.create_session(user_id)
    return {"token": token}


def _handle_auth_validate(req: dict) -> dict:
    token = req.get("token", "")
    user_id = db.validate_session(token)
    if user_id is None:
        return {"error": "Invalid session"}
    username = db.get_username(user_id)
    return {"user_id": user_id, "username": username}


def _handle_auth_logout(req: dict) -> dict:
    token = req.get("token", "")
    db.delete_session(token)
    return {"success": True}


def _route_request(req: dict) -> dict:
    action = req.get("action", "")

    if action == "get_agents":
        return _handle_get_agents()

    if action == "get_agent":
        agent_id = req.get("agent_id", "")
        return _handle_get_agent(agent_id)

    if action == "get_screen":
        agent_id = req.get("agent_id", "")
        return _handle_get_screen(agent_id)

    if action == "send_task":
        return _handle_send_task(req)

    if action == "stop_agent":
        agent_id = req.get("agent_id", "")
        return _handle_stop_agent(agent_id)

    if action == "disconnect_agent":
        agent_id = req.get("agent_id", "")
        return _handle_disconnect_agent(agent_id)

    if action == "stop_server":
        return _handle_stop_server()

    if action == "get_tasks":
        queued_tasks = db.get_all_queued_tasks()
        return {"tasks": queued_tasks}

    if action == "get_service_account":
        return _handle_get_service_account()

    if action == "auth_login":
        return _handle_auth_login(req)

    if action == "auth_signup":
        return _handle_auth_signup(req)

    if action == "auth_validate":
        return _handle_auth_validate(req)

    if action == "auth_logout":
        return _handle_auth_logout(req)

    return {"error": f"Unknown action: {action}"}


def _handle_connection(conn: socket.socket):
    try:
        req = _recv_request(conn)
        if req is not None:
            response = _route_request(req)
            _send_response(conn, response)
    except Exception as error:
        print(f"[API] Connection error: {error}")
    finally:
        conn.close()


def run_api(host: str = "0.0.0.0", port: int = 1223):
    try:
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((host, port))
        server_sock.listen()
        print(f"[✓] API socket listening on port {port}")
    except Exception as error:
        print(f"[✗] API failed to start on port {port}: {error}")
        return

    while True:
        try:
            conn, _ = server_sock.accept()
            threading.Thread(target=_handle_connection, args=(conn,), daemon=True).start()
        except Exception:
            break
