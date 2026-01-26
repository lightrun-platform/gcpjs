"""Unit tests for RequestOverheadResultsViewer."""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch

# Add parent directory
parent_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(parent_dir))

from lightrun_nodejs_request_overhead_benchmark.src.request_overhead_results_viewer import RequestOverheadResultsViewer

class TestRequestOverheadResultsViewer(unittest.TestCase):
    """Test Results Viewer."""

    def test_display(self):
        """Test display method."""
        viewer = RequestOverheadResultsViewer()
        with patch('builtins.print') as mock_print:
            viewer.display(Path('/tmp'), 'report.txt')
            # Just check it prints something
            self.assertTrue(mock_print.called)

if __name__ == '__main__':
    unittest.main()
