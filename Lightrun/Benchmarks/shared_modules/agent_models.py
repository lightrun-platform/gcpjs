from dataclasses import dataclass
from abc import ABC, abstractmethod

from Lightrun.Benchmarks.shared_modules.lightrun_api import LightrunAPI


@dataclass(frozen=True)
class LightrunAction(ABC):
    """Base class for Lightrun actions."""
    filename: str
    line_number: int
    max_hit_count: int
    expire_seconds: int

    @abstractmethod
    def apply(self, agent_id: str, lightrun_api: LightrunAPI):
        pass

@dataclass(frozen=True)
class LogAction(LightrunAction):
    """Action to log a message at a specific location."""
    log_message: str
    name: str = "LogAction"


    def apply(self, agent_id: str, lightrun_api: LightrunAPI):
        lightrun_api.add_log_action(agent_id=agent_id,
                                    filename=self.filename,
                                    line_number=self.line_number,
                                    message=self.log_message,
                                    max_hit_count=self.max_hit_count,
                                    expire_seconds=self.expire_seconds)



@dataclass(frozen=True)
class BreakpointAction(LightrunAction):
    """Action to set a snapshot/breakpoint at a specific location."""
    name: str = "BreakpointAction"

    def apply(self, agent_id: str, lightrun_api: LightrunAPI):
        lightrun_api.add_snapshot(agent_id=agent_id,
                                  filename=self.filename,
                                  line_number=self.line_number,
                                  max_hit_count=self.max_hit_count,
                                  expire_seconds=self.expire_seconds)