from connection import request


"""Small typed wrappers around the Admin gateway request payloads."""


def authenticate(action, username, password):
    """Send a login or signup request."""
    return request({"action": action, "username": username, "password": password})


def stop_server():
    """Ask the server process to shut down."""
    return request({"action": "stop_server"})


def get_agents():
    """Fetch the visible agent list."""
    return request({"action": "get_agents"})


def get_agent(agent_id):
    """Fetch one agent's current state."""
    return request({"action": "get_agent", "agent_id": agent_id})


def get_screen(agent_id):
    """Fetch one agent's latest screenshot."""
    return request({"action": "get_screen", "agent_id": agent_id})


def send_task(task, agent_id, user_id):
    """Queue a task for the selected agent."""
    return request({
        "action": "send_task",
        "task": task,
        "agent_id": agent_id,
        "user_id": user_id,
    })


def stop_agent(agent_id):
    """Request that an active agent stops its current task."""
    return request({"action": "stop_agent", "agent_id": agent_id})


def clear_agent(agent_id):
    """Clear an agent's task memory/history."""
    return request({"action": "clear_agent", "agent_id": agent_id})


def disconnect_agent(agent_id):
    """Disconnect an agent from the server."""
    return request({"action": "disconnect_agent", "agent_id": agent_id})


def get_tasks(user_id):
    """Fetch the current user's task history."""
    return request({"action": "get_tasks", "user_id": user_id})
