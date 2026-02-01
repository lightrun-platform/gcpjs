"""Code generator for Request Overhead Benchmark."""

import json
from pathlib import Path
from typing import Dict, Any


def _generate_package_json(is_lightrun: bool) -> str:
    """
    Generate package.json content.

    Args:
        is_lightrun: Whether to include lightrun dependency

    Returns:
        JSON string content for package.json
    """
    deps = {
        "@google-cloud/functions-framework": "^3.3.0"
    }

    if is_lightrun:
        deps["lightrun"] = "1.76.0"
        name = "hello-lightrun"
        main = "helloLightrun.js"
    else:
        name = "hello-no-lightrun"
        main = "helloNoLightrun.js"

    package_data = {
        "name": name,
        "version": "1.0.0",
        "main": main,
        "engines": {
            "node": ">=20"
        },
        "dependencies": deps
    }

    return json.dumps(package_data, indent=2)


class CodeGenerator:
    """Generates function code and package.json for benchmark variants."""

    def __init__(self, test_file_length: int):
        """
        Initialize code generator.
        
        Args:
            test_file_length: Number of dummy function calls to generate
        """
        self.test_file_length = test_file_length

    def _generate_dummy_functions(self) -> str:
        """Generate N dummy functions."""
        functions = []
        for i in range(1, self.test_file_length + 1):
            functions.append(f"""
function function{i}() {{
    // Synthetic load
    let res = 0;
    for(let i=0; i<1000; i++) {{
        res += i;
    }}
    return res;
}}
""")
        return "\n".join(functions)

    def _generate_function_calls(self) -> str:
        """Generate sequential calls to dummy functions."""
        calls = []
        for i in range(1, self.test_file_length + 1):
            calls.append(f"    function{i}();")
        return "\n".join(calls)

    def generate_code(self, output_dir: Path, is_lightrun: bool):
        """
        Generate all necessary files for a variant.
        
        Args:
            output_dir: Directory to generate files in
            is_lightrun: Whether this is the Lightrun variant
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine filenames
        if is_lightrun:
            filename = "helloLightrun.js"
        else:
            filename = "helloNoLightrun.js"
            
        # Generate package.json
        package_json_content = _generate_package_json(is_lightrun)
        with open(output_dir / "package.json", "w") as f:
            f.write(package_json_content)
            
        # Generate function code
        dummy_functions = self._generate_dummy_functions()
        function_calls = self._generate_function_calls()
        
        if is_lightrun:
            js_content = f"""
const functions = require('@google-cloud/functions-framework');
const lightrun = require('lightrun/gcp');

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

functions.http('functionTest', lightrun.wrap(func));
"""
        else:
            js_content = f"""
const functions = require('@google-cloud/functions-framework');

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

functions.http('functionTest', func);
"""

        with open(output_dir / filename, "w") as f:
            f.write(js_content)
            
        print(f"Generated code in {output_dir} (Lightrun={is_lightrun}, n={self.test_file_length})")
