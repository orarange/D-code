"""
streamer.py
===========
Streamer Agent: Converts logs into human-readable updates.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

# Import configuration
try:
    from .config import get_ai_config, create_genai_client
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


class MessageType(str, Enum):
    """Types of messages in the stream."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"
    CODE = "code"
    THINKING = "thinking"


@dataclass
class StreamMessage:
    """A message to be displayed in the UI."""
    id: str = ""
    timestamp: str = ""
    agent: str = ""
    agent_icon: str = "🤖"
    message_type: MessageType = MessageType.INFO
    content: str = ""
    metadata: dict = field(default_factory=dict)
    
    def model_dump(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'agent': self.agent,
            'agent_icon': self.agent_icon,
            'message_type': self.message_type.value if isinstance(self.message_type, MessageType) else self.message_type,
            'content': self.content,
            'metadata': self.metadata,
        }


# Agent icon mapping
AGENT_ICONS = {
    "orchestrator": "🎯",
    "planner": "📋",
    "engineer": "🔨",
    "streamer": "📡",
    "system": "⚙️",
    "user": "👤",
    "error": "❌",
}


def get_agent_icon(agent: str) -> str:
    """Get the icon for an agent."""
    if agent in AGENT_ICONS:
        return AGENT_ICONS[agent]
    for key in AGENT_ICONS:
        if agent.startswith(key):
            return AGENT_ICONS[key]
    return "🤖"


@dataclass
class Streamer:
    """Streamer agent for transforming logs into human-readable updates."""
    api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    model_name: str = field(default_factory=lambda: os.getenv("DCODE_STREAMER_MODEL", "gemini-2.5-flash-preview-05-20"))
    buffer_size: int = 10
    summarize_threshold: int = 5
    
    _client: Any = field(default=None, init=False)
    _message_buffer: list = field(default_factory=list, init=False)
    _message_id_counter: int = field(default=0, init=False)
    _websocket_clients: list = field(default_factory=list, init=False)
    
    def __post_init__(self) -> None:
        if self.api_key and GENAI_AVAILABLE:
            if CONFIG_AVAILABLE:
                config = get_ai_config()
                self.model_name = config.streamer_model
                self._client = create_genai_client()
            elif genai is not None:
                self._client = genai.Client(api_key=self.api_key)
    
    def _generate_id(self) -> str:
        self._message_id_counter += 1
        return f"msg_{self._message_id_counter}"
    
    def create_message(
        self,
        agent: str,
        content: str,
        message_type: MessageType = MessageType.INFO,
        metadata: Optional[dict] = None
    ) -> StreamMessage:
        """Create a new stream message."""
        return StreamMessage(
            id=self._generate_id(),
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent=agent,
            agent_icon=get_agent_icon(agent),
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )
    
    async def process_log(self, agent: str, raw_log: str) -> StreamMessage:
        """Process a raw log message."""
        message_type = self._detect_message_type(raw_log)
        
        if len(raw_log) < 200:
            return self.create_message(agent=agent, content=raw_log, message_type=message_type)
        
        if self._client and len(raw_log) > 500:
            summarized = await self._summarize(raw_log)
            return self.create_message(
                agent=agent,
                content=summarized,
                message_type=message_type,
                metadata={"original_length": len(raw_log)}
            )
        
        return self.create_message(agent=agent, content=raw_log, message_type=message_type)
    
    def _detect_message_type(self, content: str) -> MessageType:
        """Detect the message type from content."""
        content_lower = content.lower()
        
        if any(word in content_lower for word in ["error", "failed", "exception", "❌"]):
            return MessageType.ERROR
        elif any(word in content_lower for word in ["warning", "warn", "⚠️"]):
            return MessageType.WARNING
        elif any(word in content_lower for word in ["success", "completed", "done", "✅"]):
            return MessageType.SUCCESS
        elif any(word in content_lower for word in ["progress", "📊", "%"]):
            return MessageType.PROGRESS
        elif any(word in content_lower for word in ["thinking", "analyzing", "🤔"]):
            return MessageType.THINKING
        elif "```" in content:
            return MessageType.CODE
        
        return MessageType.INFO
    
    async def _summarize(self, text: str) -> str:
        """Summarize long text using AI."""
        if not self._client:
            return text[:500] + "..." if len(text) > 500 else text
        
        prompt = f"""Summarize in 1-2 sentences: {text}"""

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()
        except Exception:
            return text[:500] + "..." if len(text) > 500 else text
    
    async def broadcast(self, message: StreamMessage) -> None:
        """Broadcast a message to all WebSocket clients."""
        if not self._websocket_clients:
            return
        
        message_json = json.dumps(message.model_dump())
        
        disconnected = []
        for client in self._websocket_clients:
            try:
                await client.send(message_json)
            except Exception:
                disconnected.append(client)
        
        for client in disconnected:
            self._websocket_clients.remove(client)
    
    def add_client(self, websocket: Any) -> None:
        self._websocket_clients.append(websocket)
    
    def remove_client(self, websocket: Any) -> None:
        if websocket in self._websocket_clients:
            self._websocket_clients.remove(websocket)
    
    async def send_progress(self, current: int, total: int, description: str = "") -> StreamMessage:
        """Send a progress update."""
        percentage = (current / total * 100) if total > 0 else 0
        bar_length = 20
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)
        
        content = f"{bar} {percentage:.1f}% ({current}/{total})"
        if description:
            content = f"{description}\n{content}"
        
        message = self.create_message(
            agent="streamer",
            content=content,
            message_type=MessageType.PROGRESS,
            metadata={"current": current, "total": total, "percentage": percentage}
        )
        
        await self.broadcast(message)
        return message
    
    async def send_code_block(self, code: str, language: str = "", filename: str = "") -> StreamMessage:
        """Send a code block message."""
        header = f"📄 {filename}" if filename else "Code"
        content = f"{header}\n```{language}\n{code}\n```"
        
        message = self.create_message(
            agent="engineer",
            content=content,
            message_type=MessageType.CODE,
            metadata={"language": language, "filename": filename}
        )
        
        await self.broadcast(message)
        return message
    
    def buffer_message(self, agent: str, content: str) -> None:
        """Buffer a message for batch processing."""
        self._message_buffer.append({
            "agent": agent,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        if len(self._message_buffer) > self.buffer_size:
            self._message_buffer = self._message_buffer[-self.buffer_size:]
    
    async def flush_buffer(self) -> list:
        """Process and flush the message buffer."""
        if not self._message_buffer:
            return []
        
        if len(self._message_buffer) >= self.summarize_threshold and self._client:
            summary = await self._summarize_buffer()
            self._message_buffer.clear()
            
            message = self.create_message(agent="streamer", content=summary, message_type=MessageType.INFO)
            await self.broadcast(message)
            return [message]
        
        messages = []
        for item in self._message_buffer:
            msg = await self.process_log(item["agent"], item["content"])
            await self.broadcast(msg)
            messages.append(msg)
        
        self._message_buffer.clear()
        return messages
    
    async def _summarize_buffer(self) -> str:
        """Summarize all buffered messages."""
        if not self._client:
            return f"Processed {len(self._message_buffer)} messages"
        
        buffer_text = "\n".join([
            f"[{m['agent']}] {m['content']}"
            for m in self._message_buffer
        ])
        
        prompt = f"""Summarize in 2-3 sentences: {buffer_text}"""

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip()
        except Exception:
            return f"Processed {len(self._message_buffer)} messages"
