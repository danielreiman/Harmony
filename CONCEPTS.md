# Harmony — Concepts

This file explains every moving part in the codebase: what it is, why it exists, and how it connects to everything else.

---

## The big picture

There are three separate programs that talk to each other:

```
[admin-client]  ←→  [server]  ←→  [agent-client]
  (dashboard)          │            (remote machine)
                       │
                    [database]
```

- **server** — the brain. Holds all state, assigns tasks, coordinates everything.
- **agent-client** — runs on a remote machine. Takes screenshots, clicks things.
- **admin-client** — a web dashboard. Lets a human submit tasks and watch agents work.

Each program runs independently. You can have one server, many agent-clients, and one or more dashboards.

---

## Concept 1 — What is an "Agent"?

An agent is not a program. It is an **object that lives inside the server**, representing one connected client machine.

When a client machine connects to the server on port 1222, the server creates an `Agent` object and keeps it in memory. That object holds:

- the open TCP connection to the client machine
- the conversation history the AI is using
- the current task and status
- the active AI client

The `Agent` object is the server's way of remembering and controlling one remote machine. The `agent-client` program running on the remote machine is the other half — it just waits for instructions and executes them.

```
Server process memory:
  agents = {
    "agent-abc123": Agent(conn=<socket>, status="working", task="..."),
    "agent-def456": Agent(conn=<socket>, status="idle", task=None),
  }
```

---

## Concept 2 — The think-act loop

Every Agent runs this loop when it has a task:

```
look()   →   think()   →   parse()   →   act()   →   (repeat)
```

**look()** — sends `{"type": "request_screenshot"}` over the TCP socket to the remote machine. The remote machine takes a screenshot and sends the file back. The agent appends it to the AI conversation history.

**think()** — sends the full conversation history to the AI (Ollama). The AI returns a JSON object describing the next action:
```json
{
  "Step": "EXECUTE",
  "Status": "Opening the browser",
  "Next Action": "click",
  "Coordinate": [640, 400],
  "Value": null,
  "Reasoning": "Need to click the browser icon"
}
```

**parse()** — reads the AI's response, tracks which phase the agent is in (SEARCH, READ, WRITE, EXECUTE), and adds a hint to the history if the agent is stuck doing the same thing too many times.

**act()** — sends the action to the remote machine (or handles it locally if it's a `read_doc`/`write_doc` action). The remote machine executes the click/keystroke/etc. and reports back success or failure.

The loop runs until the AI returns `"Next Action": null`, which means the task is done.

---

## Concept 3 — The Manager

`manager.py` is a background loop that runs every second. It has four jobs:

1. **drop_disconnected** — removes agents that have disconnected from memory and the database
2. **process_commands** — checks if any agent has a stop or disconnect command waiting in the database, and applies it
3. **forward_messages** — checks if any human sent a message to a working agent (via the dashboard) and injects it into that agent's conversation history
4. **dispatch_tasks** — picks the next queued task for each idle agent and assigns it

The manager never directly touches the client machine. It only works with `Agent` objects in memory and the database.

---

## Concept 4 — The task queue

Tasks flow like this:

```
User submits task via dashboard
  → admin-client proxies to server API
    → server stores task in database with status = 'queued'
      → Manager sees idle agent + queued task
        → Manager calls agent.assign(task_text)
          → Agent sets status = 'working', signals task_ready event
            → Agent starts the think-act loop
```

Tasks stay in the database even after completion. Each task records which user submitted it, so users only see their own task history.

---

## Concept 5 — The database

`database.py` is the single source of truth for everything persistent.

Tables:
- **agents** — one row per connected agent, updated every time the agent calls `save()`
- **tasks** — every submitted task with its status (queued → assigned → complete)
- **task_log** — a log of events for each task (assigned, completed, etc.)
- **users** — usernames + salted password hashes
- **sessions** — login tokens, expire after 7 days of inactivity
- **agent_messages** — messages queued for delivery to running agents

**Thread safety**: SQLite doesn't allow sharing connections between threads. Each thread gets its own connection via `_conn()`, which stores it in `threading.local()`. This means the server, manager, API thread, and each agent thread all have their own connection to the same file.

---

## Concept 6 — How the dashboard talks to the server

The admin-client and server don't communicate over HTTP. They use a **raw TCP socket with length-prefixed JSON**.

Every message is:
```
[4 bytes: length of the JSON body][JSON body]
```

This is simpler than HTTP for a closed internal system. The `proxy.py` file in admin-client opens a socket connection to port 1223, sends a request, reads the response, and closes the socket — for every single request.

The server's `api.py` listens on port 1223, accepts these connections, reads the request, calls the right handler function, and sends the response back.

---

## Concept 7 — How the agent-client talks to the server

The agent-client uses the **same length-prefixed JSON protocol** on port 1222. The server sends commands (`request_screenshot`, `execute_step`) and the client responds.

One exception: screenshots are sent as raw binary, not JSON. The flow is:
1. Server sends `{"type": "request_screenshot"}` as a JSON message
2. Client takes a screenshot, sends `[4 bytes: file size][file bytes]`
3. Server reads the file bytes and saves them to `runtime/screenshot_{id}.png`

---

## Concept 8 — LAN auto-discovery

The agent-client doesn't need to know the server's IP address. It discovers the server automatically.

- `networking.py` → `broadcast()` — the server sends a UDP packet to `255.255.255.255:3030` every 2 seconds containing its IP and port
- `agent-client/helpers.py` → `discover()` — the client listens on port 3030 for that packet, extracts the IP and port, and connects

This is why clients can connect to the server with no configuration: they just wait for the beacon.

---

## Concept 9 — Authentication

The dashboard uses token-based auth with no cookies and no server-side sessions stored in memory.

**Login flow:**
1. User enters username + password in the browser
2. `admin-client/app.py` forwards to the server → `database.verify_user()` checks the password hash
3. Server creates a session token (random 32-byte hex string) stored in the `sessions` table
4. Token is returned as JSON: `{"success": true, "token": "abc123..."}`
5. Browser stores the token in `localStorage`

**Every subsequent request:**
1. JS reads `localStorage.getItem('token')`
2. Adds `Authorization: Bearer <token>` header to every API call
3. `admin-client/auth.py` → `@require_auth` decorator reads this header, asks the server to validate the token
4. If valid, the route runs; if not, returns 401 and JS redirects to `/login`

There is no Flask session, no `app.secret_key`, no cookie. The browser owns the token, the database owns the session record.

---

## Concept 10 — Threading model

Understanding which code runs in which thread prevents confusion:

| Thread | What it does |
|--------|-------------|
| Main thread | Accepts new TCP connections from agent-clients in a `while True` loop |
| One per agent | Runs `agent.activate()` — the look/think/act loop for that machine |
| Manager thread | Runs `manager.activate()` — polls every second |
| API thread | Accepts dashboard connections on port 1223 |
| One per API request | Runs `_handle_connection()` for one dashboard request, then exits |
| Broadcast thread | Sends UDP beacons every 2 seconds |

The `agents` dictionary is shared between the main thread (which adds agents) and the manager thread (which reads and modifies them). The `agents_lock` mutex protects all access to it.

---

## Concept 11 — Research mode vs task mode

There are two modes an agent can operate in:

**Task mode** (default) — the agent controls the desktop and executes actions directly. Uses `TASK_PROMPT`.

**Research mode** — the agent still controls the desktop, but it also has access to `read_doc` and `write_doc` actions that read from and write to a Google Doc. The idea is that the agent browses/researches and documents its findings. Uses `RESEARCH_PROMPT`.

The `doc_id` is the Google Docs document ID. The `DocManager` in `google_docs.py` handles authentication and API calls.

---

## File map

```
server/
  server.py       — starts everything: broadcast, manager, API, TCP listener
  agent.py        — Agent class: look/think/parse/act/done/save
  manager.py      — Manager class: background loop that assigns tasks
  api.py          — handles dashboard requests over TCP
  database.py     — all SQLite reads and writes
  networking.py   — UDP broadcast + TCP send/recv helpers
  google_docs.py  — DocManager: read/write Google Docs via service account
  prompts.py      — system prompts for the AI (TASK_PROMPT, RESEARCH_PROMPT)
  config.py       — loads OLLAMA_API_KEY from .env

agent-client/
  client.py       — connects to server, responds to screenshot/action requests
  helpers.py      — discover(), act(), send_json(), recv_json()

admin-client/
  app.py          — Flask routes: login, agents, tasks, control
  proxy.py        — sends requests to server API over TCP
  auth.py         — @require_auth decorator: reads Authorization header
  templates/      — HTML pages (dashboard, login, signup)
  static/         — CSS + dashboard.js
```
