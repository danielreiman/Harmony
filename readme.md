# Harmony Project

Harmony lets you give one goal and watch it unfold across multiple computers.
The system breaks big tasks into small steps and executes them in parallel across connected desktops.

---

## Setup

Create a virtual environment and install dependencies.

### macOS / Linux

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

The setup process is identical for server and client machines.

---

## Server Configuration

Before starting the server, run the setup script:

```bash
python setup.py
```

The script will:

* Ask for your **Ollama API key**
* Ask for your **DuckDNS token** (a free dynamic DNS service where the server sends its current IP to the DNS so clients can always reach it using only the DNS name)
* Create a minimal `.env` file automatically
* Update your DuckDNS domain to the server’s current IP

No manual editing required.

### Example `.env` produced

```
OLLAMA_API_KEY=your_key_here
```

Clients do **not** require an API key.

---

## Running Harmony

### Start the Server

```bash
python server.py
```

The server:

* Loads the API key from `.env`
* Updates DNS via setup.py (run once before start)
* Listens for clients
* Creates one Agent per client
* Assigns steps to idle agents

---

### Start a Client

On each client machine:

```bash
python client.py
```

Each client:

* Connects to the server
* Sends screenshots on demand
* Executes steps sent by its Agent

You may run as many clients as you want.

---

## How It Works

1. Clients connect to the server
2. The server registers one Agent per client
3. Each Agent stays alive in its own thread
4. Agents sit idle until given work
5. A Manager loop assigns tasks to idle agents
6. Agents execute the steps and report results

More clients means more parallel execution.

---

## Architecture Overview

### Server

* Hosts all planning and AI logic
* Tracks and manages agents
* Distributes tasks

### Clients

* Execute actions only
* Capture screens
* Send results back to the server

### Agents

* Server-side representations of each client
* One per connection
* Persistent workers

### Manager

* Matches idle agents with pending tasks
* Runs independently from agents and clients

---

## Ready


Once setup and running, Harmony becomes a centralized command system that coordinates and automates multiple desktops at once.
