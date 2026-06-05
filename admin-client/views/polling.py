import base64
import hashlib
from io import BytesIO

import customtkinter as ctk
from PIL import Image, ImageDraw

import gateway_requests
from theme import AGENT_STATUS_LABELS, SCREEN_PREVIEW_SCALE
from widgets import append_log_entry


"""Polling loops that keep the dashboard synchronized with the server."""


class PollingMixin:
    """Refreshes agents, screenshots, and current agent status."""

    def _start_polling_loops(self):
        """Start all recurring UI refresh loops."""
        self._poll_agents_loop()
        self._poll_agent_status_loop()
        self._poll_screenshot_loop()

    # Every few seconds, ask the server who is around.
    def _poll_agents_loop(self):
        """Refresh the agent list every few seconds."""
        if self.user_id:
            self._run_in_background(self._fetch_agents_from_server)
        self.after(3000, self._poll_agents_loop)

    # Every short while, ask the helper for a fresh picture of its screen,
    # shrink it to fit, give it rounded corners, and show it.
    def _poll_screenshot_loop(self):
        """Refresh the selected agent screenshot."""
        if self.selected_agent:
            agent_id = self.selected_agent

            def background(max_w, max_h):
                """Fetch and prepare the screenshot away from the UI thread."""
                raw_data = gateway_requests.get_screen(agent_id).get("data")
                if not raw_data:
                    self.after(0, self._refresh_view_for_current_agent)
                    return

                screenshot = Image.open(BytesIO(base64.b64decode(raw_data))).convert("RGBA")
                scale = min(max_w / screenshot.width, max_h / screenshot.height) * SCREEN_PREVIEW_SCALE
                fw, fh = int(screenshot.width * scale), int(screenshot.height * scale)
                screenshot = screenshot.resize((fw, fh), Image.LANCZOS)

                # Mask the image so screenshots match the rounded UI.
                mask = Image.new("L", (fw, fh), 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    [(0, 0), (fw - 1, fh - 1)], radius=22, fill=255)
                screenshot.putalpha(mask)

                def apply():
                    """Apply the prepared image on the UI thread."""
                    if agent_id != self.selected_agent:
                        return
                    new_image = ctk.CTkImage(
                        light_image=screenshot, dark_image=screenshot, size=(fw, fh))
                    # Keep a few recent images alive so their underlying Tk
                    # pyimages don't get garbage-collected while still in use
                    # by the inner tk.Label.
                    if not hasattr(self, "_screenshot_refs"):
                        self._screenshot_refs = []
                    self._screenshot_refs.append(new_image)
                    if len(self._screenshot_refs) > 4:
                        self._screenshot_refs = self._screenshot_refs[-4:]
                    self._current_screenshot = new_image
                    try:
                        self.screenshot_label.configure(text="", image=new_image)
                    except Exception:
                        return
                    self._refresh_view_for_current_agent()

                self.after(0, apply)

            self.update_idletasks()
            reserve_w = getattr(self, "_screen_right_reserve", 360)
            self._run_in_background(background,
                max(self.content_area.winfo_width() - reserve_w, 280),
                max(self.content_area.winfo_height() - 40, 220))
        else:
            self.after(0, self._refresh_view_for_current_agent)
        self.after(800 if self.is_agent_working else 2000, self._poll_screenshot_loop)

    # Every half second or so, ask the helper what step it is on and what
    # it is thinking, then update the side cards and activity list.
    def _poll_agent_status_loop(self):
        """Refresh the selected agent status and activity display."""
        if self.selected_agent:
            def background(agent_id):
                """Fetch status data and schedule UI updates."""
                data           = gateway_requests.get_agent(agent_id)
                if agent_id != self.selected_agent:
                    return

                # Normalize server fields into local display variables.
                step_data      = data.get("step") or {}
                action_text    = (step_data.get("action") or "").strip()
                reasoning_text = (step_data.get("reasoning") or "").strip()
                coordinate     = step_data.get("coordinate") or step_data.get("Coordinate")
                value          = step_data.get("value") or step_data.get("Value")
                cmd_output     = step_data.get("cmd_output")
                current_task   = data.get("current_task") or data.get("task") or ""
                agent_status   = data.get("agent_state", "")
                status_message = data.get("agent_activity_message", "") or ""

                # Report meaningful state changes in the activity log.
                if agent_status != self._prev_agent_status:
                    old = self._prev_agent_status
                    self._prev_agent_status = agent_status
                    if old:
                        self._write_system_log(
                            f"Agent status: {AGENT_STATUS_LABELS.get(agent_status, agent_status)}")

                if status_message and status_message != self._prev_status_message:
                    self._prev_status_message = status_message
                    self._write_system_log(status_message)

                # Keep the send button in send/stop mode.
                is_working = agent_status == "working"
                if is_working != self.is_agent_working:
                    def update_btn(w=is_working):
                        self._set_send_button_working(w)
                    self.after(0, update_btn)

                # Hash visible data so unchanged status does not redraw the UI.
                fp = hashlib.md5(
                    f"{action_text}|{reasoning_text}|{coordinate}|{value}|{cmd_output}|"
                    f"{current_task}|{agent_status}".encode()
                ).hexdigest()
                if fp != self._prev_step_hash:
                    self._prev_step_hash = fp
                    end_coord = step_data.get("end_coordinate") or step_data.get("EndCoordinate")
                    action_key = action_text.lower()
                    is_done = (action_key == "done" or
                               (agent_status == "idle" and action_key in ("none", "")))
                    if is_done:
                        primary, meta, command, icon = "Done!", "", "", self.action_done_icon
                    else:
                        primary, meta, command = self._format_action(
                            action_text, coordinate, value, end_coord)
                        icon = None
                    disp_reasoning = reasoning_text or "—"
                    disp_task = current_task or "No active task"

                    self.after(0, lambda a=primary, m=meta, c=command, i=icon:
                               self._set_action_display(a, m, c, i))
                    self.after(0, lambda r=disp_reasoning: self._set_reasoning_text(r))
                    self.after(0, lambda t=disp_task: self._set_task_text(t))

                # Add one activity row only when the action/reasoning changes.
                lf = hashlib.md5(f"{action_text}|{reasoning_text}".encode()).hexdigest()
                if lf != self._prev_log_hash and (action_text or reasoning_text
                                                   or step_data.get("cmd_output")):
                    self._prev_log_hash = lf
                    self.after(0, lambda: append_log_entry(self.log_scroll, step_data.copy()))

            self._run_in_background(background, self.selected_agent)
        self.after(500, self._poll_agent_status_loop)
