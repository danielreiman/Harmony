import os
from dotenv import load_dotenv

load_dotenv()

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")

if not OLLAMA_API_KEY:
    raise ValueError("OLLAMA_API_KEY not found. Run 'python server/setup.py' to configure.")
