import hashlib
import json
import os
import sqlite3
import threading
import time


DATABASE_FILE_PATH = os.path.join(os.path.dirname(__file__), "harmony.db")
SESSION_EXPIRES_AFTER_SECONDS = 7 * 24 * 3600

# Each thread gets its own database connection
_per_thread_storage = threading.local()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_connection():
    # Open a new connection the first time this thread talks to the database
    already_connected = hasattr(_per_thread_storage, "connection")
    if not already_connected:
        connection = sqlite3.connect(DATABASE_FILE_PATH, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.row_factory = sqlite3.Row
        _per_thread_storage.connection = connection
    return _per_thread_storage.connection


def _fetch_all_rows(sql, params=()):
    # Run a SELECT and return every matching row as a plain dict
    connection = _get_connection()
    raw_rows = connection.execute(sql, params).fetchall()
    result = [dict(row) for row in raw_rows]
    return result


def _fetch_one_row(sql, params=()):
    # Run a SELECT and return the first row as a dict, or None if nothing matched
    connection = _get_connection()
    raw_row = connection.execute(sql, params).fetchone()
    if raw_row is None:
        return None
    return dict(raw_row)


def _execute_and_commit(sql, params=()):
    # Run an INSERT / UPDATE / DELETE and save the change
    connection = _get_connection()
    cursor = connection.execute(sql, params)
    connection.commit()
    return cursor


# ── Schema ────────────────────────────────────────────────────────────────────

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
            step_json TEXT,
            cycle INTEGER NOT NULL DEFAULT 0,
            phase TEXT,
            phase_count INTEGER NOT NULL DEFAULT 0,
            connected_at REAL NOT NULL,
            updated_at REAL NOT NULL
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

    # Run any schema changes that need to be added to existing databases
    pending_migrations = [
        "ALTER TABLE tasks ADD COLUMN result_json TEXT",
    ]
    for migration_sql in pending_migrations:
        try:
            connection.execute(migration_sql)
            connection.commit()
        except Exception:
            pass  # Column already exists — skip


# ── Agents ────────────────────────────────────────────────────────────────────

def register_agent(agent_id):
    current_time = time.time()
    sql = "INSERT OR REPLACE INTO agents (agent_id, status, connected_at, updated_at) VALUES (?, 'idle', ?, ?)"
    values = (agent_id, current_time, current_time)
    _execute_and_commit(sql, values)


def update_agent(agent_id, **fields_to_update):
    # Only allow updating known safe fields — ignore anything else
    allowed_field_names = {"status", "task", "status_text", "research_mode", "step_json", "cycle", "phase", "phase_count"}
    safe_fields = {}
    for field_name, field_value in fields_to_update.items():
        if field_name in allowed_field_names:
            safe_fields[field_name] = field_value

    if not safe_fields:
        return

    safe_fields["updated_at"] = time.time()

    set_parts = [f"{field} = ?" for field in safe_fields]
    set_clause = ", ".join(set_parts)
    sql = f"UPDATE agents SET {set_clause} WHERE agent_id = ?"
    values = list(safe_fields.values()) + [agent_id]
    _execute_and_commit(sql, values)


def remove_agent(agent_id):
    sql = "DELETE FROM agents WHERE agent_id = ?"
    _execute_and_commit(sql, (agent_id,))


def get_agent(agent_id):
    sql = "SELECT * FROM agents WHERE agent_id = ?"
    return _fetch_one_row(sql, (agent_id,))


def get_all_agents():
    sql = "SELECT * FROM agents ORDER BY agent_id"
    return _fetch_all_rows(sql)


def set_agent_command(agent_id, command_status):
    sql = "UPDATE agents SET status = ? WHERE agent_id = ?"
    values = (command_status, agent_id)
    _execute_and_commit(sql, values)


# ── Tasks ─────────────────────────────────────────────────────────────────────

def add_task(task_text, research_mode=False, user_id=None, section_label=None, parent_task_id=None):
    sql = "INSERT INTO tasks (task, research_mode, status, created_at, user_id, section_label, parent_task_id) VALUES (?, ?, 'queued', ?, ?, ?, ?)"
    values = (task_text, int(research_mode), time.time(), user_id, section_label, parent_task_id)
    cursor = _execute_and_commit(sql, values)
    new_task_id = cursor.lastrowid
    return new_task_id


def add_task_for_agent(task_text, agent_id, research_mode=False, user_id=None, section_label=None, parent_task_id=None):
    sql = "INSERT INTO tasks (task, research_mode, status, assigned_agent, created_at, user_id, section_label, parent_task_id) VALUES (?, ?, 'queued', ?, ?, ?, ?, ?)"
    values = (task_text, int(research_mode), agent_id, time.time(), user_id, section_label, parent_task_id)
    cursor = _execute_and_commit(sql, values)
    new_task_id = cursor.lastrowid
    return new_task_id


def get_queued_tasks(for_agent_id=None):
    if for_agent_id:
        sql = "SELECT id, task, research_mode, assigned_agent, section_label, parent_task_id FROM tasks WHERE status = 'queued' AND assigned_agent = ? ORDER BY id"
        return _fetch_all_rows(sql, (for_agent_id,))
    else:
        sql = "SELECT id, task, research_mode, assigned_agent, section_label, parent_task_id FROM tasks WHERE status = 'queued' AND assigned_agent IS NULL ORDER BY id"
        return _fetch_all_rows(sql)


def get_tasks_for_user(user_id):
    sql = "SELECT id, task, status, assigned_agent, created_at, research_mode, parent_task_id FROM tasks WHERE user_id = ? ORDER BY id DESC"
    return _fetch_all_rows(sql, (user_id,))


def get_research_report(parent_task_id):
    parent_sql = "SELECT id, task, status, result_json FROM tasks WHERE id = ?"
    parent_task = _fetch_one_row(parent_sql, (parent_task_id,))

    subtasks_sql = "SELECT id, task, section_label, status, assigned_agent, result_json FROM tasks WHERE parent_task_id = ? ORDER BY id"
    subtask_list = _fetch_all_rows(subtasks_sql, (parent_task_id,))

    return {"parent": parent_task, "subtasks": subtask_list}


def assign_task(task_id, agent_id):
    sql = "UPDATE tasks SET status = 'assigned', assigned_agent = ? WHERE id = ?"
    values = (agent_id, task_id)
    _execute_and_commit(sql, values)


def complete_task(task_id):
    sql = "UPDATE tasks SET status = 'complete' WHERE id = ?"
    _execute_and_commit(sql, (task_id,))


def mark_task_split(task_id):
    sql = "UPDATE tasks SET status = 'split' WHERE id = ?"
    _execute_and_commit(sql, (task_id,))


def get_task_by_id(task_id):
    sql = "SELECT id, task, research_mode, status, assigned_agent, user_id, section_label, parent_task_id, result_json FROM tasks WHERE id = ?"
    return _fetch_one_row(sql, (task_id,))


def set_task_result(task_id, result_data):
    result_as_json_string = json.dumps(result_data)
    sql = "UPDATE tasks SET result_json = ? WHERE id = ?"
    values = (result_as_json_string, task_id)
    _execute_and_commit(sql, values)


def get_subtasks(parent_task_id):
    sql = "SELECT id, task, research_mode, status, assigned_agent, section_label, result_json FROM tasks WHERE parent_task_id = ? ORDER BY id"
    return _fetch_all_rows(sql, (parent_task_id,))


def get_split_tasks():
    sql = "SELECT id, task FROM tasks WHERE status = 'split' ORDER BY id"
    return _fetch_all_rows(sql)


def delete_task(task_id, user_id):
    # Make sure the task belongs to this user before deleting
    task = _fetch_one_row("SELECT id, user_id FROM tasks WHERE id = ?", (task_id,))
    task_not_found = task is None
    task_belongs_to_someone_else = task is not None and task["user_id"] != user_id
    if task_not_found or task_belongs_to_someone_else:
        return False

    # Delete subtasks first, then the parent task
    _execute_and_commit("DELETE FROM tasks WHERE parent_task_id = ?", (task_id,))
    _execute_and_commit("DELETE FROM tasks WHERE id = ?", (task_id,))
    return True


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username, password):
    random_salt = os.urandom(32).hex()
    hashed_password = hashlib.pbkdf2_hmac("sha256", password.encode(), random_salt.encode(), 100_000).hex()
    try:
        sql = "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)"
        values = (username, hashed_password, random_salt, time.time())
        _execute_and_commit(sql, values)
        return True
    except sqlite3.IntegrityError:
        # Username already taken
        return False


def verify_user(username, password):
    sql = "SELECT id, password_hash, salt FROM users WHERE username = ?"
    stored_user = _fetch_one_row(sql, (username,))
    if stored_user is None:
        return None

    stored_salt = stored_user["salt"]
    stored_hash = stored_user["password_hash"]
    typed_password_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), stored_salt.encode(), 100_000).hex()

    passwords_match = typed_password_hash == stored_hash
    if passwords_match:
        return stored_user["id"]
    return None


def get_username(user_id):
    sql = "SELECT username FROM users WHERE id = ?"
    user_row = _fetch_one_row(sql, (user_id,))
    if user_row is None:
        return None
    return user_row["username"]


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(user_id):
    session_token = os.urandom(32).hex()
    current_time = time.time()
    sql = "INSERT INTO sessions (token, user_id, created_at, last_active) VALUES (?, ?, ?, ?)"
    values = (session_token, user_id, current_time, current_time)
    _execute_and_commit(sql, values)
    return session_token


def validate_session(session_token):
    sql = "SELECT user_id, last_active FROM sessions WHERE token = ?"
    session_row = _fetch_one_row(sql, (session_token,))
    if session_row is None:
        return None

    current_time = time.time()
    seconds_since_last_activity = current_time - session_row["last_active"]
    session_has_expired = seconds_since_last_activity > SESSION_EXPIRES_AFTER_SECONDS

    if session_has_expired:
        _execute_and_commit("DELETE FROM sessions WHERE token = ?", (session_token,))
        return None

    _execute_and_commit("UPDATE sessions SET last_active = ? WHERE token = ?", (current_time, session_token))
    return session_row["user_id"]


def delete_session(session_token):
    sql = "DELETE FROM sessions WHERE token = ?"
    _execute_and_commit(sql, (session_token,))


# ── Messages ──────────────────────────────────────────────────────────────────

def send_agent_message(agent_id, message_content):
    current_time = time.time()
    sql = "INSERT INTO agent_messages (agent_id, content, consumed, created_at) VALUES (?, ?, 0, ?)"
    values = (agent_id, message_content, current_time)
    _execute_and_commit(sql, values)


def consume_agent_messages(agent_id):
    # Get all unread messages for this agent
    sql = "SELECT id, content FROM agent_messages WHERE agent_id = ? AND consumed = 0 ORDER BY id"
    unread_messages = _fetch_all_rows(sql, (agent_id,))

    if not unread_messages:
        return []

    # Mark all of them as read
    message_ids = [message["id"] for message in unread_messages]
    id_placeholders = ",".join("?" * len(message_ids))
    mark_read_sql = f"UPDATE agent_messages SET consumed = 1 WHERE id IN ({id_placeholders})"
    _execute_and_commit(mark_read_sql, message_ids)

    # Return just the text content of each message
    message_texts = [message["content"] for message in unread_messages]
    return message_texts
