from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional

from Lightrun.Benchmarks.shared_modules.api import LightrunAPI

@dataclass(frozen=True)
class LightrunAction(ABC):
    """Base class for Lightrun actions."""
    filename: str
    line_number: int
    max_hit_count: int
    expire_seconds: int
    _action_id: dict = field(default_factory=lambda: {"value": None}, init=False)

    @property
    def is_applied(self) -> bool:
        return self.action_id is not None

    @property
    def action_id(self) -> Optional[str]:
        return self._action_id["value"]

    @abstractmethod
    def apply(self, agent_id: str, agent_pool_id: str, lightrun_api: LightrunAPI) -> Optional[str]:
        pass

    def remove(self, lightrun_api: LightrunAPI) -> bool:
        if not self.action_id:
            return False

        is_deleted = lightrun_api.delete_lightrun_action(self.action_id)
        if is_deleted:
            self._action_id["value"] = None
        return is_deleted

@dataclass(frozen=True)
class LogAction(LightrunAction):
    """Action to log a message at a specific location."""
    log_message: str
    name: str = "LogAction"


    def apply(self, agent_id: str, agent_pool_id: str, lightrun_api: LightrunAPI) -> Optional[str]:
        self._action_id["value"] =  lightrun_api.add_log_action(agent_id=agent_id,
                                                                agent_pool_id=agent_pool_id,
                                                                filename=self.filename,
                                                                line_number=self.line_number,
                                                                message=self.log_message,
                                                                max_hit_count=self.max_hit_count,
                                                                expire_seconds=self.expire_seconds)

        return self.action_id



@dataclass(frozen=True)
class BreakpointAction(LightrunAction):
    """Action to set a snapshot/breakpoint at a specific location."""
    name: str = "BreakpointAction"

    def apply(self, agent_id: str, agent_pool_id: str, lightrun_api: LightrunAPI) -> Optional[str]:
        self._action_id["value"] = lightrun_api.add_snapshot(agent_id=agent_id,
                                                             agent_pool_id=agent_pool_id,
                                                             filename=self.filename,
                                                             line_number=self.line_number,
                                                             max_hit_count=self.max_hit_count,
                                                             expire_seconds=self.expire_seconds)

        return self.action_id