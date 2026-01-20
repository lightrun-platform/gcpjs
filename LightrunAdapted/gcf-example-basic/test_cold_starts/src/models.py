from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

@dataclass
class GCPFunction:
    """Represents a Google Cloud Function instance throughout its lifecycle."""
    index: int
    name: str = field(init=False)
    display_name: str = field(init=False)
    region: Optional[str] = None
    url: Optional[str] = None
    deployed: bool = False
    details: Dict[str, Any] = field(default_factory=dict)
    test_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        # Default name format, can be overridden if needed but usually standard
        pass

    def set_names(self, base_name: str):
        self.name = f"{base_name}-{self.index:03d}".lower()
        self.display_name = f"{base_name}-gcf-performance-test-{self.index:03d}"
