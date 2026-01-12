<p>
  <img src="icon.png" alt="Harmony" width="150">
</p>

<h1>Harmony</h1>

<p>
  <img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/danielreiman/Harmony">
</p>

<p>
  <strong>Distributed automation system for parallel task execution across multiple computers</strong>
</p>

> [!NOTE]  
> To use the single agent version of Harmony without the orchestrator, parallel agents, or the central server, switch to the `single-agent` branch.

## Overview

Harmony is a client-server automation system that distributes tasks across multiple computers. A central server coordinates AI-powered agents, each controlling a connected client machine. Tasks are automatically split and executed in parallel across all available clients.

**Key Features:**
- Vision-based automation using AI models
- Automatic LAN discovery
- Parallel task execution
- Real-time agent monitoring via web dashboard
- One agent per client architecture

## Quick Start

### 1. Installation

```bash
# macOS/Linux
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Windows
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

### 2. Server Setup

Configure API credentials:

```bash
python server/setup.py
```

Start the server:

```bash
python server/server.py
```

The server listens on port **1222** and broadcasts on UDP port **3030** for client discovery.

### 3. Client Setup

On each client machine:

```bash
python client/client.py
```

Clients auto-discover the server via UDP broadcast and connect automatically.

### 4. Monitor (Optional)

Start the UI of the server by running:
```
python dashboard.py
```

The UI will be available at:
```
http://localhost:1234
```

## Architecture

```
Server (Port 1222)
├── Manager          # Task distribution
├── Agents           # One per client connection
└── Dashboard        # Web UI (Port 1234)

Client (Auto-discover)
├── Screenshot capture
├── Action execution
└── Result reporting
```

### Components

**Server** (`server/`)
- `server.py` - Main TCP server, handles client connections
- `agent.py` - Agent class representing each client
- `manager.py` - Task queue and distribution system
- `dashboard.py` - Flask web dashboard
- `config.py` - Environment configuration
- `helpers.py` - Network utilities

**Client** (`client/`)
- `client.py` - Connects to server and executes actions
- `helpers.py` - Action execution and server discovery

### Data Flow

1. Client connects to server (auto-discovered via UDP)
2. Server creates Agent instance for the client
3. Manager assigns task from queue to idle Agent
4. Agent requests screenshot from client
5. AI model analyzes screenshot and generates action
6. Client executes action and reports result
7. Process repeats until task completion

### Threading Model

- **Server**: One thread per agent + manager thread + broadcast thread
- **Client**: Single-threaded with blocking socket communication
- **Agents**: Event-driven execution in separate daemon threads

## Configuration

### Environment Variables

Create `.env` in project root:

```env
OLLAMA_API_KEY=your_api_key_here
```

### Model Configuration

Default model: `qwen3-vl:235b-instruct-cloud`

Configured in `server/server.py`:

```python
MODEL = "qwen3-vl:235b-instruct-cloud"
```

## Runtime Files

```
runtime/
├── screenshot_agent-{id}.png    # Agent screenshots
└── agent-{id}.soul              # Agent state files
```

## Development

### Project Structure

```
Harmony/
├── server/
│   ├── server.py          # Main server
│   ├── agent.py           # Agent logic
│   ├── manager.py         # Task manager
│   ├── dashboard.py       # Web UI
│   ├── config.py          # Configuration
│   ├── helpers.py         # Network utils
│   ├── prompts.py         # AI prompts
│   └── setup.py           # Initial setup
├── client/
│   ├── client.py          # Client application
│   └── helpers.py         # Client utilities
├── requirements.txt       # Dependencies
└── CLAUDE.md             # Development guide
```

### Agent Execution Flow

```
agent.activate()      # Wait for task assignment
  → agent.run()       # Main execution loop
    → agent.look()    # Capture screenshot
    → agent.think()   # AI decision
    → agent.parse()   # Parse response
    → agent.done()    # Check completion
    → agent.act()     # Execute action
    → agent.save()    # Save state
```

