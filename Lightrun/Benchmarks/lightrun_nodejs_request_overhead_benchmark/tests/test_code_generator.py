"""Unit tests for CodeGenerator."""

import unittest
import json
from pathlib import Path
import tempfile
import sys
import os

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(parent_dir))

from lightrun_nodejs_request_overhead_benchmark.src.code_generator import CodeGenerator

class TestCodeGenerator(unittest.TestCase):
    """Test CodeGenerator class."""

    def test_generate_code_lightrun(self):
        """Test generating code for Lightrun variant."""
        generator = CodeGenerator(test_file_length=5)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            generator.generate_code(tmp_path, is_lightrun=True)
            
            # Check package.json
            pkg_json = tmp_path / "package.json"
            self.assertTrue(pkg_json.exists())
            with open(pkg_json) as f:
                data = json.load(f)
                self.assertEqual(data["name"], "hello-lightrun")
                self.assertIn("lightrun", data["dependencies"])
                
            # Check JS file
            js_file = tmp_path / "helloLightrun.js"
            self.assertTrue(js_file.exists())
            content = js_file.read_text()
            self.assertIn("require('lightrun/gcp')", content)
            self.assertIn("function function1()", content)
            self.assertIn("function function5()", content)
            self.assertNotIn("function function6()", content)
            self.assertIn("lightrun.wrap(func)", content)

    def test_generate_code_no_lightrun(self):
        """Test generating code for No Lightrun variant."""
        generator = CodeGenerator(test_file_length=3)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            generator.generate_code(tmp_path, is_lightrun=False)
            
            # Check package.json
            pkg_json = tmp_path / "package.json"
            self.assertTrue(pkg_json.exists())
            with open(pkg_json) as f:
                data = json.load(f)
                self.assertEqual(data["name"], "hello-no-lightrun")
                self.assertNotIn("lightrun", data["dependencies"])
                
            # Check JS file
            js_file = tmp_path / "helloNoLightrun.js"
            self.assertTrue(js_file.exists())
            content = js_file.read_text()
            self.assertNotIn("require('lightrun/gcp')", content)
            self.assertIn("function function1()", content)
            self.assertIn("function function3()", content)

if __name__ == '__main__':
    unittest.main()
