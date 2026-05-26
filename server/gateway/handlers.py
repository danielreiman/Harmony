import base64, json, os, shutil, signal, threading, time, database as db
from config import RUNTIME_DIR

RESEARCH_SECTIONS = [
    "overview",
    "benefits",
    "risks",
    "real-world examples",
    "future direction",
    "recommendations",
]
RESULT_MARKER = "\n\nAgent result:\n"


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


def _is_research_request(text):
    lower = text.lower()
    return lower.startswith("/research ") or lower.startswith("research:")


def _research_topic(text):
    if text.lower().startswith("/research "):
        return text[len("/research "):].strip()
    return text.split(":", 1)[1].strip()


def _research_prompt(mission_id, topic, section):
    return f"""Research Council | {mission_id} | {section}
Topic: {topic}

Research the topic from your assigned angle: {section}.
When you are done, use the Done message as your report section.
Keep it short and useful: 4-6 bullets and one final takeaway."""


def handle_research_mission(task_text, user_id):
    topic = _research_topic(task_text)
    if not topic:
        return {"error": "Research topic is required"}

    agents = [
        a for a in db.get_all_agents()
        if a.get("agent_state", "idle") in ("idle", "working")
    ]
    if not agents:
        return {"error": "No available agents"}

    mission_id = f"research-{int(time.time() * 1000)}"
    for index, agent in enumerate(agents):
        section = RESEARCH_SECTIONS[index % len(RESEARCH_SECTIONS)]
        db.add_task(_research_prompt(mission_id, topic, section),
                    user_id=user_id, agent_id=agent["agent_id"])

    return {
        "success": True,
        "message": f"Research council started with {len(agents)} agents",
    }


def handle_send_task(request):
    task_text = request.get("task", "").strip()
    agent_id = request.get("agent_id")
    user_id = request.get("user_id")

    if not task_text:
        return {"error": "Task is required"}

    if _is_research_request(task_text):
        return handle_research_mission(task_text, user_id)

    if not agent_id:
        db.add_task(task_text, user_id=user_id)
        return {"success": True, "message": "Task added to queue"}

    agent = db.get_agent(agent_id)
    if agent is None:
        return {"error": f"Agent {agent_id} not found"}

    if agent["agent_state"] in ("idle", "working"):
        db.add_task(task_text, user_id=user_id, agent_id=agent_id)
        return {"success": True, "message": f"Task queued for {agent_id}"}

    return {"error": f"Agent {agent_id} is {agent['agent_state']}"}


def _parse_research_task(text):
    lines = text.splitlines()
    if not lines or not lines[0].startswith("Research Council |"):
        return None

    parts = [part.strip() for part in lines[0].split("|")]
    if len(parts) < 3:
        return None

    topic = ""
    for line in lines[1:]:
        if line.startswith("Topic:"):
            topic = line.split(":", 1)[1].strip()
            break

    result = text.split(RESULT_MARKER, 1)[1].strip() if RESULT_MARKER in text else ""
    return {
        "mission": parts[1],
        "section": parts[2],
        "topic": topic,
        "result": result,
    }


def _research_report_rows(tasks):
    missions = {}
    cleaned = []

    for task in tasks:
        parsed = _parse_research_task(task.get("task", ""))
        if not parsed:
            cleaned.append(task)
            continue

        task = task.copy()
        task["task"] = (
            f"Research Council - {parsed['section']}\n"
            f"Topic: {parsed['topic']}\n\n"
            f"{parsed['result'] or 'Waiting for this agent result.'}"
        )
        cleaned.append(task)

        mission = missions.setdefault(parsed["mission"], {
            "topic": parsed["topic"],
            "created_at": task.get("created_at", 0),
            "sections": [],
        })
        mission["created_at"] = max(mission["created_at"], task.get("created_at", 0))
        mission["sections"].append({
            "agent": task.get("assigned_agent") or "unassigned",
            "section": parsed["section"],
            "status": task.get("status", "queued"),
            "result": parsed["result"],
        })

    reports = []
    for mission_id, mission in missions.items():
        sections = mission["sections"]
        done = sum(1 for section in sections if section["status"] == "done")
        lines = [f"Research Report: {mission['topic']}", ""]
        for section in sections:
            lines.append(f"{section['section']} ({section['agent']})")
            lines.append(section["result"] or "Waiting for result.")
            lines.append("")

        digits = "".join(ch for ch in mission_id if ch.isdigit())[-8:] or "1"
        reports.append({
            "id": -int(digits),
            "task": "\n".join(lines).strip(),
            "status": "done" if done == len(sections) else f"{done}/{len(sections)} done",
            "assigned_agent": "Harmony Server",
            "created_at": mission["created_at"],
        })

    return sorted(reports, key=lambda row: row["created_at"], reverse=True) + cleaned


def handle_get_tasks(request):
    tasks = db.get_tasks_for_user(request.get("user_id"))
    return {"tasks": _research_report_rows(tasks)}

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


def handle_stop_server():
    shutil.rmtree(RUNTIME_DIR, ignore_errors=True)

    def delayed_shutdown():
        time.sleep(0.3)
        os.kill(os.getpid(), signal.SIGINT)

    threading.Thread(target=delayed_shutdown, daemon=True).start()
    return {"success": True}


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
