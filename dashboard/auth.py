from functools import wraps
from flask import jsonify, redirect, request, session
import proxy

API_PATH_PREFIXES = ("/api/", "/agents", "/agent/", "/screen/")


def _request_is_api_call() -> bool:
    path = request.path
    for prefix in API_PATH_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _respond_unauthorized():
    if _request_is_api_call():
        return jsonify({"error": "Unauthorized"}), 401
    return redirect("/login")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        session_token = session.get("token")

        if not session_token:
            return _respond_unauthorized()

        validation_result = proxy.request("auth_validate", token=session_token)
        session_has_error = "error" in validation_result
        session_is_empty = not validation_result
        session_is_invalid = session_has_error or session_is_empty

        if session_is_invalid:
            session.clear()
            return _respond_unauthorized()

        request.user_id = validation_result["user_id"]
        request.username = validation_result["username"]
        return f(*args, **kwargs)

    return decorated
