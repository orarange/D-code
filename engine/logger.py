"""
logger.py
=========
会話ログ保存機能

Engineer群（AIエージェント）の会話をJSONL形式で保存する。
デバッグ・監査用途で後から確認できるようにする。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from threading import Lock

# Singleton instance
_logger_instance: Optional['ConversationLogger'] = None
_logger_lock = Lock()


def get_logger(project_root: Optional[Path] = None) -> 'ConversationLogger':
    """グローバルなロガーインスタンスを取得"""
    global _logger_instance
    with _logger_lock:
        if _logger_instance is None:
            if project_root is None:
                # デフォルトはドキュメントフォルダ
                docs_dir = Path(os.environ.get('DCODE_WORKSPACE', ''))
                if not docs_dir.exists():
                    docs_dir = Path.home() / 'Documents' / 'D-code'
                project_root = docs_dir
            _logger_instance = ConversationLogger(project_root)
        return _logger_instance


class ConversationLogger:
    """
    AIエージェント間の会話をログに保存するクラス
    
    保存先: {project_root}/.dcode/logs/session_{timestamp}.jsonl
    """
    
    def __init__(self, project_root: Path):
        """
        Args:
            project_root: プロジェクトのルートディレクトリ
        """
        self.project_root = Path(project_root)
        self.log_dir = self.project_root / ".dcode" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"session_{self.current_session}.jsonl"
        self._lock = Lock()
        self._message_count = 0
        
        # セッション開始をログ
        self._log_entry({
            "type": "session_start",
            "timestamp": datetime.now().isoformat(),
            "session_id": self.current_session,
            "project_root": str(self.project_root),
        })
        
        print(f"[logger.py] ConversationLogger initialized: {self.log_file}", file=sys.stderr)
    
    def _log_entry(self, entry: Dict[str, Any]) -> None:
        """エントリをJSONLファイルに書き込む"""
        with self._lock:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
            except Exception as e:
                print(f"[logger.py] Error writing log: {e}", file=sys.stderr)
    
    def log_message(
        self, 
        agent_name: str, 
        message: str, 
        message_type: str = "chat",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        エージェントのメッセージをログに保存
        
        Args:
            agent_name: エージェント名 (e.g., "Worker_1", "Planner", "Orchestrator")
            message: メッセージ内容
            message_type: メッセージタイプ ("chat", "code", "command", "error", "thinking")
            metadata: 追加のメタデータ
        """
        self._message_count += 1
        
        entry = {
            "type": "agent_message",
            "timestamp": datetime.now().isoformat(),
            "sequence": self._message_count,
            "agent": agent_name,
            "message_type": message_type,
            "content": message,
            "metadata": metadata or {}
        }
        
        self._log_entry(entry)
    
    def log_user_input(self, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """ユーザー入力をログに保存"""
        self._message_count += 1
        
        entry = {
            "type": "user_input",
            "timestamp": datetime.now().isoformat(),
            "sequence": self._message_count,
            "content": message,
            "metadata": metadata or {}
        }
        
        self._log_entry(entry)
    
    def log_file_operation(
        self, 
        operation: str, 
        file_path: str, 
        success: bool,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        ファイル操作をログに保存
        
        Args:
            operation: 操作タイプ ("create", "update", "delete", "read")
            file_path: ファイルパス
            success: 成功したかどうか
            agent_name: 操作を行ったエージェント名
            metadata: 追加のメタデータ
        """
        entry = {
            "type": "file_operation",
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "file_path": file_path,
            "success": success,
            "agent": agent_name,
            "metadata": metadata or {}
        }
        
        self._log_entry(entry)
    
    def log_command_execution(
        self, 
        command: str, 
        output: Optional[str] = None,
        exit_code: Optional[int] = None,
        terminal_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        コマンド実行をログに保存
        
        Args:
            command: 実行したコマンド
            output: コマンド出力
            exit_code: 終了コード
            terminal_id: ターミナルID
            agent_name: コマンドを実行したエージェント名
            metadata: 追加のメタデータ
        """
        entry = {
            "type": "command_execution",
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "output": output,
            "exit_code": exit_code,
            "terminal_id": terminal_id,
            "agent": agent_name,
            "metadata": metadata or {}
        }
        
        self._log_entry(entry)
    
    def log_error(
        self, 
        error_message: str, 
        error_type: str = "general",
        agent_name: Optional[str] = None,
        stack_trace: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        エラーをログに保存
        
        Args:
            error_message: エラーメッセージ
            error_type: エラータイプ
            agent_name: エラーが発生したエージェント名
            stack_trace: スタックトレース
            metadata: 追加のメタデータ
        """
        entry = {
            "type": "error",
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "message": error_message,
            "agent": agent_name,
            "stack_trace": stack_trace,
            "metadata": metadata or {}
        }
        
        self._log_entry(entry)
    
    def log_task_update(
        self, 
        task_id: str, 
        status: str,
        agent_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        タスク状態更新をログに保存
        
        Args:
            task_id: タスクID
            status: 新しい状態 ("pending", "in_progress", "completed", "failed")
            agent_name: 更新を行ったエージェント名
            metadata: 追加のメタデータ
        """
        entry = {
            "type": "task_update",
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "status": status,
            "agent": agent_name,
            "metadata": metadata or {}
        }
        
        self._log_entry(entry)
    
    def end_session(self, summary: Optional[Dict[str, Any]] = None) -> None:
        """セッション終了をログに記録"""
        entry = {
            "type": "session_end",
            "timestamp": datetime.now().isoformat(),
            "session_id": self.current_session,
            "total_messages": self._message_count,
            "summary": summary or {}
        }
        
        self._log_entry(entry)
    
    def get_session_logs(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        セッションのログを取得
        
        Args:
            session_id: セッションID（省略時は現在のセッション）
        
        Returns:
            ログエントリのリスト
        """
        if session_id is None:
            session_id = self.current_session
        
        log_file = self.log_dir / f"session_{session_id}.jsonl"
        
        if not log_file.exists():
            return []
        
        logs = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        logs.append(json.loads(line))
        except Exception as e:
            print(f"[logger.py] Error reading logs: {e}", file=sys.stderr)
        
        return logs
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """利用可能なセッション一覧を取得"""
        sessions = []
        
        for log_file in self.log_dir.glob("session_*.jsonl"):
            session_id = log_file.stem.replace("session_", "")
            stat = log_file.stat()
            sessions.append({
                "session_id": session_id,
                "file_path": str(log_file),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        
        # 新しい順にソート
        sessions.sort(key=lambda x: x["session_id"], reverse=True)
        return sessions


# 便利な関数
def log_agent_message(agent_name: str, message: str, message_type: str = "chat", **kwargs):
    """グローバルロガーでエージェントメッセージを記録"""
    logger = get_logger()
    logger.log_message(agent_name, message, message_type, kwargs if kwargs else None)


def log_user_input(message: str, **kwargs):
    """グローバルロガーでユーザー入力を記録"""
    logger = get_logger()
    logger.log_user_input(message, kwargs if kwargs else None)


def log_file_op(operation: str, file_path: str, success: bool, **kwargs):
    """グローバルロガーでファイル操作を記録"""
    logger = get_logger()
    logger.log_file_operation(operation, file_path, success, metadata=kwargs if kwargs else None)


def log_command(command: str, **kwargs):
    """グローバルロガーでコマンド実行を記録"""
    logger = get_logger()
    logger.log_command_execution(command, **kwargs)


def log_error(error_message: str, **kwargs):
    """グローバルロガーでエラーを記録"""
    logger = get_logger()
    logger.log_error(error_message, **kwargs)
