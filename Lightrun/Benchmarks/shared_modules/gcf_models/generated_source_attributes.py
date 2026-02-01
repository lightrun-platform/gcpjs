from dataclasses import dataclass
from pathlib import Path

@dataclass
class GeneratedSourceAttributes:

    path: Path
    entry_point: str