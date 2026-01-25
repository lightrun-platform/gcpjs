"""Creates test function code for latency testing with Lightrun."""
import json
from pathlib import Path
from .config import TEST_FUNCTIONS_DIR


class LatencyFunctionCreator:
    """Creates test function directories and code for latency testing."""
    
    def __init__(self, base_dir: Path = TEST_FUNCTIONS_DIR):
        self.base_dir = base_dir
    
    def create_latency_test_function(self, nodejs_version: int, gen_version: int, use_lightrun: bool) -> Path:
        """Create a test function directory for latency testing.
        
        Args:
            nodejs_version: Node.js version to use
            gen_version: GCP function generation (1 or 2)
            use_lightrun: If True, function uses Lightrun agent; if False, it doesn't
        """
        lightrun_suffix = "with-lightrun" if use_lightrun else "without-lightrun"
        func_dir = self.base_dir / f"latency-node{nodejs_version}-gen{gen_version}-{lightrun_suffix}"
        func_dir.mkdir(parents=True, exist_ok=True)
        
        # Create index.js
        index_js = func_dir / "index.js"
        index_js.write_text(self._get_function_code(use_lightrun))
        
        # Create package.json
        package_json = func_dir / "package.json"
        package_json.write_text(json.dumps(self._get_package_json(nodejs_version, gen_version, use_lightrun), indent=2))
        
        return func_dir
    
    def _get_function_code(self, use_lightrun: bool) -> str:
        """Get the test function code with optional Lightrun support."""
        if use_lightrun:
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

// Initialize Lightrun agent
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
    
    // Get parameters from query string
    const useLightrun = req.query.useLightrun === 'true';
    const takeSnapshot = req.query.takeSnapshot === 'true';
    
    // Simulate some work
    await new Promise(resolve => setTimeout(resolve, 10));
    
    // Snapshot location - line where snapshot will be captured
    // This is where Lightrun snapshots should be placed (around line 60)
    const snapshotLocation = 'SNAPSHOT_LOCATION'; // Line 60 - snapshot target
    
    const duration = Date.now() - startTime;
    
    res.json({
        requestCount,
        duration,
        timestamp: new Date().toISOString(),
        nodejsVersion: process.version,
        useLightrun: useLightrun,
        takeSnapshot: takeSnapshot,
        message: 'Hello from latency test!'
    });
}));
"""
        else:
            return """const functions = require('@google-cloud/functions-framework');

let requestCount = 0;

functions.http('testFunction', async (req, res) => {
    requestCount++;
    const startTime = Date.now();
    
    // Get parameters from query string
    const useLightrun = req.query.useLightrun === 'true';
    const takeSnapshot = req.query.takeSnapshot === 'true';
    
    // Simulate some work
    await new Promise(resolve => setTimeout(resolve, 10));
    
    const duration = Date.now() - startTime;
    
    res.json({
        requestCount,
        duration,
        timestamp: new Date().toISOString(),
        nodejsVersion: process.version,
        useLightrun: useLightrun,
        takeSnapshot: takeSnapshot,
        message: 'Hello from latency test (no Lightrun)!'
    });
});
"""
    
    def _get_package_json(self, nodejs_version: int, gen_version: int, use_lightrun: bool) -> dict:
        """Get package.json content."""
        deps = {
            "@google-cloud/functions-framework": "^3.3.0"
        }
        
        if use_lightrun:
            deps["lightrun"] = ">=1.76.0"
        
        return {
            "name": f"latency-test-function-node{nodejs_version}-gen{gen_version}",
            "version": "1.0.0",
            "main": "index.js",
            "engines": {
                "node": f">={nodejs_version}"
            },
            "dependencies": deps
        }
