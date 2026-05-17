import os
from dotenv import load_dotenv
load_dotenv()

HAI_API_KEY = os.environ.get("HAI_API_KEY", "")
AI_MODEL    = os.environ.get("MODEL", "holo3-122b-a10b")

RUNTIME_DIR = os.path.join(os.path.dirname(__file__), "runtime")
