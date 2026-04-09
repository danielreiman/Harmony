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
> **Branch Hub**: This repository is organized by component into dedicated branches. The source code is maintained separately to ensure modularity.

## Project Components

| Component | Branch | Description |
| :--- | :--- | :--- |
| **Server** | [**`server`**](https://github.com/danielreiman/Harmony/tree/server) | Core orchestration and agent management system. |
| **Admin Client** | [**`admin-client`**](https://github.com/danielreiman/Harmony/tree/admin-client) | Professional command dashboard and controller interface. |
| **Agent Client** | [**`agent-client`**](https://github.com/danielreiman/Harmony/tree/agent-client) | Automation client for remote machines. |

## Getting Started

To work on Harmony, select the component you wish to use and check out its branch:

```bash
# To work on the server
git checkout server

# To work on the admin client
git checkout admin-client

# To work on the agent client
git checkout agent-client
```

## Overview

Harmony is a client-server automation system that distributes tasks across multiple computers. A central server coordinates AI-powered agents, each controlling a connected client machine. Tasks are automatically assigned and executed in parallel across all available clients.

**Key Features:**
- **Vision-based automation** using state-of-the-art AI models.
- **Automatic LAN discovery** — clients find the server without manual configuration.
- **Parallel task execution** across multiple machines simultaneously.
- **Real-time monitoring** via a professional admin dashboard.

---
*Harmony: Harmonizing complex agent interactions.*
