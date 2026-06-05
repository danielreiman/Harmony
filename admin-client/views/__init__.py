"""Composable view mixins for the Admin dashboard."""

from .agent_status import AgentStatusMixin
from .bottom_bar import BottomBarMixin
from .floating_panels import FloatingPanelsMixin
from .polling import PollingMixin
from .screen import ScreenViewMixin
from .side_panel import SidePanelMixin
from .tasks_panel import TasksPanelMixin
from .top_bar import TopBarMixin
from .window import WindowMixin


class ViewMixin(
    WindowMixin,
    TopBarMixin,
    ScreenViewMixin,
    SidePanelMixin,
    BottomBarMixin,
    AgentStatusMixin,
    PollingMixin,
    FloatingPanelsMixin,
    TasksPanelMixin,
):
    """Single mixin that exposes all view-building behavior to HarmonyApp."""

    pass
