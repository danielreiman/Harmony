import hashlib
import json
import os
import sqlite3
import threading
import time


DB_PATH = os.path.join(os.path.dirname(__file__), "harmony.db")
SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600

_thread_local = threading.local()


def _conn():
    """Returns a per-thread SQLite connection, opening one with WAL mode the first time a thread calls it."""
    if hasattr(_thread_local, "connection"):
        return _thread_local.connection

    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=30000")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.row_factory = sqlite3.Row
    _thread_local.connection = connection
    return connection


# --- Schema ---

def _setup_tables(connection):
    """Creates all tables on first startup so the server has a working database immediately."""
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
            created_at REAL NOT NULL,
            user_id INTEGER,
            section_label TEXT,
            parent_task_id INTEGER,
            result_json TEXT
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

    # Schema migrations — safe to run on existing databases
    for migration in [
        "ALTER TABLE tasks ADD COLUMN result_json TEXT",
    ]:
        try:
            connection.execute(migration)
            connection.commit()
        except Exception:
            pass  # Column already exists


def init_db():
    """Creates all tables on server startup."""
    _setup_tables(_conn())


# --- Agents ---

def register_agent(agent_id):
    """Inserts or replaces an agent record with idle status when a client connects to the server."""
    connection = _conn()
    now = time.time()
    connection.execute(
        "INSERT OR REPLACE INTO agents (agent_id, status, connected_at, updated_at) VALUES (?, 'idle', ?, ?)",
        (agent_id, now, now)
    )
    connection.commit()


def update_agent(agent_id, **fields):
    """Updates allowed agent fields in the database — called by the agent after every state change."""
    connection = _conn()
    allowed_fields = {"status", "task", "status_text", "research_mode", "doc_id", "step_json", "cycle", "phase", "phase_count"}

    fields_to_update = {}
    for key, value in fields.items():
        if key in allowed_fields:
            fields_to_update[key] = value

    if not fields_to_update:
        return

    fields_to_update["updated_at"] = time.time()

    column_parts = []
    for key in fields_to_update:
        column_parts.append(f"{key} = ?")
    column_assignments = ", ".join(column_parts)

    values = list(fields_to_update.values()) + [agent_id]
    connection.execute(f"UPDATE agents SET {column_assignments} WHERE agent_id = ?", values)
    connection.commit()


def remove_agent(agent_id):
    """Deletes the agent record when the manager detects it has disconnected."""
    connection = _conn()
    connection.execute("DELETE FROM agents WHERE agent_id = ?", (agent_id,))
    connection.commit()


def get_agent(agent_id):
    """Fetches a single agent record by ID — used by the manager and API to check agent state."""
    connection = _conn()
    row = connection.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    if row:
        return dict(row)
    return None


def get_all_agents():
    """Fetches all agent records ordered by ID."""
    connection = _conn()
    rows = connection.execute("SELECT * FROM agents ORDER BY agent_id").fetchall()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


def set_command(agent_id, command):
    """Writes a command status to the agent row so the manager loop picks it up on the next tick."""
    connection = _conn()
    connection.execute(
        "UPDATE agents SET status = ? WHERE agent_id = ?",
        (command, agent_id)
    )
    connection.commit()


# --- Tasks ---

def add_task(task, research_mode=False, doc_id=None, user_id=None, section_label=None, parent_task_id=None):
    """Inserts a general queued task that the manager will assign to the next idle agent."""
    connection = _conn()
    cursor = connection.execute(
        "INSERT INTO tasks (task, research_mode, doc_id, status, created_at, user_id, section_label, parent_task_id) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)",
        (task, int(research_mode), doc_id, time.time(), user_id, section_label, parent_task_id)
    )
    connection.commit()
    return cursor.lastrowid


def add_task_for_agent(task, agent_id, research_mode=False, doc_id=None, user_id=None, section_label=None, parent_task_id=None):
    """Inserts a task pre-assigned to a specific agent so the manager routes it directly."""
    connection = _conn()
    cursor = connection.execute(
        "INSERT INTO tasks (task, research_mode, doc_id, status, assigned_agent, created_at, user_id, section_label, parent_task_id) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?)",
        (task, int(research_mode), doc_id, agent_id, time.time(), user_id, section_label, parent_task_id)
    )
    connection.commit()
    return cursor.lastrowid


def get_queued_tasks(agent_id=None):
    """Fetches queued tasks targeted at a specific agent, or all unassigned tasks if no agent is given."""
    connection = _conn()
    if agent_id:
        rows = connection.execute(
            "SELECT id, task, research_mode, doc_id, assigned_agent, section_label, parent_task_id FROM tasks WHERE status = 'queued' AND assigned_agent = ? ORDER BY id",
            (agent_id,)
        ).fetchall()
    else:
        rows = connection.execute(
            "SELECT id, task, research_mode, doc_id, assigned_agent, section_label, parent_task_id FROM tasks WHERE status = 'queued' AND assigned_agent IS NULL ORDER BY id"
        ).fetchall()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


def get_tasks_for_user(user_id):
    """Fetches all tasks belonging to the given user, newest first, for the dashboard task list."""
    connection = _conn()
    rows = connection.execute(
        "SELECT id, task, status, assigned_agent, created_at FROM tasks WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


def get_task_logs_for_user(user_id):
    """Fetches the 200 most recent task log entries for the user's tasks to populate the dashboard activity feed."""
    connection = _conn()
    rows = connection.execute(
        """SELECT task_log.id, task_log.task_id, task_log.agent_id, task_log.action,
                  task_log.detail, task_log.created_at
           FROM task_log
           JOIN tasks ON task_log.task_id = tasks.id
           WHERE tasks.user_id = ?
           ORDER BY task_log.id DESC
           LIMIT 200""",
        (user_id,)
    ).fetchall()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


def assign_task(task_id, agent_id):
    """Marks a task as assigned to the given agent so the manager doesn't hand it to another agent."""
    connection = _conn()
    connection.execute(
        "UPDATE tasks SET status = 'assigned', assigned_agent = ? WHERE id = ?",
        (agent_id, task_id)
    )
    connection.commit()


def complete_task(task_id):
    """Marks a task as complete — called by the manager after the agent finishes."""
    connection = _conn()
    connection.execute("UPDATE tasks SET status = 'complete' WHERE id = ?", (task_id,))
    connection.commit()


def mark_task_split(task_id):
    """Marks a parent research task as split so the manager ignores it in future dispatch loops."""
    connection = _conn()
    connection.execute("UPDATE tasks SET status = 'split' WHERE id = ?", (task_id,))
    connection.commit()


def get_task_by_id(task_id):
    """Fetches a single task row by its ID."""
    connection = _conn()
    row = connection.execute(
        "SELECT id, task, research_mode, doc_id, status, assigned_agent, user_id, section_label, parent_task_id, result_json FROM tasks WHERE id = ?",
        (task_id,)
    ).fetchone()
    if row:
        return dict(row)
    return None


def set_task_result(task_id, data):
    """Stores a result JSON blob for a completed task (e.g., bibliography entries from a research agent)."""
    connection = _conn()
    connection.execute(
        "UPDATE tasks SET result_json = ? WHERE id = ?",
        (json.dumps(data), task_id)
    )
    connection.commit()


def get_subtasks(parent_task_id):
    """Fetches all sub-tasks belonging to a parent research task."""
    connection = _conn()
    rows = connection.execute(
        "SELECT id, task, research_mode, doc_id, status, assigned_agent, section_label, result_json FROM tasks WHERE parent_task_id = ? ORDER BY id",
        (parent_task_id,)
    ).fetchall()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


def get_split_tasks():
    """Fetches all parent research tasks that have been split into subtasks."""
    connection = _conn()
    rows = connection.execute(
        "SELECT id, task, doc_id FROM tasks WHERE status = 'split' ORDER BY id"
    ).fetchall()
    result = []
    for row in rows:
        result.append(dict(row))
    return result


# --- Users ---

def create_user(username, password):
    """Creates a new user with a salted password hash — returns False if the username is taken."""
    connection = _conn()
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


def verify_user(username, password):
    """Verifies credentials against the stored hash and returns the user ID, or None if they don't match."""
    connection = _conn()
    row = connection.execute(
        "SELECT id, password_hash, salt FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if row is None:
        return None

    attempt_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), row["salt"].encode(), 100_000).hex()
    if attempt_hash == row["password_hash"]:
        return row["id"]
    return None


def get_username(user_id):
    """Looks up the display name for a user ID — used when building the auth_validate response."""
    connection = _conn()
    row = connection.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if row:
        return row["username"]
    return None


# --- Sessions ---

def create_session(user_id):
    """Creates a new session record and returns the generated token for the dashboard to store."""
    connection = _conn()
    token = os.urandom(32).hex()
    now = time.time()
    connection.execute(
        "INSERT INTO sessions (token, user_id, created_at, last_active) VALUES (?, ?, ?, ?)",
        (token, user_id, now, now)
    )
    connection.commit()
    return token


def validate_session(token):
    """Validates the session token, expires it if stale, refreshes last_active if valid, and returns the user ID."""
    connection = _conn()
    row = connection.execute(
        "SELECT user_id, last_active FROM sessions WHERE token = ?",
        (token,)
    ).fetchone()

    if row is None:
        return None

    age_in_seconds = time.time() - row["last_active"]
    if age_in_seconds > SESSION_MAX_AGE_SECONDS:
        connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
        connection.commit()
        return None

    connection.execute("UPDATE sessions SET last_active = ? WHERE token = ?", (time.time(), token))
    connection.commit()
    return row["user_id"]


def delete_session(token):
    """Removes the session record so the user is logged out of the dashboard."""
    connection = _conn()
    connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
    connection.commit()


# --- Messages ---

def send_agent_message(agent_id, content):
    """Inserts a message into the queue so the manager delivers it to a running agent on the next tick."""
    connection = _conn()
    connection.execute(
        "INSERT INTO agent_messages (agent_id, content, consumed, created_at) VALUES (?, ?, 0, ?)",
        (agent_id, content, time.time())
    )
    connection.commit()


def consume_agent_messages(agent_id):
    """Fetches all unconsumed messages for an agent and marks them as consumed so they aren't delivered twice."""
    connection = _conn()
    rows = connection.execute(
        "SELECT id, content FROM agent_messages WHERE agent_id = ? AND consumed = 0 ORDER BY id",
        (agent_id,)
    ).fetchall()

    if not rows:
        return []

    message_ids = []
    for row in rows:
        message_ids.append(row["id"])

    placeholder_list = []
    for _ in message_ids:
        placeholder_list.append("?")
    placeholders = ",".join(placeholder_list)

    connection.execute(
        f"UPDATE agent_messages SET consumed = 1 WHERE id IN ({placeholders})",
        message_ids
    )
    connection.commit()

    messages = []
    for row in rows:
        messages.append(row["content"])
    return messages
