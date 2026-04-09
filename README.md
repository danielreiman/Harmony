<p align="center">
  <img src="admin-client/icon.png" alt="Harmony" width="150">
</p>

<h1 align="center">Harmony</h1>

<p align="center">
  <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/danielreiman/Harmony">
</p>

<p align="center">
  <strong>Distributed automation system for parallel task execution across multiple computers</strong>
</p>

## Overview

Harmony is a client-server automation system that distributes tasks across multiple computers. A central server coordinates AI-powered agents, each controlling a connected client machine. Tasks are automatically assigned and executed in parallel across all available clients.

**Key Features:**
- **Vision-based automation** using state-of-the-art AI models.
- **Automatic LAN discovery** — clients find the server without manual configuration.
- **Parallel task execution** across multiple machines simultaneously.
- **Real-time monitoring** via a professional admin dashboard.
- **Task isolation** using session-based authentication.

## Project Structure

This repository is organized into the latest developmental components and a legacy backup for historical reference.

- **`server/`**: The core FastAPI orchestration layer and agent management logic.
- **`admin-client/`**: The professional dashboard application.
- **`agent-client/`**: The lightweight machine-specific client.
- **`legacy/`**: A backup of the original monolithic codebase.

## Quick Start

### 1. Installation

```bash
# Setup environment
python -m venv .venv
# source .venv/bin/activate  (Mac/Linux)
# .\.venv\Scripts\Activate.ps1 (Windows)

# Install dependencies for all components
pip install -r server/requirements.txt
pip install -r agent-client/requirements.txt
pip install -r admin-client/requirements.txt
```

### 2. Server Setup

```bash
python server/setup.py
python server/server.py
```
The server listens on **1222** (agents), **1223** (API), and **3030** (UDP discovery).

### 3. Agent Client Setup
On each client machine:
```bash
python agent-client/client.py
```

### 4. Admin Dashboard Setup
```bash
python admin-client/client.py
```

## Architecture

```
Harmony/
├── server/          # TCP server and management logic
├── agent-client/    # Connects to server, handles actions
├── admin-client/    # Main Dashboard UI application
└── legacy/          # Historical backup of older versions
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
