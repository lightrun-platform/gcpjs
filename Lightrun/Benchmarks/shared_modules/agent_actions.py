import logging
from typing import Iterable, List, Tuple
from Lightrun.Benchmarks.shared_modules.api import LightrunAPI
from .agent_models import LightrunAction
from .gcf_models.gcf_deploy_extended_parameters import NoPublicConstructor


class AgentNotFoundError(Exception):
    """Raised when an agent cannot be found by display name."""
    pass


class AgentActions(metaclass=NoPublicConstructor):
    """Container for a specific set of Lightrun actions.
    
    Args:
        lightrun_api: The Lightrun API client
        agent_display_name: The friendly display name of the agent (shown in UI)
        agent_id: The UUID of the agent (from server)
        actions: The actions to apply to the agent
    """

    def __init__(self, lightrun_api: LightrunAPI, agent_display_name: str, agent_id: str, actions: Iterable[LightrunAction]):
        self.logger = logging.getLogger(type(self).__name__)
        self.lightrun_api = lightrun_api
        self._agent_display_name = agent_display_name
        self._agent_id = agent_id
        self.actions = list(actions)
        self.applied_actions: List[Tuple[LightrunAction, str]] = []

    @classmethod
    def create(cls, lightrun_api: LightrunAPI, agent_display_name: str, actions: Iterable[LightrunAction]) -> 'AgentActions':
        """Factory method that resolves agent_id from display name.
        
        Args:
            lightrun_api: The Lightrun API client
            agent_display_name: The friendly display name of the agent (shown in UI)
            actions: The actions to apply to the agent
            
        Returns:
            AgentActions instance with resolved agent_id
            
        Raises:
            AgentNotFoundError: If the agent cannot be found by display name
        """
        agent_id = lightrun_api.get_agent_id(agent_display_name)
        if not agent_id:
            raise AgentNotFoundError(f"Could not find agent with display name '{agent_display_name}'")
        return cls._create(lightrun_api, agent_display_name, agent_id, actions)

    @property
    def agent_display_name(self) -> str:
        """The friendly display name of the agent (shown in UI)."""
        return self._agent_display_name

    @property
    def agent_id(self) -> str:
        """The actual UUID of the agent."""
        return self._agent_id

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
                self.logger.warning(f"Failed to remove {action.__class__.__name__}:{action_id} from agent '{self._agent_display_name}'")
                self.applied_actions.append((action, action_id))
