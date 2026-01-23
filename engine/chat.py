"""
chat.py
=======
Chat functionality using AI APIs.
Provides synchronous chat for the desktop UI.
Supports both simple chat and multi-agent orchestration modes.
"""

import os
import re
import sys
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Any, List, Dict

# Import logger
try:
    from .logger import get_logger, log_agent_message, log_user_input, log_error
    LOGGER_AVAILABLE = True
except ImportError:
    LOGGER_AVAILABLE = False
    def log_agent_message(*args, **kwargs): pass
    def log_user_input(*args, **kwargs): pass
    def log_error(*args, **kwargs): pass

# Import configuration
try:
    from .config import get_ai_config, create_genai_client, create_openai_client
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Try to import orchestrator for multi-agent mode
try:
    from .orchestrator import create_orchestrator, AgentMessage
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False
    AgentMessage = None  # Placeholder for type hints
    create_orchestrator = None

# Try to import google generative AI
try:
    from google import genai
    from google.genai import errors as genai_errors
    GENAI_AVAILABLE = True
except ImportError as e:
    genai = None
    genai_errors = None
    GENAI_AVAILABLE = False
    _genai_import_error = str(e)

# Try to import OpenAI (for LM Studio compatibility)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError as e:
    OpenAI = None
    OPENAI_AVAILABLE = False
    _openai_import_error = str(e)

# Global orchestrator instance for multi-agent mode
_orchestrator = None
_message_callback = None

# ============================================
# 会話履歴管理
# ============================================

class ConversationManager:
    """会話セッションの永続化を管理するクラス"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Args:
            project_root: プロジェクトルート。Noneの場合はカレントディレクトリ
        """
        self.project_root = project_root or Path.cwd()
        self.conv_dir = self.project_root / ".dcode" / "conversations"
        self.conv_dir.mkdir(parents=True, exist_ok=True)
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._session_file = self.conv_dir / f"{self.current_session}.jsonl"
        
    def save_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """メッセージをJSONL形式でファイルに保存"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }
        if metadata:
            entry["metadata"] = metadata
        
        try:
            with open(self._session_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[chat.py] Failed to save message: {e}", file=sys.stderr)
    
    def load_session(self, session_id: str) -> List[Dict]:
        """指定セッションの会話を読み込む"""
        session_file = self.conv_dir / f"{session_id}.jsonl"
        messages = []
        
        if session_file.exists():
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            messages.append(json.loads(line))
            except Exception as e:
                print(f"[chat.py] Failed to load session: {e}", file=sys.stderr)
        
        return messages
    
    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """セッション一覧を取得（新しい順）"""
        sessions = []
        
        try:
            for f in sorted(self.conv_dir.glob("*.jsonl"), reverse=True)[:limit]:
                session_id = f.stem
                # セッションIDから日時をパース
                try:
                    dt = datetime.strptime(session_id, "%Y%m%d_%H%M%S")
                    display_date = dt.strftime("%Y/%m/%d %H:%M")
                except ValueError:
                    display_date = session_id
                
                # 最初のメッセージを取得してプレビュー
                preview = ""
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        first_line = file.readline().strip()
                        if first_line:
                            first_msg = json.loads(first_line)
                            preview = first_msg.get("content", "")[:50]
                            if len(first_msg.get("content", "")) > 50:
                                preview += "..."
                except Exception:
                    pass
                
                sessions.append({
                    "session_id": session_id,
                    "display_date": display_date,
                    "preview": preview,
                    "file_path": str(f)
                })
        except Exception as e:
            print(f"[chat.py] Failed to list sessions: {e}", file=sys.stderr)
        
        return sessions
    
    def get_current_session_id(self) -> str:
        """現在のセッションIDを取得"""
        return self.current_session
    
    def set_project_root(self, project_root: Path) -> None:
        """プロジェクトルートを変更（ワークスペース切り替え時）"""
        self.project_root = project_root
        self.conv_dir = self.project_root / ".dcode" / "conversations"
        self.conv_dir.mkdir(parents=True, exist_ok=True)
        # セッションIDは維持


class ConversationHistory:
    """会話履歴を管理するクラス"""
    
    def __init__(self, max_messages: int = 50, max_tokens_estimate: int = 100000, 
                manager: Optional[ConversationManager] = None):
        """
        Args:
            max_messages: 保持する最大メッセージ数
            max_tokens_estimate: 推定最大トークン数（超えたら古いメッセージを削除）
            manager: 永続化マネージャー
        """
        self.messages: List[Dict[str, str]] = []
        self.max_messages = max_messages
        self.max_tokens_estimate = max_tokens_estimate
        self._manager = manager
    
    def set_manager(self, manager: ConversationManager) -> None:
        """永続化マネージャーを設定"""
        self._manager = manager
    
    def add_user_message(self, content: str) -> None:
        """ユーザーメッセージを追加"""
        self.messages.append({"role": "user", "content": content})
        self._trim_history()
        # ファイルに保存
        if self._manager:
            self._manager.save_message("user", content)
    
    def add_assistant_message(self, content: str) -> None:
        """アシスタント（AI）のメッセージを追加"""
        self.messages.append({"role": "assistant", "content": content})
        self._trim_history()
        # ファイルに保存
        if self._manager:
            self._manager.save_message("assistant", content)
    
    def add_system_result(self, content: str) -> None:
        """システム実行結果を追加（ファイル作成、コマンド結果など）"""
        # 実行結果はユーザーメッセージとして追加（AIには参考情報として見える）
        self.messages.append({"role": "user", "content": f"[システム実行結果]\n{content}"})
        self._trim_history()
        # ファイルに保存
        if self._manager:
            self._manager.save_message("system_result", content)
    
    def get_messages_for_api(self, system_prompt: str) -> List[Dict[str, str]]:
        """API呼び出し用のメッセージリストを取得"""
        return [{"role": "system", "content": system_prompt}] + self.messages
    
    def get_context_string(self) -> str:
        """Gemini API用のコンテキスト文字列を取得"""
        lines = []
        for msg in self.messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{role}: {msg['content']}")
        return "\n\n".join(lines)
    
    def _estimate_tokens(self) -> int:
        """トークン数を概算（4文字 ≈ 1トークン）"""
        total_chars = sum(len(m["content"]) for m in self.messages)
        return total_chars // 4
    
    def _trim_history(self) -> None:
        """履歴が制限を超えた場合、古いメッセージを削除"""
        # メッセージ数制限
        while len(self.messages) > self.max_messages:
            self.messages.pop(0)
        
        # トークン数制限（推定）
        while self._estimate_tokens() > self.max_tokens_estimate and len(self.messages) > 2:
            self.messages.pop(0)
    
    def clear(self) -> None:
        """履歴をクリア"""
        self.messages.clear()
    
    def load_from_session(self, session_id: str) -> bool:
        """指定セッションから履歴を復元"""
        if not self._manager:
            return False
        
        messages = self._manager.load_session(session_id)
        if not messages:
            return False
        
        self.messages.clear()
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # system_resultはユーザーメッセージとして扱う
            if role == "system_result":
                self.messages.append({"role": "user", "content": f"[システム実行結果]\n{content}"})
            elif role in ("user", "assistant"):
                self.messages.append({"role": role, "content": content})
        
        self._trim_history()
        print(f"[chat.py] Loaded {len(self.messages)} messages from session {session_id}", file=sys.stderr)
        return True
    
    def get_summary(self) -> str:
        """履歴の概要を取得（デバッグ用）"""
        return f"Messages: {len(self.messages)}, Est. tokens: {self._estimate_tokens()}"


# グローバルインスタンス
_conversation_manager: Optional[ConversationManager] = None
_conversation_history = ConversationHistory()


def init_conversation_manager(project_root: Optional[Path] = None) -> ConversationManager:
    """会話マネージャーを初期化"""
    global _conversation_manager, _conversation_history
    _conversation_manager = ConversationManager(project_root)
    _conversation_history.set_manager(_conversation_manager)
    print(f"[chat.py] Conversation manager initialized. Session: {_conversation_manager.current_session}", file=sys.stderr)
    return _conversation_manager


def get_conversation_manager() -> Optional[ConversationManager]:
    """会話マネージャーを取得"""
    global _conversation_manager
    return _conversation_manager


def get_conversation_history() -> ConversationHistory:
    """会話履歴インスタンスを取得"""
    global _conversation_history
    return _conversation_history


def clear_conversation_history() -> None:
    """会話履歴をクリア"""
    global _conversation_history
    _conversation_history.clear()
    print("[chat.py] Conversation history cleared", file=sys.stderr)


def load_previous_session(session_id: str) -> bool:
    """前のセッションから履歴を復元"""
    global _conversation_history
    return _conversation_history.load_from_session(session_id)


def list_conversation_sessions(limit: int = 20) -> List[Dict[str, Any]]:
    """会話セッション一覧を取得"""
    global _conversation_manager
    if _conversation_manager:
        return _conversation_manager.list_sessions(limit)
    return []


def add_system_result_to_history(result: str) -> None:
    """システム実行結果を会話履歴に追加（ファイル作成結果、コマンド出力など）"""
    global _conversation_history
    _conversation_history.add_system_result(result)
    print(f"[chat.py] Added system result to history: {result[:100]}...", file=sys.stderr)


def set_message_callback(callback: Callable[[dict], None]):
    """Set a callback for receiving agent messages."""
    global _message_callback
    _message_callback = callback


# ストリーミングコールバック（チャンクごとに呼ばれる）
_streaming_callback: Optional[Callable[[str, str, str], None]] = None

def set_streaming_callback(callback: Optional[Callable[[str, str, str], None]]):
    """
    Set a callback for receiving streaming chunks.
    
    Args:
        callback: Function(message_id, chunk, agent) called for each chunk
    """
    global _streaming_callback
    _streaming_callback = callback
    print(f"[chat.py] Streaming callback {'set' if callback else 'cleared'}", file=sys.stderr)


def _emit_streaming_chunk(message_id: str, chunk: str, agent: str = "D-code"):
    """Emit a streaming chunk through the callback."""
    global _streaming_callback
    if _streaming_callback and chunk:
        _streaming_callback(message_id, chunk, agent)


def _emit_agent_message(msg: Any):
    """Emit an agent message through the callback."""
    global _message_callback
    if _message_callback and msg is not None:
        _message_callback(msg.to_dict())


def _parse_retry_delay(error_message: str) -> float:
    """Extract retry delay from error message."""
    # Look for patterns like "retry in 33.026120094s" or "retryDelay': '33s'"
    patterns = [
        r'retry in (\d+\.?\d*)s',
        r'retryDelay[\'"]?\s*:\s*[\'"]?(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, str(error_message), re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 30.0  # Default retry delay


def _format_rate_limit_error(error_str: str) -> str:
    """Format a user-friendly rate limit error message."""
    retry_delay = _parse_retry_delay(error_str)
    
    # Check if it's a daily limit
    if 'PerDay' in error_str or 'limit: 0' in error_str:
        return (
            "⚠️ **Gemini API 日次クォータ超過**\n\n"
            "無料プランの1日あたりのリクエスト上限に達しました。\n\n"
            "**対処方法:**\n"
            "1. 明日（太平洋時間0時）まで待つ\n"
            "2. [Google AI Studio](https://aistudio.google.com/) で有料プランにアップグレード\n"
            "3. 別のAPIキーを使用する\n\n"
            f"_推奨待機時間: {retry_delay:.0f}秒_"
        )
    else:
        return (
            f"⚠️ **レート制限** - {retry_delay:.0f}秒後に自動リトライします...\n"
            "リクエスト頻度が高すぎます。少々お待ちください。"
        )


def chat_sync(message: str, api_key: Optional[str] = None, max_retries: int = 3, terminal_context: Optional[str] = None, message_id: str = "") -> str:
    """
    Send a message to AI and get a synchronous response.
    Supports both Gemini API and OpenAI-compatible APIs (like LM Studio).
    
    Args:
        message: The user's message/prompt
        api_key: Optional API key (uses env var if not provided)
        max_retries: Maximum number of retry attempts for rate limits
        terminal_context: Optional recent terminal output for context
        message_id: Optional message ID for streaming callbacks
    
    Returns:
        The AI's response as a string
    """
    # Debug: print to stderr for logging
    print(f"[chat.py] chat_sync called with message: {message[:50]}...", file=sys.stderr)
    
    # Log user input
    log_user_input(message, has_terminal_context=bool(terminal_context))
    
    # If terminal context is provided, append it to the message
    original_message = message
    if terminal_context and terminal_context.strip():
        print(f"[chat.py] Terminal context provided: {len(terminal_context)} chars", file=sys.stderr)
        message = f"""{message}

---
## 最近のターミナル出力（参考情報）
以下はユーザーのターミナルの最近の出力です。エラーがある場合は分析して修正案を提示してください：

```
{terminal_context}
```"""
    
    # Load configuration
    if CONFIG_AVAILABLE:
        config = get_ai_config()
        key = api_key or config.api_key
        model_name = config.chat_model
        base_url = config.api_base_url
        max_retries = config.max_retries
        api_backend = config.api_backend
        is_local = config.is_local_server()
    else:
        key = api_key or os.getenv("GEMINI_API_KEY", "")
        model_name = os.getenv("DCODE_CHAT_MODEL", "gemini-2.0-flash")
        base_url = os.getenv("GEMINI_API_BASE_URL") or os.getenv("DCODE_API_BASE_URL")
        api_backend = "auto"
        is_local = base_url and ("localhost" in base_url or "127.0.0.1" in base_url)
    
    # Resolve "auto" backend
    if api_backend == "auto":
        if is_local or (base_url and ("localhost" in base_url or "127.0.0.1" in base_url)):
            api_backend = "openai"
        else:
            api_backend = "gemini"
    
    # Force OpenAI backend if local server detected
    if is_local:
        api_backend = "openai"
    
    print(f"[chat.py] API key found: {'Yes' if key else 'No (local server mode)'}", file=sys.stderr)
    print(f"[chat.py] Model: {model_name}, Base URL: {base_url or 'default'}, Backend: {api_backend}, Is Local: {is_local}", file=sys.stderr)
    
    # Use OpenAI-compatible API for local servers (LM Studio, etc.)
    if api_backend == "openai" or is_local:
        if not OPENAI_AVAILABLE:
            err_msg = f"Error: openai package is not installed. Import error: {_openai_import_error}. Please run: pip install openai"
            print(f"[chat.py] {err_msg}", file=sys.stderr)
            return err_msg
        return _chat_openai(message, key, model_name, base_url, max_retries, message_id)
    else:
        # Gemini API requires API key
        if not GENAI_AVAILABLE:
            err_msg = f"Error: google-genai package is not installed. Import error: {_genai_import_error}. Please run: pip install google-genai"
            print(f"[chat.py] {err_msg}", file=sys.stderr)
            return err_msg
        if not key:
            err_msg = "Error: GEMINI_API_KEY is not set. Please set your API key in the environment or .env file."
            print(f"[chat.py] {err_msg}", file=sys.stderr)
            return err_msg
        return _chat_gemini(message, key, model_name, base_url, max_retries)


def _chat_openai(message: str, api_key: Optional[str], model_name: str, base_url: str, max_retries: int, message_id: str = "") -> str:
    """
    Send chat via OpenAI-compatible API (LM Studio, etc.).
    
    Supports streaming: if _streaming_callback is set, chunks are emitted in real-time.
    """
    global _conversation_history, _streaming_callback
    
    use_streaming = _streaming_callback is not None
    print(f"[chat.py] Using OpenAI-compatible API (LM Studio mode), streaming={use_streaming}", file=sys.stderr)
    print(f"[chat.py] Conversation history: {_conversation_history.get_summary()}", file=sys.stderr)
    
    # Create client with timeout settings for LM Studio
    # LM Studio can be slow, especially with larger models
    url = base_url
    if not url.endswith("/v1"):
        url = url.rstrip("/") + "/v1"
    
    try:
        # Set a longer timeout for local LM Studio (300 seconds = 5 minutes)
        client = OpenAI(
            api_key=api_key or "lm-studio",
            base_url=url,
            timeout=300.0,  # 5 minutes timeout for slow local models
        )
    except Exception as e:
        return f"Error: Failed to create OpenAI client: {e}"
    
    if client is None:
        return "Error: Failed to create OpenAI client. Make sure openai package is installed."
    
    system_prompt = """あなたはD-code、AI搭載のソフトウェア開発アシスタントです。

## 能力
- コードとアーキテクチャの説明
- 要件に基づくコード生成
- バグの修正とデバッグ
- 技術的な概念の説明
- ソフトウェアプロジェクトの計画
- コードの実行

## ファイル操作（重要）
ファイルを作成・編集する必要がある場合は、必ず以下の**正確な形式**でコードブロックを出力してください。
角括弧は使わず、言語名をそのまま記載してください：

```言語名::ファイルパス
ファイルの内容
```

### 具体例（この形式を厳守）：

```python::my_project/main.py
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
```

```markdown::my_project/README.md
# My Project
This is my project.
```

```json::my_project/package.json
{"name": "my-project", "version": "1.0.0"}
```

## コマンド実行（重要）
コードを実行する必要がある場合は、以下の形式でコマンドを出力してください：

```bash::run
コマンド
```

**重要**: コマンドは`projects`ディレクトリで実行されます。ファイルパスはプロジェクトフォルダを含めてください。

### コマンド実行の具体例：

Pythonファイルを実行する場合（プロジェクトフォルダを含める）：
```bash::run
python my_project/main.py
```

npmコマンドを実行する場合（プロジェクトフォルダに移動してから実行）：
```bash::run
cd my_project && npm install
```

複数のコマンドを実行する場合は、それぞれ別のブロックで出力してください。

## プロセス終了（重要）
実行中のプロセスを終了する必要がある場合、以下の形式で出力してください：

**会話履歴からPIDを確認して指定する方法（推奨）：**
会話履歴のターミナル実行結果から「PID: 12345」のような表記を探し、そのPIDを指定してください。

```bash::kill
12345
```

**すべてのプロセスを終了する場合：**
```bash::kill
all
```

**特定のターミナルIDを指定する場合：**
```bash::kill
term_123456
```

**重要**: ユーザーが「サーバーを停止して」「プロセスを終了して」と言った場合、必ず会話履歴を確認し、該当するプロセスのPIDを特定してから上記の形式で出力してください。

## ルール
- 簡潔で技術的に正確な回答を心がけてください
- ファイル作成時は上記の形式を**必ず**使用してください（角括弧[]は禁止）
- プロジェクト作成時は必要なすべてのファイルを生成してください
- 「実行して」「動かして」と言われたら、bash::run形式でコマンドを出力してください
- **コマンドの実行結果を予測して出力しないでください** - 実際に実行されます
- 以前の会話内容を参照して、文脈を理解してください
- エラーが発生した場合は、以前の会話から原因を分析してください
- 日本語で回答してください"""

    # 会話履歴にユーザーメッセージを追加
    _conversation_history.add_user_message(message)
    
    # API用のメッセージリストを取得（システムプロンプト + 履歴）
    messages = _conversation_history.get_messages_for_api(system_prompt)
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            print(f"[chat.py] Sending request to OpenAI API (attempt {attempt + 1}/{max_retries})...", file=sys.stderr)
            print(f"[chat.py] Using URL: {url}, Model: {model_name}, Messages: {len(messages)}, Streaming: {use_streaming}", file=sys.stderr)
            
            if use_streaming:
                # ストリーミングモード
                full_response = ""
                stream = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.7,
                    stream=True,
                )
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                        delta_content = chunk.choices[0].delta.content
                        full_response += delta_content
                        # ストリーミングコールバックを呼び出し
                        _emit_streaming_chunk(message_id, delta_content, "D-code")
                
                text = full_response
                print(f"[chat.py] Streaming completed, total length: {len(text)}", file=sys.stderr)
            else:
                # 非ストリーミングモード
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.7,
                )
                text = response.choices[0].message.content
                print(f"[chat.py] Response received, length: {len(text) if text else 0}", file=sys.stderr)
            
            # 会話履歴にAIの応答を追加
            if text:
                _conversation_history.add_assistant_message(text)
                log_agent_message("D-code", text, message_type="response", model=model_name, backend="openai")
            
            return text if text else "Error: Empty response from model"
            
        except Exception as e:
            error_str = str(e)
            last_error = error_str
            print(f"[chat.py] Error (attempt {attempt + 1}): {error_str}", file=sys.stderr)
            log_error(error_str, error_type="api_error", agent_name="D-code", attempt=attempt + 1)
            
            # Check for rate limit or connection errors
            if '429' in error_str or 'rate' in error_str.lower():
                retry_delay = _parse_retry_delay(error_str)
                if attempt < max_retries - 1:
                    wait_time = min(retry_delay + 1, 60)
                    print(f"[chat.py] Rate limited. Waiting {wait_time:.1f}s before retry...", file=sys.stderr)
                    time.sleep(wait_time)
                    continue
            elif 'connection' in error_str.lower() or 'refused' in error_str.lower():
                return f"⚠️ **接続エラー**\n\nLM Studioサーバーに接続できません。\n\n**確認事項:**\n1. LM Studioが起動しているか\n2. サーバーが開始されているか (Server → Start Server)\n3. ポートが正しいか ({base_url})\n\n_エラー: {error_str}_"
            break
    
    return f"Error communicating with OpenAI API: {last_error}"


def _chat_gemini(message: str, api_key: str, model_name: str, base_url: Optional[str], max_retries: int) -> str:
    """Send chat via Gemini API."""
    global _conversation_history
    
    print("[chat.py] Using Gemini API", file=sys.stderr)
    print(f"[chat.py] Conversation history: {_conversation_history.get_summary()}", file=sys.stderr)
    
    # Create client with optional custom endpoint
    if CONFIG_AVAILABLE:
        client = create_genai_client(api_key=api_key, base_url=base_url)
    else:
        client = genai.Client(api_key=api_key)
    
    if client is None:
        return "Error: Failed to create Gemini client"
    
    # System prompt for D-code assistant
    system_prompt = """あなたはD-code、AI搭載のソフトウェア開発アシスタントです。

## 能力
- コードとアーキテクチャの説明
- 要件に基づくコード生成
- バグの修正とデバッグ
- 技術的な概念の説明
- ソフトウェアプロジェクトの計画
- コードの実行

## ファイル操作（重要）
ファイルを作成・編集する必要がある場合は、必ず以下の**正確な形式**でコードブロックを出力してください。
角括弧は使わず、言語名をそのまま記載してください：

```言語名::ファイルパス
ファイルの内容
```

### 具体例（この形式を厳守）：

```python::my_project/main.py
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
```

```markdown::my_project/README.md
# My Project
This is my project.
```

## コマンド実行（重要）
コードを実行する必要がある場合は、以下の形式でコマンドを出力してください：

```bash::run
コマンド
```

### コマンド実行の具体例：

```bash::run
python my_project/main.py
```

## プロセス終了（重要）
実行中のプロセスを終了する必要がある場合、以下の形式で出力してください：

**会話履歴からPIDを確認して指定する方法（推奨）：**
会話履歴のターミナル実行結果から「PID: 12345」のような表記を探し、そのPIDを指定してください。

```bash::kill
12345
```

**すべてのプロセスを終了する場合：**
```bash::kill
all
```

**重要**: ユーザーが「サーバーを停止して」「プロセスを終了して」と言った場合、必ず会話履歴を確認し、該当するプロセスのPIDを特定してから上記の形式で出力してください。

## ルール
- 簡潔で技術的に正確な回答を心がけてください
- ファイル作成時は上記の形式を**必ず**使用してください（角括弧[]は禁止）
- プロジェクト作成時は必要なすべてのファイルを生成してください
- 「実行して」「動かして」と言われたら、bash::run形式でコマンドを出力してください
- **コマンドの実行結果を予測して出力しないでください** - 実際に実行されます
- 以前の会話内容を参照して、文脈を理解してください
- エラーが発生した場合は、以前の会話から原因を分析してください
- 日本語で回答してください"""

    # 会話履歴にユーザーメッセージを追加
    _conversation_history.add_user_message(message)
    
    # Gemini API用のコンテキスト文字列を作成
    conversation_context = _conversation_history.get_context_string()
    full_prompt = f"{system_prompt}\n\n## 会話履歴\n{conversation_context}"

    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Send message with system context and conversation history
            print(f"[chat.py] Sending request to Gemini API (attempt {attempt + 1}/{max_retries})...", file=sys.stderr)
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt
            )
            
            print(f"[chat.py] Response received, type: {type(response)}", file=sys.stderr)
            
            # Extract text from response
            text = None
            if hasattr(response, 'text'):
                text = response.text
                print(f"[chat.py] Response text length: {len(text)}", file=sys.stderr)
            elif hasattr(response, 'candidates') and response.candidates:
                text = response.candidates[0].content.parts[0].text
                print(f"[chat.py] Response from candidates, length: {len(text)}", file=sys.stderr)
            else:
                err_msg = f"Error: Unexpected response format from Gemini API: {response}"
                print(f"[chat.py] {err_msg}", file=sys.stderr)
                return err_msg
            
            # 会話履歴にAIの応答を追加
            if text:
                _conversation_history.add_assistant_message(text)
                log_agent_message("D-code", text, message_type="response", model=model_name, backend="gemini")
            
            return text if text else "Error: Empty response from model"
                
        except Exception as e:
            error_str = str(e)
            last_error = error_str
            print(f"[chat.py] Error (attempt {attempt + 1}): {error_str}", file=sys.stderr)
            
            # Check for rate limit errors (429)
            is_rate_limit = (
                '429' in error_str or 
                'RESOURCE_EXHAUSTED' in error_str or
                'quota' in error_str.lower() or
                'rate' in error_str.lower()
            )
            
            if is_rate_limit:
                retry_delay = _parse_retry_delay(error_str)
                
                # Check if it's a daily limit (limit: 0 indicates exhausted)
                if 'limit: 0' in error_str or 'PerDay' in error_str:
                    print(f"[chat.py] Daily quota exhausted", file=sys.stderr)
                    return _format_rate_limit_error(error_str)
                
                # For per-minute limits, retry after delay
                if attempt < max_retries - 1:
                    wait_time = min(retry_delay + 1, 60)  # Cap at 60 seconds
                    print(f"[chat.py] Rate limited. Waiting {wait_time:.1f}s before retry...", file=sys.stderr)
                    time.sleep(wait_time)
                    continue
                else:
                    return _format_rate_limit_error(error_str)
            else:
                # Non-rate-limit error, don't retry
                break
    
    # If we get here, all retries failed
    import traceback
    err_msg = f"Error communicating with Gemini API: {last_error}"
    print(f"[chat.py] {err_msg}", file=sys.stderr)
    print(f"[chat.py] Traceback: {traceback.format_exc()}", file=sys.stderr)
    return err_msg


def chat_orchestrated(message: str, workspace_path: Optional[str] = None) -> str:
    """
    Send a message to the multi-agent orchestrator.
    This enables the full PDCA cycle with multiple engineers.
    
    Args:
        message: The user's message/prompt
        workspace_path: Path to the workspace directory
    
    Returns:
        The orchestrator's response
    """
    global _orchestrator
    
    print(f"[chat.py] chat_orchestrated called with message: {message[:50]}...", file=sys.stderr)
    
    if not ORCHESTRATOR_AVAILABLE:
        print("[chat.py] Orchestrator not available, falling back to simple chat", file=sys.stderr)
        return chat_sync(message)
    
    try:
        # Initialize orchestrator if needed
        if _orchestrator is None:
            print("[chat.py] Initializing orchestrator...", file=sys.stderr)
            _orchestrator = create_orchestrator(
                on_message=_emit_agent_message,
                workspace_path=workspace_path,
            )
        
        # Process the request
        result = _orchestrator.process_user_request(message)
        return result
        
    except Exception as e:
        import traceback
        print(f"[chat.py] Orchestrator error: {e}", file=sys.stderr)
        print(f"[chat.py] Traceback: {traceback.format_exc()}", file=sys.stderr)
        # Fall back to simple chat on error
        return chat_sync(message)


def request_break():
    """Request the orchestrator to pause execution."""
    global _orchestrator
    if _orchestrator:
        _orchestrator.request_break()


# Export for use from Rust
__all__ = [
    "chat_sync", 
    "chat_orchestrated",
    "request_break",
    "set_message_callback",
    "get_conversation_history",
    "clear_conversation_history",
    "add_system_result_to_history",
    "GENAI_AVAILABLE", 
    "OPENAI_AVAILABLE",
    "ORCHESTRATOR_AVAILABLE",
]
