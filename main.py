#!/usr/bin/env python3
"""
D-code Main Entry Point
=======================
Uses pywebview to host the React UI and FastAPI backend.
This allows building a single executable without Rust.
"""

import asyncio
import json
import os
import sys
import threading
from pathlib import Path

import webview

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent))

from engine import DCodeEngine, Streamer


class DCodeApp:
    """
    Main application class that bridges the UI and Python engine.
    """
    
    def __init__(self):
        self.engine = None
        self.streamer = Streamer()
        self.window = None
        self._messages = []
        self._ws_clients = []
        
    def _get_api_key(self) -> str:
        """Get API key from environment or prompt user."""
        return os.environ.get("GEMINI_API_KEY", "")
    
    def _get_workspace(self) -> str:
        """Get workspace directory."""
        workspace = Path(__file__).parent / "workspace"
        workspace.mkdir(exist_ok=True)
        return str(workspace)
    
    # === JS API Methods (exposed to frontend) ===
    
    def get_status(self) -> dict:
        """Get current engine status."""
        return {
            "connected": True,
            "engineRunning": self.engine is not None and hasattr(self.engine, '_state'),
            "apiKeySet": bool(self._get_api_key()),
        }
    
    def get_messages(self) -> list:
        """Get all messages."""
        return self._messages
    
    def send_message(self, content: str) -> dict:
        """Send a message to the engine."""
        # Add user message
        user_msg = {
            "id": f"user_{len(self._messages)}",
            "timestamp": self._get_timestamp(),
            "agent": "user",
            "agentIcon": "👤",
            "messageType": "info",
            "content": content,
        }
        self._messages.append(user_msg)
        self._notify_ui("message", user_msg)
        
        # Process with engine if available
        if self.engine:
            threading.Thread(
                target=self._process_message_async,
                args=(content,),
                daemon=True
            ).start()
        else:
            # Initialize engine if not started
            api_key = self._get_api_key()
            if api_key:
                self._initialize_engine(api_key)
                threading.Thread(
                    target=self._process_message_async,
                    args=(content,),
                    daemon=True
                ).start()
            else:
                error_msg = {
                    "id": f"error_{len(self._messages)}",
                    "timestamp": self._get_timestamp(),
                    "agent": "system",
                    "agentIcon": "⚠️",
                    "messageType": "error",
                    "content": "GEMINI_API_KEY environment variable not set. Please set it and restart.",
                }
                self._messages.append(error_msg)
                self._notify_ui("message", error_msg)
        
        return {"success": True}
    
    def request_break(self) -> dict:
        """Request engine to pause."""
        if self.engine:
            self.engine.request_break()
            
        break_msg = {
            "id": f"system_{len(self._messages)}",
            "timestamp": self._get_timestamp(),
            "agent": "system",
            "agentIcon": "🛑",
            "messageType": "warning",
            "content": "Break requested - engine pausing...",
        }
        self._messages.append(break_msg)
        self._notify_ui("message", break_msg)
        
        return {"success": True}
    
    def get_files(self) -> list:
        """Get workspace file tree."""
        workspace = Path(self._get_workspace())
        return self._build_file_tree(workspace)
    
    def read_file(self, path: str) -> dict:
        """Read a file's content."""
        try:
            workspace = Path(self._get_workspace())
            full_path = workspace / path
            
            if not full_path.exists():
                return {"error": "File not found"}
            
            content = full_path.read_text(encoding="utf-8")
            return {
                "path": path,
                "content": content,
                "language": self._detect_language(path),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def set_api_key(self, key: str) -> dict:
        """Set the API key (stores in memory only)."""
        os.environ["GEMINI_API_KEY"] = key
        self._initialize_engine(key)
        return {"success": True}
    
    # === Internal Methods ===
    
    def _initialize_engine(self, api_key: str):
        """Initialize the D-code engine."""
        try:
            self.engine = DCodeEngine(
                api_key=api_key,
                workspace_path=self._get_workspace()
            )
            self.engine.add_stream_callback(self._on_agent_message)
            self.engine.compile()
            
            init_msg = {
                "id": f"system_{len(self._messages)}",
                "timestamp": self._get_timestamp(),
                "agent": "system",
                "agentIcon": "✅",
                "messageType": "success",
                "content": "D-code engine initialized and ready!",
            }
            self._messages.append(init_msg)
            self._notify_ui("message", init_msg)
            
        except Exception as e:
            error_msg = {
                "id": f"error_{len(self._messages)}",
                "timestamp": self._get_timestamp(),
                "agent": "system",
                "agentIcon": "❌",
                "messageType": "error",
                "content": f"Failed to initialize engine: {e}",
            }
            self._messages.append(error_msg)
            self._notify_ui("message", error_msg)
    
    def _process_message_async(self, content: str):
        """Process a message asynchronously."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.engine.send_human_message(content))
        except Exception as e:
            error_msg = {
                "id": f"error_{len(self._messages)}",
                "timestamp": self._get_timestamp(),
                "agent": "system",
                "agentIcon": "❌",
                "messageType": "error",
                "content": f"Error: {e}",
            }
            self._messages.append(error_msg)
            self._notify_ui("message", error_msg)
    
    def _on_agent_message(self, agent: str, content: str):
        """Callback for agent messages."""
        msg = {
            "id": f"agent_{len(self._messages)}",
            "timestamp": self._get_timestamp(),
            "agent": agent,
            "agentIcon": self._get_agent_icon(agent),
            "messageType": self._detect_message_type(content),
            "content": content,
        }
        self._messages.append(msg)
        self._notify_ui("message", msg)
    
    def _notify_ui(self, event: str, data: dict):
        """Send event to UI."""
        if self.window:
            try:
                js_code = f"window.dispatchEvent(new CustomEvent('dcode-{event}', {{detail: {json.dumps(data)}}}));"
                self.window.evaluate_js(js_code)
            except Exception:
                pass
    
    def _get_timestamp(self) -> str:
        """Get ISO timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _get_agent_icon(self, agent: str) -> str:
        """Get icon for agent."""
        icons = {
            "orchestrator": "🎯",
            "planner": "📋",
            "engineer": "🔧",
            "streamer": "📡",
            "system": "💻",
            "user": "👤",
        }
        return icons.get(agent.lower().split("_")[0], "🤖")
    
    def _detect_message_type(self, content: str) -> str:
        """Detect message type from content."""
        content_lower = content.lower()
        if any(x in content_lower for x in ["error", "failed", "❌"]):
            return "error"
        if any(x in content_lower for x in ["warning", "⚠️"]):
            return "warning"
        if any(x in content_lower for x in ["success", "completed", "✅"]):
            return "success"
        if any(x in content_lower for x in ["progress", "%"]):
            return "progress"
        return "info"
    
    def _detect_language(self, path: str) -> str:
        """Detect language from file extension."""
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        lang_map = {
            "py": "python",
            "rs": "rust",
            "js": "javascript",
            "ts": "typescript",
            "tsx": "typescriptreact",
            "jsx": "javascriptreact",
            "json": "json",
            "html": "html",
            "css": "css",
            "md": "markdown",
        }
        return lang_map.get(ext, "plaintext")
    
    def _build_file_tree(self, directory: Path, prefix: str = "") -> list:
        """Build file tree structure."""
        items = []
        try:
            for item in sorted(directory.iterdir()):
                rel_path = f"{prefix}{item.name}" if prefix else item.name
                
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "path": rel_path,
                        "type": "folder",
                        "children": self._build_file_tree(item, f"{rel_path}/"),
                    })
                else:
                    items.append({
                        "name": item.name,
                        "path": rel_path,
                        "type": "file",
                        "language": self._detect_language(item.name),
                    })
        except PermissionError:
            pass
        
        return items


def get_html_path() -> str:
    """Get the path to the UI HTML file."""
    # Check for built UI
    ui_dist = Path(__file__).parent / "ui" / "dist" / "index.html"
    if ui_dist.exists():
        return str(ui_dist)
    
    # Fallback to development
    return "http://localhost:5173"


def main():
    """Main entry point."""
    print("╔════════════════════════════════════════════╗")
    print("║            D-code Starting...              ║")
    print("╚════════════════════════════════════════════╝")
    
    app = DCodeApp()
    
    # Determine UI path
    html_path = get_html_path()
    is_url = html_path.startswith("http")
    
    if is_url:
        print(f"📡 Using development server: {html_path}")
    else:
        print(f"📦 Using built UI: {html_path}")
    
    # Create webview window
    window = webview.create_window(
        title="D-code - AI Development Platform",
        url=html_path,
        width=1400,
        height=900,
        min_size=(1000, 700),
        js_api=app,
        text_select=True,
    )
    app.window = window
    
    # Start webview
    webview.start(debug=False)


if __name__ == "__main__":
    main()
