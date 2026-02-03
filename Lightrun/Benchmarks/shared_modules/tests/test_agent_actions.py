import unittest
from unittest.mock import Mock
import sys
from pathlib import Path

# Add parent directory to path so we can import as a package
benchmarks_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.agent_actions import AgentActions, AgentNotFoundError
from Lightrun.Benchmarks.shared_modules.agent_models import LogAction, BreakpointAction
from Lightrun.Benchmarks.shared_modules.api import LightrunAPI

class TestAgentActions(unittest.TestCase):
    def setUp(self):
        self.mock_api = Mock(spec=LightrunAPI)
        self.agent_display_name = "test-function-display-name"
        self.agent_id = "agent-uuid-123"  # The real UUID
        # Mock get_agent_id to return the UUID when called with display name
        self.mock_api.get_agent_id.return_value = self.agent_id

    def test_apply_actions(self):
        # Mock return values for action IDs
        self.mock_api.add_log_action.return_value = "log-123"
        self.mock_api.add_snapshot.return_value = "snap-456"

        actions = [
            LogAction(filename="main.py", line_number=10, log_message="Hello", max_hit_count=5, expire_seconds=60),
            BreakpointAction(filename="utils.py", line_number=20, max_hit_count=1, expire_seconds=300)
        ]
        
        # Use factory method (direct constructor blocked by metaclass)
        with AgentActions.create(self.mock_api, self.agent_display_name, actions) as agent_actions:
            # Verify get_agent_id was called with the display name
            self.mock_api.get_agent_id.assert_called_once_with(self.agent_display_name)
            
            # Verify actions were applied with the UUID
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
            
            # Verify properties return correct values
            self.assertEqual(agent_actions.agent_display_name, self.agent_display_name)
            self.assertEqual(agent_actions.agent_id, self.agent_id)
        
        # Verify removal after exit
        self.mock_api.delete_log_action.assert_called_once_with("log-123")
        self.mock_api.delete_snapshot.assert_called_once_with("snap-456")

    def test_empty_actions(self):
        with AgentActions.create(self.mock_api, self.agent_display_name, []):
            pass
        
        self.mock_api.add_log_action.assert_not_called()
        self.mock_api.add_snapshot.assert_not_called()
        self.mock_api.delete_log_action.assert_not_called()
        self.mock_api.delete_snapshot.assert_not_called()

    def test_agent_not_found(self):
        """Test factory method raises AgentNotFoundError when agent not found."""
        self.mock_api.get_agent_id.return_value = None
        
        actions = [
            LogAction(filename="main.py", line_number=10, log_message="Hello", max_hit_count=5, expire_seconds=60)
        ]
        
        with self.assertRaises(AgentNotFoundError) as context:
            AgentActions.create(self.mock_api, self.agent_display_name, actions)
        
        self.assertIn(self.agent_display_name, str(context.exception))

if __name__ == '__main__':
    unittest.main()
