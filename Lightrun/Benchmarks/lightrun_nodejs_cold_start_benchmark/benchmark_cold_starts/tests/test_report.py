"""Unit tests for report.py module."""

import unittest
import statistics
import sys
from pathlib import Path
import numpy as np

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from report import (
    calculate_stats,
    format_duration,
    calculate_t_test,
    calculate_effect_size,
    calculate_f_test,
    ReportGenerator
)


class TestCalculateStats(unittest.TestCase):
    """Test calculate_stats function."""
    
    def test_empty_list(self):
        """Test with empty list."""
        result = calculate_stats([])
        self.assertEqual(result, {})
    
    def test_single_value(self):
        """Test with single value."""
        result = calculate_stats([100])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['min'], 100)
        self.assertEqual(result['max'], 100)
        self.assertEqual(result['mean'], 100)
        self.assertEqual(result['median'], 100)
        self.assertEqual(result['stdev'], 0.0)
    
    def test_multiple_values(self):
        """Test with multiple values."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_stats(values)
        self.assertEqual(result['count'], 5)
        self.assertEqual(result['min'], 1.0)
        self.assertEqual(result['max'], 5.0)
        self.assertEqual(result['mean'], 3.0)
        self.assertEqual(result['median'], 3.0)
        self.assertAlmostEqual(result['stdev'], statistics.stdev(values))


class TestFormatDuration(unittest.TestCase):
    """Test format_duration function."""
    
    def test_nanoseconds_only(self):
        """Test formatting nanoseconds."""
        result = format_duration(500)
        self.assertIn('500ns', result)
    
    def test_microseconds(self):
        """Test formatting microseconds."""
        result = format_duration(1500)
        self.assertIn('1µs', result)
        self.assertIn('500ns', result)
    
    def test_milliseconds(self):
        """Test formatting milliseconds."""
        result = format_duration(1_500_000)
        self.assertIn('1ms', result)
        self.assertIn('500µs', result)
    
    def test_seconds(self):
        """Test formatting seconds."""
        result = format_duration(1_500_000_000)
        self.assertIn('1s', result)
        self.assertIn('500ms', result)
    
    def test_mixed_units(self):
        """Test formatting with multiple units."""
        result = format_duration(1_234_567_890)
        self.assertIn('1s', result)
        self.assertIn('234ms', result)
        self.assertIn('567µs', result)
        self.assertIn('890ns', result)


class TestCalculateTTest(unittest.TestCase):
    """Test calculate_t_test function."""
    
    def test_insufficient_data(self):
        """Test with insufficient data."""
        result = calculate_t_test([1.0], [2.0])
        self.assertTrue(np.isnan(result['t_statistic']))
        self.assertTrue(np.isnan(result['p_value']))
        self.assertFalse(result['significant'])
    
    def test_equal_means(self):
        """Test with equal means."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_t_test(values1, values2)
        self.assertAlmostEqual(result['t_statistic'], 0.0, places=5)
        self.assertGreater(result['p_value'], 0.9)
        self.assertFalse(result['significant'])
    
    def test_different_means(self):
        """Test with significantly different means."""
        values1 = [10.0, 11.0, 12.0, 13.0, 14.0]
        values2 = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_t_test(values1, values2)
        self.assertGreater(abs(result['t_statistic']), 5)  # Lower threshold
        self.assertLess(result['p_value'], 0.05)
        self.assertTrue(result['significant'])
    
    def test_small_difference(self):
        """Test with small difference."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [1.1, 2.1, 3.1, 4.1, 5.1]
        result = calculate_t_test(values1, values2)
        self.assertIsInstance(result['t_statistic'], (int, float))
        self.assertIsInstance(result['p_value'], (int, float))
        self.assertIsInstance(result['degrees_of_freedom'], (int, float))


class TestCalculateEffectSize(unittest.TestCase):
    """Test calculate_effect_size function."""
    
    def test_insufficient_data(self):
        """Test with insufficient data."""
        result = calculate_effect_size([1.0], [2.0])
        self.assertTrue(np.isnan(result['cohens_d']))
    
    def test_equal_means(self):
        """Test with equal means."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_effect_size(values1, values2)
        self.assertAlmostEqual(result['cohens_d'], 0.0, places=5)
        self.assertEqual(result['magnitude'], 'negligible')
    
    def test_large_difference(self):
        """Test with large difference."""
        values1 = [10.0, 11.0, 12.0, 13.0, 14.0]
        values2 = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_effect_size(values1, values2)
        self.assertGreater(abs(result['cohens_d']), 0.8)
        self.assertEqual(result['magnitude'], 'large')
    
    def test_small_difference(self):
        """Test with small difference."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [1.1, 2.1, 3.1, 4.1, 5.1]
        result = calculate_effect_size(values1, values2)
        self.assertIsInstance(result['cohens_d'], (int, float))
        self.assertIn(result['magnitude'], ['negligible', 'small', 'medium', 'large'])
    
    def test_zero_pooled_std(self):
        """Test with zero pooled standard deviation."""
        values1 = [1.0, 1.0, 1.0]
        values2 = [2.0, 2.0, 2.0]
        result = calculate_effect_size(values1, values2)
        self.assertTrue(np.isnan(result['cohens_d']))


class TestCalculateFTest(unittest.TestCase):
    """Test calculate_f_test function."""
    
    def test_insufficient_data(self):
        """Test with insufficient data."""
        result = calculate_f_test([1.0], [2.0])
        self.assertTrue(np.isnan(result['f_statistic']))
        self.assertTrue(np.isnan(result['p_value']))
        self.assertFalse(result['significant'])
    
    def test_equal_variances(self):
        """Test with equal variances."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = calculate_f_test(values1, values2)
        self.assertAlmostEqual(result['f_statistic'], 1.0, places=5)
        self.assertGreater(result['p_value'], 0.9)
        self.assertFalse(result['significant'])
    
    def test_different_variances(self):
        """Test with different variances."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [10.0, 10.1, 10.2, 10.3, 10.4]  # Low variance
        result = calculate_f_test(values1, values2)
        self.assertGreater(result['f_statistic'], 1.0)
        self.assertIsInstance(result['p_value'], (int, float))
    
    def test_f_statistic_always_ge_one(self):
        """Test that F-statistic is always >= 1."""
        values1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        values2 = [10.0, 10.1, 10.2, 10.3, 10.4]
        result = calculate_f_test(values1, values2)
        self.assertGreaterEqual(result['f_statistic'], 1.0)


class TestReportGenerator(unittest.TestCase):
    """Test ReportGenerator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.with_lightrun = {
            'deployments': [
                {'is_deployed': True, 'function_name': 'test-001', 'time_to_cold_seconds': 1200}
            ],
            'test_results': [
                {
                    'isColdStart': True,
                    'totalDuration': '1000000000',
                    'totalImportsDuration': '500000000',
                    'gcfImportDuration': '1000000',
                    'envCheckDuration': '10000',
                    'totalSetupDuration': '501000000',
                    'functionInvocationOverhead': '499000000',
                    'lightrunImportDuration': '499000000',
                    'lightrunInitDuration': '50000',
                    '_request_latency': 1500000000
                }
            ]
        }
        self.without_lightrun = {
            'deployments': [
                {'is_deployed': True, 'function_name': 'test-002', 'time_to_cold_seconds': 1100}
            ],
            'test_results': [
                {
                    'isColdStart': True,
                    'totalDuration': '50000000',
                    'totalImportsDuration': '1000000',
                    'gcfImportDuration': '1000000',
                    'envCheckDuration': '5000',
                    'totalSetupDuration': '1005000',
                    'functionInvocationOverhead': '48995000',
                    '_request_latency': 60000000
                }
            ]
        }
    
    def test_init(self):
        """Test ReportGenerator initialization."""
        generator = ReportGenerator(self.with_lightrun, self.without_lightrun)
        self.assertEqual(generator.with_lightrun, self.with_lightrun)
        self.assertEqual(generator.without_lightrun, self.without_lightrun)
    
    def test_set_output_dir(self):
        """Test setting output directory."""
        from pathlib import Path
        generator = ReportGenerator(self.with_lightrun, self.without_lightrun)
        test_dir = Path('/tmp/test_output')
        generator.set_output_dir(test_dir)
        self.assertEqual(generator.output_dir, test_dir)
    
    def test_extract_metrics(self):
        """Test metric extraction."""
        generator = ReportGenerator(self.with_lightrun, self.without_lightrun)
        metrics = generator._extract_metrics(self.with_lightrun)
        
        self.assertIn('totalDuration', metrics)
        self.assertIn('totalImportsDuration', metrics)
        self.assertIn('isColdStart', metrics)
        self.assertEqual(len(metrics['totalDuration']), 1)
        self.assertEqual(float(metrics['totalDuration'][0]), 1000000000.0)
    
    def test_extract_metrics_with_time_to_cold(self):
        """Test metric extraction includes timeToCold."""
        generator = ReportGenerator(self.with_lightrun, self.without_lightrun)
        metrics = generator._extract_metrics(self.with_lightrun)
        
        self.assertIn('timeToCold', metrics)
        self.assertEqual(len(metrics['timeToCold']), 1)
        # timeToCold is in seconds, converted to nanoseconds
        self.assertEqual(metrics['timeToCold'][0], 1200 * 1_000_000_000)
    
    def test_generate_comparative_report(self):
        """Test report generation."""
        generator = ReportGenerator(self.with_lightrun, self.without_lightrun)
        report = generator.generate_comparative_report()
        
        self.assertIsInstance(report, str)
        self.assertIn('Cloud Function Cold Start Performance', report)
        self.assertIn('TEST SUMMARY', report)
        self.assertIn('METRICS COMPARISON', report)
        self.assertIn('With Lightrun', report)
        self.assertIn('Without Lightrun', report)
    
    def test_generate_comparative_report_includes_statistics(self):
        """Test report includes statistical tests."""
        # Add more data points to ensure statistical tests are included
        self.with_lightrun['test_results'].append({
            'isColdStart': True,
            'totalDuration': '1100000000',
            'totalImportsDuration': '510000000',
            'gcfImportDuration': '1100000',
            'envCheckDuration': '11000',
            'totalSetupDuration': '511000000',
            'functionInvocationOverhead': '489000000',
            'lightrunImportDuration': '509000000',
            'lightrunInitDuration': '51000',
            '_request_latency': 1600000000
        })
        self.without_lightrun['test_results'].append({
            'isColdStart': True,
            'totalDuration': '55000000',
            'totalImportsDuration': '1100000',
            'gcfImportDuration': '1100000',
            'envCheckDuration': '6000',
            'totalSetupDuration': '1106000',
            'functionInvocationOverhead': '53894000',
            '_request_latency': 65000000
        })
        
        generator = ReportGenerator(self.with_lightrun, self.without_lightrun)
        report = generator.generate_comparative_report()
        
        # Check for statistical test results
        self.assertIn('T-Test', report)
        self.assertIn('Effect Size', report)
        self.assertIn('F-Test', report)
        self.assertIn('Cohen', report)
        self.assertIn('StdDev', report)


if __name__ == '__main__':
    unittest.main()
