"""GCP Cloud Functions deployment and management."""
from typing import Tuple, Optional
from pathlib import Path
from .config import REGION_PRECEDENCE, REGION, PROJECT_ID, LIGHTRUN_SECRET
from .utils import run_command, run_command_async
from .models import DeploymentResult


class GCPDeployer:
    """Handles GCP Cloud Functions deployment and management."""
    
    def __init__(self, project_id: str = PROJECT_ID):
        self.project_id = project_id
    
    async def deploy_function(
        self, 
        function_name: str, 
        func_dir: Path, 
        nodejs_version: int, 
        gen_version: int, 
        region: Optional[str] = None
    ) -> DeploymentResult:
        """Deploy a GCP Cloud Function. Returns DeploymentResult."""
        gen_flag = "--gen2" if gen_version == 2 else "--no-gen2"
        deploy_region = region or REGION
        
        cmd = [
            "gcloud", "functions", "deploy", function_name,
            gen_flag,
            "--runtime", f"nodejs{nodejs_version}",
            "--region", deploy_region,
            "--trigger-http",
            "--allow-unauthenticated",
            "--entry-point", "testFunction",
            "--memory", "512MB",
            "--source", str(func_dir),
            "--set-env-vars", f"LIGHTRUN_SECRET={LIGHTRUN_SECRET},DISPLAY_NAME={function_name}",
            "--quiet"
        ]
        
        exit_code, stdout, stderr = await run_command_async(cmd, timeout=600)
        
        if exit_code != 0:
            return DeploymentResult(
                success=False,
                error=f"Deployment failed: {stderr}",
                used_region=deploy_region
            )
        
        # Extract function URL from output
        url = self._extract_url_from_output(stdout, deploy_region, function_name)
        
        return DeploymentResult(
            success=True,
            url=url,
            used_region=deploy_region
        )
    
    async def deploy_with_fallback(
        self, 
        function_name: str, 
        func_dir: Path, 
        nodejs_version: int, 
        gen_version: int
    ) -> DeploymentResult:
        """Deploy a function trying regions in precedence order."""
        for region in REGION_PRECEDENCE:
            print(f"  Attempting deployment to {region}...")
            result = await self.deploy_function(function_name, func_dir, nodejs_version, gen_version, region)
            if result.success:
                return result
            # Check if error is region-related
            if result.error and ("Permission denied" in result.error or "not found" in result.error.lower()):
                print(f"  Region {region} not available, trying next...")
                continue
            # If it's a different error, return it
            return result
        
        return DeploymentResult(
            success=False,
            error="All regions in precedence list failed"
        )
    
    async def delete_function(self, function_name: str, region: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Delete a GCP Cloud Function. Returns (success, error)."""
        delete_region = region or REGION
        cmd = [
            "gcloud", "functions", "delete", function_name,
            "--region", delete_region,
            "--quiet"
        ]
        
        exit_code, stdout, stderr = await run_command_async(cmd, timeout=300)
        
        if exit_code != 0:
            return False, f"Deletion failed: {stderr}"
        
        return True, None
    
    async def check_logs_for_errors(self, function_name: str, region: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Check Cloud Function logs for errors."""
        check_region = region or REGION
        cmd = [
            "gcloud", "functions", "logs", "read", function_name,
            "--region", check_region,
            "--limit", "1000"
        ]
        
        exit_code, stdout, stderr = await run_command_async(cmd, timeout=60)
        
        if exit_code != 0:
            return False, f"Failed to read logs: {stderr}"
        
        # Check for error patterns
        error_patterns = ["ERROR", "Error", "Exception", "Failed", "failed"]
        has_errors = any(pattern in stdout for pattern in error_patterns)
        
        if has_errors:
            # Extract error lines
            error_lines = [line for line in stdout.split('\n') 
                          if any(pattern in line for pattern in error_patterns)]
            error_msg = "\n".join(error_lines[:10])  # First 10 error lines
            return False, error_msg
        
        return True, None
    
    def _extract_url_from_output(self, stdout: str, region: str, function_name: str) -> Optional[str]:
        """Extract function URL from deployment output."""
        url = None
        for line in stdout.split('\n'):
            if 'httpsTrigger:' in line or 'url:' in line:
                if 'https://' in line:
                    url = line.split('https://')[1].split()[0] if 'https://' in line else None
                    if url:
                        url = f"https://{url}"
            if 'https://' in line and '.cloudfunctions.net' in line:
                url = line.split('https://')[1].strip() if 'https://' in line else None
                if url:
                    url = f"https://{url}"
        
        # Fallback: construct URL from function name
        if not url:
            url = f"https://{region}-{self.project_id}.cloudfunctions.net/{function_name}"
        
        return url
