import unittest
from unittest.mock import Mock, patch
import sys
import logging
from pathlib import Path

# Add parent directory to path so we can import as a package
benchmarks_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(benchmarks_dir))
sys.path.insert(0, str(benchmarks_dir.parent.parent))

from Lightrun.Benchmarks.shared_modules.debugging_session import DebuggingSession, AgentNotFoundError
from Lightrun.Benchmarks.shared_modules.agent_models import LogAction, BreakpointAction
from Lightrun.Benchmarks.shared_modules.api import LightrunAPI


class TestAgentActions(unittest.TestCase):
    def setUp(self):
        self.mock_api = Mock(spec=LightrunAPI)
        self.agent_display_name = "test-function-display-name"
        self.agent_id = "agent-uuid-123"
        self.agent_pool_id = "pool-1"
        self.mock_api.get_agent.return_value = {"id": self.agent_id, "agentPoolId": self.agent_pool_id}
        self.logger = Mock(spec=logging.Logger)

    def test_apply_actions(self):
        self.mock_api.add_log_action.return_value = "log-123"
        self.mock_api.add_snapshot.return_value = "snap-456"
        self.mock_api.delete_lightrun_action.return_value = True

        actions = [
            LogAction(filename="main.py", line_number=10, log_message="Hello", max_hit_count=5, expire_seconds=60),
            BreakpointAction(filename="utils.py", line_number=20, max_hit_count=1, expire_seconds=300),
        ]

        with DebuggingSession(self.mock_api, self.agent_display_name, actions, self.logger) as session:
            session.apply_actions()
            self.mock_api.get_agent.assert_called_with(self.agent_display_name)
            self.mock_api.add_log_action.assert_called_once_with(
                agent_id=self.agent_id,
                agent_pool_id=self.agent_pool_id,
                filename="main.py",
                line_number=10,
                message="Hello",
                max_hit_count=5,
                expire_seconds=60,
            )
            self.mock_api.add_snapshot.assert_called_once_with(
                agent_id=self.agent_id,
                agent_pool_id=self.agent_pool_id,
                filename="utils.py",
                line_number=20,
                max_hit_count=1,
                expire_seconds=300,
            )
            self.assertEqual(session.agent_display_name, self.agent_display_name)
            self.assertEqual(session.agent_id, self.agent_id)

        self.assertEqual(self.mock_api.delete_lightrun_action.call_count, 2)
        self.mock_api.delete_lightrun_action.assert_any_call("log-123", self.agent_pool_id)
        self.mock_api.delete_lightrun_action.assert_any_call("snap-456", self.agent_pool_id)

    def test_empty_actions(self):
        with DebuggingSession(self.mock_api, self.agent_display_name, [], self.logger) as session:
            session.apply_actions()

        self.mock_api.add_log_action.assert_not_called()
        self.mock_api.add_snapshot.assert_not_called()
        self.mock_api.delete_lightrun_action.assert_not_called()

    @patch.object(DebuggingSession, "FIND_AGENT_RETRIES", 1)
    @patch.object(DebuggingSession, "RETRY_DELAY", 0)
    def test_agent_not_found(self):
        self.mock_api.get_agent.return_value = None
        self.mock_api.list_agents.return_value = []

        actions = [
            LogAction(filename="main.py", line_number=10, log_message="Hello", max_hit_count=5, expire_seconds=60),
        ]

        with self.assertRaises(AgentNotFoundError) as context:
            with DebuggingSession(self.mock_api, self.agent_display_name, actions, self.logger) as session:
                session.apply_actions()

        self.assertIn(self.agent_display_name, str(context.exception))


if __name__ == "__main__":
    unittest.main()
