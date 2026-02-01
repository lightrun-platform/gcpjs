"""Code generator for Request Overhead Benchmark."""

import json
from pathlib import Path

from Lightrun.Benchmarks.shared_modules.gcf_models.generated_source_attributes import GeneratedSourceAttributes
from Lightrun.Benchmarks.shared_modules.source_code_generator import SourceCodeGenerator


def _generate_package_json(lightrun_version: str, node_version: str, gcp_functions_version: str) -> str:
    """
    Generate package.json content.

    Args:
        lightrun_version: Lightrun package version
        gcp_functions_version: Google Cloud Functions Framework version

    Returns:
        JSON string content for package.json
    """
    deps = {
        "@google-cloud/functions-framework": gcp_functions_version,
        "lightrun": lightrun_version
    }

    name = "hello-lightrun"
    main = "helloLightrun.js"

    package_data = {
        "name": name,
        "version": "1.0.0",
        "main": main,
        "engines": {
            "node": node_version
        },
        "dependencies": deps
    }

    return json.dumps(package_data, indent=2)


class OverheadBenchmarkSourceCodeGenerator(SourceCodeGenerator):
    """Generates function code and package.json for benchmark variants."""

    def __init__(self, test_size: int, lightrun_version: str, node_version: str, gcp_functions_version: str):
        """
        Initialize code generator.
        
        Args:
            test_size: Number of dummy function calls to generate
            lightrun_version: Lightrun package version
            node_version: Node.js engine version
            gcp_functions_version: Google Cloud Functions Framework version
        """
        self.test_size = test_size
        self.lightrun_version = lightrun_version
        self.node_version = node_version
        self.gcp_functions_version = gcp_functions_version

    def _generate_dummy_functions(self) -> str:
        """Generate N dummy functions."""
        functions = [f"""
        let functionResult = 0;
        
        function calc(secret, salt) {{
            // Synthetic load using crypto to avoid V8 optimization
            return crypto.pbkdf2Sync(secret, salt, 1000, 64, 'sha512');
        }}
        """]

        for i in range(1, self.test_size + 1):
            functions.append(f"""
function function{i}() {{
    // Synthetic load using crypto to avoid V8 optimization
    const start = process.hrtime.bigint();
    functionResult = calc(functionResult, 'function{i}');
    return process.hrtime.bigint() - start;
}}
""")
        return "\n".join(functions)

    def _generate_function_calls(self) -> str:
        """Generate sequential calls to dummy functions."""
        calls = []
        for i in range(1, self.test_size + 1):
            calls.append(f"    function{i}();")
        return "\n".join(calls)

    def create_source_dir(self, output_dir: Path) -> GeneratedSourceAttributes:
        """
        Generate all necessary files for a variant.
        
        Args:
            output_dir: Directory to generate files in

        Returns:
            Path to the generated source directory
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine filenames
        filename = "benchmarkLightrun.js"
        entry_point = "benchmarkLightrunOverhead"
            
        # Generate package.json
        package_json_content = _generate_package_json(
            self.lightrun_version,
            self.node_version,
            self.gcp_functions_version
        )
        with open(output_dir / "package.json", "w") as f:
            f.write(package_json_content)
            
        # Generate function code
        dummy_functions = self._generate_dummy_functions()
        function_calls = self._generate_function_calls()
        
        js_content = f"""
const functions = require('@google-cloud/functions-framework');
const lightrun = require('lightrun/gcp');
const crypto = require('crypto');

const lightrunSecret = process.env.LIGHTRUN_SECRET;
if (!lightrunSecret || lightrunSecret.trim() === '') {{
  throw new Error('LIGHTRUN_SECRET environment variable is required');
}}

const displayName = process.env.DISPLAY_NAME;
if (!displayName || displayName.trim() === '') {{
  throw new Error('DISPLAY_NAME environment variable is required and cannot be empty');
}}

lightrun.init({{
  lightrunSecret: lightrunSecret,
  metadata: {{
    registration: {{
      displayName: displayName
    }}
  }}
}});

{dummy_functions}

let func = async (req, res) => {{
    const handlerStartTime = process.hrtime.bigint();
{function_calls}
    const handlerEndTime = process.hrtime.bigint();
    res.send({{ 
        handlerRunTime: (handlerEndTime - handlerStartTime).toString(),
        message: 'Function execution complete'
    }});
}};

functions.http('{entry_point}', lightrun.wrap(func));
"""

        with open(output_dir / filename, "w") as f:
            f.write(js_content)
            
        print(f"Generated code in {output_dir} (n={self.test_size})")
        return GeneratedSourceAttributes(path=output_dir, entry_point=entry_point)
