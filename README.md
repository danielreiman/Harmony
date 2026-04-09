<p align="center">
  <img src="https://github.com/danielreiman/Harmony/raw/admin-client/icon.png" alt="Harmony" width="150">
</p>

<h1 align="center">Harmony</h1>

<p align="center">
  <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/danielreiman/Harmony">
</p>

<p align="center">
  <strong>Distributed automation system for parallel task execution across multiple computers</strong>
</p>

> [!IMPORTANT]
> **Architecture Update**: To maintain a professional and scalable codebase, this project has been divided into specialized branches. You will not find the source code on the `main` branch. Please switch to the appropriate branch based on your needs.

## 🌿 Branch Index

| Component | Branch | Description |
| :--- | :--- | :--- |
| **Server** | [**`server`**](https://github.com/danielreiman/Harmony/tree/server) | Central orchestration, API, and agent management. |
| **Admin Client** | [**`admin-client`**](https://github.com/danielreiman/Harmony/tree/admin-client) | Professional dashboard for monitoring and task submission. |
| **Agent Client** | [**`agent-client`**](https://github.com/danielreiman/Harmony/tree/agent-client) | Lightweight client for remote machine automation. |
| **Legacy** | [`old-versions`](https://github.com/danielreiman/Harmony/tree/old-versions) | The previous monolithic version of the codebase. |

> [!NOTE]
> To use the single agent version of Harmony without the orchestrator, parallel agents, or the central server, switch to the `single-agent` branch (if available).

## Overview

Harmony is a client-server automation system that distributes tasks across multiple computers. A central server coordinates AI-powered agents, each controlling a connected client machine. Tasks are automatically assigned and executed in parallel across all available clients.

**Key Features:**
- **Vision-based automation** using state-of-the-art AI models.
- **Automatic LAN discovery** — clients find the server without manual configuration.
- **Parallel task execution** across multiple machines simultaneously.
- **Research mode** with native Google Docs integration.
- **Real-time monitoring** via a professional admin dashboard.
- **Task isolation** using session-based authentication.

## How It Looks

<p align="center">
  <img src="https://github.com/danielreiman/Harmony/raw/admin-client/screenshot.png" alt="Harmony Dashboard" width="700">
</p>

## Quick Start (Per Branch)

### 1. Installation
Each component has its own `requirements.txt`. Checkout the relevant branch first.

```bash
git checkout [branch-name]
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. server Branch Setup
Run the setup wizard to configure your API key:
```bash
python setup.py
python server.py
```
The server listens on **1222** (agents), **1223** (API), and **3030** (UDP discovery).

### 3. agent-client Branch Setup
On each client machine:
```bash
python client.py
```
The client auto-discovers the server via UDP broadcast.

### 4. admin-client Branch Setup
Start the dashboard on any machine in the LAN:
```bash
python client.py  # Launches the professional UI
```

## Project Architecture

```
Harmony (Multi-Branch)
├── branch:server
│   ├── server.py        # TCP listener — accepts agent connections
│   ├── manager.py       # Assigns queued tasks to idle agents
│   ├── agent.py         # One Agent instance per connected client
│   ├── api.py           # Dashboard API
│   └── database.py      # SQLite persistence layer
│
├── branch:agent-client
│   ├── client.py        # Connects to server, handles actions
│   └── helpers.py       # Discovery and PyAutoGUI utilities
│
└── branch:admin-client
    ├── client.py        # Main Dashboard UI application
    └── ui_functions.py  # UI logic and API communication
```

### Data Flow

1. **Discovery**: Agent client listens for a UDP beacon from the server.
2. **Connection**: Client connects to server on TCP port 1222.
3. **Orchestration**: User submits a task via the dashboard.
4. **Assignment**: Manager assigns the task to an idle agent.
5. **Vision**: Agent requests screenshots; AI analyzes and decides actions.
6. **Execution**: Client executes actions via PyAutoGUI and reports back.

---
*Harmony: Harmonizing complex agent interactions.*
