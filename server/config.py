import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")

_here = os.path.dirname(os.path.abspath(__file__))


def _find_service_account():
    """Looks for a Google service account JSON file in the server/ directory."""
    env_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if env_path and os.path.exists(env_path):
        return env_path

    for filename in os.listdir(_here):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(_here, filename)
        try:
            import json
            with open(filepath) as f:
                data = json.load(f)
            if data.get("type") == "service_account":
                return filepath
        except Exception:
            continue

    return None


GOOGLE_SERVICE_ACCOUNT_FILE = _find_service_account()

if not OLLAMA_API_KEY:
    raise ValueError("OLLAMA_API_KEY not found. Run 'python server/setup.py' to configure.")

if not GOOGLE_SERVICE_ACCOUNT_FILE:
    raise ValueError(
        "Google service account not found. Place your service account JSON file "
        "in the server/ directory and restart."
    )
