"""
orchestrator.py
===============
Multi-Agent Orchestration System for D-code.
Implements the pyramid AI architecture with specialized roles.

Roles:
- Orchestrator: High-level coordination and interrupt handling
- Planner: Task breakdown and planning
- Engineers (x10): Actual code implementation with PDCA cycles
- Streamer: Real-time UI updates
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path

# Import configuration
try:
    from .config import get_ai_config, create_openai_client
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False


class AgentRole(str, Enum):
    """Agent roles in the system."""
    ORCHESTRATOR = "orchestrator"
    PLANNER = "planner"
    ENGINEER = "engineer"
    STREAMER = "streamer"
    USER = "user"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """Message between agents."""
    id: str
    timestamp: str
    sender: AgentRole
    sender_id: str
    content: str
    message_type: str = "info"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "agent": self.sender_id,
            "agent_icon": self._get_icon(),
            "message_type": self.message_type,
            "content": self.content,
            "metadata": self.metadata,
        }
    
    def _get_icon(self) -> str:
        icons = {
            AgentRole.ORCHESTRATOR: "🎯",
            AgentRole.PLANNER: "📋",
            AgentRole.ENGINEER: "🔧",
            AgentRole.STREAMER: "📡",
            AgentRole.USER: "👤",
        }
        return icons.get(self.sender, "🤖")


@dataclass
class Task:
    """A task to be executed by engineers."""
    id: str
    title: str
    description: str
    task_type: str
    priority: int
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    review_count: int = 0
    max_reviews: int = 3


@dataclass
class FileOperation:
    """File operation to be performed."""
    action: str  # create, update, delete
    path: str
    content: Optional[str] = None
    language: Optional[str] = None


class BaseAgent:
    """Base class for all agents."""
    
    def __init__(
        self,
        role: AgentRole,
        agent_id: str,
        model_name: Optional[str] = None,
        on_message: Optional[Callable[[AgentMessage], None]] = None,
    ):
        self.role = role
        self.agent_id = agent_id
        self.model_name = model_name
        self.on_message = on_message
        self._client = None
        
    def _get_client(self):
        """Get or create OpenAI-compatible client."""
        if self._client is None and CONFIG_AVAILABLE:
            self._client = create_openai_client()
        return self._client
    
    def _emit_message(
        self,
        content: str,
        message_type: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Emit a message to the UI."""
        if self.on_message:
            msg = AgentMessage(
                id=f"{self.agent_id}_{int(time.time() * 1000)}",
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                sender=self.role,
                sender_id=self.agent_id,
                content=content,
                message_type=message_type,
                metadata=metadata or {},
            )
            self.on_message(msg)
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Call the LLM with the given prompts."""
        client = self._get_client()
        if client is None:
            return "Error: LLM client not available"
        
        try:
            response = client.chat.completions.create(
                model=self.model_name or "default",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"Error calling LLM: {e}"


class Orchestrator(BaseAgent):
    """
    The central coordinator.
    Handles human interrupts and coordinates all agents.
    """
    
    def __init__(
        self,
        on_message: Optional[Callable[[AgentMessage], None]] = None,
        workspace_path: Optional[str] = None,
    ):
        config = get_ai_config() if CONFIG_AVAILABLE else None
        model = config.orchestrator_model if config else "default"
        super().__init__(AgentRole.ORCHESTRATOR, "orchestrator", model, on_message)
        
        self.workspace_path = workspace_path or os.getenv("DCODE_WORKSPACE", "./workspace")
        self.planner: Optional[Planner] = None
        self.engineers: List[Engineer] = []
        self.streamer: Optional[Streamer] = None
        self.tasks: List[Task] = []
        self.break_requested = False
        self.current_project: Optional[str] = None
        
    def initialize_team(self, num_engineers: int = 3):
        """Initialize the AI team."""
        self._emit_message("🚀 Initializing D-code AI Team...", "info")
        
        # Create Planner
        self.planner = Planner(on_message=self.on_message)
        
        # Create Engineers
        self.engineers = []
        for i in range(num_engineers):
            engineer = Engineer(
                engineer_id=i,
                on_message=self.on_message,
                workspace_path=self.workspace_path,
            )
            self.engineers.append(engineer)
        
        # Create Streamer
        self.streamer = Streamer(on_message=self.on_message)
        
        self._emit_message(
            f"✅ Team ready: 1 Planner, {num_engineers} Engineers, 1 Streamer",
            "success"
        )
    
    def process_user_request(self, request: str) -> str:
        """Process a user request."""
        self._emit_message(f"📝 Received request: {request[:100]}...", "info")
        
        # Analyze request
        system_prompt = """You are the Orchestrator of a software development AI team.
Your job is to understand user requests and decide how to proceed.

Respond in JSON format:
{
    "action": "plan" | "clarify" | "execute" | "modify",
    "project_name": "suggested project name",
    "summary": "brief summary of what needs to be done",
    "needs_planning": true/false,
    "clarification_needed": "question for user if any"
}"""

        response = self._call_llm(system_prompt, request)
        
        try:
            # Try to parse JSON response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                
                if analysis.get("action") == "clarify":
                    return analysis.get("clarification_needed", "Could you provide more details?")
                
                if analysis.get("needs_planning", True):
                    self.current_project = analysis.get("project_name", "untitled_project")
                    return self._start_planning(request, analysis.get("summary", request))
                    
        except json.JSONDecodeError:
            pass
        
        # Default: start planning
        return self._start_planning(request, request)
    
    def _start_planning(self, original_request: str, summary: str) -> str:
        """Start the planning phase."""
        if not self.planner:
            self.initialize_team()
        
        self._emit_message("📋 Starting planning phase...", "info")
        
        # Get plan from Planner
        self.tasks = self.planner.create_plan(summary)
        
        if not self.tasks:
            return "Failed to create a plan. Please try again with more details."
        
        self._emit_message(
            f"✅ Plan created: {len(self.tasks)} tasks",
            "success"
        )
        
        # Start execution
        return self._execute_tasks()
    
    def _execute_tasks(self) -> str:
        """Execute all tasks using the engineer team."""
        results = []
        
        for task in self.tasks:
            if self.break_requested:
                self._emit_message("⚠️ Execution paused by user", "warning")
                break
            
            # Assign task to an available engineer
            engineer = self._get_available_engineer()
            if engineer:
                self._emit_message(
                    f"🔧 Engineer {engineer.engineer_id} starting: {task.title}",
                    "info"
                )
                
                task.status = TaskStatus.IN_PROGRESS
                task.assigned_to = engineer.agent_id
                
                # Engineer executes task with PDCA cycle
                result = engineer.execute_task(task, self.engineers)
                
                if result.get("success"):
                    task.status = TaskStatus.COMPLETED
                    task.result = result.get("output", "")
                    results.append(f"✅ {task.title}: Completed")
                else:
                    task.status = TaskStatus.FAILED
                    task.error = result.get("error", "Unknown error")
                    results.append(f"❌ {task.title}: {task.error}")
        
        # Summary
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)
        self._emit_message(
            f"📊 Execution complete: {completed}/{len(self.tasks)} tasks successful",
            "success" if completed == len(self.tasks) else "warning"
        )
        
        return "\n".join(results)
    
    def _get_available_engineer(self) -> Optional[Engineer]:
        """Get an available engineer."""
        for engineer in self.engineers:
            if not engineer.is_busy:
                return engineer
        # If all busy, return the first one
        return self.engineers[0] if self.engineers else None
    
    def request_break(self):
        """Request a break in execution."""
        self.break_requested = True
        self._emit_message("🛑 Break requested - pausing after current task", "warning")


class Planner(BaseAgent):
    """
    The planning agent.
    Creates task breakdown from requirements.
    """
    
    def __init__(self, on_message: Optional[Callable[[AgentMessage], None]] = None):
        config = get_ai_config() if CONFIG_AVAILABLE else None
        model = config.planner_model if config else "default"
        super().__init__(AgentRole.PLANNER, "planner", model, on_message)
    
    def create_plan(self, requirements: str) -> List[Task]:
        """Create a task plan from requirements."""
        self._emit_message("📋 Analyzing requirements and creating plan...", "info")
        
        system_prompt = """You are a Software Project Planner.
Break down the user's requirements into concrete, actionable tasks.

Respond in JSON format:
{
    "tasks": [
        {
            "id": "task_1",
            "title": "Short task title",
            "description": "Detailed description of what needs to be done",
            "type": "setup|code|test|config|docs",
            "priority": 1-5 (1 highest)
        }
    ]
}

Create 3-10 tasks depending on project complexity.
Order tasks by dependency (tasks that others depend on come first)."""

        response = self._call_llm(system_prompt, requirements)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                plan = json.loads(json_match.group())
                tasks = []
                for t in plan.get("tasks", []):
                    task = Task(
                        id=t.get("id", f"task_{len(tasks)}"),
                        title=t.get("title", "Untitled Task"),
                        description=t.get("description", ""),
                        task_type=t.get("type", "code"),
                        priority=t.get("priority", 3),
                    )
                    tasks.append(task)
                    self._emit_message(f"  📌 Task: {task.title}", "info")
                
                return tasks
        except json.JSONDecodeError as e:
            self._emit_message(f"❌ Failed to parse plan: {e}", "error")
        
        return []


class Engineer(BaseAgent):
    """
    An engineer agent.
    Executes tasks and performs code operations.
    Implements PDCA (Plan-Do-Check-Act) cycles.
    """
    
    def __init__(
        self,
        engineer_id: int,
        on_message: Optional[Callable[[AgentMessage], None]] = None,
        workspace_path: Optional[str] = None,
    ):
        config = get_ai_config() if CONFIG_AVAILABLE else None
        model = config.worker_model if config else "default"
        super().__init__(
            AgentRole.ENGINEER,
            f"engineer_{engineer_id}",
            model,
            on_message,
        )
        self.engineer_id = engineer_id
        self.workspace_path = workspace_path or os.getenv("DCODE_WORKSPACE", "./workspace")
        self.is_busy = False
    
    def execute_task(self, task: Task, team: List[Engineer]) -> Dict[str, Any]:
        """
        Execute a task with PDCA cycle.
        
        PDCA:
        - Plan: Understand and plan implementation
        - Do: Write code/make changes
        - Check: Review and test
        - Act: Fix issues, iterate until done
        """
        self.is_busy = True
        max_iterations = task.max_reviews
        
        try:
            for iteration in range(max_iterations):
                self._emit_message(
                    f"🔄 PDCA Cycle {iteration + 1}/{max_iterations}",
                    "info"
                )
                
                # PLAN: Understand the task
                plan = self._plan_implementation(task)
                if not plan.get("understood"):
                    self._emit_message(f"❓ Need clarification: {plan.get('question')}", "warning")
                    continue
                
                # DO: Implement the solution
                implementation = self._implement(task, plan)
                if not implementation.get("success"):
                    self._emit_message(f"⚠️ Implementation issue: {implementation.get('error')}", "warning")
                    continue
                
                # CHECK: Review the implementation
                review = self._review(task, implementation, team)
                if review.get("approved"):
                    self._emit_message(f"✅ Task completed and approved!", "success")
                    return {"success": True, "output": implementation.get("output")}
                
                # ACT: Address feedback
                feedback = review.get("feedback", "")
                self._emit_message(f"📝 Feedback received: {feedback}", "info")
                task.description += f"\n\nFeedback from review: {feedback}"
            
            # Max iterations reached
            return {"success": False, "error": "Max review iterations reached"}
            
        finally:
            self.is_busy = False
    
    def _plan_implementation(self, task: Task) -> Dict[str, Any]:
        """Plan how to implement the task."""
        system_prompt = """You are a Software Engineer planning task implementation.
Analyze the task and create an implementation plan.

Respond in JSON format:
{
    "understood": true/false,
    "question": "clarification question if not understood",
    "approach": "brief description of implementation approach",
    "files_to_create": ["path/to/file1.py", "path/to/file2.py"],
    "files_to_modify": ["existing/file.py"],
    "estimated_complexity": "low|medium|high"
}"""

        response = self._call_llm(system_prompt, f"Task: {task.title}\n\n{task.description}")
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        
        return {"understood": True, "approach": "Direct implementation"}
    
    def _implement(self, task: Task, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Implement the task based on the plan."""
        self._emit_message(f"💻 Implementing: {plan.get('approach', 'task')}", "code")
        
        system_prompt = f"""You are a Software Engineer implementing a task.
Workspace path: {self.workspace_path}

Create the necessary code to complete this task.
Respond in JSON format:
{{
    "success": true/false,
    "error": "error message if failed",
    "output": "summary of what was done",
    "files": [
        {{
            "action": "create|update|delete",
            "path": "relative/path/to/file.py",
            "content": "full file content",
            "language": "python"
        }}
    ]
}}

IMPORTANT: 
- Use relative paths from the workspace root
- Include complete, working code
- Follow best practices for the language"""

        user_prompt = f"""Task: {task.title}

Description: {task.description}

Plan: {json.dumps(plan, indent=2)}

Implement this task now."""

        response = self._call_llm(system_prompt, user_prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Actually write the files
                if result.get("success") and result.get("files"):
                    for file_op in result["files"]:
                        self._perform_file_operation(file_op)
                
                return result
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Failed to parse implementation: {e}"}
        
        return {"success": False, "error": "No valid response from LLM"}
    
    def _perform_file_operation(self, file_op: Dict[str, Any]):
        """Perform a file operation."""
        action = file_op.get("action", "create")
        rel_path = file_op.get("path", "")
        content = file_op.get("content", "")
        
        if not rel_path:
            return
        
        full_path = Path(self.workspace_path) / "projects" / rel_path
        
        try:
            if action in ("create", "update"):
                # Ensure directory exists
                full_path.parent.mkdir(parents=True, exist_ok=True)
                # Write file
                full_path.write_text(content, encoding="utf-8")
                self._emit_message(f"📄 Created: {rel_path}", "code")
            elif action == "delete":
                if full_path.exists():
                    full_path.unlink()
                    self._emit_message(f"🗑️ Deleted: {rel_path}", "info")
        except Exception as e:
            self._emit_message(f"❌ File operation failed: {e}", "error")
    
    def _review(
        self,
        task: Task,
        implementation: Dict[str, Any],
        team: List[Engineer],
    ) -> Dict[str, Any]:
        """Review the implementation (get feedback from another engineer)."""
        # Find a reviewer (another engineer)
        reviewer = None
        for eng in team:
            if eng.engineer_id != self.engineer_id and not eng.is_busy:
                reviewer = eng
                break
        
        if not reviewer:
            # Self-review if no other engineer available
            reviewer = self
        
        reviewer._emit_message(f"🔍 Reviewing implementation by Engineer {self.engineer_id}...", "info")
        
        system_prompt = """You are a Senior Software Engineer reviewing code.
Check for:
1. Correctness - Does the code do what it should?
2. Best practices - Is the code well-written?
3. Completeness - Is anything missing?
4. Errors - Any bugs or issues?

Respond in JSON format:
{
    "approved": true/false,
    "score": 1-10,
    "feedback": "constructive feedback if not approved",
    "issues": ["list of specific issues if any"]
}"""

        user_prompt = f"""Task: {task.title}
Description: {task.description}

Implementation result:
{json.dumps(implementation, indent=2)}

Review this implementation."""

        response = reviewer._call_llm(system_prompt, user_prompt)
        
        try:
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                review = json.loads(json_match.group())
                score = review.get("score", 5)
                
                if review.get("approved") or score >= 7:
                    reviewer._emit_message(f"✅ Approved (Score: {score}/10)", "success")
                    return {"approved": True}
                else:
                    reviewer._emit_message(f"📝 Needs revision (Score: {score}/10)", "warning")
                    return {"approved": False, "feedback": review.get("feedback", "")}
        except json.JSONDecodeError:
            pass
        
        # Default: approve
        return {"approved": True}


class Streamer(BaseAgent):
    """
    The streamer agent.
    Converts internal events to user-friendly messages.
    """
    
    def __init__(self, on_message: Optional[Callable[[AgentMessage], None]] = None):
        config = get_ai_config() if CONFIG_AVAILABLE else None
        model = config.streamer_model if config else "default"
        super().__init__(AgentRole.STREAMER, "streamer", model, on_message)
    
    def format_progress(self, completed: int, total: int) -> str:
        """Format a progress bar."""
        percentage = (completed / total * 100) if total > 0 else 0
        filled = int(percentage / 5)
        bar = "█" * filled + "░" * (20 - filled)
        return f"[{bar}] {percentage:.1f}% ({completed}/{total} tasks)"


# Convenience function for chat integration
def create_orchestrator(
    on_message: Optional[Callable[[AgentMessage], None]] = None,
    workspace_path: Optional[str] = None,
) -> Orchestrator:
    """Create and initialize an orchestrator with a full team."""
    orchestrator = Orchestrator(on_message=on_message, workspace_path=workspace_path)
    orchestrator.initialize_team(num_engineers=3)
    return orchestrator


# Export
__all__ = [
    "AgentRole",
    "TaskStatus",
    "AgentMessage",
    "Task",
    "BaseAgent",
    "Orchestrator",
    "Planner",
    "Engineer",
    "Streamer",
    "create_orchestrator",
]
