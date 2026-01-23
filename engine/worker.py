"""
worker.py
=========
Engineer/Worker Agent: Uses Gemini 2.0 Flash for code implementation.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# Import configuration
try:
    from .config import get_ai_config, create_genai_client, get_engine_config
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Conditional imports
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False


@dataclass
class CodeChange:
    """Represents a code change."""
    file_path: str = ""
    action: str = "create"
    content: Optional[str] = None
    diff: Optional[str] = None
    
    def model_dump(self):
        return self.__dict__.copy()


@dataclass
class ExecutionResult:
    """Result of task execution."""
    task_id: str = ""
    success: bool = False
    files_changed: list = field(default_factory=list)
    output: str = ""
    error: Optional[str] = None
    execution_time_seconds: float = 0.0
    
    def model_dump(self):
        return self.__dict__.copy()


@dataclass
class Engineer:
    """Engineer agent using Gemini 2.0 Flash."""
    worker_id: str = "engineer_1"
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model_name: str = field(default_factory=lambda: os.getenv("DCODE_WORKER_MODEL", "gemini-2.0-flash"))
    workspace_path: str = field(default_factory=lambda: os.getenv("DCODE_WORKSPACE_DIR", "./workspace"))
    max_retries: int = 3
    
    _client: Any = field(default=None, init=False)
    _on_stream: Optional[Callable[[str, str], None]] = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        if self.api_key and GENAI_AVAILABLE:
            if CONFIG_AVAILABLE:
                config = get_ai_config()
                engine_config = get_engine_config()
                self.model_name = config.worker_model
                self.max_retries = config.max_retries
                self.workspace_path = engine_config.workspace_dir
                self._client = create_genai_client()
            elif genai is not None:
                self._client = genai.Client(api_key=self.api_key)
        Path(self.workspace_path).mkdir(parents=True, exist_ok=True)
    
    def set_stream_callback(self, callback: Callable[[str, str], None]) -> None:
        self._on_stream = callback
    
    def _emit(self, message: str) -> None:
        if self._on_stream:
            self._on_stream(f"engineer:{self.worker_id}", message)
    
    async def execute_task(self, task: dict) -> ExecutionResult:
        """Execute a task and return the result."""
        import time
        start_time = time.time()
        task_id = task.get("id", "unknown")
        
        self._emit(f"🔨 Starting task: {task.get('title', task_id)}")
        
        if not self._client:
            return ExecutionResult(
                task_id=task_id,
                success=False,
                error="No API client configured",
                execution_time_seconds=time.time() - start_time
            )
        
        files_changed = []
        
        try:
            for file_path in task.get("files_to_create", []):
                self._emit(f"📝 Generating: {file_path}")
                code = await self._generate_code(task, file_path)
                if code:
                    self._write_file(file_path, code)
                    files_changed.append(file_path)
            
            for file_path in task.get("files_to_modify", []):
                self._emit(f"✏️ Modifying: {file_path}")
                changes = await self._generate_modifications(task, file_path)
                if changes:
                    self._apply_changes(file_path, changes)
                    files_changed.append(file_path)
            
            self._emit(f"✅ Task completed: {task_id}")
            
            return ExecutionResult(
                task_id=task_id,
                success=True,
                files_changed=files_changed,
                output=f"Created/modified {len(files_changed)} files",
                execution_time_seconds=time.time() - start_time
            )
        except Exception as e:
            self._emit(f"❌ Task failed: {e}")
            return ExecutionResult(
                task_id=task_id,
                success=False,
                files_changed=files_changed,
                error=str(e),
                execution_time_seconds=time.time() - start_time
            )
    
    async def _generate_code(self, task: dict, file_path: str) -> Optional[str]:
        """Generate code for a new file."""
        if not self._client:
            return None
        
        prompt = f"""Generate code for: {task.get('title', '')}
Description: {task.get('description', '')}
File: {file_path}
Respond with only code, no markdown."""

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            code = response.text.strip()
            if code.startswith("```"):
                lines = code.split("\n")
                code = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            return code
        except Exception as e:
            self._emit(f"⚠️ Code generation failed: {e}")
            return None
    
    async def _generate_modifications(self, task: dict, file_path: str) -> Optional[list]:
        """Generate modifications for an existing file."""
        if not self._client:
            return None
        
        full_path = Path(self.workspace_path) / file_path
        if not full_path.exists():
            return None
        
        current_content = full_path.read_text(encoding="utf-8")
        
        prompt = f"""Modify this file for task: {task.get('title', '')}
Description: {task.get('description', '')}
Current content:
{current_content}
Respond with complete modified file, no markdown."""

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            new_content = response.text.strip()
            if new_content.startswith("```"):
                lines = new_content.split("\n")
                new_content = "\n".join(lines[1:-1])
            return [{"action": "replace", "content": new_content}]
        except Exception as e:
            self._emit(f"⚠️ Modification failed: {e}")
            return None
    
    def _write_file(self, file_path: str, content: str) -> None:
        """Write content to a file."""
        full_path = Path(self.workspace_path) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        self._emit(f"💾 Saved: {file_path}")
    
    def _apply_changes(self, file_path: str, changes: list) -> None:
        """Apply changes to an existing file."""
        full_path = Path(self.workspace_path) / file_path
        for change in changes:
            if change.get("action") == "replace":
                full_path.write_text(change["content"], encoding="utf-8")
        self._emit(f"💾 Updated: {file_path}")


@dataclass
class WorkerPool:
    """Pool of Engineer workers for parallel execution."""
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    workspace_path: str = "./workspace"
    max_workers: int = 4
    
    _workers: list = field(default_factory=list, init=False)
    _on_stream: Optional[Callable[[str, str], None]] = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        for i in range(self.max_workers):
            worker = Engineer(
                worker_id=f"worker_{i+1}",
                api_key=self.api_key,
                workspace_path=self.workspace_path
            )
            self._workers.append(worker)
    
    def set_stream_callback(self, callback: Callable[[str, str], None]) -> None:
        self._on_stream = callback
        for worker in self._workers:
            worker.set_stream_callback(callback)
    
    async def execute_batch(self, tasks: list) -> list:
        """Execute a batch of tasks in parallel."""
        if not tasks:
            return []
        
        async def execute_with_worker(worker: Engineer, task: dict) -> ExecutionResult:
            return await worker.execute_task(task)
        
        assignments = []
        for i, task in enumerate(tasks):
            worker = self._workers[i % len(self._workers)]
            assignments.append(execute_with_worker(worker, task))
        
        results = await asyncio.gather(*assignments, return_exceptions=True)
        
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ExecutionResult(
                    task_id=tasks[i].get("id", "unknown"),
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results
    
    async def execute_all(self, tasks: list, parallel_groups: list) -> list:
        """Execute all tasks respecting dependencies."""
        task_map = {t["id"]: t for t in tasks}
        all_results = []
        
        for group in parallel_groups:
            group_tasks = [task_map[tid] for tid in group if tid in task_map]
            if group_tasks:
                results = await self.execute_batch(group_tasks)
                all_results.extend(results)
        
        return all_results
