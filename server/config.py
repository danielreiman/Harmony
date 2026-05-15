import os
from dotenv import load_dotenv
from setup import main as run_setup
load_dotenv()

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")

if not OLLAMA_API_KEY:
    run_setup()
    OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")

RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")
