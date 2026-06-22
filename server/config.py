import os
from dotenv import load_dotenv
load_dotenv()  # read settings from a .env file if present

HAI_API_KEY = os.environ.get("HAI_API_KEY", "")          # key for the AI provider
AI_MODEL    = os.environ.get("MODEL", "holo3-1-35b-a3b")  # which model the agents use

RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")  # temp screenshots, etc.
