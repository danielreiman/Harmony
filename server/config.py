import os
from dotenv import load_dotenv
from setup import main as run_setup
load_dotenv()

HAI_API_KEY = os.environ.get("HAI_API_KEY")

if not HAI_API_KEY:
    run_setup()
    HAI_API_KEY = os.environ.get("HAI_API_KEY")

RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")
