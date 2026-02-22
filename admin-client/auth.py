from functools import wraps
from flask import jsonify, request
import proxy


def require_auth(f):
    """Decorator that validates the Authorization header token before allowing access to the route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            resp = jsonify({"error": "Unauthorized"})
            resp.status_code = 401
            return resp

        token = auth_header[len("Bearer "):]

        validation_result = proxy.request("auth_validate", token=token)
        if "error" in validation_result or not validation_result:
            resp = jsonify({"error": "Unauthorized"})
            resp.status_code = 401
            return resp

        request.user_id = validation_result["user_id"]
        request.username = validation_result["username"]
        return f(*args, **kwargs)

    return decorated
