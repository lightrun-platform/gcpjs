import logging
import time
from typing import Iterable, List, Tuple
from Lightrun.Benchmarks.shared_modules.api import LightrunAPI
from .agent_models import LightrunAction


class AgentNotFoundError(Exception):
    """Raised when an agent cannot be found by display name."""
    pass


class DebuggingSession:
    """Context manager applying and removing a specific set of Lightrun actions.
    
    Args:
        lightrun_api: The Lightrun API client
        agent_display_name: The friendly display name of the agent (shown in UI)
        agent_id: The UUID of the agent (from server)
        actions: The actions to apply to the agent
    """

    RETRY_DELAY = 1
    FIND_AGENT_RETRIES = 10

    def __init__(self, lightrun_api: LightrunAPI, agent_display_name: str, actions: Iterable[LightrunAction], agent_actions_update_interval_seconds: int, logger: logging.Logger):
        self.lightrun_api = lightrun_api
        self._agent_display_name = agent_display_name
        self._agent_id = None # looked up on __enter__
        self.actions = list(actions)
        self.applied_actions: List[Tuple[LightrunAction, str]] = []
        self.agent_actions_update_interval_seconds = agent_actions_update_interval_seconds
        self._applied_actions: bool = False
        self.logger = logger

    def __enter__(self):
        self._find_agent_id()
        return self

    def _find_agent_id(self) -> None:
        if self._agent_id is not None:
            return

        successful_attempt_id = None
        for attempt in range(DebuggingSession.FIND_AGENT_RETRIES):
            self._agent_id = self.lightrun_api.get_agent_id(self.agent_display_name)
            if self._agent_id:
                successful_attempt_id = attempt
                break
            
            if attempt < DebuggingSession.FIND_AGENT_RETRIES:
                self.logger.info(f"Agent '{self.agent_display_name}' not found, retrying in {DebuggingSession.RETRY_DELAY}s... ({attempt + 1}/{DebuggingSession.FIND_AGENT_RETRIES})")
                time.sleep(DebuggingSession.RETRY_DELAY)
                
        if not self.agent_id:
            raise AgentNotFoundError(f"Timed out after looking for the agent for "
                                     f"{DebuggingSession.FIND_AGENT_RETRIES * DebuggingSession.RETRY_DELAY}"
                                     f"seconds. Could not find agent with display name '{self.agent_display_name}' "
                                     f"for {DebuggingSession.FIND_AGENT_RETRIES} retries "
                                     f"with {DebuggingSession.RETRY_DELAY} seconds break between them. "
                                     f"All agents: {self.lightrun_api.list_agents()}")
        
        if successful_attempt_id > 0:
             self.logger.info(f"Agent '{self.agent_display_name}' found {f"after {successful_attempt_id} retries" if successful_attempt_id > 0 else "on first attempt"}")

    @property
    def agent_display_name(self) -> str:
        """The friendly display name of the agent (shown in UI)."""
        return self._agent_display_name

    @property
    def agent_id(self) -> str:
        """The actual UUID of the agent."""
        return self._agent_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Remove all actions when exiting context."""
        if not self._applied_actions:
            self.logger.debug("Exiting the the DebuggingSession scope without apply_actions ever being called. did you forget to call it? actions are not applied automatically on context entry.")
        self.remove_all()

    def apply_actions(self):
        """Apply all actions to the specified agent."""

        if not self.agent_id:
            self.logger.info("Agent id was not found yet, attempting to find it so we can apply the actions.")
            self._find_agent_id() # will raise an exception if unsuccessful
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
