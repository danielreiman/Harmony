"""Harmony Admin dashboard — browser UI built with NiceGUI.

A browser twin of the CustomTkinter desktop app. It speaks the same JSON gateway
protocol through connection.request, so the server needs no changes.
Run:  python client.py   (opens http://localhost:8080)
"""

import sys
from datetime import datetime

from nicegui import app, run, ui

from connection import request


# Friendly display names for the raw action names the server sends.
ACTION_LABELS = {
    "left_click": "Left Click", "click": "Left Click",
    "double_click": "Double Click", "right_click": "Right Click",
    "drag": "Drag", "type": "Type", "press_key": "Press", "hotkey": "Hotkey",
    "scroll_up": "Scroll Up", "scroll_down": "Scroll Down",
    "run_command": "Run Command", "wait": "Wait",
}

# Agent states that should never appear in the dropdown.
HIDDEN_AGENT_STATES = {"disconnected", "disconnect_requested"}
PASSWORD_ERROR = "Use 7+ chars with letters and numbers"

# Reused inline styles.
SEND_BUTTON_STYLE = "background:#ffffff;color:#000000;font-weight:600;border-radius:14px"
STOP_BUTTON_STYLE = "background:#ff6467;color:#ffffff;font-weight:600;border-radius:14px"
PANEL_STYLE = "background:#242424;border:1px solid #343434;border-radius:18px"

GLOBAL_CSS = """
body{background:#171717;font-family:"Helvetica Neue",Arial,sans-serif;color:#f4f4f4;overflow:hidden}
.nicegui-content{padding:0;height:100vh;overflow:hidden;gap:0}
.q-card{background:#282828;border:1px solid #343434;border-radius:18px}
.q-card,.q-btn,.q-field__control,.q-menu{box-shadow:none!important}
.q-field--outlined .q-field__control{border-radius:10px}
.cap{background:#282828;border:1px solid #343434;border-radius:21px;padding:0 16px;height:42px;display:flex;align-items:center}
.act{background:#f1f1f3!important}
"""


def send_request(action, **fields):
    """Send one JSON request to the gateway and return the parsed reply."""
    return request({"action": action, **fields})


def password_is_valid(password):
    return len(password) > 6 and any(c.isalpha() for c in password) and any(c.isdigit() for c in password)


def describe_step(step):
    """Return a short human label for one agent step, e.g. 'Left Click  (10, 20)'."""
    raw_action = (step.get("action") or "").strip()
    if not raw_action or raw_action.lower() == "none":
        return "—"
    if raw_action.lower() == "done":
        return "Done!"

    action_key = raw_action.lower()
    label = ACTION_LABELS.get(action_key, raw_action.replace("_", " ").title())
    coordinate = step.get("coordinate") or step.get("Coordinate")
    value = step.get("value") or step.get("Value")

    # Mouse actions show the target coordinate.
    if coordinate:
        try:
            return f"{label}  ({int(coordinate[0])}, {int(coordinate[1])})"
        except Exception:
            return f"{label}  {coordinate}"

    # Keyboard actions show the key combination.
    if action_key in ("press_key", "hotkey") and value:
        keys = value if isinstance(value, (list, tuple)) else [value]
        return f"{label}  {' + '.join(str(key).title() for key in keys)}"

    # A couple of actions carry a plain value.
    if action_key == "wait" and value:
        return f"{label}  {value}s"
    if action_key == "run_command" and value:
        return f"{label}: {value}"

    return label


class Session:
    """Per-browser state for one signed-in admin."""

    def __init__(self):
        self.user_id = None
        self.username = ""
        self.selected_agent = None
        self.agent_is_working = False
        self.last_logged_step = None  # used to avoid logging the same step twice


@ui.page("/")
def index():
    """Show the login screen, then the live dashboard after sign-in."""
    ui.add_head_html(f"<style>{GLOBAL_CSS}</style>")
    ui.colors(primary="#a8a8a8")  # gray accents instead of Quasar's default blue
    session = Session()
    page_root = ui.column().style("width:100%;height:100vh;padding:0;gap:0")

    # ============================== LOGIN ==============================
    def show_login_screen():
        session.user_id = None
        page_root.clear()
        with page_root, ui.column().classes("w-full h-screen items-center justify-center"), \
                ui.card().classes("items-stretch gap-3").style(
                    f"width:390px;padding:38px 37px;{PANEL_STYLE};border-radius:22px"):
            ui.label("Harmony").classes("font-bold self-center").style("font-size:28px")
            ui.label("Sign in to continue").classes("self-center").style(
                "color:#777;font-size:13px;margin-bottom:16px")

            username_input = ui.input("Username").props("outlined dense dark").classes("w-full")
            password_input = ui.input("Password", password=True, password_toggle_button=True) \
                .props("outlined dense dark").classes("w-full")
            error_label = ui.label("").classes("text-sm h-5 self-center").style("color:#ff6467")

            async def authenticate(gateway_action):
                """Log in or sign up, then open the dashboard on success."""
                if not username_input.value.strip() or not password_input.value:
                    error_label.text = "Username and password are required"
                    return
                if gateway_action == "auth_signup" and not password_is_valid(password_input.value):
                    error_label.text = PASSWORD_ERROR
                    return
                error_label.text = "Authenticating…"
                reply = await run.io_bound(send_request, gateway_action,
                                           username=username_input.value,
                                           password=password_input.value)
                if "user_id" in reply:
                    session.user_id = reply["user_id"]
                    session.username = username_input.value.strip() or "User"
                    show_dashboard()
                else:
                    error_label.text = reply.get("error", "Failed")

            ui.button("Sign in", on_click=lambda: authenticate("auth_login"), color=None) \
                .classes("w-full").style(SEND_BUTTON_STYLE)
            ui.label("Create account").classes("self-center font-bold cursor-pointer").style(
                "color:#777;font-size:12px;margin-top:8px") \
                .on("click", lambda: authenticate("auth_signup"))

            # Enter submits the form from either field.
            username_input.on("keydown.enter", lambda: authenticate("auth_login"))
            password_input.on("keydown.enter", lambda: authenticate("auth_login"))

    # ============================ DASHBOARD ============================
    def show_dashboard():
        page_root.clear()

        # ---- small UI helper shared by several handlers ----
        def show_empty_message(title, subtitle):
            """Show the centered overlay instead of a screenshot, and hide the cards."""
            empty_overlay.visible = True
            side_panels.visible = False
            empty_title_label.text = title
            empty_subtitle_label.text = subtitle

        # ---- activity log (writes rows into activity_log_column) ----
        def trim_activity_log():
            """Keep only the 120 most recent log rows."""
            rows = activity_log_column.default_slot.children
            while len(rows) > 120:
                activity_log_column.remove(rows[0])

        def add_log_detail(label, text, label_color, text_color="#c9c9ce", monospace=False):
            """Add one 'Label  text' line inside a step entry."""
            with ui.row().classes("w-full items-baseline gap-2 no-wrap"):
                ui.label(label).classes("text-xs font-bold shrink-0") \
                    .style(f"color:{label_color};min-width:62px")
                text_classes = "text-xs grow break-words" + (" font-mono" if monospace else "")
                ui.label(text).classes(text_classes).style(f"color:{text_color}")

        def add_system_message(message, color="#a8a8a8"):
            """Add a timestamped one-line note (e.g. 'Switched to agent-1')."""
            with activity_log_column, ui.row().classes("w-full items-start gap-2 no-wrap"):
                ui.label(f"{datetime.now():%H:%M:%S}").classes(
                    "text-xs font-mono shrink-0").style("color:#777")
                ui.label(message).classes("text-xs break-words").style(f"color:{color}")
            trim_activity_log()

        def add_step_entry(step):
            """Add a full agent step: thinking, executed action, and any output."""
            with activity_log_column, ui.column().classes("w-full gap-1").style(
                    "border-left:2px solid #343434;padding:2px 0 8px 10px"):
                ui.label(f"{datetime.now():%H:%M:%S}").classes("text-xs font-mono").style("color:#777")
                reasoning = (step.get("reasoning") or "").strip()
                if reasoning:
                    add_log_detail("Thinking", reasoning, "#a8a8a8", "#9a9a9a")
                add_log_detail("Executing", describe_step(step), "#35d399", "#f4f4f4")
                if step.get("cmd_output"):
                    add_log_detail("Output", str(step["cmd_output"]), "#35d399", "#35d399", monospace=True)
            trim_activity_log()

        # ---- task history window ----
        def render_task_list(tasks):
            """Draw the task cards inside the Tasks window."""
            task_list_column.clear()
            with task_list_column:
                if not tasks:
                    ui.label("No tasks yet").classes("text-sm self-center mt-4").style("color:#a8a8a8")
                    return
                for task in tasks:
                    status = task.get("status", "queued")
                    agent_name = task.get("assigned_agent") or "unassigned"
                    dot_color = {"queued": "#d6b16a", "in_progress": "#35d399",
                                 "working": "#35d399"}.get(status, "#a8a8a8")
                    with ui.card().classes("w-full p-3 gap-1").style("background:#282828"):
                        ui.label(task.get("task", "")).classes(
                            "text-sm font-semibold break-words").style("color:#f4f4f4")
                        with ui.row().classes("items-center gap-2 no-wrap"):
                            ui.element("div").style(
                                f"width:6px;height:6px;border-radius:3px;background:{dot_color};flex:none")
                            ui.label(f"{status} · {agent_name}").classes(
                                "text-xs font-mono").style("color:#777")

        async def open_tasks_window():
            """Open the Tasks window and load this user's tasks."""
            tasks_window.open()
            task_list_column.clear()
            with task_list_column:
                ui.label("Loading…").classes("text-sm self-center mt-4").style("color:#a8a8a8")
            reply = await run.io_bound(send_request, "get_tasks", user_id=session.user_id)
            render_task_list(reply.get("tasks", []))

        # ---- agent selection and actions ----
        def select_agent(agent_id):
            """Switch the dashboard to a different agent and reset the panels."""
            session.selected_agent = agent_id or None
            session.last_logged_step = None
            action_label.text = "—"
            reasoning_label.text = "—"
            current_task_label.text = "No active task"
            task_window_label.text = "No active task"
            if session.selected_agent:
                screen_image.set_source("")
                show_empty_message("Waiting for screen", "The agent hasn't sent a screenshot yet")
                add_system_message(f"Switched to {session.selected_agent}")

        async def shutdown_server():
            """Stop the server, then close this app."""
            await run.io_bound(send_request, "stop_server")
            app.shutdown()

        async def clear_agent_memory():
            """Clear the selected agent's memory and reset the panels."""
            if not session.selected_agent:
                ui.notify("Select an agent first")
                return
            await run.io_bound(send_request, "clear_agent", agent_id=session.selected_agent)
            activity_log_column.clear()
            action_label.text = "—"
            reasoning_label.text = "—"
            current_task_label.text = "No active task"
            task_window_label.text = "No active task"
            add_system_message(f"Clearing {session.selected_agent}")

        async def disconnect_agent():
            """Disconnect the selected agent."""
            if not session.selected_agent:
                ui.notify("Select an agent first")
                return
            add_system_message(f"Disconnecting {session.selected_agent}")
            await run.io_bound(send_request, "disconnect_agent", agent_id=session.selected_agent)
            session.selected_agent = None
            agent_select.value = None

        async def send_task_or_stop():
            """Send the typed task, or stop the agent when the box is empty."""
            text = prompt_input.value.strip()
            if not session.selected_agent:
                ui.notify("Select an agent first")
                return
            if not text:
                # Empty box while the agent works = stop request; otherwise nudge the user.
                if session.agent_is_working:
                    add_system_message(f"Stop requested for {session.selected_agent}")
                    await run.io_bound(send_request, "stop_agent", agent_id=session.selected_agent)
                else:
                    ui.notify("Describe a command first")
                return
            prompt_input.value = ""
            reply = await run.io_bound(send_request, "send_task", task=text,
                                       agent_id=session.selected_agent, user_id=session.user_id)
            add_system_message(reply.get("message") or reply.get("error") or "Sent")

        # ---- background refresh loops ----
        async def refresh_agent_list():
            """Reload the agent dropdown and auto-select the first agent."""
            reply = await run.io_bound(send_request, "get_agents")
            visible_agents = [agent["id"] for agent in reply.get("agents", [])
                              if agent.get("agent_state", "idle") not in HIDDEN_AGENT_STATES]
            if list(agent_select.options) != visible_agents:
                agent_select.options = visible_agents
                agent_select.update()
            if not session.selected_agent and visible_agents:
                session.selected_agent = visible_agents[0]
                agent_select.value = visible_agents[0]

        async def refresh_screenshot():
            """Show the latest screenshot, or the empty overlay when there is none."""
            if not session.selected_agent:
                screen_image.set_source("")
                show_empty_message("No agent connected", "Connect an agent to see its screen here")
                return
            reply = await run.io_bound(send_request, "get_screen", agent_id=session.selected_agent)
            image_data = reply.get("data")
            if image_data:
                screen_image.set_source(f"data:image/png;base64,{image_data}")
                empty_overlay.visible = False
                side_panels.visible = True
            else:
                show_empty_message("Waiting for screen", "The agent hasn't sent a screenshot yet")

        async def refresh_agent_status():
            """Update the action/reasoning/task panels and the Send/Stop button."""
            if not session.selected_agent:
                return
            reply = await run.io_bound(send_request, "get_agent", agent_id=session.selected_agent)
            step = reply.get("step") or {}
            state = reply.get("agent_state", "")
            session.agent_is_working = state == "working"

            # Empty prompt while working turns Send into Stop.
            show_stop = session.agent_is_working and not prompt_input.value.strip()
            send_button.text = "Stop" if show_stop else "Send"
            send_button.style(STOP_BUTTON_STYLE if show_stop else SEND_BUTTON_STYLE)

            action_label.text = describe_step(step)
            reasoning_label.text = (step.get("reasoning") or "—").strip() or "—"
            current_task = reply.get("current_task") or reply.get("task") or "No active task"
            current_task_label.text = current_task
            task_window_label.text = current_task

            # Log the step only when it changed, so the log doesn't fill with repeats.
            step_fingerprint = (step.get("action"), step.get("reasoning"),
                                str(step.get("coordinate")), str(step.get("cmd_output")))
            step_has_content = step.get("action") or step.get("reasoning") or step.get("cmd_output")
            if step_fingerprint != session.last_logged_step and step_has_content:
                session.last_logged_step = step_fingerprint
                add_step_entry(step)

        # ------------------------------ LAYOUT ------------------------------
        with page_root, ui.column().classes("w-full h-screen gap-3").style("padding:12px"):
            # Pop-out windows, opened from the strip and the footer buttons.
            with ui.dialog() as task_window, ui.card().style(f"width:520px;max-width:92vw;{PANEL_STYLE}"):
                ui.label("Current Task").classes("text-sm font-bold")
                task_window_label = ui.label("No active task").classes(
                    "text-sm break-words").style("color:#e8e8e8")
            with ui.dialog() as tasks_window, ui.card().style(f"width:440px;max-width:92vw;{PANEL_STYLE}"):
                ui.label("Tasks").classes("text-sm font-bold")
                with ui.scroll_area().classes("w-full h-96"):
                    task_list_column = ui.column().classes("w-full gap-2 p-1")
            with ui.dialog() as activity_window, ui.card().style(f"width:480px;max-width:92vw;{PANEL_STYLE}"):
                ui.label("Activity").classes("text-sm font-bold")
                with ui.scroll_area().classes("w-full h-96"):
                    activity_log_column = ui.column().classes("w-full gap-1 p-1")

            # Top bar: greeting | title | account actions.
            with ui.element("div").classes("w-full").style(
                    "display:grid;grid-template-columns:1fr auto 1fr;align-items:center"):
                with ui.row().classes("cap items-center gap-2").style("justify-self:start"):
                    ui.label("👋")
                    ui.label(f"Good to see you {session.username}").classes("font-semibold")
                ui.label("Harmony").classes("cap font-bold").style("justify-self:center")
                with ui.row().classes("cap items-center gap-1").style("justify-self:end"):
                    ui.button("Log out", on_click=show_login_screen, color=None) \
                        .props("flat").style("color:#a8a8a8")
                    ui.button("Shutdown", on_click=shutdown_server, color=None) \
                        .props("flat").style("color:#ff4444")

            # Middle: screenshot centered, action + reasoning cards on the right.
            with ui.element("div").classes("w-full").style(
                    "flex:1;min-height:0;display:grid;"
                    "grid-template-columns:320px 1fr 320px;align-items:center;gap:16px"):
                ui.element("div")  # left spacer keeps the screenshot centered
                with ui.column().classes("items-center justify-center gap-1").style(
                        "align-self:stretch;min-height:0"):
                    with ui.element("div").classes("w-full").style(
                            "position:relative;flex:1;min-height:0;display:flex"):
                        screen_image = ui.image().props("fit=contain").style(
                            "flex:1;min-height:0;width:100%;border-radius:16px")
                        # Overlay shown until a screenshot arrives.
                        with ui.column().classes("absolute-center items-center gap-1") as empty_overlay:
                            empty_title_label = ui.label("No agent connected").classes(
                                "text-xl font-bold").style("color:#f4f4f4")
                            empty_subtitle_label = ui.label(
                                "Connect an agent to see its screen here").classes(
                                "text-sm").style("color:#a8a8a8")
                side_panels = ui.column().classes("w-80 gap-3").style("justify-self:start")
                with side_panels:
                    with ui.card().classes("act w-full p-4"):
                        ui.label("ACTION").classes("text-xs font-mono").style("color:#6a6a70")
                        action_label = ui.label("—").classes(
                            "text-xl font-bold break-words").style("color:#282828")
                    with ui.card().classes("w-full p-4").style("min-height:0"):
                        ui.label("REASONING").classes("text-xs font-mono").style("color:#7a7a80")
                        reasoning_label = ui.label("—").classes("text-sm break-words").style(
                            "color:#c9c9ce;overflow:auto;max-height:32vh")

            # Bottom: current-task strip, prompt + dropdown + Send, footer buttons.
            with ui.column().classes("gap-0 self-center items-center").style("width:760px;max-width:92vw"):
                # Strip shows the active task and opens the Current Task window.
                task_strip = ui.row().classes("items-center gap-2 no-wrap cursor-pointer").style(
                    "width:660px;max-width:88%;height:46px;background:#242424;border:1px solid #343434;"
                    "border-radius:14px;padding:0 16px 12px;margin-bottom:-12px")
                with task_strip:
                    ui.label("Current Task:").classes("font-semibold text-gray-500 shrink-0")
                    current_task_label = ui.label("No active task").classes(
                        "font-semibold truncate grow").style("color:#e8e8e8")
                    ui.label("⤢").classes("shrink-0").style("color:#777")
                task_strip.on("click", task_window.open)

                # Prompt box with the agent dropdown and the Send/Stop button.
                with ui.card().classes("w-full gap-2 p-3").style("position:relative;z-index:1"):
                    prompt_input = ui.input(placeholder="What can I do for you?") \
                        .props("borderless dark").classes("w-full text-lg")
                    with ui.row().classes("w-full items-center justify-end gap-2"):
                        agent_select = ui.select([], label="Agent",
                                                 on_change=lambda e: select_agent(e.value)) \
                            .props("outlined dense dark rounded").classes("w-44")
                        send_button = ui.button("Send", on_click=send_task_or_stop, color=None) \
                            .style(SEND_BUTTON_STYLE)

                # Footer: log/task windows on the left, agent actions on the right.
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.row().classes("gap-1"):
                        ui.button("⌘ Activity", on_click=activity_window.open, color=None) \
                            .props("flat").style("color:#a8a8a8")
                        ui.button("☑ Tasks", on_click=open_tasks_window, color=None) \
                            .props("flat").style("color:#a8a8a8")
                    with ui.row().classes("gap-1"):
                        ui.button("Clear Memory", on_click=clear_agent_memory, color=None) \
                            .props("flat").style("color:#a8a8a8")
                        ui.button("Disconnect", on_click=disconnect_agent, color=None) \
                            .props("flat").style("color:#d6b16a")
                prompt_input.on("keydown.enter", send_task_or_stop)

            # Background refresh loops: agents (slow), screenshot, then status (fast).
            ui.timer(3.0, refresh_agent_list)
            ui.timer(0.8, refresh_screenshot)
            ui.timer(0.5, refresh_agent_status)

    show_login_screen()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Harmony", port=8080, dark=True, reload=False, show=("--no-show" not in sys.argv))
