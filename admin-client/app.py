import base64
import os
import threading
import time

from flask import Flask, Response, jsonify, render_template, request, send_file

from auth import require_auth
import proxy


app = Flask(__name__)


@app.after_request
def disable_caching(response):
    """Adds no-cache headers to every response so the browser always fetches fresh agent data."""
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/")
def index():
    """Serves the main dashboard page — JS checks localStorage for the token and redirects to login if missing."""
    return render_template("dashboard.html", service_account_present=False, service_account_email="")


@app.route("/icon.png")
def icon():
    """Serves the dashboard icon PNG, or returns 404 if the file is missing."""
    icon_path = os.path.join(os.path.dirname(__file__), "static", "icon.png")
    if os.path.exists(icon_path):
        return send_file(icon_path, mimetype="image/png")
    return "", 404


# --- Auth Routes ---

@app.route("/login", methods=["GET", "POST"])
def login():
    """Renders the login page on GET, or validates credentials and returns the token as JSON on POST."""
    if request.method == "GET":
        return render_template("login.html")

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    login_result = proxy.request("auth_login", username=username, password=password)

    if "error" in login_result:
        return jsonify({"error": login_result["error"]}), 401

    if "token" not in login_result:
        return jsonify({"error": "Could not connect to server"}), 503

    return jsonify({"success": True, "token": login_result["token"]})


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handles new account creation and returns the token as JSON so the JS can store it in localStorage."""
    if request.method == "GET":
        return render_template("login.html")

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    confirm_password = body.get("confirm") or ""

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    signup_result = proxy.request("auth_signup", username=username, password=password)

    if "error" in signup_result:
        return jsonify({"error": signup_result["error"]}), 409

    if "token" not in signup_result:
        return jsonify({"error": "Could not connect to server"}), 503

    return jsonify({"success": True, "token": signup_result["token"]})


@app.route("/logout", methods=["POST"])
def logout():
    """Invalidates the session token on the server — JS clears localStorage and redirects after calling this."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):]
        proxy.request("auth_logout", token=token)
    return jsonify({"success": True})


# --- Agent Routes ---

@app.route("/agents")
@require_auth
def agents():
    """Returns the list of connected agents visible to the current user as JSON."""
    agent_list_result = proxy.request("get_agents", user_id=request.user_id)
    agent_list = agent_list_result.get("agents", [])
    return jsonify(agent_list)


@app.route("/agent/<path:agent_id>")
@require_auth
def agent_state(agent_id):
    """Returns the current state of the specified agent as JSON — polled by the dashboard to update the UI."""
    agent_data = proxy.request("get_agent", agent_id=agent_id, user_id=request.user_id)
    return jsonify(agent_data)


@app.route("/screen/<path:agent_id>")
@require_auth
def agent_screen(agent_id):
    """Fetches the agent's latest screenshot and returns it as a PNG image for the dashboard live view."""
    screenshot_result = proxy.request("get_screen", agent_id=agent_id, user_id=request.user_id)

    if "error" in screenshot_result or "data" not in screenshot_result:
        error_message = screenshot_result.get("error", "No screenshot")
        return error_message, 404

    image_bytes = base64.b64decode(screenshot_result["data"])
    return Response(image_bytes, content_type="image/png", headers={"Cache-Control": "no-store"})


# --- Task Routes ---

@app.route("/api/send-task", methods=["POST", "OPTIONS"])
@require_auth
def send_task():
    """Submits a task to the server for the current user, optionally targeting a specific agent."""
    if request.method == "OPTIONS":
        return "", 204

    body = request.json or {}
    task_text = body.get("task", "")
    agent_id = body.get("agent_id")
    research_mode = body.get("research_mode", False)

    task_result = proxy.request(
        "send_task",
        task=task_text,
        agent_id=agent_id,
        research_mode=research_mode,
        user_id=request.user_id,
    )
    return jsonify(task_result)


@app.route("/api/tasks")
@require_auth
def get_tasks():
    """Returns all tasks belonging to the current user as JSON for the dashboard task list."""
    tasks_result = proxy.request("get_tasks", user_id=request.user_id)
    task_list = tasks_result.get("tasks", [])
    return jsonify(task_list)


@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@require_auth
def delete_task(task_id):
    """Deletes a task and its subtasks if it belongs to the current user."""
    result = proxy.request("delete_task", task_id=task_id, user_id=request.user_id)
    return jsonify(result)


# --- Control Routes ---

@app.route("/api/status")
def api_status():
    """Checks whether the Harmony server is reachable and returns the result as JSON."""
    server_is_reachable = proxy.ping()
    return jsonify({"ok": server_is_reachable})


@app.route("/api/research/<int:task_id>")
@require_auth
def get_research_report(task_id):
    """Returns the research report (parent task + all subtask findings) for the results panel."""
    result = proxy.request("get_research_report", task_id=task_id)
    return jsonify(result)


@app.route("/api/server/stop", methods=["POST", "OPTIONS"])
def stop_server():
    """Sends a stop command to the Harmony server to shut it down."""
    if request.method == "OPTIONS":
        return "", 204
    stop_result = proxy.request("stop_server")
    return jsonify(stop_result)


@app.route("/api/admin-agent-client/stop", methods=["POST"])
def dashboard_stop():
    """Schedules the dashboard process to exit after a short delay so the HTTP response can be sent first."""
    def _exit_after_delay():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_exit_after_delay, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/agent/<path:agent_id>/stop", methods=["POST", "OPTIONS"])
@require_auth
def stop_agent(agent_id):
    """Sends a stop command for the specified agent so it finishes its current step and goes idle."""
    if request.method == "OPTIONS":
        return "", 204
    stop_result = proxy.request("stop_agent", agent_id=agent_id, user_id=request.user_id)
    return jsonify(stop_result)


@app.route("/api/agent/<path:agent_id>/disconnect", methods=["POST", "OPTIONS"])
@require_auth
def disconnect_agent(agent_id):
    """Sends a disconnect command for the specified agent and removes its runtime files from the server."""
    if request.method == "OPTIONS":
        return "", 204
    disconnect_result = proxy.request("disconnect_agent", agent_id=agent_id, user_id=request.user_id)
    return jsonify(disconnect_result)


def run(host="0.0.0.0", port=1234):
    """Starts the dashboard web server using waitress if available, falling back to Flask's built-in server."""
    print(f"[✓] Dashboard running on http://localhost:{port}")
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=4, _quiet=True)
    except ImportError:
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run()
