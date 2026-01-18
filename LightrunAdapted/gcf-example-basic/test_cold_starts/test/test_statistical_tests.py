"""Unit tests for statistical test functions with various scenarios."""

import unittest
import sys
from pathlib import Path
import numpy as np

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from report import (
    calculate_t_test,
    calculate_effect_size,
    calculate_f_test
)


class TestStatisticalTestsScenarios(unittest.TestCase):
    """Test statistical functions with various real-world scenarios."""
    
    def test_t_test_with_realistic_timing_data(self):
        """Test t-test with realistic Cloud Function timing data."""
        # Simulate cold start durations (in nanoseconds)
        with_lightrun = [
            1_500_000_000,  # 1.5 seconds
            1_600_000_000,  # 1.6 seconds
            1_550_000_000,  # 1.55 seconds
        ]
        without_lightrun = [
            500_000_000,    # 0.5 seconds
            600_000_000,    # 0.6 seconds
            550_000_000,    # 0.55 seconds
        ]
        
        result = calculate_t_test(with_lightrun, without_lightrun)
        
        self.assertGreater(result['t_statistic'], 0)
        self.assertLess(result['p_value'], 0.05)  # Should be significant
        self.assertTrue(result['significant'])
        self.assertIsInstance(result['degrees_of_freedom'], (int, float))
    
    def test_effect_size_with_realistic_data(self):
        """Test effect size with realistic Cloud Function timing data."""
        with_lightrun = [
            1_500_000_000,
            1_600_000_000,
            1_550_000_000,
        ]
        without_lightrun = [
            500_000_000,
            600_000_000,
            550_000_000,
        ]
        
        result = calculate_effect_size(with_lightrun, without_lightrun)
        
        self.assertGreater(result['cohens_d'], 0)  # Positive effect
        self.assertGreater(abs(result['cohens_d']), 0.8)  # Should be large
        self.assertEqual(result['magnitude'], 'large')
    
    def test_f_test_with_different_variances(self):
        """Test F-test with groups having different variances."""
        # High variance group
        high_var = [100, 200, 300, 400, 500]
        # Low variance group
        low_var = [250, 251, 252, 253, 254]
        
        result = calculate_f_test(high_var, low_var)
        
        self.assertGreater(result['f_statistic'], 1.0)
        self.assertLess(result['p_value'], 1.0)
        # With such different variances, should be significant
        self.assertTrue(result['significant'])
    
    def test_all_tests_with_identical_data(self):
        """Test all statistical tests with identical data."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        
        t_result = calculate_t_test(data, data)
        es_result = calculate_effect_size(data, data)
        f_result = calculate_f_test(data, data)
        
        # T-test should show no difference
        self.assertAlmostEqual(t_result['t_statistic'], 0.0, places=5)
        self.assertGreater(t_result['p_value'], 0.9)
        
        # Effect size should be zero
        self.assertAlmostEqual(es_result['cohens_d'], 0.0, places=5)
        self.assertEqual(es_result['magnitude'], 'negligible')
        
        # F-test should show equal variances
        self.assertAlmostEqual(f_result['f_statistic'], 1.0, places=5)
        self.assertGreater(f_result['p_value'], 0.9)
    
    def test_statistical_tests_with_single_difference(self):
        """Test when groups differ by a single outlier."""
        group1 = [100, 100, 100, 100, 1000]  # One outlier
        group2 = [100, 100, 100, 100, 100]   # Consistent
        
        t_result = calculate_t_test(group1, group2)
        es_result = calculate_effect_size(group1, group2)
        f_result = calculate_f_test(group1, group2)
        
        # Should detect the difference
        self.assertNotEqual(t_result['t_statistic'], 0.0)
        self.assertNotEqual(es_result['cohens_d'], 0.0)
        self.assertGreater(f_result['f_statistic'], 1.0)
    
    def test_edge_case_very_small_differences(self):
        """Test with very small differences between groups."""
        group1 = [1_000_000_000, 1_000_000_001, 1_000_000_002]
        group2 = [1_000_000_000, 1_000_000_001, 1_000_000_002]
        
        t_result = calculate_t_test(group1, group2)
        es_result = calculate_effect_size(group1, group2)
        
        # Should show negligible/no difference
        self.assertAlmostEqual(t_result['t_statistic'], 0.0, places=2)
        self.assertAlmostEqual(es_result['cohens_d'], 0.0, places=2)
        self.assertEqual(es_result['magnitude'], 'negligible')


if __name__ == '__main__':
    unittest.main()
