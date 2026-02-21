import os
from dotenv import load_dotenv

load_dotenv()

HARMONY_SERVER = os.environ.get("HARMONY_SERVER", "")
SECRET_KEY = os.environ.get("DASHBOARD_SECRET_KEY") or os.urandom(32).hex()
