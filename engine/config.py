"""
config.py
=========
Centralized configuration management for D-code AI Engine.
All environment variables and settings are managed here.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AIConfig:
    """AI model and API configuration."""
    
    # API Key (optional for local servers like LM Studio)
    api_key: Optional[str]
    
    # API Endpoint (for custom/proxy endpoints like LM Studio)
    api_base_url: Optional[str]
    
    # API Backend type: 'gemini', 'openai', or 'auto'
    api_backend: str
    
    # Model names for different agents
    orchestrator_model: str
    planner_model: str
    worker_model: str
    streamer_model: str
    chat_model: str
    
    # Rate limiting
    max_retries: int
    retry_delay: float
    
    @classmethod
    def from_env(cls) -> "AIConfig":
        """Load configuration from environment variables."""
        import sys
        
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        base_url = os.getenv("GEMINI_API_BASE_URL") or os.getenv("DCODE_API_BASE_URL") or os.getenv("OPENAI_API_BASE")
        
        # Debug logging
        print(f"[config.py] GEMINI_API_KEY: {'set' if os.getenv('GEMINI_API_KEY') else 'not set'}", file=sys.stderr)
        print(f"[config.py] DCODE_API_BASE_URL: {os.getenv('DCODE_API_BASE_URL')}", file=sys.stderr)
        print(f"[config.py] Resolved base_url: {base_url}", file=sys.stderr)
        
        # Auto-detect backend based on configuration
        backend = os.getenv("DCODE_API_BACKEND", "auto")
        if backend == "auto":
            if base_url and ("localhost" in base_url or "127.0.0.1" in base_url):
                backend = "openai"  # Local servers like LM Studio use OpenAI API
            elif base_url and "openai" in base_url.lower():
                backend = "openai"
            else:
                backend = "gemini"
        
        print(f"[config.py] Resolved backend: {backend}", file=sys.stderr)
        
        return cls(
            api_key=api_key if api_key else None,
            api_base_url=base_url,
            api_backend=backend,
            orchestrator_model=os.getenv("DCODE_ORCHESTRATOR_MODEL", "gemini-2.5-flash-preview-05-20"),
            planner_model=os.getenv("DCODE_PLANNER_MODEL", "gemini-2.5-flash-preview-05-20"),
            worker_model=os.getenv("DCODE_WORKER_MODEL", "gemini-2.0-flash"),
            streamer_model=os.getenv("DCODE_STREAMER_MODEL", "gemini-2.5-flash-preview-05-20"),
            chat_model=os.getenv("DCODE_CHAT_MODEL", "gemini-2.0-flash"),
            max_retries=int(os.getenv("DCODE_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("DCODE_RETRY_DELAY", "30.0")),
        )
    
    def is_valid(self) -> bool:
        """Check if the configuration is valid (API key optional for local servers)."""
        # If using local server (openai backend with localhost), API key is optional
        if self.api_backend == "openai" and self.api_base_url:
            if "localhost" in self.api_base_url or "127.0.0.1" in self.api_base_url:
                return True
        return bool(self.api_key)
    
    def is_local_server(self) -> bool:
        """Check if using a local server like LM Studio."""
        if self.api_base_url:
            return "localhost" in self.api_base_url or "127.0.0.1" in self.api_base_url
        return False


@dataclass  
class EngineConfig:
    """Engine operational configuration."""
    
    # Worker pool
    max_workers: int
    task_timeout: int
    
    # Workspace
    workspace_dir: str
    sandbox_fs: bool
    allowed_extensions: list
    
    # Logging
    log_level: str
    debug_mode: bool
    
    @classmethod
    def from_env(cls) -> "EngineConfig":
        """Load configuration from environment variables."""
        extensions_str = os.getenv(
            "DCODE_ALLOWED_EXTENSIONS", 
            ".rs,.py,.ts,.tsx,.js,.jsx,.json,.toml,.yaml,.yml,.md,.txt,.html,.css"
        )
        return cls(
            max_workers=int(os.getenv("DCODE_MAX_WORKERS", "10")),
            task_timeout=int(os.getenv("DCODE_TASK_TIMEOUT", "300")),
            workspace_dir=os.getenv("DCODE_WORKSPACE_DIR", "./workspace"),
            sandbox_fs=os.getenv("DCODE_SANDBOX_FS", "true").lower() == "true",
            allowed_extensions=[ext.strip() for ext in extensions_str.split(",")],
            log_level=os.getenv("DCODE_LOG_LEVEL", "info"),
            debug_mode=os.getenv("DCODE_DEBUG", "false").lower() == "true",
        )


# Global configuration instances (lazy loaded)
_ai_config: Optional[AIConfig] = None
_engine_config: Optional[EngineConfig] = None


def get_ai_config() -> AIConfig:
    """Get the AI configuration (singleton)."""
    global _ai_config
    if _ai_config is None:
        _ai_config = AIConfig.from_env()
    return _ai_config


def get_engine_config() -> EngineConfig:
    """Get the engine configuration (singleton)."""
    global _engine_config
    if _engine_config is None:
        _engine_config = EngineConfig.from_env()
    return _engine_config


def reload_config() -> None:
    """Reload configuration from environment variables."""
    global _ai_config, _engine_config
    _ai_config = AIConfig.from_env()
    _engine_config = EngineConfig.from_env()


def create_genai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    """
    Create a Google GenAI client with optional custom endpoint.
    
    Args:
        api_key: API key (uses config if not provided)
        base_url: Custom API endpoint URL (uses config if not provided)
    
    Returns:
        Configured genai.Client or None if not available
    """
    try:
        from google import genai
    except ImportError:
        return None
    
    config = get_ai_config()
    key = api_key or config.api_key
    url = base_url or config.api_base_url
    
    # For local servers, API key is optional
    if not key and not config.is_local_server():
        return None
    
    # Create client with optional custom endpoint
    client_kwargs = {}
    if key:
        client_kwargs["api_key"] = key
    
    # If a custom base URL is specified, configure the client
    if url:
        # google-genai supports http_options for custom endpoints
        from google.genai import types
        http_options = types.HttpOptions(base_url=url)
        client_kwargs["http_options"] = http_options
    
    return genai.Client(**client_kwargs)


def create_openai_client(api_key: Optional[str] = None, base_url: Optional[str] = None):
    """
    Create an OpenAI-compatible client (for LM Studio, etc.).
    
    Args:
        api_key: API key (optional for local servers)
        base_url: API endpoint URL
    
    Returns:
        Configured OpenAI client or None if not available
    """
    try:
        from openai import OpenAI
    except ImportError:
        return None
    
    config = get_ai_config()
    key = api_key or config.api_key or "lm-studio"  # LM Studio accepts any key
    url = base_url or config.api_base_url
    
    if not url:
        return None
    
    # Ensure URL ends with /v1 for OpenAI compatibility
    if not url.endswith("/v1"):
        url = url.rstrip("/") + "/v1"
    
    # Set a longer timeout for local servers (5 minutes)
    return OpenAI(api_key=key, base_url=url, timeout=300.0)


# Export commonly used functions and classes
__all__ = [
    "AIConfig",
    "EngineConfig", 
    "get_ai_config",
    "get_engine_config",
    "reload_config",
    "create_genai_client",
    "create_openai_client",
]
