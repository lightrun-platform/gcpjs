"""Tests for ResultHandler class."""
import pytest
import sys
import json
from pathlib import Path
from datetime import datetime

# Import from package
from gcp_function_tests.result_handler import ResultHandler
from gcp_function_tests.models import TestResult, DeploymentResult


class TestResultHandler:
    """Tests for ResultHandler class."""
    
    def test_save_result(self, tmp_path):
        """Test saving result to file."""
        handler = ResultHandler(results_dir=tmp_path)
        result = TestResult(
            function_name="test-node20-gen2",
            gen_version=2,
            nodejs_version=20,
            deployment_result=DeploymentResult(success=True),
            cold_start_avg_ms=123.45,
            warm_start_avg_ms=45.67
        )
        
        result_file = handler.save_result(result)
        
        assert result_file.exists()
        assert result_file.name == "test-node20-gen2.json"
        
        # Verify content
        with open(result_file) as f:
            data = json.load(f)
            assert data["function_name"] == "test-node20-gen2"
            assert data["gen_version"] == 2
            assert data["nodejs_version"] == 20
            assert data["deployment_success"] is True
            assert data["cold_start_avg_ms"] == 123.45
            assert data["warm_start_avg_ms"] == 45.67
            assert "timestamp" in data
    
    def test_print_summary(self, capsys):
        """Test summary printing."""
        handler = ResultHandler()
        results = [
            TestResult(
                function_name="test-node20-gen2",
                gen_version=2,
                nodejs_version=20,
                deployment_result=DeploymentResult(success=True),
                cold_start_avg_ms=100.0,
                warm_start_avg_ms=50.0,
                snapshot_test=True,
                counter_test=True,
                metric_test=True,
                logs_error_check=True
            ),
            TestResult(
                function_name="test-node18-gen1",
                gen_version=1,
                nodejs_version=18,
                deployment_result=DeploymentResult(success=False)
            )
        ]
        
        handler.print_summary(results)
        
        captured = capsys.readouterr()
        assert "Total functions tested: 2" in captured.out
        assert "Successfully deployed: 1" in captured.out
        assert "Failed to deploy: 1" in captured.out
        assert "Cold start average" in captured.out
        assert "Warm start average" in captured.out
        assert "Snapshots: 1/1 passed" in captured.out
    
    def test_result_to_dict(self):
        """Test result to dictionary conversion."""
        result = TestResult(
            function_name="test-node20-gen2",
            gen_version=2,
            nodejs_version=20,
            deployment_result=DeploymentResult(success=True, used_region="europe-west1", url="https://test.com"),
            region_used="europe-west1",
            cold_start_avg_ms=123.45,
            function_url="https://test.com"
        )
        
        result_dict = result.to_dictionary()
        
        assert result_dict["function_name"] == "test-node20-gen2"
        assert result_dict["gen_version"] == 2
        assert result_dict["nodejs_version"] == 20
        assert result_dict["deployment_success"] is True  # Computed property
        assert result_dict["region_used"] == "europe-west1"
        assert result_dict["cold_start_avg_ms"] == 123.45
        assert result_dict["function_url"] == "https://test.com"
        assert "deployment_result" in result_dict