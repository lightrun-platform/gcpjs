import logging
from typing import Iterable, List, Tuple
from Lightrun.Benchmarks.shared_modules.api import LightrunAPI
from .agent_models import LightrunAction

class AgentActions:
    """Container for a specific set of Lightrun actions."""

    def __init__(self, lightrun_api: LightrunAPI, agent_id: str, actions: Iterable[LightrunAction]):
        self.logger = logging.getLogger(type(self).__name__)
        self.lightrun_api = lightrun_api
        self.agent_id = agent_id
        self.actions = list(actions)
        self.applied_actions: List[Tuple[LightrunAction, str]] = []

    def __enter__(self):
        """Apply all actions when entering context."""
        self.apply()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove all actions when exiting context."""
        self.remove_all()

    def apply(self):
        """Apply all actions to the specified agent."""
        for action in self.actions:
            action_id = action.apply(self.agent_id, self.lightrun_api)
            if action_id:
                self.applied_actions.append((action, action_id))

    def remove_all(self):
        """Remove all applied actions."""

        updated_state = [(action, action_id, action.remove(self.lightrun_api, action_id)) for action, action_id in self.applied_actions]

        self.applied_actions.clear()
        for action, action_id, is_removed in updated_state:
            if not is_removed:
                self.logger.warning(f"Failed to remove {action.__class__.__name__}:{action_id} from {self.agent_id}")
                self.applied_actions.append((action, action_id))

