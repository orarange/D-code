"""
D-code AI Engine
================
Multi-agent orchestration system using LangGraph and Gemini API.

Architecture:
- Orchestrator (Gemini 2.5 Flash): Supervises all operations, handles interrupts
- Planner (Gemini 2.5 Flash): Generates task plans from requirements
- Engineer/Worker (Gemini 2.0 Flash × N): Parallel code implementation with PDCA
- Streamer (Gemini 2.5 Flash): Real-time progress reporting to UI
"""

# Lazy imports to handle missing dependencies gracefully
def __getattr__(name):
    """Lazy import of submodules to handle missing dependencies."""
    if name == "Orchestrator" or name == "DCodeEngine":
        from .main_agent import Orchestrator, DCodeEngine
        return Orchestrator if name == "Orchestrator" else DCodeEngine
    elif name == "Planner" or name == "TaskPlan":
        from .planner import Planner, TaskPlan
        return Planner if name == "Planner" else TaskPlan
    elif name == "Engineer" or name == "WorkerPool":
        from .worker import Engineer, WorkerPool
        return Engineer if name == "Engineer" else WorkerPool
    elif name == "Streamer" or name == "StreamMessage":
        from .streamer import Streamer, StreamMessage
        return Streamer if name == "Streamer" else StreamMessage
    elif name in ("chat_sync", "chat_orchestrated", "request_break", "GENAI_AVAILABLE", "ORCHESTRATOR_AVAILABLE"):
        from .chat import chat_sync, chat_orchestrated, request_break, GENAI_AVAILABLE, ORCHESTRATOR_AVAILABLE
        return {
            "chat_sync": chat_sync,
            "chat_orchestrated": chat_orchestrated,
            "request_break": request_break,
            "GENAI_AVAILABLE": GENAI_AVAILABLE,
            "ORCHESTRATOR_AVAILABLE": ORCHESTRATOR_AVAILABLE,
        }[name]
    elif name == "create_orchestrator":
        from .orchestrator import create_orchestrator
        return create_orchestrator
    elif name in ("get_ai_config", "get_engine_config", "AIConfig", "EngineConfig", "reload_config"):
        from .config import get_ai_config, get_engine_config, AIConfig, EngineConfig, reload_config
        return {
            "get_ai_config": get_ai_config,
            "get_engine_config": get_engine_config,
            "AIConfig": AIConfig,
            "EngineConfig": EngineConfig,
            "reload_config": reload_config,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Orchestrator",
    "DCodeEngine",
    "Planner",
    "TaskPlan",
    "Engineer",
    "WorkerPool",
    "Streamer",
    "StreamMessage",
    "chat_sync",
    "chat_orchestrated",
    "request_break",
    "create_orchestrator",
    "GENAI_AVAILABLE",
    "ORCHESTRATOR_AVAILABLE",
    "get_ai_config",
    "get_engine_config",
    "AIConfig",
    "EngineConfig",
    "reload_config",
]

__version__ = "0.1.0"
