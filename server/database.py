import hashlib
import json
import os
import sqlite3
import threading
import time


DATABASE_FILE_PATH = os.path.join(os.path.dirname(__file__), "harmony.db")
_local = threading.local()  # each worker gets its own link to the database


def get_connection():
    # If it already opened the database earlier, use that same one again.
    if hasattr(_local, "conn"): # Check inside the thread object if there is a conn in it already
        return _local.conn

    # Open the database file for the first time.
    conn = sqlite3.connect(DATABASE_FILE_PATH, timeout=30, isolation_level=None)

    conn.execute("PRAGMA journal_mode=WAL")    # let many threads read and write at once
    conn.execute("PRAGMA busy_timeout=30000")  # if it's busy, wait up to 30 seconds
    conn.execute("PRAGMA synchronous=NORMAL")  # faster writes
    conn.row_factory = sqlite3.Row  # access columns by name (row["id"]) instead of index (row[0])

    # Remember it so it don't open a new one next time.
    _local.conn = conn
    return conn


def fetch_all_rows(sql, params=()):
    return [dict(row) for row in get_connection().execute(sql, params).fetchall()]


def fetch_one_row(sql, params=()):
    row = get_connection().execute(sql, params).fetchone()
    return dict(row) if row else None


def execute_and_commit(sql, params=()):
    connection = get_connection()
    connection.execute("BEGIN IMMEDIATE")
    try:
        cursor = connection.execute(sql, params)
        connection.execute("COMMIT")
        return cursor
    except Exception:
        connection.execute("ROLLBACK")
        raise


def init_db():
    get_connection().executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            assigned_agent TEXT,
            created_at REAL NOT NULL,
            user_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'idle',
            task TEXT,
            status_text TEXT,
            step_json TEXT,
            connected_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal TEXT NOT NULL,
            steps_json TEXT NOT NULL,
            current_step INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'running',
            user_id INTEGER,
            agent_id TEXT,
            created_at REAL NOT NULL
        );
    """)

    # Older databases may not have the plan_id column on tasks yet.
    try:
        execute_and_commit("ALTER TABLE tasks ADD COLUMN plan_id INTEGER")
    except sqlite3.OperationalError:
        pass


def register_agent(agent_id):
    now = time.time()
    execute_and_commit(
        "INSERT OR REPLACE INTO agents (agent_id, status, connected_at, updated_at) VALUES (?, 'idle', ?, ?)",
        (agent_id, now, now))


def update_agent(agent_id, **fields):
    allowed = {"status", "task", "status_text", "step_json"}
    safe = {k: v for k, v in fields.items() if k in allowed}
    if not safe:
        return
    safe["updated_at"] = time.time()
    set_clause = ", ".join(f"{k} = ?" for k in safe)
    execute_and_commit(f"UPDATE agents SET {set_clause} WHERE agent_id = ?",
                       list(safe.values()) + [agent_id])


def remove_agent(agent_id):
    execute_and_commit("DELETE FROM agents WHERE agent_id = ?", (agent_id,))


def get_agent(agent_id):
    return fetch_one_row("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))


def get_all_agents():
    return fetch_all_rows("SELECT * FROM agents ORDER BY agent_id")


def set_agent_status(agent_id, status):
    execute_and_commit("UPDATE agents SET status = ? WHERE agent_id = ?", (status, agent_id))


def add_task(task_text, user_id=None, agent_id=None, plan_id=None):
    cursor = execute_and_commit(
        "INSERT INTO tasks (task, status, assigned_agent, created_at, user_id, plan_id) VALUES (?, 'queued', ?, ?, ?, ?)",
        (task_text, agent_id, time.time(), user_id, plan_id))
    return cursor.lastrowid


def get_task(task_id):
    return fetch_one_row("SELECT * FROM tasks WHERE id = ?", (task_id,))


def mark_task_done(task_id):
    execute_and_commit("UPDATE tasks SET status = 'done' WHERE id = ?", (task_id,))


def get_queued_tasks(agent_id=None):
    if agent_id:
        return fetch_all_rows(
            "SELECT id, task, assigned_agent FROM tasks WHERE status = 'queued' AND assigned_agent = ? ORDER BY id",
            (agent_id,))
    return fetch_all_rows(
        "SELECT id, task, assigned_agent FROM tasks WHERE status = 'queued' AND assigned_agent IS NULL ORDER BY id")


def get_tasks_for_user(user_id):
    return fetch_all_rows(
        "SELECT id, task, status, assigned_agent, created_at FROM tasks WHERE user_id = ? ORDER BY id DESC",
        (user_id,))


def assign_task(task_id, agent_id):
    execute_and_commit(
        "UPDATE tasks SET status = 'assigned', assigned_agent = ? WHERE id = ?",
        (agent_id, task_id))


def delete_task(task_id, user_id):
    task = fetch_one_row("SELECT id, user_id FROM tasks WHERE id = ?", (task_id,))
    if task is None or str(task["user_id"]) != str(user_id):
        return False
    execute_and_commit("DELETE FROM tasks WHERE id = ?", (task_id,))
    return True


def create_user(username, password):
    salt = os.urandom(32).hex()
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    try:
        execute_and_commit(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, hashed, salt, time.time()))
        return True
    except sqlite3.IntegrityError:
        return False


# --- Plans ------------------------------------------------------------------

def create_plan(goal, steps, user_id=None, agent_id=None):
    # Store a new plan. `steps` is a list of short task descriptions.
    cursor = execute_and_commit(
        "INSERT INTO plans (goal, steps_json, user_id, agent_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (goal, json.dumps(steps), user_id, agent_id, time.time()))
    return cursor.lastrowid


def get_plan(plan_id):
    plan = fetch_one_row("SELECT * FROM plans WHERE id = ?", (plan_id,))
    if plan:
        plan["steps"] = json.loads(plan["steps_json"])
    return plan


def get_plans_for_user(user_id):
    rows = fetch_all_rows(
        "SELECT * FROM plans WHERE user_id = ? ORDER BY id DESC",
        (user_id,))
    for row in rows:
        row["steps"] = json.loads(row["steps_json"])
    return rows


def advance_plan(plan_id):
    # Move to the next step. Returns the next step text, or None if finished.
    plan = get_plan(plan_id)
    if plan is None:
        return None

    next_index = plan["current_step"] + 1
    if next_index >= len(plan["steps"]):
        execute_and_commit(
            "UPDATE plans SET status = 'done', current_step = ? WHERE id = ?",
            (len(plan["steps"]), plan_id))
        return None

    execute_and_commit(
        "UPDATE plans SET current_step = ? WHERE id = ?",
        (next_index, plan_id))
    return plan["steps"][next_index]


def verify_user(username, password):
    user = fetch_one_row("SELECT id, password_hash, salt FROM users WHERE username = ?", (username,))
    if user is None:
        return None
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), user["salt"].encode(), 100_000).hex()
    return user["id"] if hashed == user["password_hash"] else None
