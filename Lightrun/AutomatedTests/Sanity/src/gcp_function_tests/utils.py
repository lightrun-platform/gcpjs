"""Utility functions."""
import asyncio
import subprocess
from typing import Tuple, Optional
from pathlib import Path


def run_command(cmd: list, cwd: Optional[Path] = None, timeout: int = 600) -> Tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


async def run_command_async(cmd: list, cwd: Optional[Path] = None, timeout: int = 600) -> Tuple[int, str, str]:
    """Run a shell command asynchronously and return exit code, stdout, stderr."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            return process.returncode, stdout.decode('utf-8'), stderr.decode('utf-8')
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return 1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)
