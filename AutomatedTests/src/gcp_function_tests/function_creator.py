"""Creates test function code for deployment."""
import json
from pathlib import Path
from .config import TEST_FUNCTIONS_DIR


class FunctionCreator:
    """Creates test function directories and code."""
    
    def __init__(self, base_dir: Path = TEST_FUNCTIONS_DIR):
        self.base_dir = base_dir
    
    def create_test_function(self, nodejs_version: int, gen_version: int) -> Path:
        """Create a test function directory for the given Node.js and Gen version."""
        func_dir = self.base_dir / f"test-node{nodejs_version}-gen{gen_version}"
        func_dir.mkdir(parents=True, exist_ok=True)
        
        # Create index.js
        index_js = func_dir / "index.js"
        index_js.write_text(self._get_function_code())
        
        # Create package.json
        package_json = func_dir / "package.json"
        package_json.write_text(json.dumps(self._get_package_json(nodejs_version, gen_version), indent=2))
        
        return func_dir
    
    def _get_function_code(self) -> str:
        """Get the test function code."""
        return """const functions = require('@google-cloud/functions-framework');
const lightrun = require('lightrun/gcp');

let requestCount = 0;

const lightrunSecret = process.env.LIGHTRUN_SECRET;
if (!lightrunSecret || lightrunSecret.trim() === '') {
    throw new Error('LIGHTRUN_SECRET environment variable is required');
}

const displayName = process.env.DISPLAY_NAME;
if (!displayName || displayName.trim() === '') {
    throw new Error('DISPLAY_NAME environment variable is required');
}

lightrun.init({
    lightrunSecret: lightrunSecret,
    agentLog: { agentLogTargetDir: '', agentLogLevel: 'warn' },
    internal: { gcpDebug: false },
    metadata: { 
        registration: { 
            displayName: displayName,
            tags: [displayName]
        } 
    }
});

functions.http('testFunction', lightrun.wrap(async (req, res) => {
    requestCount++;
    const startTime = Date.now();
    
    // Simulate some work
    await new Promise(resolve => setTimeout(resolve, 10));
    
    const duration = Date.now() - startTime;
    
    res.json({
        requestCount,
        duration,
        timestamp: new Date().toISOString(),
        nodejsVersion: process.version,
        message: 'Hello from Lightrun!'
    });
}));
"""
    
    def _get_package_json(self, nodejs_version: int, gen_version: int) -> dict:
        """Get package.json content."""
        return {
            "name": f"test-function-node{nodejs_version}-gen{gen_version}",
            "version": "1.0.0",
            "main": "index.js",
            "engines": {
                "node": f">={nodejs_version}"
            },
            "dependencies": {
                "@google-cloud/functions-framework": "^3.3.0",
                "lightrun": ">=1.76.0"
            }
        }
