import base64
import json
import os
import re
import shutil
import signal
import socket
import threading
import time

import database as db

RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")
AGENT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def read_exact(sock, byte_count):
    """Reads an exact number of bytes from the socket, returning None if the connection closes early."""
    received = b""
    while len(received) < byte_count:
        chunk = sock.recv(byte_count - len(received))
        if not chunk:
            return None
        received += chunk
    return received


def read_request(sock):
    """Reads a 4-byte length-prefixed JSON request from the dashboard proxy and returns it as a dict."""
    length_bytes = read_exact(sock, 4)
    if length_bytes is None:
        return None
    message_length = int.from_bytes(length_bytes, "big")
    body_bytes = read_exact(sock, message_length)
    if body_bytes is None:
        return None
    return json.loads(body_bytes)


def write_response(sock, response):
    """Serializes the response dict and sends it back to the dashboard proxy with a 4-byte length prefix."""
    body_bytes = json.dumps(response).encode()
    length_prefix = len(body_bytes).to_bytes(4, "big")
    sock.sendall(length_prefix + body_bytes)


def is_valid_agent_id(agent_id):
    """Checks the agent ID against a safe character pattern to prevent path traversal attacks."""
    if not agent_id:
        return False
    return bool(AGENT_ID_PATTERN.match(str(agent_id)))


# --- Agent Handlers ---

def handle_get_agents(req):
    """Returns all connected agents sorted by ID."""
    active_statuses = {"idle", "working", "stop_requested"}
    connected_agents = []
    for agent in db.get_all_agents():
        if agent.get("status") in active_statuses:
            connected_agents.append({"id": agent["agent_id"]})
    connected_agents.sort(key=lambda a: a["id"])
    return {"agents": connected_agents}


def handle_get_agent(agent_id, req):
    """Returns the agent's current state from the database — the dashboard polls this to update the UI."""
    if not is_valid_agent_id(agent_id):
        return {"error": "Invalid agent id"}

    agent = db.get_agent(agent_id)
    if agent is None:
        return {}

    if agent.get("step_json"):
        agent["step"] = json.loads(agent["step_json"])
    else:
        agent["step"] = {}
    del agent["step_json"]

    agent["id"] = agent.pop("agent_id")
    agent["ts"] = agent.get("updated_at")
    return agent


def handle_get_screen(agent_id, req):
    """Reads the agent's latest screenshot and returns it base64-encoded for the dashboard to display."""
    if not is_valid_agent_id(agent_id):
        return {"error": "Invalid agent id"}

    screenshot_path = os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png")
    if not os.path.exists(screenshot_path):
        return {"error": "No screenshot"}

    with open(screenshot_path, "rb") as screenshot_file:
        image_bytes = screenshot_file.read()

    return {"data": base64.b64encode(image_bytes).decode()}


def handle_send_task(req):
    """Queues a task for the next idle agent or sends a message to an already-running agent."""
    task_text = req.get("task", "").strip()
    agent_id = req.get("agent_id")
    research_mode = req.get("research_mode", False)
    user_id = req.get("user_id")

    if not task_text:
        return {"error": "Task is required"}

    if not agent_id:
        db.add_task(task_text, research_mode=research_mode, user_id=user_id)
        return {"success": True, "message": "Task added to queue"}

    agent = db.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent {agent_id} not found"}

    agent_status = agent["status"]

    if agent_status == "idle":
        db.add_task_for_agent(task_text, agent_id, research_mode=research_mode, user_id=user_id)
        return {"success": True, "message": f"Task queued for {agent_id}"}

    if agent_status == "working":
        db.send_agent_message(agent_id, task_text)
        return {"success": True, "message": f"Message sent to {agent_id}"}

    return {"error": f"Agent {agent_id} is {agent_status}"}


def handle_stop_agent(agent_id, req):
    """Sets the agent's status to stop_requested so the manager loop halts it on the next tick."""
    if not is_valid_agent_id(agent_id):
        return {"error": "Invalid agent id"}

    db.set_agent_command(agent_id, "stop_requested")
    return {"success": True}


def handle_disconnect_agent(agent_id, req):
    """Requests agent disconnection and cleans up its runtime files from disk."""
    if not is_valid_agent_id(agent_id):
        return {"error": "Invalid agent id"}

    db.set_agent_command(agent_id, "disconnect_requested")

    try:
        os.remove(os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png"))
    except FileNotFoundError:
        pass

    return {"success": True}


def handle_stop_server():
    """Clears the runtime directory and sends SIGINT to the server process to shut it down cleanly."""
    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)

    def delayed_shutdown():
        time.sleep(0.3)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=delayed_shutdown, daemon=True).start()
    return {"success": True}


# --- Task Handlers ---

def handle_get_tasks(req):
    """Fetches all tasks belonging to the requesting user for the dashboard task list."""
    user_id = req.get("user_id")
    return {"tasks": db.get_tasks_for_user(user_id)}


def handle_get_research_report(req):
    """Returns the parent task and all subtask findings for the dashboard results panel."""
    task_id = req.get("task_id")
    if not task_id:
        return {"error": "task_id is required"}
    return db.get_research_report(int(task_id))


def handle_delete_task(req):
    """Deletes a task and its subtasks, only if the task belongs to the requesting user."""
    task_id = req.get("task_id")
    user_id = req.get("user_id")
    if not task_id:
        return {"error": "task_id is required"}
    deleted = db.delete_task(int(task_id), user_id)
    return {"success": deleted}


# --- Auth Handlers ---

def handle_auth_login(req):
    """Verifies credentials against the database and returns a session token on success."""
    username = req.get("username", "").strip()
    password = req.get("password", "")

    user_id = db.verify_user(username, password)
    if user_id is None:
        return {"error": "Invalid username or password"}

    return {"token": db.create_session(user_id)}


def handle_auth_signup(req):
    """Creates a new user account and returns a session token so the user is logged in immediately."""
    username = req.get("username", "").strip()
    password = req.get("password", "")

    if not db.create_user(username, password):
        return {"error": "Username already taken"}

    user_id = db.verify_user(username, password)
    return {"token": db.create_session(user_id)}


def handle_auth_validate(req):
    """Validates a session token and returns the user's ID and username for the dashboard."""
    token = req.get("token", "")

    user_id = db.validate_session(token)
    if user_id is None:
        return {"error": "Invalid session"}

    return {
        "user_id": user_id,
        "username": db.get_username(user_id),
    }


def handle_auth_logout(req):
    """Deletes the session so the user is logged out of the dashboard."""
    db.delete_session(req.get("token", ""))
    return {"success": True}


# --- Router ---

def route_request(req):
    """Dispatches the incoming request to the appropriate handler based on the action field."""
    action = req.get("action", "")
    agent_id = req.get("agent_id", "")

    if action == "get_agents":
        return handle_get_agents(req)
    if action == "get_agent":
        return handle_get_agent(agent_id, req)
    if action == "get_screen":
        return handle_get_screen(agent_id, req)
    if action == "send_task":
        return handle_send_task(req)
    if action == "stop_agent":
        return handle_stop_agent(agent_id, req)
    if action == "disconnect_agent":
        return handle_disconnect_agent(agent_id, req)
    if action == "stop_server":
        return handle_stop_server()
    if action == "get_tasks":
        return handle_get_tasks(req)
    if action == "get_research_report":
        return handle_get_research_report(req)
    if action == "delete_task":
        return handle_delete_task(req)
    if action == "auth_login":
        return handle_auth_login(req)
    if action == "auth_signup":
        return handle_auth_signup(req)
    if action == "auth_validate":
        return handle_auth_validate(req)
    if action == "auth_logout":
        return handle_auth_logout(req)

    return {"error": f"Unknown action: {action}"}


def handle_connection(conn):
    """Reads one request from the dashboard, routes it to the right handler, and sends back the response."""
    try:
        request = read_request(conn)
        if request is not None:
            response = route_request(request)
            write_response(conn, response)
    except Exception as error:
        print(f"[API] Connection error: {error}")
    finally:
        conn.close()


def run_api(host="0.0.0.0", port=1223):
    """Binds the API socket and accepts dashboard connections in a loop, spawning a thread per request."""
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
            threading.Thread(target=handle_connection, args=(conn,), daemon=True).start()
        except Exception:
            break
