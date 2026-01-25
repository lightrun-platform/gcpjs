"""Report generation and visualization utilities."""

import statistics
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path


def calculate_stats(values: List[float]) -> Dict[str, float]:
    """Calculate statistics for a list of values."""
    if not values:
        return {}
    
    return {
        'count': len(values),
        'min': min(values),
        'max': max(values),
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'stdev': statistics.stdev(values) if len(values) > 1 else 0.0
    }


def format_duration(nanoseconds: float) -> str:
    """Format nanoseconds to human-readable duration."""
    ns = int(nanoseconds)
    seconds = ns // 1_000_000_000
    milliseconds = (ns % 1_000_000_000) // 1_000_000
    microseconds = (ns % 1_000_000) // 1_000
    remaining_ns = ns % 1_000
    
    parts = []
    if seconds > 0:
        parts.append(f"{seconds}s")
    if milliseconds > 0:
        parts.append(f"{milliseconds}ms")
    if microseconds > 0:
        parts.append(f"{microseconds}µs")
    if remaining_ns > 0 or not parts:
        parts.append(f"{remaining_ns}ns")
    
    return ", ".join(parts)


def calculate_t_test(with_values: List[float], without_values: List[float]) -> Dict[str, Any]:
    """
    Perform independent samples t-test to compare means between two groups.
    
    Args:
        with_values: List of values for "with Lightrun" group
        without_values: List of values for "without Lightrun" group
        
    Returns:
        Dictionary with t-statistic, p-value, degrees of freedom, and interpretation
    """
    if len(with_values) < 2 or len(without_values) < 2:
        return {
            't_statistic': float('nan'),
            'p_value': float('nan'),
            'degrees_of_freedom': float('nan'),
            'significant': False,
            'interpretation': 'Insufficient data for t-test'
        }
    
    # Perform independent samples t-test
    # Use scipy.stats.ttest_ind which handles unequal variances with Welch's t-test
    try:
        t_statistic, p_value = stats.ttest_ind(with_values, without_values, equal_var=False)
        # Degrees of freedom for Welch's t-test (approximate)
        n1, n2 = len(with_values), len(without_values)
        var1 = statistics.variance(with_values)
        var2 = statistics.variance(without_values)
        df = ((var1/n1 + var2/n2)**2) / ((var1/n1)**2/(n1-1) + (var2/n2)**2/(n2-1))
    except (ValueError, ZeroDivisionError):
        return {
            't_statistic': float('nan'),
            'p_value': float('nan'),
            'degrees_of_freedom': float('nan'),
            'significant': False,
            'interpretation': 'Error calculating t-test'
        }
    
    # Significance at alpha = 0.05
    significant = not np.isnan(p_value) and p_value < 0.05
    
    interpretation = (
        f"Means are {'significantly different' if significant else 'not significantly different'} "
        f"(p={p_value:.4f}, α=0.05)"
    )
    
    return {
        't_statistic': float(t_statistic),
        'p_value': float(p_value),
        'degrees_of_freedom': float(df),
        'significant': significant,
        'interpretation': interpretation
    }


def calculate_effect_size(with_values: List[float], without_values: List[float]) -> Dict[str, Any]:
    """
    Calculate Cohen's d effect size to measure the magnitude of difference between two groups.
    
    Cohen's d = (mean1 - mean2) / pooled_standard_deviation
    
    Interpretation:
    - |d| < 0.2: negligible effect
    - 0.2 <= |d| < 0.5: small effect
    - 0.5 <= |d| < 0.8: medium effect
    - |d| >= 0.8: large effect
    
    Args:
        with_values: List of values for "with Lightrun" group
        without_values: List of values for "without Lightrun" group
        
    Returns:
        Dictionary with Cohen's d value and interpretation
    """
    if len(with_values) < 2 or len(without_values) < 2:
        return {
            'cohens_d': float('nan'),
            'interpretation': 'Insufficient data for effect size calculation'
        }
    
    # Calculate means
    mean_with = statistics.mean(with_values)
    mean_without = statistics.mean(without_values)
    
    # Calculate standard deviations
    std_with = statistics.stdev(with_values)
    std_without = statistics.stdev(without_values)
    
    # Calculate sample sizes
    n_with = len(with_values)
    n_without = len(without_values)
    
    # Calculate pooled standard deviation
    # For unequal sample sizes: sqrt(((n1-1)*s1^2 + (n2-1)*s2^2) / (n1+n2-2))
    pooled_std = np.sqrt(
        ((n_with - 1) * std_with**2 + (n_without - 1) * std_without**2) / 
        (n_with + n_without - 2)
    )
    
    if pooled_std == 0:
        return {
            'cohens_d': float('nan'),
            'interpretation': 'Cannot calculate effect size (pooled std = 0)'
        }
    
    # Calculate Cohen's d
    cohens_d = (mean_with - mean_without) / pooled_std
    
    # Interpret effect size
    abs_d = abs(cohens_d)
    if abs_d < 0.2:
        magnitude = 'negligible'
    elif abs_d < 0.5:
        magnitude = 'small'
    elif abs_d < 0.8:
        magnitude = 'medium'
    else:
        magnitude = 'large'
    
    direction = 'positive' if cohens_d > 0 else 'negative'
    interpretation = f"{magnitude.capitalize()} effect ({direction}, |d|={abs_d:.3f})"
    
    return {
        'cohens_d': float(cohens_d),
        'magnitude': magnitude,
        'interpretation': interpretation
    }


def calculate_f_test(with_values: List[float], without_values: List[float]) -> Dict[str, float]:
    """
    Perform F-test to compare variances between two groups.
    
    Args:
        with_values: List of values for "with Lightrun" group
        without_values: List of values for "without Lightrun" group
        
    Returns:
        Dictionary with F-statistic, p-value, and interpretation
    """
    if len(with_values) < 2 or len(without_values) < 2:
        return {
            'f_statistic': float('nan'),
            'p_value': float('nan'),
            'significant': False,
            'interpretation': 'Insufficient data for F-test'
        }
    
    # Calculate variances
    with_var = statistics.variance(with_values)
    without_var = statistics.variance(without_values)
    
    # F-statistic: larger variance / smaller variance
    if with_var >= without_var:
        f_statistic = with_var / without_var if without_var > 0 else float('inf')
        df1 = len(with_values) - 1
        df2 = len(without_values) - 1
    else:
        f_statistic = without_var / with_var if with_var > 0 else float('inf')
        df1 = len(without_values) - 1
        df2 = len(with_values) - 1
    
    # Calculate p-value using F-distribution
    # Two-tailed test: test if variances are significantly different
    try:
        # F-statistic is already >= 1 (larger variance / smaller variance)
        # For two-tailed test, we calculate probability of F being this extreme or more
        p_value_one_tailed = 1 - stats.f.cdf(f_statistic, df1, df2)
        # Two-tailed: multiply by 2
        p_value = 2 * p_value_one_tailed
        # Ensure p-value is between 0 and 1
        p_value = min(p_value, 1.0)
    except (ValueError, OverflowError):
        p_value = float('nan')
    
    # Significance at alpha = 0.05
    significant = not np.isnan(p_value) and p_value < 0.05
    
    interpretation = (
        f"Variances are {'significantly different' if significant else 'not significantly different'} "
        f"(p={p_value:.4f}, α=0.05)"
    )
    
    return {
        'f_statistic': f_statistic,
        'p_value': p_value,
        'significant': significant,
        'interpretation': interpretation,
        'with_variance': with_var,
        'without_variance': without_var
    }


class ReportGenerator:
    """Generates comparative reports and visualizations for cold start tests."""
    
    def __init__(self, with_lightrun_results: Dict[str, Any], without_lightrun_results: Dict[str, Any]):
        """
        Initialize report generator.
        
        Args:
            with_lightrun_results: Test results from helloLightrun
            without_lightrun_results: Test results from helloNoLightrun
        """
        self.with_lightrun = with_lightrun_results
        self.without_lightrun = without_lightrun_results
        self.output_dir = Path('.')
    
    def set_output_dir(self, output_dir: Path):
        """Set the output directory for reports and visualizations."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _extract_metrics(self, results: Dict[str, Any]) -> Dict[str, List[float]]:
        """Extract metrics from test results."""
        test_results = results.get('test_results', [])
        successful_results = [r for r in test_results if not r.get('error', False)]
        deployments = results.get('deployments', [])
        
        if not successful_results:
            return {}
        
        metrics = {
            'isColdStart': [1 if r.get('isColdStart') else 0 for r in successful_results],
            'totalDuration': [float(r.get('totalDuration', 0)) for r in successful_results],
            'totalImportsDuration': [float(r.get('totalImportsDuration', 0)) for r in successful_results],
            'gcfImportDuration': [float(r.get('gcfImportDuration', 0)) for r in successful_results],
            'envCheckDuration': [float(r.get('envCheckDuration', 0)) for r in successful_results],
            'totalSetupDuration': [float(r.get('totalSetupDuration', 0)) for r in successful_results],
            'functionInvocationOverhead': [float(r.get('functionInvocationOverhead', 0)) for r in successful_results],
            'requestLatency': [r.get('_request_latency', 0) for r in successful_results]
        }
        
        # Extract time_to_cold from deployments (in seconds, convert to nanoseconds for consistency)
        time_to_cold_values = []
        for deployment in deployments:
            if deployment.get('is_deployed') and deployment.get('time_to_cold_seconds') is not None:
                # Convert seconds to nanoseconds for consistency with other duration metrics
                time_to_cold_values.append(deployment['time_to_cold_seconds'] * 1_000_000_000)
        if time_to_cold_values:
            metrics['timeToCold'] = time_to_cold_values
        
        # Extract deployment_duration from deployments (only successful deployments)
        # This measures only the time the successful attempt took, excluding retry wait times
        deployment_duration_values = []
        for deployment in deployments:
            if deployment.get('is_deployed') and deployment.get('deployment_duration_nanoseconds') is not None:
                deployment_duration_values.append(float(deployment['deployment_duration_nanoseconds']))
        if deployment_duration_values:
            metrics['deploymentDuration'] = deployment_duration_values
        
        # Add Lightrun-specific metrics if present
        if any('lightrunImportDuration' in r for r in successful_results):
            metrics['lightrunImportDuration'] = [float(r.get('lightrunImportDuration', 0)) for r in successful_results]
            metrics['lightrunInitDuration'] = [float(r.get('lightrunInitDuration', 0)) for r in successful_results]
        
        # Add new cold/warm request duration metrics
        cold_start_durations = [float(r.get('totalDurationForColdStarts', 0)) for r in successful_results]
        warm_request_durations = [float(r.get('totalDurationForWarmRequests', 0)) for r in successful_results]
        
        if any(v > 0 for v in cold_start_durations):
            metrics['totalDurationForColdStarts'] = cold_start_durations
        if any(v > 0 for v in warm_request_durations):
            metrics['totalDurationForWarmRequests'] = warm_request_durations
        
        return metrics
    
    def generate_comparative_report(self) -> str:
        """Generate a comparative text report."""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("Cloud Function Cold Start Performance - Comparative Analysis")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        # Extract metrics
        with_metrics = self._extract_metrics(self.with_lightrun)
        without_metrics = self._extract_metrics(self.without_lightrun)
        
        # Summary statistics
        with_deployments = self.with_lightrun.get('deployments', [])
        without_deployments = self.without_lightrun.get('deployments', [])
        with_successful = sum(1 for d in with_deployments if d.get('is_deployed'))
        without_successful = sum(1 for d in without_deployments if d.get('is_deployed'))
        
        report_lines.append("TEST SUMMARY")
        report_lines.append("-" * 80)
        report_lines.append(f"With Lightrun:")
        report_lines.append(f"  Functions Deployed: {with_successful}/{len(with_deployments)}")
        report_lines.append(f"  Successful Requests: {len([r for r in self.with_lightrun.get('test_results', []) if not r.get('error', False)])}")
        report_lines.append(f"")
        report_lines.append(f"Without Lightrun:")
        report_lines.append(f"  Functions Deployed: {without_successful}/{len(without_deployments)}")
        report_lines.append(f"  Successful Requests: {len([r for r in self.without_lightrun.get('test_results', []) if not r.get('error', False)])}")
        report_lines.append("")
        
        # Common metrics to compare
        common_metrics = [
            'deploymentDuration',
            'timeToCold',
            'totalDuration',
            'totalDurationForColdStarts',
            'totalDurationForWarmRequests',
            'totalImportsDuration',
            'gcfImportDuration',
            'envCheckDuration',
            'totalSetupDuration',
            'functionInvocationOverhead',
            'requestLatency'
        ]
        
        report_lines.append("METRICS COMPARISON")
        report_lines.append("-" * 80)
        
        for metric_name in common_metrics:
            if metric_name not in with_metrics or metric_name not in without_metrics:
                continue
            
            with_values = with_metrics[metric_name]
            without_values = without_metrics[metric_name]
            
            # Filter out None values for timeToCold and deploymentDuration
            if metric_name in ['timeToCold', 'deploymentDuration']:
                with_values = [v for v in with_values if v is not None]
                without_values = [v for v in without_values if v is not None]
            
            if not with_values or not without_values or all(v == 0 for v in with_values + without_values):
                continue
            
            with_stats = calculate_stats(with_values)
            without_stats = calculate_stats(without_values)
            
            overhead = with_stats['mean'] - without_stats['mean']
            overhead_pct = (overhead / without_stats['mean'] * 100) if without_stats['mean'] > 0 else 0
            
            report_lines.append(f"\n{metric_name}:")
            report_lines.append(f"  With Lightrun:")
            report_lines.append(f"    Mean:   {format_duration(with_stats['mean'])}")
            report_lines.append(f"    Median: {format_duration(with_stats['median'])}")
            report_lines.append(f"    StdDev: {format_duration(with_stats['stdev'])}")
            report_lines.append(f"    Min:    {format_duration(with_stats['min'])}")
            report_lines.append(f"    Max:    {format_duration(with_stats['max'])}")
            report_lines.append(f"  Without Lightrun:")
            report_lines.append(f"    Mean:   {format_duration(without_stats['mean'])}")
            report_lines.append(f"    Median: {format_duration(without_stats['median'])}")
            report_lines.append(f"    StdDev: {format_duration(without_stats['stdev'])}")
            report_lines.append(f"    Min:    {format_duration(without_stats['min'])}")
            report_lines.append(f"    Max:    {format_duration(without_stats['max'])}")
            report_lines.append(f"  Overhead: {format_duration(overhead)} ({overhead_pct:+.1f}%)")
            
            # T-test for mean comparison
            t_test_result = calculate_t_test(with_values, without_values)
            if not np.isnan(t_test_result['t_statistic']):
                report_lines.append(f"  T-Test (mean comparison):")
                report_lines.append(f"    T-statistic: {t_test_result['t_statistic']:.4f}")
                report_lines.append(f"    P-value: {t_test_result['p_value']:.4f}")
                report_lines.append(f"    Degrees of freedom: {t_test_result['degrees_of_freedom']:.2f}")
                report_lines.append(f"    {t_test_result['interpretation']}")
            
            # Effect size (Cohen's d)
            effect_size_result = calculate_effect_size(with_values, without_values)
            if not np.isnan(effect_size_result['cohens_d']):
                report_lines.append(f"  Effect Size (Cohen's d):")
                report_lines.append(f"    Cohen's d: {effect_size_result['cohens_d']:.4f}")
                report_lines.append(f"    {effect_size_result['interpretation']}")
            
            # F-test for variance comparison
            f_test_result = calculate_f_test(with_values, without_values)
            if not np.isnan(f_test_result['f_statistic']):
                report_lines.append(f"  F-Test (variance comparison):")
                report_lines.append(f"    F-statistic: {f_test_result['f_statistic']:.4f}")
                report_lines.append(f"    P-value: {f_test_result['p_value']:.4f}")
                report_lines.append(f"    P-value: {f_test_result['p_value']:.4f}")
                report_lines.append(f"    {f_test_result['interpretation']}")

        # Lightrun Registration Overhead (Special Metric)
        if 'functionInvocationOverhead' in with_metrics and 'functionInvocationOverhead' in without_metrics:
            with_vals = with_metrics['functionInvocationOverhead']
            without_vals = without_metrics['functionInvocationOverhead']
            
            if with_vals and without_vals:
                with_stats = calculate_stats(with_vals)
                without_stats = calculate_stats(without_vals)
                
                registration_overhead_mean = with_stats['mean'] - without_stats['mean']
                # Standard deviation of the difference (assuming independence): sqrt(s1^2 + s2^2)
                registration_overhead_stdev = np.sqrt(with_stats['stdev']**2 + without_stats['stdev']**2)
                
                report_lines.append("\n" + "-" * 80)
                report_lines.append("LIGHTRUN REGISTRATION OVERHEAD")
                report_lines.append("(Calculated as: functionInvocationOverhead[With] - functionInvocationOverhead[Without])")
                report_lines.append("-" * 80)
                report_lines.append(f"  Mean:   {format_duration(registration_overhead_mean)}")
                report_lines.append(f"  StdDev: {format_duration(registration_overhead_stdev)}")

        if 'lightrunImportDuration' in with_metrics:
            report_lines.append("\n" + "-" * 80)
            report_lines.append("LIGHTRUN-SPECIFIC METRICS")
            report_lines.append("-" * 80)
            
            for metric_name in ['lightrunImportDuration', 'lightrunInitDuration']:
                if metric_name not in with_metrics:
                    continue
                
                values = with_metrics[metric_name]
                if not values or all(v == 0 for v in values):
                    continue
                
                stats = calculate_stats(values)
                report_lines.append(f"\n{metric_name}:")
                report_lines.append(f"  Mean:   {format_duration(stats['mean'])}")
                report_lines.append(f"  Median: {format_duration(stats['median'])}")
                report_lines.append(f"  StdDev: {format_duration(stats['stdev'])}")
                report_lines.append(f"  Min:    {format_duration(stats['min'])}")
                report_lines.append(f"  Max:    {format_duration(stats['max'])}")
        
        # Cold start analysis
        report_lines.append("\n" + "-" * 80)
        report_lines.append("COLD START ANALYSIS")
        report_lines.append("-" * 80)
        
        with_cold = sum(with_metrics.get('isColdStart', []))
        with_total = len([r for r in self.with_lightrun.get('test_results', []) if not r.get('error', False)])
        without_cold = sum(without_metrics.get('isColdStart', []))
        without_total = len([r for r in self.without_lightrun.get('test_results', []) if not r.get('error', False)])
        
        report_lines.append(f"With Lightrun:")
        report_lines.append(f"  Cold Starts: {with_cold}/{with_total} ({with_cold/with_total*100:.1f}%)" if with_total > 0 else "  Cold Starts: N/A")
        report_lines.append(f"Without Lightrun:")
        report_lines.append(f"  Cold Starts: {without_cold}/{without_total} ({without_cold/without_total*100:.1f}%)" if without_total > 0 else "  Cold Starts: N/A")
        
        report_lines.append("\n" + "=" * 80)
        
        return "\n".join(report_lines)
    
    def generate_visualizations(self):
        """Generate visualization graphs for all metrics."""
        with_metrics = self._extract_metrics(self.with_lightrun)
        without_metrics = self._extract_metrics(self.without_lightrun)
        
        # Common metrics to visualize
        metrics_to_plot = [
            'totalDuration',
            'totalDurationForColdStarts',
            'totalDurationForWarmRequests',
            'totalImportsDuration',
            'gcfImportDuration',
            'envCheckDuration',
            'totalSetupDuration',
            'functionInvocationOverhead',
            'requestLatency',
            'timeToCold'
        ]
        
        for metric_name in metrics_to_plot:
            if metric_name not in with_metrics or metric_name not in without_metrics:
                continue
            
            with_values = with_metrics[metric_name]
            without_values = without_metrics[metric_name]
            
            # Filter out None values for timeToCold and deploymentDuration
            if metric_name in ['timeToCold', 'deploymentDuration']:
                with_values = [v for v in with_values if v is not None]
                without_values = [v for v in without_values if v is not None]
            
            if not with_values or not without_values or all(v == 0 for v in with_values + without_values):
                continue
            
            self._plot_comparison(metric_name, with_values, without_values)
        
        # Lightrun-specific metrics
        if 'lightrunImportDuration' in with_metrics:
            for metric_name in ['lightrunImportDuration', 'lightrunInitDuration']:
                if metric_name not in with_metrics:
                    continue
                
                values = with_metrics[metric_name]
                if not values or all(v == 0 for v in values):
                    continue
                
                self._plot_single_distribution(metric_name, values)
    
    def _plot_comparison(self, metric_name: str, with_values: List[float], without_values: List[float]):
        """Create a comparison plot for a metric."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'{metric_name} - With vs Without Lightrun', fontsize=14, fontweight='bold')
        
        # Convert to seconds for readability
        with_seconds = [v / 1_000_000_000 for v in with_values]
        without_seconds = [v / 1_000_000_000 for v in without_values]
        
        # Histogram comparison
        ax1 = axes[0, 0]
        ax1.hist(with_seconds, bins=30, alpha=0.6, label='With Lightrun', color='blue', edgecolor='black')
        ax1.hist(without_seconds, bins=30, alpha=0.6, label='Without Lightrun', color='orange', edgecolor='black')
        ax1.set_xlabel('Duration (seconds)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Distribution Comparison')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Box plot comparison
        ax2 = axes[0, 1]
        bp = ax2.boxplot([with_seconds, without_seconds], labels=['With Lightrun', 'Without Lightrun'], patch_artist=True)
        bp['boxes'][0].set_facecolor('lightblue')
        bp['boxes'][1].set_facecolor('lightcoral')
        ax2.set_ylabel('Duration (seconds)')
        ax2.set_title('Box Plot Comparison')
        ax2.grid(True, alpha=0.3)
        
        # Statistics comparison bar chart
        ax3 = axes[1, 0]
        with_stats = calculate_stats(with_values)
        without_stats = calculate_stats(without_values)
        
        categories = ['Mean', 'Median', 'StdDev', 'Min', 'Max']
        with_stats_list = [
            with_stats['mean'] / 1_000_000_000,
            with_stats['median'] / 1_000_000_000,
            with_stats['stdev'] / 1_000_000_000,
            with_stats['min'] / 1_000_000_000,
            with_stats['max'] / 1_000_000_000
        ]
        without_stats_list = [
            without_stats['mean'] / 1_000_000_000,
            without_stats['median'] / 1_000_000_000,
            without_stats['stdev'] / 1_000_000_000,
            without_stats['min'] / 1_000_000_000,
            without_stats['max'] / 1_000_000_000
        ]
        
        x = np.arange(len(categories))
        width = 0.35
        ax3.bar(x - width/2, with_stats_list, width, label='With Lightrun', color='blue', alpha=0.7)
        ax3.bar(x + width/2, without_stats_list, width, label='Without Lightrun', color='orange', alpha=0.7)
        ax3.set_xlabel('Statistic')
        ax3.set_ylabel('Duration (seconds)')
        ax3.set_title('Statistics Comparison')
        ax3.set_xticks(x)
        ax3.set_xticklabels(categories)
        ax3.legend()
        ax3.grid(True, alpha=0.3, axis='y')
        
        # Statistical analysis summary visualization
        ax4 = axes[1, 1]
        overhead = (with_stats['mean'] - without_stats['mean']) / 1_000_000_000
        overhead_pct = (overhead / (without_stats['mean'] / 1_000_000_000) * 100) if without_stats['mean'] > 0 else 0
        
        # Calculate all statistical tests
        t_test_result = calculate_t_test(with_values, without_values)
        effect_size_result = calculate_effect_size(with_values, without_values)
        f_test_result = calculate_f_test(with_values, without_values)
        
        # Create text summary
        ax4.axis('off')
        summary_text = f"""Statistical Analysis Summary

Mean Overhead: {overhead:.3f}s ({overhead_pct:+.1f}%)

T-Test (Mean Comparison):
  T-statistic: {t_test_result['t_statistic']:.4f}
  P-value: {t_test_result['p_value']:.4f}
  {t_test_result['interpretation']}

Effect Size (Cohen's d):
  d = {effect_size_result['cohens_d']:.4f}
  {effect_size_result['interpretation']}

F-Test (Variance Comparison):
  F-statistic: {f_test_result['f_statistic']:.4f}
  P-value: {f_test_result['p_value']:.4f}
  {f_test_result['interpretation']}
"""
        ax4.text(0.1, 0.5, summary_text, fontsize=9, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        ax4.set_title('Statistical Analysis Summary', fontweight='bold')
        
        plt.tight_layout()
        
        # Save figure
        safe_name = metric_name.replace(' ', '_').lower()
        output_path = self.output_dir / f'{safe_name}_comparison.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"  Generated visualization: {output_path}")
    
    def _plot_single_distribution(self, metric_name: str, values: List[float]):
        """Create a distribution plot for a single metric."""
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle(f'{metric_name} - Distribution', fontsize=14, fontweight='bold')
        
        # Convert to seconds
        seconds = [v / 1_000_000_000 for v in values]
        
        # Histogram
        ax1 = axes[0]
        ax1.hist(seconds, bins=30, color='blue', alpha=0.7, edgecolor='black')
        ax1.set_xlabel('Duration (seconds)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Distribution')
        ax1.grid(True, alpha=0.3)
        
        # Box plot
        ax2 = axes[1]
        bp = ax2.boxplot([seconds], labels=[metric_name], patch_artist=True)
        bp['boxes'][0].set_facecolor('lightblue')
        ax2.set_ylabel('Duration (seconds)')
        ax2.set_title('Box Plot')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # Save figure
        safe_name = metric_name.replace(' ', '_').lower()
        output_path = self.output_dir / f'{safe_name}_distribution.png'
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"  Generated visualization: {output_path}")
    
    def generate_all(self, report_file: str = 'comparative_report.txt'):
        """Generate both report and visualizations."""
        print("\n" + "=" * 80)
        print("Generating Comparative Report and Visualizations...")
        print("=" * 80)
        
        # Generate text report
        report = self.generate_comparative_report()
        report_path = self.output_dir / report_file
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"\nReport saved to: {report_path}")
        print(report)
        
        # Generate visualizations
        print("\nGenerating visualizations...")
        self.generate_visualizations()
        
        print(f"\nAll outputs saved to: {self.output_dir.absolute()}")
