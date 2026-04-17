import hashlib
import json
import os
import sqlite3
import threading
import time


DATABASE_FILE_PATH = os.path.join(os.path.dirname(__file__), "harmony.db")

# Each thread gets its own database connection
per_thread_storage = threading.local()


def get_connection():
    if not hasattr(per_thread_storage, "connection"):
        connection = sqlite3.connect(DATABASE_FILE_PATH, timeout=30, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.row_factory = sqlite3.Row
        per_thread_storage.connection = connection
    return per_thread_storage.connection


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
    """)


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


def add_task(task_text, user_id=None, agent_id=None):
    cursor = execute_and_commit(
        "INSERT INTO tasks (task, status, assigned_agent, created_at, user_id) VALUES (?, 'queued', ?, ?, ?)",
        (task_text, agent_id, time.time(), user_id))
    return cursor.lastrowid


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


def verify_user(username, password):
    user = fetch_one_row("SELECT id, password_hash, salt FROM users WHERE username = ?", (username,))
    if user is None:
        return None
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), user["salt"].encode(), 100_000).hex()
    return user["id"] if hashed == user["password_hash"] else None
