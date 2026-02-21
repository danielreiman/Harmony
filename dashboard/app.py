import base64
import os
import threading
import time
from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, session
from auth import require_auth
import proxy
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


@app.after_request
def disable_caching(response):
    response.headers["Cache-Control"] = "no-store, no-cache, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    credentials_are_missing = not username or not password
    if credentials_are_missing:
        return jsonify({"error": "Username and password are required"}), 400

    login_result = proxy.request("auth_login", username=username, password=password)

    if "error" in login_result:
        return jsonify({"error": login_result["error"]}), 401

    if "token" not in login_result:
        return jsonify({"error": "Could not connect to server"}), 503

    session["token"] = login_result["token"]
    return jsonify({"success": True})


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return redirect("/login")

    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    confirm_password = body.get("confirm") or ""

    credentials_are_missing = not username or not password
    if credentials_are_missing:
        return jsonify({"error": "Username and password are required"}), 400

    username_too_short = len(username) < 3
    if username_too_short:
        return jsonify({"error": "Username must be at least 3 characters"}), 400

    password_too_short = len(password) < 6
    if password_too_short:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    passwords_do_not_match = password != confirm_password
    if passwords_do_not_match:
        return jsonify({"error": "Passwords do not match"}), 400

    signup_result = proxy.request("auth_signup", username=username, password=password)

    if "error" in signup_result:
        return jsonify({"error": signup_result["error"]}), 409

    if "token" not in signup_result:
        return jsonify({"error": "Could not connect to server"}), 503

    session["token"] = signup_result["token"]
    return jsonify({"success": True})


@app.route("/logout")
def logout():
    session_token = session.get("token")
    if session_token:
        proxy.request("auth_logout", token=session_token)
    session.clear()
    return redirect("/login")


@app.route("/")
@require_auth
def index():
    service_account_info = proxy.request("get_service_account")
    service_account_is_present = service_account_info.get("has_key", False)
    service_account_email = service_account_info.get("email", "")
    return render_template(
        "dashboard.html",
        service_account_present=service_account_is_present,
        service_account_email=service_account_email,
    )


@app.route("/icon.png")
def icon():
    icon_path = os.path.join(os.path.dirname(__file__), "static", "icon.png")
    if os.path.exists(icon_path):
        return send_file(icon_path, mimetype="image/png")
    return "", 404


@app.route("/agents")
@require_auth
def agents():
    agent_list_result = proxy.request("get_agents")
    agent_list = agent_list_result.get("agents", [])
    return jsonify(agent_list)


@app.route("/agent/<path:agent_id>")
@require_auth
def agent_state(agent_id):
    agent_data = proxy.request("get_agent", agent_id=agent_id)
    return jsonify(agent_data)


@app.route("/screen/<path:agent_id>")
@require_auth
def agent_screen(agent_id):
    screenshot_result = proxy.request("get_screen", agent_id=agent_id)

    has_error = "error" in screenshot_result
    has_no_data = "data" not in screenshot_result
    screenshot_is_unavailable = has_error or has_no_data
    if screenshot_is_unavailable:
        error_message = screenshot_result.get("error", "No screenshot")
        return error_message, 404

    image_bytes = base64.b64decode(screenshot_result["data"])
    return Response(image_bytes, content_type="image/png", headers={"Cache-Control": "no-store"})


@app.route("/api/send-task", methods=["POST", "OPTIONS"])
@require_auth
def send_task():
    if request.method == "OPTIONS":
        return "", 204

    body = request.json or {}
    task_text = body.get("task", "")
    agent_id = body.get("agent_id")
    research_mode = body.get("research_mode", False)
    doc_id = body.get("doc_id")

    task_result = proxy.request(
        "send_task",
        task=task_text,
        agent_id=agent_id,
        research_mode=research_mode,
        doc_id=doc_id,
    )
    return jsonify(task_result)


@app.route("/api/agent/<path:agent_id>/stop", methods=["POST", "OPTIONS"])
@require_auth
def stop_agent(agent_id):
    if request.method == "OPTIONS":
        return "", 204
    stop_result = proxy.request("stop_agent", agent_id=agent_id)
    return jsonify(stop_result)


@app.route("/api/agent/<path:agent_id>/disconnect", methods=["POST", "OPTIONS"])
@require_auth
def disconnect_agent(agent_id):
    if request.method == "OPTIONS":
        return "", 204
    disconnect_result = proxy.request("disconnect_agent", agent_id=agent_id)
    return jsonify(disconnect_result)


@app.route("/api/server/stop", methods=["POST", "OPTIONS"])
def stop_server():
    if request.method == "OPTIONS":
        return "", 204
    stop_result = proxy.request("stop_server")
    return jsonify(stop_result)


@app.route("/api/status")
def api_status():
    server_is_reachable = proxy.ping()
    return jsonify({"ok": server_is_reachable})


@app.route("/api/dashboard/stop", methods=["POST"])
def dashboard_stop():
    def _exit_after_delay():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_exit_after_delay, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/tasks")
@require_auth
def get_tasks():
    tasks_result = proxy.request("get_tasks")
    task_list = tasks_result.get("tasks", [])
    return jsonify(task_list)


def run(host: str = "0.0.0.0", port: int = 1234):
    print(f"[✓] Dashboard running on http://localhost:{port}")
    try:
        from waitress import serve
        serve(app, host=host, port=port, threads=4, _quiet=True)
    except ImportError:
        app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run()
