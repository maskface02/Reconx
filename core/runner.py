"""
Async subprocess wrapper for running external tools.
"""
import asyncio
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
import json

from .logger import get_logger


@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool: str
    command: str
    returncode: int
    stdout: str
    stderr: str
    output_file: Optional[Path] = None
    item_count: int = 0
    success: bool = False
    error_message: Optional[str] = None


class AsyncRunner:
    """Async subprocess runner for external tools."""
    
    def __init__(self, rate_limit: int = 50, timeout: int = 300):
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.semaphore = asyncio.Semaphore(rate_limit)
        self.logger = get_logger()
    
    def check_tool(self, tool_path: str) -> bool:
        """Check if a tool is available in PATH."""
        tool_name = tool_path.split()[0]
        return shutil.which(tool_name) is not None
    
    async def run(
        self,
        tool: str,
        command: List[str],
        output_file: Optional[Path] = None,
        input_file: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        callback: Optional[Callable[[str], None]] = None
    ) -> ToolResult:
        """
        Run a tool asynchronously with rate limiting.
        
        Args:
            tool: Tool name for logging
            command: Command and arguments as list
            output_file: Optional file to redirect stdout to
            input_file: Optional file to use as stdin
            env: Optional environment variables
            callback: Optional callback for stdout lines
        """
        async with self.semaphore:
            cmd_str = ' '.join(command)
            self.logger.tool_start(tool, cmd_str)
            
            try:
                # Prepare stdout
                if output_file:
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    stdout_target = open(output_file, 'w')
                else:
                    stdout_target = asyncio.subprocess.PIPE
                
                # Prepare stdin
                stdin_target = None
                if input_file:
                    stdin_target = open(input_file, 'r')
                
                # Run the process
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=stdout_target if isinstance(stdout_target, int) else stdout_target,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=stdin_target,
                    env=env
                )
                
                # Wait for completion with timeout
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), 
                        timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return ToolResult(
                        tool=tool,
                        command=cmd_str,
                        returncode=-1,
                        stdout="",
                        stderr="Timeout exceeded",
                        success=False,
                        error_message=f"Tool timed out after {self.timeout} seconds"
                    )
                
                # Close files
                if output_file and isinstance(stdout_target, type(open(__file__))):
                    stdout_target.close()
                if input_file and stdin_target:
                    stdin_target.close()
                
                # Read output if not written to file
                stdout_str = ""
                if stdout:
                    stdout_str = stdout.decode('utf-8', errors='ignore')
                if stderr:
                    stderr_str = stderr.decode('utf-8', errors='ignore')
                else:
                    stderr_str = ""
                
                # Read output file if created
                if output_file and output_file.exists():
                    with open(output_file, 'r') as f:
                        stdout_str = f.read()
                
                success = process.returncode == 0
                
                # Call callback for each line if provided
                if callback and stdout_str:
                    for line in stdout_str.split('\n'):
                        if line.strip():
                            callback(line.strip())
                
                return ToolResult(
                    tool=tool,
                    command=cmd_str,
                    returncode=process.returncode,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    output_file=output_file,
                    success=success
                )
                
            except Exception as e:
                return ToolResult(
                    tool=tool,
                    command=cmd_str,
                    returncode=-1,
                    stdout="",
                    stderr=str(e),
                    success=False,
                    error_message=str(e)
                )
    
    async def run_shell(
        self,
        tool: str,
        command: str,
        output_file: Optional[Path] = None,
        **kwargs
    ) -> ToolResult:
        """Run a shell command asynchronously."""
        async with self.semaphore:
            self.logger.tool_start(tool, command)
            
            try:
                if output_file:
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE if not output_file else open(output_file, 'w'),
                    stderr=asyncio.subprocess.PIPE,
                    **kwargs
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.timeout
                    )
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    return ToolResult(
                        tool=tool,
                        command=command,
                        returncode=-1,
                        stdout="",
                        stderr="Timeout exceeded",
                        success=False,
                        error_message=f"Tool timed out after {self.timeout} seconds"
                    )
                
                stdout_str = stdout.decode('utf-8', errors='ignore') if stdout else ""
                stderr_str = stderr.decode('utf-8', errors='ignore') if stderr else ""
                
                if output_file and output_file.exists():
                    with open(output_file, 'r') as f:
                        stdout_str = f.read()
                
                return ToolResult(
                    tool=tool,
                    command=command,
                    returncode=process.returncode,
                    stdout=stdout_str,
                    stderr=stderr_str,
                    output_file=output_file,
                    success=process.returncode == 0
                )
                
            except Exception as e:
                return ToolResult(
                    tool=tool,
                    command=command,
                    returncode=-1,
                    stdout="",
                    stderr=str(e),
                    success=False,
                    error_message=str(e)
                )
    
    async def run_many(
        self,
        tasks: List[tuple],
        continue_on_error: bool = True
    ) -> List[ToolResult]:
        """
        Run multiple tools in parallel.
        
        Args:
            tasks: List of (tool, command, output_file, input_file) tuples
            continue_on_error: Whether to continue if one task fails
        """
        coroutines = []
        for task in tasks:
            if len(task) >= 2:
                tool, command = task[0], task[1]
                output_file = task[2] if len(task) > 2 else None
                input_file = task[3] if len(task) > 3 else None
                coroutines.append(self.run(tool, command, output_file, input_file))
        
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Task failed with exception: {result}")
                if not continue_on_error:
                    raise result
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def fetch_url(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        tool_name: str = "curl"
    ) -> Dict[str, Any]:
        """Fetch a URL using curl subprocess."""
        cmd = ["curl", "-s", "-L", "-m", str(timeout), "-w",
               "\\n%{http_code}\\n%{size_download}"]
        
        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])
        
        if method != "GET":
            cmd.extend(["-X", method])
        
        cmd.append(url)

        result = await self.run(tool_name, cmd)
        
        if result.success:
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                try:
                    status_code = int(lines[-2])
                    content_length = int(lines[-1])
                    body = '\n'.join(lines[:-2])
                    return {
                        "url": url,
                        "status_code": status_code,
                        "content_length": content_length,
                        "body": body,
                        "success": True
                    }
                except ValueError:
                    pass
        
        return {
            "url": url,
            "status_code": 0,
            "content_length": 0,
            "body": "",
            "success": False,
            "error": result.stderr
        }
