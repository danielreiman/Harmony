# Harmony

Harmony is a robust, multi-agent orchestration platform designed for seamless coordination between administrative oversight and distributed agent clients.

## Repository Architecture

This repository follows a decoupled architecture where each core component is maintained in its own dedicated branch. This allows for independent development, deployment, and scaling of the different layers of the Harmony ecosystem.

### 🌐 [server](https://github.com/danielreiman/Harmony/tree/server)
The central nervous system of Harmony. This branch contains the FastAPI-based orchestration layer that manages agent registration, command routing, and state persistence.
- **Key Features**: WebSocket management, REST API, Database migrations, Agent heartbeat monitoring.

### 🖥️ [admin-client](https://github.com/danielreiman/Harmony/tree/admin-client)
The command center for Harmony controllers. A professional UI built to provide full visibility and control over all active agents in the field.
- **Key Features**: Live viewport streaming, Command issuance, Agent status dashboard, Real-time logs.

### 🤖 [agent-client](https://github.com/danielreiman/Harmony/tree/agent-client)
The lightweight client module designed to run on target environments. It executes commands, reports system health, and streams visual feedback to the server.
- **Key Features**: Low-latency communication, Resource monitoring, Command execution environment.

---

## Getting Started

To work on a specific component, checkout the corresponding branch:

```bash
# To contribute to the Server
git checkout server

# To contribute to the Admin Interface
git checkout admin-client

# To contribute to the Agent module
git checkout agent-client
```

## Legacy Code
Previous monolithic versions of the codebase can be found in the [old-versions](https://github.com/danielreiman/Harmony/tree/old-versions) branch for historical reference.

---
*Harmony: Harmonizing complex agent interactions.*
