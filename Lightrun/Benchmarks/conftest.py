"""Pytest conftest: set up path and Benchmarks alias so all Benchmark tests can import correctly."""
import sys
from pathlib import Path

# Ensure repo root is on path so "Lightrun" package resolves
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# cli_parser and some code use "from Benchmarks.shared_modules..."; alias Lightrun.Benchmarks
import Lightrun.Benchmarks  # noqa: E402
sys.modules["Benchmarks"] = Lightrun.Benchmarks
