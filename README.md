# Harmony

Distributed AI automation platform — one server coordinates multiple AI-powered agents across your network.

## Structure

```
server/          Central coordination hub
agent-client/    AI worker that runs on each target machine
admin-client/    Desktop dashboard to monitor and control agents
```

## Quick Start

**1. Start the server** (on your main machine):
```bash
cd server && python3 -m pip install -r requirements.txt && python3 server.py
```

**2. Start the admin dashboard** (on your main machine):
```bash
cd admin-client && python3 -m pip install -r requirements.txt && python3 app.py
```

**3. Deploy the agent** (on each machine you want to control):
```bash
cd agent-client && python3 -m pip install -r requirements.txt && python3 client.py
```

Agents auto-discover the server on your LAN via UDP broadcast — no manual configuration needed.
