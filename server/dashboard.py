from flask import Flask, send_file, jsonify, make_response, request, render_template
import os, json, signal, shutil

RUNTIME_DIR = "./runtime"
app = Flask(__name__)

# Shared state (set by init_dashboard)
_agents = None
_agents_lock = None
_tasks = None

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
    return render_template('dashboard.html')


@app.route("/icon.png")
def icon():
    icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.png")
    if os.path.exists(icon_path):
        return send_file(icon_path, mimetype="image/png")
    return "", 404


@app.route("/agents")
def agents():
    out=[]
    if os.path.exists(RUNTIME_DIR):
        for f in os.listdir(RUNTIME_DIR):
            if f.endswith(".soul"):
                try:
                    with open(os.path.join(RUNTIME_DIR,f)) as jf:
                        d=json.load(jf)
                    if d.get("id"): out.append({"id":d["id"]})
                except: pass
    return jsonify(sorted(out,key=lambda x:x["id"]))


@app.route("/agent/<agent_id>")
def agent_state(agent_id):
    p=os.path.join(RUNTIME_DIR,f"{agent_id}.soul")
    if not os.path.exists(p): return jsonify({})
    try:
        with open(p) as f: return jsonify(json.load(f))
    except: return jsonify({})


@app.route("/screen/<agent_id>")
def screen_file(agent_id):
    p=os.path.join(RUNTIME_DIR,f"screenshot_{agent_id}.png")
    if not os.path.exists(p): return "No screenshot",404
    resp=make_response(send_file(p,mimetype="image/png"))
    resp.headers["Cache-Control"]="no-store"
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

    if not task:
        return jsonify({"success": False, "error": "Task is required"}), 400

    with _agents_lock:
        if agent_id:
            agent = _agents.get(agent_id)
            if not agent:
                return jsonify({"success": False, "error": f"Agent {agent_id} not found"}), 404
            if agent.status == "idle":
                agent.assign(task, research_mode=research_mode)
                mode_text = " (research mode)" if research_mode else ""
                return jsonify({"success": True, "message": f"Task assigned to {agent_id}{mode_text}"})
            else:
                agent.history.append({"role": "user", "content": task})
                return jsonify({"success": True, "message": f"Message sent to {agent_id}"})
        else:
            # For queue, we can store a tuple with research_mode info
            _tasks.append({"task": task, "research_mode": research_mode} if research_mode else task)
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
        else:
            return jsonify({"success": False, "error": f"Agent {agent_id} is not working"}), 400


@app.route("/api/agent/<agent_id>/disconnect", methods=["POST", "OPTIONS"])
def disconnect_agent(agent_id):
    if request.method == "OPTIONS":
        return "", 204
    if _agents is None:
        return jsonify({"success": False, "error": "Dashboard not connected to server"}), 503

    with _agents_lock:
        agent = _agents.get(agent_id)
        if not agent:
            return jsonify({"success": False, "error": f"Agent {agent_id} not found"}), 404

        agent.status = "disconnected"
        try:
            agent.conn.close()
        except:
            pass

        # Clean up agent files
        try:
            soul_path = os.path.join(RUNTIME_DIR, f"{agent_id}.soul")
            screen_path = os.path.join(RUNTIME_DIR, f"screenshot_{agent_id}.png")
            if os.path.exists(soul_path):
                os.remove(soul_path)
            if os.path.exists(screen_path):
                os.remove(screen_path)
        except:
            pass

        # Remove from agents dict
        if agent_id in _agents:
            del _agents[agent_id]

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


if __name__=="__main__":
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    run_dashboard()
