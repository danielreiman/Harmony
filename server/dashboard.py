import json
import os
import signal
import shutil
from flask import Flask, jsonify, make_response, render_template, request, send_file

RUNTIME_DIR = "./runtime"
app = Flask(__name__)

# Shared state (set by init_dashboard)
_agents = None
_agents_lock = None
_tasks = None

SERVICE_ACCOUNT_PATH = os.path.join(os.path.dirname(__file__), "service-account.json")


def _service_account_email():
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        return None
    try:
        with open(SERVICE_ACCOUNT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("client_email")
    except Exception:
        return None


def init_dashboard(agents, agents_lock, tasks):
    global _agents, _agents_lock, _tasks
    _agents = agents
    _agents_lock = agents_lock
    _tasks = tasks

@app.after_request
def add_no_cache_headers(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return resp


@app.route("/")
def index():
    email = _service_account_email()
    return render_template(
        "dashboard.html",
        service_account_present=bool(email),
        service_account_email=email or "",
    )


@app.route("/icon.png")
def icon():
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.png")
    if os.path.exists(icon_path):
        return send_file(icon_path, mimetype="image/png")
    return "", 404


@app.route("/agents")
def agents():
    out = []
    if os.path.exists(RUNTIME_DIR):
        for f in os.listdir(RUNTIME_DIR):
            if f.endswith(".soul"):
                try:
                    with open(os.path.join(RUNTIME_DIR, f)) as jf:
                        data = json.load(jf)
                    if data.get("id"):
                        out.append({"id": data["id"]})
                except Exception:
                    pass
    return jsonify(sorted(out, key=lambda x: x["id"]))


@app.route("/agent/<agent_id>")
def agent_state(agent_id):
    path = os.path.join(RUNTIME_DIR, f"{agent_id}.soul")
    if not os.path.exists(path):
        return jsonify({})
    try:
        with open(path) as f:
            return jsonify(json.load(f))
    except Exception:
        return jsonify({})


@app.route("/screen/<agent_id>")
def screen_file(agent_id):
    path = os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png")
    if not os.path.exists(path):
        return "No screenshot", 404
    resp = make_response(send_file(path, mimetype="image/png"))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/send-task", methods=["POST", "OPTIONS"])
def send_task():
    if request.method == "OPTIONS":
        return "", 204
    if _agents is None or _tasks is None:
        return jsonify({"success": False, "error": "Dashboard not connected to server"}), 503

    data = request.json or {}
    task = data.get("task", "").strip()
    agent_id = data.get("agent_id")
    research_mode = data.get("research_mode", False)
    doc_id = data.get("doc_id")

    if not task:
        return jsonify({"success": False, "error": "Task is required"}), 400

    with _agents_lock:
        if agent_id:
            agent = _agents.get(agent_id)
            if not agent:
                return jsonify({"success": False, "error": f"Agent {agent_id} not found"}), 404
            if agent.status == "idle":
                mode_text = " (research mode)" if research_mode else ""
                agent.assign(task, research_mode=research_mode, doc_id=doc_id)
                return jsonify({"success": True, "message": f"Task assigned to {agent_id}{mode_text}"})

            agent.history.append({"role": "user", "content": task})
            return jsonify({"success": True, "message": f"Message sent to {agent_id}"})

        queued_task = {"task": task, "research_mode": research_mode, "doc_id": doc_id} if research_mode else task
        _tasks.append(queued_task)
        return jsonify({"success": True, "message": "Task added to queue"})


@app.route("/api/agent/<agent_id>/stop", methods=["POST", "OPTIONS"])
def stop_agent(agent_id):
    if request.method == "OPTIONS":
        return "", 204
    if _agents is None:
        return jsonify({"success": False, "error": "Dashboard not connected to server"}), 503

    with _agents_lock:
        agent = _agents.get(agent_id)
        if not agent:
            return jsonify({"success": False, "error": f"Agent {agent_id} not found"}), 404

        if agent.status == "working":
            agent.status = "idle"
            agent.task = None
            agent.status_msg = "Stopped"
            agent.save()
            return jsonify({"success": True, "message": f"Agent {agent_id} stopped"})

        return jsonify({"success": False, "error": f"Agent {agent_id} is not working"}), 400


@app.route("/api/agent/<agent_id>/disconnect", methods=["POST", "OPTIONS"])
def disconnect_agent(agent_id):
    if request.method == "OPTIONS":
        return "", 204
    if _agents is None:
        return jsonify({"success": False, "error": "Dashboard not connected to server"}), 503

    def cleanup_agent_files():
        try:
            for fname in (
                f"{agent_id}.soul",
                f"screenshot_{agent_id}.png",
            ):
                fpath = os.path.join(RUNTIME_DIR, fname)
                if os.path.exists(fpath):
                    os.remove(fpath)
        except Exception:
            pass

    with _agents_lock:
        agent = _agents.get(agent_id)
        if not agent:
            cleanup_agent_files()
            return jsonify({"success": True, "message": f"Agent {agent_id} already disconnected"})

        agent.status = "disconnected"
        try:
            agent.conn.close()
        except:
            pass

        # Clean up agent files
        cleanup_agent_files()

        # Remove from agents dict
        _agents.pop(agent_id, None)

        return jsonify({"success": True, "message": f"Agent {agent_id} removed"})


@app.route("/api/server/stop", methods=["POST", "OPTIONS"])
def stop_server():
    if request.method == "OPTIONS":
        return "", 204
    try:
        if os.path.exists(RUNTIME_DIR):
            shutil.rmtree(RUNTIME_DIR)
    except:
        pass
    os.kill(os.getpid(), signal.SIGINT)
    return jsonify({"success": True, "message": "Server shutting down"})


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    if _tasks is None:
        return jsonify([])
    return jsonify(list(_tasks))


def run_dashboard(host="0.0.0.0", port=1234):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=4, _quiet=True)
    except ImportError:
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    run_dashboard()
