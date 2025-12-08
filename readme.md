# Harmony Project

Harmony lets you give one goal and watch it happen across multiple computers.
The system divides the work into smaller actions and runs them in parallel on connected desktops.

---

## Setup

### macOS / Linux

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

The setup process is the same for both server and client machines.

---

## Configuration (Server Required)

Harmony uses **qwen3-vl:235b-instruct-cloud** via the Ollama Cloud API.

Official Ollama site:
[https://ollama.com](https://ollama.com)

The **server machine must have an API key** configured before startup.

Create a `.env` file in the project root:

```
OLLAMA_API_KEY=your_api_key_here
```

The server will **not prompt** for a missing key.
If the key is not set, the server will fail to start.

Clients do **not** require an API key.

---

## Running Harmony

### Start the Server

On the server machine:

```bash
python server.py
```

The server:

* Loads the Ollama API key
* Listens for incoming client connections
* Manages agents and task assignment

---

### Start a Client

On each client machine:

```bash
python client.py
```

Each client:

* Connects to the server
* Captures the desktop screen
* Executes actions sent by the server

You can run multiple clients simultaneously.

---

## How It Works

Harmony follows a simple and predictable flow:

1. Clients connect to the server
2. The server registers one Agent per client
3. Each Agent runs in its own persistent thread
4. Agents wait idle until assigned a task
5. A Manager loop assigns pending tasks to idle agents
6. Agents execute actions through their client and return to idle

If there are more tasks than agents, tasks wait.
If there are more agents than tasks, agents wait.

---

## Architecture Overview

* **Server**

  * Runs the AI model and planning logic
  * Tracks connected agents
  * Assigns tasks to idle agents

* **Clients**

  * Perform execution only
  * Handle input events and screenshots
  * Do not plan or coordinate

* **Agents**

  * Server-side representations of clients
  * One per connected client
  * Persistent and reusable

* **Manager**

  * Runs in its own thread
  * Matches idle agents with pending tasks
  * Does not execute tasks directly

---

## Ready

After configuration and startup, Harmony is ready to coordinate and automate multiple desktops from a single centralized server.

