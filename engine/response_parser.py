"""
response_parser.py
==================
AI応答パーサー

AIの出力を以下の3つのカテゴリに分離する：
1. ファイル作成命令 (`言語::パス` 形式) → ファイルシステムへ直接書き込み
2. ターミナル実行命令 (`bash::run` 形式) → ターミナルで実行
3. ユーザーメッセージ → チャットUIに表示

ユーザー向けメッセージにはコード全文を含めないようにする。
"""

import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from enum import Enum


class ContentType(Enum):
    """コンテンツタイプ"""
    FILE_OPERATION = "file"      # ファイル作成/編集
    COMMAND = "command"          # ターミナルコマンド
    USER_MESSAGE = "message"     # ユーザー向けメッセージ


@dataclass
class FileOperation:
    """ファイル操作"""
    path: str
    content: str
    language: str


@dataclass
class CommandOperation:
    """コマンド実行操作"""
    command: str
    shell: str = "bash"  # bash, powershell, cmd


@dataclass
class ParsedResponse:
    """パース済みAI応答"""
    # ユーザー向けメッセージ（コード全文を除いたもの）
    user_message: str
    # ファイル操作リスト
    file_operations: List[FileOperation] = field(default_factory=list)
    # コマンド実行リスト
    commands: List[CommandOperation] = field(default_factory=list)
    # 元の応答（デバッグ用）
    raw_response: str = ""


class ResponseParser:
    """AI応答パーサー"""
    
    # ファイル作成パターン: ```言語::パス
    # 例: ```python::my_project/main.py
    FILE_PATTERN = re.compile(
        r'```(\w+)::([^\n]+)\n(.*?)```',
        re.DOTALL
    )
    
    # コマンド実行パターン: ```bash::run または ```shell::run など
    COMMAND_PATTERN = re.compile(
        r'```(?:bash|shell|cmd|powershell)::run\n(.*?)```',
        re.DOTALL
    )
    
    # プロセス終了パターン: ```bash::kill など
    KILL_PATTERN = re.compile(
        r'```(?:bash|shell|cmd|powershell)::kill\n(.*?)```',
        re.DOTALL
    )
    
    # 通常のコードブロック（ファイル作成でもコマンドでもない）
    REGULAR_CODE_BLOCK = re.compile(
        r'```(\w*)\n(.*?)```',
        re.DOTALL
    )
    
    def __init__(self):
        pass
    
    def parse(self, response: str) -> ParsedResponse:
        """
        AI応答をパースして、ファイル操作/コマンド/ユーザーメッセージに分離
        
        Args:
            response: AI応答テキスト
        
        Returns:
            ParsedResponse オブジェクト
        """
        result = ParsedResponse(
            user_message="",
            file_operations=[],
            commands=[],
            raw_response=response
        )
        
        # 作業用テキスト（ユーザーメッセージを構築）
        user_text = response
        
        # 1. ファイル操作を抽出
        for match in self.FILE_PATTERN.finditer(response):
            language = match.group(1)
            path = match.group(2).strip()
            content = match.group(3)
            
            # bash::run や shell::run, bash::kill などは除外（これはコマンド/プロセス操作）
            if language.lower() in ('bash', 'shell', 'cmd', 'powershell') and path.lower() in ('run', 'kill'):
                continue
            
            result.file_operations.append(FileOperation(
                path=path,
                content=content,
                language=language
            ))
            
            # ユーザーメッセージからファイル内容を除去し、通知に置換
            replacement = f"\n📄 **ファイル作成:** `{path}`\n"
            user_text = user_text.replace(match.group(0), replacement)
        
        # 2. コマンドを抽出
        for match in self.COMMAND_PATTERN.finditer(response):
            command = match.group(1).strip()
            if command:
                result.commands.append(CommandOperation(command=command))
                
                # ユーザーメッセージからコマンドブロックを除去し、通知に置換
                replacement = f"\n⚡ **コマンド実行:** `{command[:50]}{'...' if len(command) > 50 else ''}`\n"
                user_text = user_text.replace(match.group(0), replacement)
        
        # 2.5. プロセス終了パターンを処理
        for match in self.KILL_PATTERN.finditer(response):
            target = match.group(1).strip()
            # ユーザーメッセージからkillブロックを除去し、通知に置換
            replacement = f"\n🛑 **プロセス終了:** `{target}`\n"
            user_text = user_text.replace(match.group(0), replacement)
        
        # 3. 残りの通常コードブロックを簡略化（任意）
        # 大きなコードブロックは要約に置換することも可能だが、
        # 説明用のコードは残す（30行未満は残す）
        for match in self.REGULAR_CODE_BLOCK.finditer(user_text):
            language = match.group(1) or "code"
            content = match.group(2)
            line_count = content.count('\n') + 1
            
            # 30行以上のコードブロックは要約に置換
            if line_count > 30:
                preview_lines = content.split('\n')[:5]
                preview = '\n'.join(preview_lines)
                replacement = f"```{language}\n{preview}\n... ({line_count - 5}行省略)\n```"
                user_text = user_text.replace(match.group(0), replacement)
        
        # 4. ユーザーメッセージをクリーンアップ
        user_text = self._cleanup_message(user_text)
        result.user_message = user_text
        
        return result
    
    def _cleanup_message(self, text: str) -> str:
        """メッセージをクリーンアップ"""
        # 連続する空行を2行までに制限
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        # 先頭と末尾の空白を除去
        text = text.strip()
        return text
    
    def extract_file_operations(self, response: str) -> List[FileOperation]:
        """ファイル操作のみを抽出"""
        return self.parse(response).file_operations
    
    def extract_commands(self, response: str) -> List[CommandOperation]:
        """コマンドのみを抽出"""
        return self.parse(response).commands
    
    def get_user_message(self, response: str) -> str:
        """ユーザー向けメッセージのみを取得"""
        return self.parse(response).user_message


# グローバルインスタンス
_parser: Optional[ResponseParser] = None


def get_parser() -> ResponseParser:
    """グローバルパーサーインスタンスを取得"""
    global _parser
    if _parser is None:
        _parser = ResponseParser()
    return _parser


def parse_ai_response(response: str) -> ParsedResponse:
    """AI応答をパース（便利関数）"""
    return get_parser().parse(response)


def extract_user_message(response: str) -> str:
    """ユーザー向けメッセージを抽出（便利関数）"""
    return get_parser().get_user_message(response)


# テスト用
if __name__ == "__main__":
    test_response = '''こんにちは！シンプルなPythonプロジェクトを作成しましょう。

以下のファイルを作成します：

```python::my_project/main.py
def main():
    print("Hello, World!")
    
if __name__ == "__main__":
    main()
```

```markdown::my_project/README.md
# My Project

This is a sample project.
```

プロジェクトを実行するには：

```bash::run
python my_project/main.py
```

以上でプロジェクトの作成が完了しました！
'''
    
    result = parse_ai_response(test_response)
    
    print("=== User Message ===")
    print(result.user_message)
    print("\n=== File Operations ===")
    for op in result.file_operations:
        print(f"  {op.language}::{op.path} ({len(op.content)} chars)")
    print("\n=== Commands ===")
    for cmd in result.commands:
        print(f"  {cmd.command}")
