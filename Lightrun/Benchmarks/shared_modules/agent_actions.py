from typing import Iterable, List
from .lightrun_api import LightrunAPI
from .agent_models import LightrunAction, LogAction, BreakpointAction

class AgentActions:
    """Container for a specific set of Lightrun actions."""

    def __init__(self, lightrun_api: LightrunAPI, actions: Iterable[LightrunAction]):
        self.lightrun_api = lightrun_api
        self.actions = list(actions)

    def apply(self, agent_id: str):
        """Apply all actions to the specified agent."""
        for action in self.actions:
            action.apply(agent_id, self.lightrun_api)
