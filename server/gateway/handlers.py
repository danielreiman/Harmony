import base64, json, os, shutil, signal, threading, time, database as db
from config import RUNTIME_DIR


def handle_get_agents():
    agents = []
    hidden_states = {"disconnected", "disconnect_requested"}

    for a in db.get_all_agents():
        agent_state = a.get("agent_state", "idle")

        if agent_state in hidden_states:
            continue

        agents.append({"id": a["agent_id"], "agent_state": agent_state})

    return {"agents": agents}


def handle_get_agent(agent_id):
    agent = db.get_agent(agent_id)

    if agent is None:
        return {}

    try:
        agent["step"] = json.loads(agent["step_json"]) if agent.get("step_json") else {}
    except Exception:
        agent["step"] = {}

    agent["id"] = agent.pop("agent_id")
    agent["ts"] = agent.pop("updated_at")

    return agent


def handle_get_screen(agent_id):
    # Return the agent's latest screenshot as base64 text the browser can show.
    screenshot_path = os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png")

    if not os.path.exists(screenshot_path):
        return {"error": "No screenshot"}

    with open(screenshot_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
        return {"data": data}


def handle_stop_agent(agent_id):
    db.set_agent_state(agent_id, "stop_requested")
    return {"success": True}


def handle_clear_agent(agent_id):
    db.set_agent_state(agent_id, "clear_requested")
    return {"success": True}


def handle_disconnect_agent(agent_id):
    db.set_agent_state(agent_id, "disconnect_requested")

    try:
        os.remove(os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png"))
    except FileNotFoundError:
        pass

    return {"success": True}


def handle_send_task(request):
    task_text = request.get("task", "").strip()
    agent_id = request.get("agent_id")
    user_id = request.get("user_id")

    if not task_text:
        return {"error": "Task is required"}

    if not agent_id:  # no agent chosen → drop it in the shared queue
        db.add_task(task_text, user_id=user_id)
        return {"success": True, "message": "Task added to queue"}

    agent = db.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent {agent_id} not found"}

    state = agent.get("agent_state", "")
    if state in ("idle", "working"):
        db.add_task(task_text, user_id=user_id, agent_id=agent_id)
        return {"success": True, "message": f"Task queued for {agent_id}"}

    return {"error": f"Agent {agent_id} is {state}"}


def handle_get_tasks(request):
    tasks = db.get_tasks_for_user(request.get("user_id"))
    return {"tasks": tasks}


def handle_delete_task(request):
    task_id = request.get("task_id")

    try:
        task_id = int(task_id)
    except (TypeError, ValueError):
        return {"error": "task_id is required"}

    success = db.delete_task(task_id, request.get("user_id"))
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


def handle_stop_server():
    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)

    def delayed_shutdown():
        time.sleep(0.3)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=delayed_shutdown, daemon=True).start()
    return {"success": True}


def route_request(request):
    # Map the admin's "action" string to the function that handles it.
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
