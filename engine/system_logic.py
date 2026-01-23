"""
system_logic.py
===============
D-code System Logic Module

Responsibilities:
- Git version control and history tracking
- External API integration
- Performance analysis
- Terminal output capture and analysis
- Dependency management
"""

import os
import re
import sys
import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Pydantic for validation
try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    Field = lambda **kwargs: None


class TerminalOutputType(str, Enum):
    """Types of terminal output"""
    STDOUT = "stdout"
    STDERR = "stderr"
    EXIT_CODE = "exit_code"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class TerminalResult:
    """Result of a terminal command execution"""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    working_dir: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def is_success(self) -> bool:
        return self.exit_code == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "working_dir": self.working_dir,
            "timestamp": self.timestamp,
            "is_success": self.is_success(),
        }


@dataclass
class GitCommit:
    """Git commit information"""
    hash: str
    short_hash: str
    author: str
    date: str
    message: str
    files_changed: List[str] = field(default_factory=list)


@dataclass
class DependencyInfo:
    """Dependency information"""
    name: str
    version: str
    latest_version: Optional[str] = None
    is_outdated: bool = False
    vulnerabilities: List[str] = field(default_factory=list)


class TerminalManager:
    """
    Manages terminal command execution and output analysis.
    
    Features:
    - Execute commands with timeout
    - Capture stdout/stderr
    - Analyze output for errors
    - Track command history
    """
    
    def __init__(self, working_dir: Optional[str] = None):
        self.working_dir = working_dir or os.getcwd()
        self.history: List[TerminalResult] = []
        self.max_history = 100
        
        # Common error patterns for analysis
        self.error_patterns = {
            "python": [
                (r"ModuleNotFoundError: No module named '(\w+)'", "missing_module"),
                (r"SyntaxError: (.+)", "syntax_error"),
                (r"IndentationError: (.+)", "indentation_error"),
                (r"TypeError: (.+)", "type_error"),
                (r"ValueError: (.+)", "value_error"),
                (r"FileNotFoundError: (.+)", "file_not_found"),
                (r"ImportError: (.+)", "import_error"),
                (r"AttributeError: (.+)", "attribute_error"),
                (r"KeyError: (.+)", "key_error"),
                (r"NameError: (.+)", "name_error"),
            ],
            "npm": [
                (r"npm ERR! (.+)", "npm_error"),
                (r"ENOENT: no such file or directory", "file_not_found"),
                (r"permission denied", "permission_denied"),
                (r"Cannot find module '(.+)'", "missing_module"),
            ],
            "rust": [
                (r"error\[E\d+\]: (.+)", "compile_error"),
                (r"warning: (.+)", "warning"),
                (r"cannot find (.+)", "not_found"),
            ],
            "general": [
                (r"[Ee]rror:?\s*(.+)", "general_error"),
                (r"[Ff]ailed:?\s*(.+)", "failure"),
                (r"[Ee]xception:?\s*(.+)", "exception"),
                (r"[Ww]arning:?\s*(.+)", "warning"),
            ],
        }
    
    def execute(
        self,
        command: str,
        timeout: float = 60.0,
        env: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None
    ) -> TerminalResult:
        """
        Execute a terminal command and return the result.
        """
        cwd = working_dir or self.working_dir
        start_time = time.time()
        
        # Prepare environment
        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)
        
        try:
            # Use shell=True on Windows for proper command execution
            is_windows = sys.platform == "win32"
            
            if is_windows:
                # Use PowerShell for better compatibility
                full_cmd = f'powershell -Command "{command}"'
                process = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    env=cmd_env,
                    shell=True,
                    text=True,
                )
            else:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=cwd,
                    env=cmd_env,
                    shell=True,
                    text=True,
                )
            
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
            
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            exit_code = -1
            stderr = f"Command timed out after {timeout} seconds\n" + (stderr or "")
            
        except Exception as e:
            stdout = ""
            stderr = str(e)
            exit_code = -1
        
        duration = time.time() - start_time
        
        result = TerminalResult(
            command=command,
            stdout=stdout.strip() if stdout else "",
            stderr=stderr.strip() if stderr else "",
            exit_code=exit_code,
            duration=duration,
            working_dir=cwd,
        )
        
        # Add to history
        self.history.append(result)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        return result
    
    def analyze_output(self, result: TerminalResult) -> Dict[str, Any]:
        """
        Analyze terminal output for errors and patterns.
        """
        analysis = {
            "success": result.is_success(),
            "errors": [],
            "warnings": [],
            "suggestions": [],
        }
        
        # Combine stdout and stderr for analysis
        output = f"{result.stdout}\n{result.stderr}"
        
        # Check all pattern categories
        for category, patterns in self.error_patterns.items():
            for pattern, error_type in patterns:
                matches = re.findall(pattern, output, re.MULTILINE)
                for match in matches:
                    error_info = {
                        "type": error_type,
                        "category": category,
                        "message": match if isinstance(match, str) else match[0],
                    }
                    
                    # Add suggestions based on error type
                    suggestion = self._get_suggestion(error_type, match)
                    if suggestion:
                        error_info["suggestion"] = suggestion
                        analysis["suggestions"].append(suggestion)
                    
                    if "warning" in error_type:
                        analysis["warnings"].append(error_info)
                    else:
                        analysis["errors"].append(error_info)
        
        return analysis
    
    def _get_suggestion(self, error_type: str, match: Any) -> Optional[str]:
        """Get suggestion for fixing an error."""
        suggestions = {
            "missing_module": f"Try installing the module: pip install {match}" if isinstance(match, str) else None,
            "syntax_error": "Check for missing colons, brackets, or quotes",
            "indentation_error": "Check indentation (use 4 spaces consistently)",
            "file_not_found": "Verify the file path exists",
            "permission_denied": "Check file permissions or run with elevated privileges",
            "npm_error": "Try running 'npm install' first",
        }
        return suggestions.get(error_type)
    
    def get_recent_errors(self, count: int = 5) -> List[TerminalResult]:
        """Get recent failed commands."""
        failed = [r for r in self.history if not r.is_success()]
        return failed[-count:]


class GitManager:
    """
    Manages Git operations for version control.
    
    Features:
    - Initialize repositories
    - Commit changes
    - Track history
    - Manage branches
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.terminal = TerminalManager(str(self.repo_path))
    
    def is_git_repo(self) -> bool:
        """Check if directory is a git repository."""
        return (self.repo_path / ".git").exists()
    
    def init(self) -> TerminalResult:
        """Initialize a new git repository."""
        return self.terminal.execute("git init")
    
    def status(self) -> Dict[str, List[str]]:
        """Get git status."""
        result = self.terminal.execute("git status --porcelain")
        
        status = {
            "staged": [],
            "modified": [],
            "untracked": [],
            "deleted": [],
        }
        
        if result.is_success():
            for line in result.stdout.split("\n"):
                if not line.strip():
                    continue
                code = line[:2]
                file_path = line[3:].strip()
                
                if code[0] in "MADRC":
                    status["staged"].append(file_path)
                if code[1] == "M":
                    status["modified"].append(file_path)
                elif code[1] == "?":
                    status["untracked"].append(file_path)
                elif code[1] == "D":
                    status["deleted"].append(file_path)
        
        return status
    
    def add(self, files: Optional[List[str]] = None) -> TerminalResult:
        """Stage files for commit."""
        if files:
            files_str = " ".join(f'"{f}"' for f in files)
            return self.terminal.execute(f"git add {files_str}")
        else:
            return self.terminal.execute("git add -A")
    
    def commit(self, message: str, auto_add: bool = False) -> TerminalResult:
        """Create a commit."""
        if auto_add:
            self.add()
        
        # Escape quotes in message
        safe_message = message.replace('"', '\\"')
        return self.terminal.execute(f'git commit -m "{safe_message}"')
    
    def log(self, count: int = 10) -> List[GitCommit]:
        """Get commit history."""
        format_str = "%H|%h|%an|%ai|%s"
        result = self.terminal.execute(
            f'git log --format="{format_str}" -n {count}'
        )
        
        commits = []
        if result.is_success():
            for line in result.stdout.split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|", 4)
                if len(parts) >= 5:
                    commits.append(GitCommit(
                        hash=parts[0],
                        short_hash=parts[1],
                        author=parts[2],
                        date=parts[3],
                        message=parts[4],
                    ))
        
        return commits
    
    def diff(self, file_path: Optional[str] = None) -> str:
        """Get diff of changes."""
        cmd = "git diff"
        if file_path:
            cmd += f' "{file_path}"'
        result = self.terminal.execute(cmd)
        return result.stdout if result.is_success() else ""
    
    def branch_list(self) -> List[str]:
        """List all branches."""
        result = self.terminal.execute("git branch")
        branches = []
        if result.is_success():
            for line in result.stdout.split("\n"):
                branch = line.strip().lstrip("* ")
                if branch:
                    branches.append(branch)
        return branches
    
    def create_branch(self, name: str) -> TerminalResult:
        """Create a new branch."""
        return self.terminal.execute(f"git checkout -b {name}")
    
    def checkout(self, branch: str) -> TerminalResult:
        """Switch to a branch."""
        return self.terminal.execute(f"git checkout {branch}")
    
    def auto_commit(self, prefix: str = "D-code") -> TerminalResult:
        """Automatically commit all changes with timestamp."""
        status = self.status()
        total_changes = (
            len(status["staged"]) + 
            len(status["modified"]) + 
            len(status["untracked"])
        )
        
        if total_changes == 0:
            return TerminalResult(
                command="auto_commit",
                stdout="No changes to commit",
                stderr="",
                exit_code=0,
                duration=0,
                working_dir=str(self.repo_path),
            )
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = f"[{prefix}] Auto-commit at {timestamp} ({total_changes} files)"
        
        return self.commit(message, auto_add=True)


class DependencyManager:
    """
    Manages project dependencies.
    
    Features:
    - Detect project type
    - List dependencies
    - Check for updates
    - Identify vulnerabilities
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.terminal = TerminalManager(str(self.project_path))
    
    def detect_project_type(self) -> List[str]:
        """Detect project type(s) based on config files."""
        types = []
        
        if (self.project_path / "package.json").exists():
            types.append("nodejs")
        if (self.project_path / "requirements.txt").exists():
            types.append("python")
        if (self.project_path / "pyproject.toml").exists():
            types.append("python")
        if (self.project_path / "Cargo.toml").exists():
            types.append("rust")
        if (self.project_path / "go.mod").exists():
            types.append("go")
        if (self.project_path / "pom.xml").exists():
            types.append("java")
        
        return types or ["unknown"]
    
    def get_python_dependencies(self) -> List[DependencyInfo]:
        """Get Python dependencies."""
        deps = []
        
        # Try requirements.txt
        req_file = self.project_path / "requirements.txt"
        if req_file.exists():
            with open(req_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    # Parse package name and version
                    match = re.match(r"([a-zA-Z0-9_-]+)([<>=!]+)?(.+)?", line)
                    if match:
                        name = match.group(1)
                        version = match.group(3) or "any"
                        deps.append(DependencyInfo(name=name, version=version))
        
        return deps
    
    def get_nodejs_dependencies(self) -> List[DependencyInfo]:
        """Get Node.js dependencies."""
        deps = []
        
        pkg_file = self.project_path / "package.json"
        if pkg_file.exists():
            with open(pkg_file, "r") as f:
                data = json.load(f)
            
            for dep_type in ["dependencies", "devDependencies"]:
                for name, version in data.get(dep_type, {}).items():
                    deps.append(DependencyInfo(name=name, version=version))
        
        return deps
    
    def install_dependencies(self) -> List[TerminalResult]:
        """Install dependencies for all detected project types."""
        results = []
        types = self.detect_project_type()
        
        if "python" in types:
            req_file = self.project_path / "requirements.txt"
            if req_file.exists():
                results.append(
                    self.terminal.execute(f"pip install -r {req_file}")
                )
        
        if "nodejs" in types:
            results.append(self.terminal.execute("npm install"))
        
        if "rust" in types:
            results.append(self.terminal.execute("cargo build"))
        
        return results


class PerformanceAnalyzer:
    """
    Analyzes code performance.
    
    Features:
    - Profile Python code
    - Measure execution time
    - Memory analysis
    - Identify bottlenecks
    """
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.terminal = TerminalManager(str(self.project_path))
    
    def profile_python(self, script: str, args: str = "") -> Dict[str, Any]:
        """Profile a Python script."""
        result = self.terminal.execute(
            f'python -m cProfile -s cumulative "{script}" {args}',
            timeout=120
        )
        
        return {
            "success": result.is_success(),
            "output": result.stdout,
            "errors": result.stderr,
            "duration": result.duration,
        }
    
    def time_command(self, command: str, iterations: int = 3) -> Dict[str, Any]:
        """Time a command execution."""
        times = []
        
        for _ in range(iterations):
            result = self.terminal.execute(command)
            times.append(result.duration)
        
        return {
            "command": command,
            "iterations": iterations,
            "times": times,
            "average": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
        }


class APIConnector:
    """
    Manages external API connections.
    
    Features:
    - HTTP requests
    - Authentication
    - Rate limiting
    - Response caching
    """
    
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl = 300  # 5 minutes
    
    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
        cache: bool = False
    ) -> Dict[str, Any]:
        """Make an HTTP request."""
        # Use urllib for simplicity (no external deps)
        import urllib.request
        import urllib.error
        
        cache_key = f"{method}:{url}"
        
        # Check cache
        if cache and cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return {"success": True, "data": cached_data, "cached": True}
        
        try:
            # Build request
            req_data = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=req_data, method=method)
            
            # Add headers
            req.add_header("Content-Type", "application/json")
            if headers:
                for key, value in headers.items():
                    req.add_header(key, value)
            
            # Make request
            with urllib.request.urlopen(req, timeout=timeout) as response:
                response_data = response.read().decode()
                try:
                    result = json.loads(response_data)
                except json.JSONDecodeError:
                    result = response_data
            
            # Cache if requested
            if cache:
                self.cache[cache_key] = (result, time.time())
            
            return {"success": True, "data": result, "cached": False}
            
        except urllib.error.HTTPError as e:
            return {
                "success": False,
                "error": f"HTTP {e.code}: {e.reason}",
                "code": e.code,
            }
        except urllib.error.URLError as e:
            return {
                "success": False,
                "error": f"URL Error: {e.reason}",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class SystemLogic:
    """
    Main system logic coordinator.
    
    Combines all system management features.
    """
    
    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.terminal = TerminalManager(str(self.workspace_path))
        self.git = GitManager(str(self.workspace_path))
        self.deps = DependencyManager(str(self.workspace_path))
        self.perf = PerformanceAnalyzer(str(self.workspace_path))
        self.api = APIConnector()
    
    def execute_command(self, command: str, analyze: bool = True) -> Dict[str, Any]:
        """Execute a command and optionally analyze the output."""
        result = self.terminal.execute(command)
        
        response = result.to_dict()
        
        if analyze:
            response["analysis"] = self.terminal.analyze_output(result)
        
        return response
    
    def auto_version_control(self, message: Optional[str] = None) -> Dict[str, Any]:
        """Automatically version control changes."""
        if not self.git.is_git_repo():
            init_result = self.git.init()
            if not init_result.is_success():
                return {"success": False, "error": "Failed to initialize git"}
        
        if message:
            commit_result = self.git.commit(message, auto_add=True)
        else:
            commit_result = self.git.auto_commit()
        
        return {
            "success": commit_result.is_success(),
            "message": commit_result.stdout,
            "error": commit_result.stderr if not commit_result.is_success() else None,
        }
    
    def get_project_status(self) -> Dict[str, Any]:
        """Get overall project status."""
        return {
            "project_types": self.deps.detect_project_type(),
            "git": {
                "is_repo": self.git.is_git_repo(),
                "status": self.git.status() if self.git.is_git_repo() else None,
                "recent_commits": [
                    {"hash": c.short_hash, "message": c.message, "author": c.author}
                    for c in self.git.log(5)
                ] if self.git.is_git_repo() else [],
            },
            "terminal": {
                "recent_errors": [
                    {"command": r.command, "exit_code": r.exit_code}
                    for r in self.terminal.get_recent_errors(3)
                ],
            },
        }


# Convenience function for direct terminal execution
def run_command(command: str, working_dir: Optional[str] = None) -> TerminalResult:
    """Run a terminal command and return the result."""
    terminal = TerminalManager(working_dir)
    return terminal.execute(command)


def analyze_error(output: str) -> Dict[str, Any]:
    """Analyze error output for common patterns."""
    terminal = TerminalManager()
    dummy_result = TerminalResult(
        command="",
        stdout="",
        stderr=output,
        exit_code=1,
        duration=0,
        working_dir="",
    )
    return terminal.analyze_output(dummy_result)
