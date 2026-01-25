"""Additional unit tests for format_duration edge cases."""

import unittest
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from report import format_duration


class TestFormatDurationEdgeCases(unittest.TestCase):
    """Test format_duration with edge cases."""
    
    def test_zero(self):
        """Test formatting zero."""
        result = format_duration(0)
        self.assertIn('0ns', result)
    
    def test_very_large_value(self):
        """Test formatting very large value."""
        result = format_duration(3_600_000_000_000)  # 1 hour in nanoseconds
        self.assertIn('3600s', result)
    
    def test_only_seconds(self):
        """Test formatting with only seconds."""
        result = format_duration(5_000_000_000)
        self.assertIn('5s', result)
        # Should not have fractional parts if exact
        parts = result.split(', ')
        self.assertTrue(any('5s' in part for part in parts))
    
    def test_precision(self):
        """Test that formatting maintains precision."""
        # Test with exact microsecond value
        result = format_duration(1_234_567)
        # Should show milliseconds, microseconds and nanoseconds
        self.assertIn('1ms', result)
        self.assertIn('234µs', result)
        self.assertIn('567ns', result)
