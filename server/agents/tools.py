from typing import Literal, Union
from pydantic import BaseModel, Field



class LeftClickTool(BaseModel):
    tool_name: Literal["left_click"]
    element: str = Field(description="Description of the target UI element")
    x: int = Field(description="X coordinate in [0, 1000]")
    y: int = Field(description="Y coordinate in [0, 1000]")


class DoubleClickTool(BaseModel):
    tool_name: Literal["double_click"]
    element: str = Field(description="Description of the target UI element")
    x: int = Field(description="X coordinate in [0, 1000]")
    y: int = Field(description="Y coordinate in [0, 1000]")


class RightClickTool(BaseModel):
    tool_name: Literal["right_click"]
    element: str = Field(description="Description of the target UI element")
    x: int = Field(description="X coordinate in [0, 1000]")
    y: int = Field(description="Y coordinate in [0, 1000]")


class DragTool(BaseModel):
    tool_name: Literal["drag"]
    element: str = Field(description="Description of what to drag")
    x: int = Field(description="Start X in [0, 1000]")
    y: int = Field(description="Start Y in [0, 1000]")
    end_x: int = Field(description="End X in [0, 1000]")
    end_y: int = Field(description="End Y in [0, 1000]")


class TypeTool(BaseModel):
    tool_name: Literal["type"]
    content: str = Field(description="Text to type into the focused field")


class PressKeyTool(BaseModel):
    tool_name: Literal["press_key"]
    key: str = Field(description="Key to press, e.g. 'enter', 'tab', 'escape'")


class HotkeyTool(BaseModel):
    tool_name: Literal["hotkey"]
    keys: list[str] = Field(description="Keys to press together, e.g. ['ctrl', 's']")


class ScrollUpTool(BaseModel):
    tool_name: Literal["scroll_up"]


class ScrollDownTool(BaseModel):
    tool_name: Literal["scroll_down"]


class RunCommandTool(BaseModel):
    tool_name: Literal["run_command"]
    command: str = Field(description="Windows shell command to run")


class WaitTool(BaseModel):
    tool_name: Literal["wait"]
    seconds: float = Field(default=0.15, description="Seconds to wait")


class DoneTool(BaseModel):
    tool_name: Literal["done"]
    message: str = Field(description="Task completion summary")


AnyTool = Union[
    LeftClickTool,
    DoubleClickTool,
    RightClickTool,
    DragTool,
    TypeTool,
    PressKeyTool,
    HotkeyTool,
    ScrollUpTool,
    ScrollDownTool,
    RunCommandTool,
    WaitTool,
    DoneTool,
]


class Step(BaseModel):
    note: str = Field(
        min_length=15,
        description=(
            "REQUIRED. Durable memory — the ONLY field that persists between turns; "
            "your reasoning is discarded. Write a concrete fact you observed on the "
            "current screen that you'll need later: URLs, IDs, error messages, form "
            "state, what just succeeded or failed, color feedback from a game, the "
            "last value you typed. Example: 'Salary B9=$0. Tab moved cursor to B11 "
            "not B12.' If nothing new, write 'No new info; continuing: <plan>'."
        ),
    )
    thought: str = Field(
        min_length=10,
        description="One concrete sentence: what you'll do next and why, given the current screen.",
    )
    tool_call: AnyTool


STEP_SCHEMA = Step.model_json_schema()


def value_for(tool_call: AnyTool):
    name = tool_call.tool_name

    if name == "type":
        return tool_call.content
    if name == "press_key":
        return tool_call.key
    if name == "hotkey":
        return tool_call.keys
    if name == "run_command":
        return tool_call.command
    if name == "wait":
        return str(tool_call.seconds)
    return None


def coordinate_for(tool_call: AnyTool):
    if hasattr(tool_call, "x") and hasattr(tool_call, "y"):
        return [tool_call.x, tool_call.y]
    return None


def end_coordinate_for(tool_call: AnyTool):
    if tool_call.tool_name == "drag":
        return [tool_call.end_x, tool_call.end_y]
    return None


def build_cmd_step(tool_call: AnyTool) -> dict:
    return {
        "Next Action": tool_call.tool_name,
        "Coordinate": coordinate_for(tool_call),
        "EndCoordinate": end_coordinate_for(tool_call),
        "Value": value_for(tool_call),
    }
