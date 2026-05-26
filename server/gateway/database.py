import hashlib, os, sqlite3, threading, time


DATABASE_FILE_PATH = os.path.join(os.path.dirname(__file__), "resources", "harmony.db")
_local = threading.local()  # each worker gets its own link to the database
RESULT_MARKER = "\n\nAgent result:\n"


def get_connection():
    # If it already opened the database earlier, use that same one again.
    if hasattr(_local, "conn"):
        return _local.conn

    # Open the database file for the first time.
    conn = sqlite3.connect(DATABASE_FILE_PATH, timeout=30, isolation_level=None)

    conn.execute("PRAGMA journal_mode=WAL")    # let many threads read and write at once
    conn.execute("PRAGMA busy_timeout=30000")  # if it's busy, wait up to 30 seconds
    conn.execute("PRAGMA synchronous=NORMAL")  # faster writes
    conn.row_factory = sqlite3.Row             # access columns by name (row["id"]) instead of index (row[0])

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
            agent_state TEXT NOT NULL DEFAULT 'idle',
            task TEXT,
            agent_activity_message TEXT,
            step_json TEXT,
            connected_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );
    """)


# ── Agents ───────────────────────────────────────────────────────────────────

def register_agent(agent_id):
    now = time.time()

    execute_and_commit(
        "INSERT OR REPLACE INTO agents (agent_id, agent_state, connected_at, updated_at) VALUES (?, 'idle', ?, ?)",
        (agent_id, now, now))


def update_agent(agent_id, **fields):
    allowed = {"agent_state", "task", "agent_activity_message", "step_json"}
    safe = {k: v for k, v in fields.items() if k in allowed}

    if not safe:
        return

    safe["updated_at"] = time.time()

    set_clause = ", ".join(f"{k} = ?" for k in safe)
    execute_and_commit(
        f"UPDATE agents SET {set_clause} WHERE agent_id = ?",
        list(safe.values()) + [agent_id])


def set_agent_state(agent_id, agent_state):
    execute_and_commit(
        "UPDATE agents SET agent_state = ? WHERE agent_id = ?",
        (agent_state, agent_id))


def remove_agent(agent_id):
    execute_and_commit("DELETE FROM agents WHERE agent_id = ?", (agent_id,))


def get_agent(agent_id):
    return fetch_one_row("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))


def get_all_agents():
    return fetch_all_rows("SELECT * FROM agents ORDER BY agent_id")


# ── Tasks ────────────────────────────────────────────────────────────────────

def add_task(task_text, user_id=None, agent_id=None):
    cursor = execute_and_commit(
        "INSERT INTO tasks (task, status, assigned_agent, created_at, user_id) VALUES (?, 'queued', ?, ?, ?)",
        (task_text, agent_id, time.time(), user_id))
    return cursor.lastrowid


def get_task(task_id):
    return fetch_one_row("SELECT * FROM tasks WHERE id = ?", (task_id,))


def _parse_research_task(text):
    lines = (text or "").splitlines()
    if not lines or not lines[0].startswith("Research(") or ") |" not in lines[0]:
        return None

    research_id = lines[0].split("Research(", 1)[1].split(")", 1)[0].strip()
    section = lines[0].split("|", 1)[1].strip()
    topic = ""
    for line in lines:
        if line.startswith("Topic:"):
            topic = line.split(":", 1)[1].strip()
            break

    result = text.split(RESULT_MARKER, 1)[1].strip() if RESULT_MARKER in text else ""
    return {"id": research_id, "section": section, "topic": topic, "result": result}


def _field(text, label):
    labels = ("Research ID", "Section", "Paragraph", "Sources", "Takeaway")
    out, collecting = [], False
    for line in (text or "").splitlines():
        clean = line.strip()
        if clean.lower().startswith(label.lower() + ":"):
            collecting = True
            first = line.split(":", 1)[1].strip()
            if first:
                out.append(first)
            continue
        if collecting and any(clean.lower().startswith(x.lower() + ":") for x in labels):
            break
        if collecting and clean:
            out.append(clean)
    return "\n".join(out).strip()


def _write_pdf(path, lines):
    from xml.sax.saxutils import escape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    styles = getSampleStyleSheet()
    story = []
    for line in lines:
        style = styles["Heading2"] if line and not line.startswith("-") else styles["BodyText"]
        text = escape(str(line)).replace("\n", "<br/>") or " "
        story.append(Paragraph(text, style))
        story.append(Spacer(1, 6))

    SimpleDocTemplate(path).build(story)


def _export_research_report_if_ready(done_task):
    parsed = _parse_research_task(done_task.get("task", ""))
    if not parsed:
        return

    rows = fetch_all_rows(
        "SELECT * FROM tasks WHERE user_id = ? AND task LIKE ? ORDER BY id",
        (done_task.get("user_id"), f"Research({parsed['id']}) |%"))
    if not rows or any(row.get("status") != "done" for row in rows):
        return

    sections = [(row, _parse_research_task(row["task"])) for row in rows]
    topic = parsed["topic"]
    lines = [
        "Harmony Research Report",
        f"Research ID: {parsed['id']}",
        f"Topic: {topic}",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "Executive Summary",
    ]

    for row, section in sections:
        takeaway = _field(section["result"], "Takeaway") or "No takeaway provided."
        lines.append(f"- {section['section']} ({row.get('assigned_agent')}): {takeaway}")

    lines += ["", "Research Sections"]
    for index, (row, section) in enumerate(sections, 1):
        result = section["result"]
        lines += [
            "",
            f"{index}. {section['section'].title()}",
            f"Agent: {row.get('assigned_agent')}",
            "",
            "Paragraph:",
            _field(result, "Paragraph") or result or "No paragraph provided.",
            "",
            "Sources:",
            _field(result, "Sources") or "No sources provided.",
            "",
            "Takeaway:",
            _field(result, "Takeaway") or "No takeaway provided.",
        ]

    filename = f"Harmony-Research-{parsed['id']}.pdf"
    path = os.path.join(os.path.expanduser("~"), "Downloads", filename)
    try:
        _write_pdf(path, lines)
    except OSError:
        reports_dir = os.path.join(os.path.dirname(__file__), "resources", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        path = os.path.join(reports_dir, filename)
        _write_pdf(path, lines)
    print(f"[Research] Exported report: {path}")


def mark_task_done(task_id, result=None):
    task = get_task(task_id)
    parsed = _parse_research_task(task.get("task", "")) if task else None

    if parsed:
        addition = "" if RESULT_MARKER in task["task"] or not result else RESULT_MARKER + result
        execute_and_commit(
            "UPDATE tasks SET status = 'done', task = task || ? WHERE id = ?",
            (addition, task_id))
        _export_research_report_if_ready(get_task(task_id))
        return

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


# ── Users ────────────────────────────────────────────────────────────────────

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
