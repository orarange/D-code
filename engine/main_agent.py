"""
main_agent.py
=============
Orchestrator: The central coordinator using LangGraph for state management.
Uses Gemini 2.5 Flash for high-level decision making.

Responsibilities:
- Coordinate all agents (Planner, Engineers, Streamer)
- Handle human interrupts and break commands
- Manage task lifecycle and error escalation
"""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

# Import configuration
try:
    from .config import get_ai_config, create_genai_client
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Conditional imports with fallbacks
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    GENAI_AVAILABLE = False

try:
    from langgraph.graph import StateGraph, START, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    StateGraph = None  # type: ignore
    START = None  # type: ignore
    END = None  # type: ignore
    LANGGRAPH_AVAILABLE = False

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    # Fallback to dataclass if pydantic not available
    PYDANTIC_AVAILABLE = False
    
    class BaseModel:  # type: ignore
        """Fallback BaseModel when pydantic is not available."""
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        
        def model_dump(self):
            return self.__dict__.copy()
    
    def Field(default=None, default_factory=None, **kwargs):  # type: ignore
        if default_factory is not None:
            return default_factory()
        return default


class AgentState(str, Enum):
    """Possible states for the orchestration system."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    ERROR = "error"
    WAITING_HUMAN = "waiting_human"


# Always use dataclass for SystemState to avoid import issues
@dataclass
class SystemState:
    """LangGraph state schema for the orchestration system."""
    current_state: AgentState = AgentState.IDLE
    current_task_id: Optional[str] = None
    tasks: list = field(default_factory=list)
    completed_tasks: list = field(default_factory=list)
    error_log: list = field(default_factory=list)
    consecutive_errors: int = 0
    human_message: Optional[str] = None
    break_requested: bool = False
    messages: list = field(default_factory=list)
    
    def model_dump(self):
        return {
            'current_state': self.current_state,
            'current_task_id': self.current_task_id,
            'tasks': self.tasks,
            'completed_tasks': self.completed_tasks,
            'error_log': self.error_log,
            'consecutive_errors': self.consecutive_errors,
            'human_message': self.human_message,
            'break_requested': self.break_requested,
            'messages': self.messages,
        }


@dataclass
class Orchestrator:
    """
    Central orchestrator using Gemini 2.5 Flash.
    Supervises all operations and handles human interventions.
    """
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model_name: str = field(default_factory=lambda: os.getenv("DCODE_ORCHESTRATOR_MODEL", "gemini-2.5-flash-preview-05-20"))
    max_consecutive_errors: int = 3
    
    _client: Any = field(default=None, init=False)
    _on_stream: Optional[Callable[[str, str], None]] = field(default=None, init=False)
    
    def __post_init__(self) -> None:
        if self.api_key and GENAI_AVAILABLE:
            if CONFIG_AVAILABLE:
                config = get_ai_config()
                self.model_name = config.orchestrator_model
                self._client = create_genai_client()
            elif genai is not None:
                self._client = genai.Client(api_key=self.api_key)
    
    def set_stream_callback(self, callback: Callable[[str, str], None]) -> None:
        """Set callback for streaming messages to UI."""
        self._on_stream = callback
    
    def _emit(self, agent: str, message: str) -> None:
        """Emit a message to the stream callback."""
        if self._on_stream:
            self._on_stream(agent, message)
    
    def interpret_interrupt_sync(self, state: SystemState, human_input: str) -> dict[str, Any]:
        """
        Synchronous core of interrupt interpretation.

        This performs a *blocking* network call to the model. It is kept
        separate from the async wrapper so callers can offload it to a worker
        thread (via ``asyncio.to_thread``) and keep the event loop responsive
        to Stop-AI / break requests while the model is thinking.
        """
        if not self._client:
            return {"action": "continue", "reason": "No API client configured"}

        prompt = f"""You are an AI orchestrator managing a software development team.

Current state: {state.current_state.value}
Current task: {state.current_task_id}
Pending tasks: {len(state.tasks)}

Human just sent this message:
"{human_input}"

Decide the appropriate action:
1. "inject" - Immediately interrupt current work and address this
2. "queue" - Add to the task queue for later
3. "abort" - Stop all work and wait for further instructions
4. "continue" - Acknowledge but continue current work

Respond with JSON: {{"action": "<action>", "reason": "<brief explanation>", "priority": <1-10>}}"""

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            import json
            result = json.loads(response.text)
            self._emit("orchestrator", f"Interrupt interpreted: {result['action']} - {result['reason']}")
            return result
        except Exception as e:
            self._emit("orchestrator", f"Error interpreting interrupt: {e}")
            return {"action": "continue", "reason": str(e)}

    async def interpret_interrupt(self, state: SystemState, human_input: str) -> dict[str, Any]:
        """
        Interpret human interrupt and decide how to handle it.
        Returns action to take: 'inject', 'queue', 'abort', 'continue'.

        The blocking model call is offloaded to a worker thread so the event
        loop stays responsive (e.g. to Stop-AI requests) while it runs.
        """
        return await asyncio.to_thread(self.interpret_interrupt_sync, state, human_input)
    
    async def handle_error_escalation(self, state: SystemState, error: dict[str, Any]) -> dict[str, Any]:
        """
        Handle error escalation when consecutive errors exceed threshold.
        Ask Gemini for analysis and suggestions.
        """
        if not self._client:
            return {"suggestion": "Manual intervention required", "hints": []}
        
        prompt = f"""Analyze this recurring error in our development system:

Error occurred {state.consecutive_errors} times consecutively.
Latest error: {error}

Recent error log:
{state.error_log[-5:]}

Provide:
1. Likely root cause
2. Suggested fixes (as a list)
3. Questions for the human developer that would help resolve this

Respond as JSON: {{"root_cause": "...", "suggestions": [...], "questions": [...]}}"""

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            import json
            return json.loads(response.text)
        except Exception as e:
            return {"root_cause": "Unknown", "suggestions": [], "questions": [str(e)]}


class DCodeEngine:
    """
    Main engine that ties together all components using LangGraph.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace_path: str = "./workspace",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.workspace_path = workspace_path
        self.orchestrator = Orchestrator(api_key=self.api_key)
        self._graph: Any = None
        self._compiled_graph: Any = None
        self._state = SystemState()
        self._stream_callbacks: list[Callable[[str, str], None]] = []
        # threading.Event (not asyncio.Event): request_break() is invoked from a
        # different thread than the one running the asyncio loop that processes a
        # message, so the break signal must be thread-safe.
        self._break_event = threading.Event()
        # Serialize message processing: only one AI request may be in flight per
        # engine. Without this, a second concurrent send_human_message (the
        # pywebview path spawns a thread per message) could clear the break flag
        # out from under an in-flight request and make Stop-AI ineffective.
        self._message_lock = threading.Lock()
        # Force-stop the AI if it does not respond within this many seconds.
        try:
            timeout = float(os.getenv("DCODE_RESPONSE_TIMEOUT", "120"))
        except (TypeError, ValueError):
            timeout = 120.0
        # A non-positive timeout would force-stop every request immediately;
        # fall back to the default rather than break the UI.
        self._response_timeout = timeout if timeout > 0 else 120.0
        self._langgraph_available = LANGGRAPH_AVAILABLE
        
    def add_stream_callback(self, callback: Callable[[str, str], None]) -> None:
        """Register a callback for streaming agent messages."""
        self._stream_callbacks.append(callback)
        self.orchestrator.set_stream_callback(self._broadcast)
    
    def _broadcast(self, agent: str, message: str) -> None:
        """Broadcast message to all registered callbacks."""
        for cb in self._stream_callbacks:
            try:
                cb(agent, message)
            except Exception:
                pass
    
    def _build_graph(self) -> Any:
        """Build the LangGraph state machine."""
        if not LANGGRAPH_AVAILABLE or StateGraph is None:
            return None
            
        graph = StateGraph(SystemState)
        
        # Define nodes
        graph.add_node("check_break", self._node_check_break)
        graph.add_node("plan", self._node_plan)
        graph.add_node("execute", self._node_execute)
        graph.add_node("handle_error", self._node_handle_error)
        graph.add_node("wait_human", self._node_wait_human)
        graph.add_node("stream_update", self._node_stream_update)
        
        # Define edges
        graph.add_edge(START, "check_break")
        graph.add_conditional_edges(
            "check_break",
            self._route_after_break_check,
            {
                "paused": "wait_human",
                "planning": "plan",
                "executing": "execute",
                "idle": END,
            }
        )
        graph.add_edge("plan", "stream_update")
        graph.add_edge("stream_update", "execute")
        graph.add_conditional_edges(
            "execute",
            self._route_after_execute,
            {
                "continue": "check_break",
                "error": "handle_error",
                "done": END,
            }
        )
        graph.add_conditional_edges(
            "handle_error",
            self._route_after_error,
            {
                "retry": "execute",
                "escalate": "wait_human",
            }
        )
        graph.add_conditional_edges(
            "wait_human",
            self._route_after_human,
            {
                "continue": "check_break",
                "abort": END,
            }
        )
        
        return graph
    
    def _node_check_break(self, state: SystemState) -> dict[str, Any]:
        """Check if break was requested."""
        if state.break_requested:
            self._broadcast("system", "⏸️ Break requested - pausing operations")
            return {"current_state": AgentState.PAUSED, "break_requested": False}
        return {}
    
    def _node_plan(self, state: SystemState) -> dict[str, Any]:
        """Planning node - delegates to Planner agent."""
        self._broadcast("planner", "📋 Generating task plan...")
        return {"current_state": AgentState.PLANNING}
    
    def _node_execute(self, state: SystemState) -> dict[str, Any]:
        """Execution node - delegates to Engineer agents."""
        self._broadcast("engineer", "🔨 Executing tasks...")
        return {"current_state": AgentState.EXECUTING}
    
    def _node_handle_error(self, state: SystemState) -> dict[str, Any]:
        """Error handling node."""
        new_count = state.consecutive_errors + 1
        self._broadcast("system", f"⚠️ Error occurred (count: {new_count})")
        return {
            "current_state": AgentState.ERROR,
            "consecutive_errors": new_count
        }
    
    def _node_wait_human(self, state: SystemState) -> dict[str, Any]:
        """Wait for human input node."""
        self._broadcast("system", "👤 Waiting for human input...")
        return {"current_state": AgentState.WAITING_HUMAN}
    
    def _node_stream_update(self, state: SystemState) -> dict[str, Any]:
        """Stream progress update to UI."""
        completed = len(state.completed_tasks)
        total = len(state.tasks) + completed
        if total > 0:
            progress = (completed / total) * 100
            self._broadcast("streamer", f"📊 Progress: {progress:.1f}% ({completed}/{total} tasks)")
        return {}
    
    def _route_after_break_check(self, state: SystemState) -> str:
        """Route after checking break status."""
        if state.current_state == AgentState.PAUSED:
            return "paused"
        if state.tasks and state.current_state == AgentState.IDLE:
            return "planning"
        if state.current_task_id:
            return "executing"
        return "idle"
    
    def _route_after_execute(self, state: SystemState) -> str:
        """Route after execution."""
        if state.current_state == AgentState.ERROR:
            return "error"
        if not state.tasks and not state.current_task_id:
            return "done"
        return "continue"
    
    def _route_after_error(self, state: SystemState) -> str:
        """Route after error handling."""
        if state.consecutive_errors >= self.orchestrator.max_consecutive_errors:
            return "escalate"
        return "retry"
    
    def _route_after_human(self, state: SystemState) -> str:
        """Route after human input."""
        if state.human_message and state.human_message.lower() == "abort":
            return "abort"
        return "continue"
    
    def compile(self) -> None:
        """Compile the LangGraph."""
        if not LANGGRAPH_AVAILABLE:
            self._broadcast("system", "⚠️ LangGraph not available - running in limited mode")
            return
        self._graph = self._build_graph()
        if self._graph:
            self._compiled_graph = self._graph.compile()
    
    async def run(self, initial_prompt: str) -> SystemState:
        """Run the engine with an initial prompt."""
        if not self._compiled_graph:
            if not LANGGRAPH_AVAILABLE:
                self._broadcast("system", "❌ Cannot run: LangGraph not installed")
                return self._state
            self.compile()
        
        self._state.messages.append({"role": "user", "content": initial_prompt})
        self._state.tasks = [{"id": "initial", "description": initial_prompt, "status": "pending"}]
        
        self._broadcast("orchestrator", f"🚀 Starting D-code engine with: {initial_prompt[:100]}...")
        
        if self._compiled_graph:
            result = await asyncio.to_thread(
                self._compiled_graph.invoke,
                self._state.model_dump()
            )
            self._state = SystemState(**result)
        
        return self._state
    
    def request_break(self) -> None:
        """Request a break/pause in processing.

        Safe to call from any thread. Sets a thread-safe event that the
        message-processing loop polls, so an in-flight AI call is abandoned
        promptly instead of blocking until it returns.
        """
        self._state.break_requested = True
        self._break_event.set()
        self._log_break_requested()
        self._broadcast("system", "🛑 Break requested!")

    def _log_break_requested(self) -> None:
        """Write a debug log entry when the user presses Stop AI."""
        try:
            from .logger import log_agent_message
            log_agent_message(
                "system",
                "Stop AI pressed: break requested by user",
                message_type="command",
            )
        except Exception:
            # Logging must never crash the stop path.
            pass

    async def _wait_for_break(self, poll_interval: float = 0.1) -> None:
        """Await until a break has been requested (polls the threading event)."""
        while not self._break_event.is_set():
            await asyncio.sleep(poll_interval)
    
    async def send_human_message(self, message: str) -> None:
        """Send a message from the human user.

        The orchestrator's (blocking) interpretation runs in a worker thread and
        is raced against a break request and an overall response timeout, so the
        Stop-AI button takes effect immediately and a hung AI is force-stopped.
        """
        # Serialize processing so a second (concurrent) message cannot clear the
        # break flag while this request is still running. Acquire off-loop so the
        # event loop stays responsive while queued behind an in-flight request.
        await asyncio.to_thread(self._message_lock.acquire)
        try:
            # Start each request from a clean break state so a stale Stop from a
            # previous turn does not immediately cancel this one.
            self._break_event.clear()
            self._state.break_requested = False

            self._state.human_message = message
            self._state.messages.append({"role": "user", "content": message})

            # Let the orchestrator interpret the interrupt, but do not let it
            # block the loop: race it against a user break and a timeout.
            interpret_task = asyncio.ensure_future(
                self.orchestrator.interpret_interrupt(self._state, message)
            )
            break_task = asyncio.ensure_future(self._wait_for_break())

            try:
                done, _pending = await asyncio.wait(
                    {interpret_task, break_task},
                    timeout=self._response_timeout,
                    return_when=asyncio.FIRST_COMPLETED,
                )
            finally:
                # Cancel whatever is still pending and await every task so its
                # cancellation completes cleanly (avoids "Task was destroyed but
                # it is pending" / unhandled-exception warnings).
                for t in (interpret_task, break_task):
                    if not t.done():
                        t.cancel()
                await asyncio.gather(interpret_task, break_task, return_exceptions=True)

            if interpret_task not in done:
                # Either the user stopped it, or it timed out. In both cases we
                # stop waiting on the model. (The worker thread may still finish
                # in the background, but its result is discarded.)
                if self._break_event.is_set():
                    self._broadcast("system", "🛑 AI processing stopped by user.")
                else:
                    self._broadcast(
                        "system",
                        f"⏱️ AI did not respond within {self._response_timeout:.0f}s - "
                        "forcibly stopped.",
                    )
                return

            try:
                action = interpret_task.result()
            except asyncio.CancelledError:
                return
            except Exception as e:  # pragma: no cover - defensive
                self._broadcast("system", f"❌ Error interpreting message: {e}")
                return

            if action["action"] == "inject":
                self._state.tasks.insert(0, {
                    "id": f"human_{len(self._state.messages)}",
                    "description": message,
                    "status": "pending",
                    "priority": action.get("priority", 5)
                })
            elif action["action"] == "abort":
                self.request_break()
        finally:
            self._message_lock.release()


# Factory function for easy instantiation
def create_engine(api_key: Optional[str] = None, workspace: str = "./workspace") -> DCodeEngine:
    """Create and compile a new D-code engine instance."""
    engine = DCodeEngine(api_key=api_key, workspace_path=workspace)
    engine.compile()
    return engine
