import os
import json
import base64
import signal
import threading
import shutil
import time
import socket
import database as db
from config import RUNTIME_DIR
from helpers import read_exact


def read_request(sock):
    request_length_bytes = read_exact(sock, 8)
    if request_length_bytes is None:
        return None

    request_length = int.from_bytes(request_length_bytes, "big")
    request_body = read_exact(sock, request_length)
    if request_body is None:
        return None

    return json.loads(request_body)


def write_response(sock, response):
    response_bytes = json.dumps(response).encode()
    sock.sendall(len(response_bytes).to_bytes(8, "big") + response_bytes)


def handle_get_agents():
    agents = []
    hidden_statuses = {"disconnected", "disconnect_requested"}
    for a in db.get_all_agents():
        status = a.get("status", "idle")
        if status in hidden_statuses:
            continue
        agents.append({"id": a["agent_id"], "status": status})
    return {"agents": agents}


def handle_get_agent(agent_id):
    agent = db.get_agent(agent_id)
    if agent is None:
        return {}

    if agent.get("step_json"):
        agent["step"] = json.loads(agent["step_json"])
    else:
        agent["step"] = {}

    agent["id"] = agent.pop("agent_id")
    agent["ts"] = agent.pop("updated_at")
    return agent


def handle_get_screen(agent_id):
    screenshot_path = os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png")
    if not os.path.exists(screenshot_path):
        return {"error": "No screenshot"}

    with open(screenshot_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
        return {"data": data}


def handle_send_task(request):
    task_text = request.get("task", "").strip()
    agent_id = request.get("agent_id")
    user_id = request.get("user_id")

    if not task_text:
        return {"error": "Task is required"}

    if not agent_id:
        db.add_task(task_text, user_id=user_id)
        return {"success": True, "message": "Task added to queue"}

    agent = db.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent {agent_id} not found"}

    if agent["status"] in ("idle", "working"):
        db.add_task(task_text, user_id=user_id, agent_id=agent_id)
        return {"success": True, "message": f"Task queued for {agent_id}"}

    return {"error": f"Agent {agent_id} is {agent['status']}"}


def handle_stop_agent(agent_id):
    db.set_agent_status(agent_id, "stop_requested")
    return {"success": True}


def handle_clear_agent(agent_id):
    db.set_agent_status(agent_id, "clear_requested")
    return {"success": True}


def handle_disconnect_agent(agent_id):
    db.set_agent_status(agent_id, "disconnect_requested")
    try:
        os.remove(os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png"))
    except FileNotFoundError:
        pass
    return {"success": True}


def handle_stop_server():
    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)

    def delayed_shutdown():
        time.sleep(0.3)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=delayed_shutdown, daemon=True).start()
    return {"success": True}


def handle_get_tasks(request):
    tasks = db.get_tasks_for_user(request.get("user_id"))
    return {"tasks": tasks}


def handle_delete_task(request):
    task_id = request.get("task_id")
    if not task_id:
        return {"error": "task_id is required"}
    
    success = db.delete_task(int(task_id), request.get("user_id"))
    return {"success": success}


def handle_auth_login(request):
    u = request.get("username", "").strip()
    p = request.get("password", "")
    user_id = db.verify_user(u, p)
    
    if user_id is None:
        return {"error": "Invalid username or password"}
    return {"user_id": user_id}


def handle_auth_signup(request):
    u = request.get("username", "").strip()
    p = request.get("password", "")
    
    if not db.create_user(u, p):
        return {"error": "Username already taken"}
    
    user_id = db.verify_user(u, p)
    return {"user_id": user_id}


def route_request(request):
    action = request.get("action", "")
    agent_id = request.get("agent_id", "")

    if action == "get_agents":
        return handle_get_agents()
    
    if action == "get_agent":
        return handle_get_agent(agent_id)
    
    if action == "get_screen":
        return handle_get_screen(agent_id)
    
    if action == "send_task":
        return handle_send_task(request)
    
    if action == "stop_agent":
        return handle_stop_agent(agent_id)
    
    if action == "clear_agent":
        return handle_clear_agent(agent_id)
    
    if action == "disconnect_agent":
        return handle_disconnect_agent(agent_id)
    
    if action == "stop_server":
        return handle_stop_server()
    
    if action == "get_tasks":
        return handle_get_tasks(request)
    
    if action == "delete_task":
        return handle_delete_task(request)
    
    if action == "auth_login":
        return handle_auth_login(request)
    
    if action == "auth_signup":
        return handle_auth_signup(request)

    return {"error": f"Unknown action: {action}"}


def handle_connection(conn):
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
            t = threading.Thread(target=handle_connection, args=(conn,), daemon=True)
            t.start()
        except Exception:
            break
