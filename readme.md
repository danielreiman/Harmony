> [!NOTE]  
> To use the orchestrator version of Harmony, which includes a central server, multiple clients, parallel agents, and a manager for coordinated execution, switch to the `distributed-execution` branch.

# Harmony Desktop Agent

Harmony is a vision based desktop automation agent. It observes the screen, understands UI elements, plans actions using a vision language model, and controls the desktop through precise input events.

## Setup

### macOS / Linux

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

## Configuration

Harmony uses **qwen3-vl:235b-cloud** via the Ollama Cloud API.

Create a `.env` file:

```
OLLAMA_API_KEY=your_api_key_here
```

If no key is found, Harmony will prompt at runtime.

## How It Works

Harmony runs a simple loop:

* Capture the screen
* Interpret the UI
* Decide the next action
* Execute the action

## Ready

After setup, Harmony is ready to operate the desktop in real time.
