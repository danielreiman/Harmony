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
> **Branch Hub**: This repository is organized by component into dedicated branches. The source code is not stored on the `main` branch. Please use the navigation guide below to find the specific component you need.

## 🌿 Project Navigation

| Component | Branch | Description |
| :--- | :--- | :--- |
| **Server** | [**`server`**](https://github.com/danielreiman/Harmony/tree/server) | Core orchestration and agent management. |
| **Admin Client** | [**`admin-client`**](https://github.com/danielreiman/Harmony/tree/admin-client) | Professional dashboard and controller UI. |
| **Agent Client** | [**`agent-client`**](https://github.com/danielreiman/Harmony/tree/agent-client) | Automation client for remote machines. |
| **Legacy & Unified** | [**`legacy`**](https://github.com/danielreiman/Harmony/tree/legacy) | Complete backup containing both old and new structures. |

## Quick Start

To work on Harmony, choose your component and switch to its branch:

```bash
# Example: Working on the server
git checkout server

# Example: Accessing the unified legacy/dev backup
git checkout legacy
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
