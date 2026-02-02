"""Unit tests for CodeGenerator."""

import unittest
import json
from pathlib import Path
import tempfile
import sys

# Add parent directory to path so we can import as a package
parent_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(parent_dir.parent.parent))

from Lightrun.Benchmarks.lightrun_nodejs_request_overhead_benchmark_v2.src.overhead_benchmark_source_code_generator import OverheadBenchmarkSourceCodeGenerator

class TestOverheadBenchmarkSourceCodeGenerator(unittest.TestCase):
    """Test OverheadBenchmarkSourceCodeGenerator class."""

    def test_generate_code_lightrun(self):
        """Test generating code."""
        generator = OverheadBenchmarkSourceCodeGenerator(
            test_size=5,
            lightrun_version="1.76.0",
            node_version=">=20",
            gcp_functions_version="^3.3.0"
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            generator.create_source_dir(tmp_path)
            
            # Check package.json
            pkg_json = tmp_path / "package.json"
            self.assertTrue(pkg_json.exists())
            with open(pkg_json) as f:
                data = json.load(f)
                self.assertEqual(data["name"], "lightrun-overhead-benchmark")
                self.assertIn("lightrun", data["dependencies"])
                
            # Check JS file
            js_file = tmp_path / "lightrunOverheadBenchmark.js"
            self.assertTrue(js_file.exists())
            content = js_file.read_text()
            self.assertIn("require('lightrun/gcp')", content)
            self.assertIn("require('crypto')", content)
            self.assertIn("crypto.pbkdf2Sync", content)
            self.assertIn("function function1()", content)
            self.assertIn("function function5()", content)
            self.assertNotIn("function function6()", content)
            self.assertIn("lightrun.wrap(func)", content)


    def test_custom_versions(self):
        """Test generating code with custom versions."""
        generator = OverheadBenchmarkSourceCodeGenerator(
            test_size=3,
            lightrun_version="1.0.0",
            node_version="14",
            gcp_functions_version="^3.0.0"
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            generator.create_source_dir(tmp_path)
            
            pkg_json = tmp_path / "package.json"
            with open(pkg_json) as f:
                data = json.load(f)
                self.assertEqual(data["dependencies"]["lightrun"], "1.0.0")
                self.assertEqual(data["engines"]["node"], "14")
                self.assertEqual(data["dependencies"]["@google-cloud/functions-framework"], "^3.0.0")

if __name__ == '__main__':
    unittest.main()
