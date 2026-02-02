import unittest
from unittest.mock import Mock, call
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
benchmarks_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.agent_actions import AgentActions
from Lightrun.Benchmarks.shared_modules.agent_models import LogAction, BreakpointAction
from Lightrun.Benchmarks.shared_modules.api import LightrunAPI

class TestAgentActions(unittest.TestCase):
    def setUp(self):
        self.mock_api = Mock(spec=LightrunAPI)
        self.agent_id = "test-agent-123"

    def test_apply_actions(self):
        # Mock return values for action IDs
        self.mock_api.add_log_action.return_value = "log-123"
        self.mock_api.add_snapshot.return_value = "snap-456"

        actions = [
            LogAction(filename="main.py", line_number=10, log_message="Hello", max_hit_count=5, expire_seconds=60),
            BreakpointAction(filename="utils.py", line_number=20, max_hit_count=1, expire_seconds=300)
        ]
        
        # Use context manager
        with AgentActions(self.mock_api, self.agent_id, actions): 
            self.mock_api.add_log_action.assert_called_once_with(
                agent_id=self.agent_id,
                filename="main.py",
                line_number=10,
                message="Hello",
                max_hit_count=5,
                expire_seconds=60
            )
            self.mock_api.add_snapshot.assert_called_once_with(
                agent_id=self.agent_id,
                filename="utils.py",
                line_number=20,
                max_hit_count=1,
                expire_seconds=300
            )
        
        # Verify removal after exit
        self.mock_api.delete_log_action.assert_called_once_with("log-123")
        self.mock_api.delete_snapshot.assert_called_once_with("snap-456")

    def test_empty_actions(self):
        with AgentActions(self.mock_api, self.agent_id, []):
            pass
        
        self.mock_api.add_log_action.assert_not_called()
        self.mock_api.add_snapshot.assert_not_called()
        self.mock_api.delete_log_action.assert_not_called()
        self.mock_api.delete_snapshot.assert_not_called()

if __name__ == '__main__':
    unittest.main()
