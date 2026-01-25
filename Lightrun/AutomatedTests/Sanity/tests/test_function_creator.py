"""Tests for FunctionCreator class."""
import pytest
import sys
import json
from pathlib import Path

# Import from package
from gcp_function_tests.function_creator import FunctionCreator


class TestFunctionCreator:
    """Tests for FunctionCreator class."""
    
    def test_create_test_function(self, tmp_path):
        """Test creating a test function."""
        creator = FunctionCreator(base_dir=tmp_path)
        func_dir = creator.create_test_function(20, 2)
        
        assert func_dir.exists()
        assert func_dir.name == "test-node20-gen2"
        
        # Check index.js exists
        index_js = func_dir / "index.js"
        assert index_js.exists()
        content = index_js.read_text()
        assert "lightrun/gcp" in content
        assert "testFunction" in content
        
        # Check package.json exists
        package_json = func_dir / "package.json"
        assert package_json.exists()
        pkg_data = json.loads(package_json.read_text())
        assert pkg_data["engines"]["node"] == ">=20"
        assert "@google-cloud/functions-framework" in pkg_data["dependencies"]
        assert "lightrun" in pkg_data["dependencies"]
    
    def test_get_function_code(self):
        """Test function code generation."""
        creator = FunctionCreator()
        code = creator._get_function_code()
        
        assert "lightrun/gcp" in code
        assert "testFunction" in code
        assert "lightrun.init" in code
        assert "lightrun.wrap" in code
    
    def test_get_package_json(self):
        """Test package.json generation."""
        creator = FunctionCreator()
        pkg = creator._get_package_json(18, 1)
        
        assert pkg["engines"]["node"] == ">=18"
        assert pkg["name"] == "test-function-node18-gen1"
        assert "@google-cloud/functions-framework" in pkg["dependencies"]
        assert "lightrun" in pkg["dependencies"]
