import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")

if not OLLAMA_API_KEY:
    raise ValueError("OLLAMA_API_KEY not found. Run 'python server/setup.py' to configure.")

if not GOOGLE_SERVICE_ACCOUNT_FILE:
    raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE not found. Run 'python server/setup.py' to configure.")
