import hashlib
import os
import sqlite3
import threading
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "harmony.db")
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600

_thread_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    connection = getattr(_thread_local, "connection", None)
    if connection is None:
        connection = sqlite3.connect(DB_PATH, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.row_factory = sqlite3.Row
        _thread_local.connection = connection
    return connection


def init_db():
    connection = _get_connection()
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            created_at REAL NOT NULL,
            last_active REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            research_mode INTEGER NOT NULL DEFAULT 0,
            doc_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            assigned_agent TEXT,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'idle',
            task TEXT,
            status_text TEXT,
            research_mode INTEGER NOT NULL DEFAULT 0,
            doc_id TEXT,
            step_json TEXT,
            cycle INTEGER NOT NULL DEFAULT 0,
            phase TEXT,
            phase_count INTEGER NOT NULL DEFAULT 0,
            connected_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER REFERENCES tasks(id),
            agent_id TEXT,
            action TEXT NOT NULL,
            detail TEXT,
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            content TEXT NOT NULL,
            consumed INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        );
    """)
    connection.commit()


def add_task(task: str, research_mode: bool = False, doc_id: str = None) -> int:
    connection = _get_connection()
    cursor = connection.execute(
        "INSERT INTO tasks (task, research_mode, doc_id, status, created_at) VALUES (?, ?, ?, 'queued', ?)",
        (task, int(research_mode), doc_id, time.time())
    )
    connection.commit()
    return cursor.lastrowid


def add_task_for_agent(task: str, agent_id: str, research_mode: bool = False, doc_id: str = None) -> int:
    connection = _get_connection()
    cursor = connection.execute(
        "INSERT INTO tasks (task, research_mode, doc_id, status, assigned_agent, created_at) VALUES (?, ?, ?, 'queued', ?, ?)",
        (task, int(research_mode), doc_id, agent_id, time.time())
    )
    connection.commit()
    return cursor.lastrowid


def get_queued_tasks(agent_id: str = None) -> list[dict]:
    connection = _get_connection()
    if agent_id:
        rows = connection.execute(
            "SELECT id, task, research_mode, doc_id, assigned_agent FROM tasks WHERE status = 'queued' AND assigned_agent = ? ORDER BY id",
            (agent_id,)
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT id, task, research_mode, doc_id, assigned_agent FROM tasks WHERE status = 'queued' AND assigned_agent IS NULL ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_queued_tasks() -> list[dict]:
    connection = _get_connection()
    rows = connection.execute(
        "SELECT id, task, research_mode, doc_id, assigned_agent FROM tasks WHERE status = 'queued' ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


def assign_task(task_id: int, agent_id: str):
    connection = _get_connection()
    connection.execute(
        "UPDATE tasks SET status = 'assigned', assigned_agent = ? WHERE id = ?",
        (agent_id, task_id)
    )
    connection.commit()


def complete_task(task_id: int):
    connection = _get_connection()
    connection.execute("UPDATE tasks SET status = 'completed' WHERE id = ?", (task_id,))
    connection.commit()


def register_agent(agent_id: str):
    connection = _get_connection()
    now = time.time()
    connection.execute(
        "INSERT OR REPLACE INTO agents (agent_id, status, connected_at, updated_at) VALUES (?, 'idle', ?, ?)",
        (agent_id, now, now)
    )
    connection.commit()


def update_agent(agent_id: str, **fields):
    connection = _get_connection()
    allowed_fields = {"status", "task", "status_text", "research_mode", "doc_id", "step_json", "cycle", "phase", "phase_count"}
    fields_to_update = {key: value for key, value in fields.items() if key in allowed_fields}

    if not fields_to_update:
        return

    fields_to_update["updated_at"] = time.time()
    column_assignments = ", ".join(f"{key} = ?" for key in fields_to_update)
    values = list(fields_to_update.values()) + [agent_id]
    connection.execute(f"UPDATE agents SET {column_assignments} WHERE agent_id = ?", values)
    connection.commit()


def remove_agent(agent_id: str):
    connection = _get_connection()
    connection.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
    connection.commit()


def get_agent(agent_id: str) -> dict | None:
    connection = _get_connection()
    row = connection.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    return dict(row) if row else None


def get_all_agents() -> list[dict]:
    connection = _get_connection()
    rows = connection.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()
    return [dict(row) for row in rows]


def log_task_event(task_id: int, agent_id: str, action: str, detail: str = None):
    connection = _get_connection()
    connection.execute(
        "INSERT INTO task_log (task_id, agent_id, action, detail, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_id, agent_id, action, detail, time.time())
    )
    connection.commit()


def set_command(agent_id: str, command: str):
    connection = _get_connection()
    connection.execute(
        "UPDATE agents SET status = ? WHERE agent_id = ?",
        (command, agent_id)
    )
    connection.commit()


def send_agent_message(agent_id: str, content: str):
    connection = _get_connection()
    connection.execute(
        "INSERT INTO agent_messages (agent_id, content, consumed, created_at) VALUES (?, ?, 0, ?)",
        (agent_id, content, time.time())
    )
    connection.commit()


def create_user(username: str, password: str) -> bool:
    connection = _get_connection()
    salt = os.urandom(32).hex()
    password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    try:
        connection.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, salt, time.time())
        )
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def verify_user(username: str, password: str) -> int | None:
    connection = _get_connection()
    row = connection.execute(
        "SELECT id, password_hash, salt FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if row is None:
        return None

    attempt_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), row["salt"].encode(), 100_000).hex()
    password_is_correct = attempt_hash == row["password_hash"]

    if password_is_correct:
        return row["id"]
    return None


def create_session(user_id: int) -> str:
    connection = _get_connection()
    token = os.urandom(32).hex()
    now = time.time()
    connection.execute(
        "INSERT INTO sessions (token, user_id, created_at, last_active) VALUES (?, ?, ?, ?)",
        (token, user_id, now, now)
    )
    connection.commit()
    return token


def validate_session(token: str) -> int | None:
    connection = _get_connection()
    row = connection.execute(
        "SELECT user_id, last_active FROM sessions WHERE token = ?",
        (token,)
    ).fetchone()

    if row is None:
        return None

    session_age_seconds = time.time() - row["last_active"]
    session_is_expired = session_age_seconds > SESSION_MAX_AGE_SECONDS
    if session_is_expired:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        connection.commit()
        return None

    connection.execute("UPDATE sessions SET last_active = ? WHERE token = ?", (time.time(), token))
    connection.commit()
    return row["user_id"]


def delete_session(token: str):
    connection = _get_connection()
    connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
    connection.commit()


def get_username(user_id: int) -> str | None:
    connection = _get_connection()
    row = connection.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["username"] if row else None


def consume_agent_messages(agent_id: str) -> list[str]:
    connection = _get_connection()
    rows = connection.execute(
        "SELECT id, content FROM agent_messages WHERE agent_id = ? AND consumed = 0 ORDER BY id",
        (agent_id,)
    ).fetchall()

    if not rows:
        return []

    message_ids = [row["id"] for row in rows]
    placeholders = ",".join("?" * len(message_ids))
    connection.execute(
        f"UPDATE agent_messages SET consumed = 1 WHERE id IN ({placeholders})",
        message_ids
    )
    connection.commit()
    return [row["content"] for row in rows]
