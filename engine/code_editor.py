"""
code_editor.py
==============
Diff-based file editing utilities for D-code.
Supports partial updates using unified diff format.
"""

import difflib
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any


class CodeEditor:
    """
    差分ベースのコード編集を行うクラス
    ファイル全体を書き換えずに、変更部分のみを更新する
    """
    
    def __init__(self):
        self.last_error: Optional[str] = None
    
    def create_diff(
        self, 
        original: str, 
        modified: str, 
        filename: str = "file"
    ) -> str:
        """
        2つのテキスト間のunified diffを生成
        
        Args:
            original: 元のテキスト
            modified: 変更後のテキスト
            filename: ファイル名（diff出力用）
            
        Returns:
            unified diff形式の文字列
        """
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        # 最後の行が改行で終わっていない場合の処理
        if original_lines and not original_lines[-1].endswith('\n'):
            original_lines[-1] += '\n'
        if modified_lines and not modified_lines[-1].endswith('\n'):
            modified_lines[-1] += '\n'
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm=""
        )
        
        return "".join(diff)
    
    def apply_diff(self, original: str, diff_text: str) -> Tuple[bool, str]:
        """
        unified diffをテキストに適用
        
        Args:
            original: 元のテキスト
            diff_text: unified diff形式のパッチ
            
        Returns:
            (成功フラグ, 結果テキストまたはエラーメッセージ)
        """
        try:
            lines = original.splitlines(keepends=True)
            if lines and not lines[-1].endswith('\n'):
                lines[-1] += '\n'
            
            # diffをパース
            hunks = self._parse_unified_diff(diff_text)
            
            if not hunks:
                self.last_error = "No valid hunks found in diff"
                return False, original
            
            # 逆順に適用（後ろから前へ）でインデックスずれを防ぐ
            hunks.sort(key=lambda h: h['start_line'], reverse=True)
            
            for hunk in hunks:
                lines = self._apply_hunk(lines, hunk)
                if lines is None:
                    return False, self.last_error or "Hunk application failed"
            
            return True, "".join(lines)
            
        except Exception as e:
            self.last_error = str(e)
            return False, str(e)
    
    def _parse_unified_diff(self, diff_text: str) -> List[Dict[str, Any]]:
        """
        unified diffをパースしてhunkのリストを返す
        """
        hunks = []
        current_hunk = None
        
        for line in diff_text.splitlines(keepends=True):
            # @@ -start,count +start,count @@ header
            hunk_header = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            
            if hunk_header:
                if current_hunk:
                    hunks.append(current_hunk)
                
                current_hunk = {
                    'start_line': int(hunk_header.group(1)),
                    'old_count': int(hunk_header.group(2) or 1),
                    'new_start': int(hunk_header.group(3)),
                    'new_count': int(hunk_header.group(4) or 1),
                    'remove_lines': [],
                    'add_lines': [],
                    'context_before': [],
                    'context_after': [],
                }
            elif current_hunk is not None:
                if line.startswith('-') and not line.startswith('---'):
                    current_hunk['remove_lines'].append(line[1:])
                elif line.startswith('+') and not line.startswith('+++'):
                    current_hunk['add_lines'].append(line[1:])
                elif line.startswith(' '):
                    # Context line
                    if not current_hunk['remove_lines'] and not current_hunk['add_lines']:
                        current_hunk['context_before'].append(line[1:])
                    else:
                        current_hunk['context_after'].append(line[1:])
        
        if current_hunk:
            hunks.append(current_hunk)
        
        return hunks
    
    def _apply_hunk(self, lines: List[str], hunk: Dict[str, Any]) -> Optional[List[str]]:
        """
        単一のhunkをテキストに適用
        """
        start = hunk['start_line'] - 1  # 0-indexed
        
        # 境界チェック
        if start < 0:
            self.last_error = f"Invalid hunk start line: {hunk['start_line']}"
            return None
        
        if start > len(lines):
            # ファイル末尾への追加
            start = len(lines)
        
        # コンテキスト検証（オプション）
        # 削除行と置換
        end = start + len(hunk['remove_lines'])
        
        # 削除して追加
        result = lines[:start] + hunk['add_lines'] + lines[end:]
        
        return result
    
    def apply_search_replace(
        self, 
        content: str, 
        search: str, 
        replace: str,
        occurrence: int = 1
    ) -> Tuple[bool, str, int]:
        """
        検索置換方式でテキストを編集
        
        Args:
            content: 元のテキスト
            search: 検索文字列
            replace: 置換文字列
            occurrence: 何番目の出現を置換するか (0=全て, 1=最初)
            
        Returns:
            (成功フラグ, 結果テキスト, 置換回数)
        """
        if not search:
            return False, content, 0
        
        if occurrence == 0:
            # 全置換
            new_content = content.replace(search, replace)
            count = content.count(search)
            return count > 0, new_content, count
        else:
            # N番目の出現のみ置換
            index = -1
            for i in range(occurrence):
                index = content.find(search, index + 1)
                if index == -1:
                    return False, content, 0
            
            new_content = content[:index] + replace + content[index + len(search):]
            return True, new_content, 1
    
    def apply_line_edit(
        self,
        content: str,
        line_number: int,
        new_line: str
    ) -> Tuple[bool, str]:
        """
        特定の行を編集
        
        Args:
            content: 元のテキスト
            line_number: 行番号 (1-indexed)
            new_line: 新しい行の内容
            
        Returns:
            (成功フラグ, 結果テキスト)
        """
        lines = content.splitlines(keepends=True)
        
        if line_number < 1 or line_number > len(lines):
            return False, content
        
        # 改行を保持
        if lines[line_number - 1].endswith('\n') and not new_line.endswith('\n'):
            new_line += '\n'
        
        lines[line_number - 1] = new_line
        return True, "".join(lines)
    
    def insert_lines(
        self,
        content: str,
        after_line: int,
        new_lines: List[str]
    ) -> str:
        """
        指定行の後に新しい行を挿入
        
        Args:
            content: 元のテキスト
            after_line: この行の後に挿入 (0=先頭)
            new_lines: 挿入する行のリスト
            
        Returns:
            結果テキスト
        """
        lines = content.splitlines(keepends=True)
        
        # 改行を追加
        formatted_lines = []
        for line in new_lines:
            if not line.endswith('\n'):
                line += '\n'
            formatted_lines.append(line)
        
        insert_pos = min(after_line, len(lines))
        result = lines[:insert_pos] + formatted_lines + lines[insert_pos:]
        
        return "".join(result)
    
    def delete_lines(
        self,
        content: str,
        start_line: int,
        end_line: int
    ) -> str:
        """
        指定範囲の行を削除
        
        Args:
            content: 元のテキスト
            start_line: 開始行 (1-indexed, inclusive)
            end_line: 終了行 (1-indexed, inclusive)
            
        Returns:
            結果テキスト
        """
        lines = content.splitlines(keepends=True)
        
        start = max(0, start_line - 1)
        end = min(len(lines), end_line)
        
        result = lines[:start] + lines[end:]
        
        return "".join(result)


# グローバルエディターインスタンス
_editor = CodeEditor()


def get_editor() -> CodeEditor:
    """エディターインスタンスを取得"""
    return _editor


def create_diff(original: str, modified: str, filename: str = "file") -> str:
    """差分を生成"""
    return _editor.create_diff(original, modified, filename)


def apply_diff(original: str, diff_text: str) -> Tuple[bool, str]:
    """差分を適用"""
    return _editor.apply_diff(original, diff_text)


def apply_search_replace(
    content: str, 
    search: str, 
    replace: str,
    occurrence: int = 1
) -> Tuple[bool, str, int]:
    """検索置換"""
    return _editor.apply_search_replace(content, search, replace, occurrence)


def apply_line_edit(content: str, line_number: int, new_line: str) -> Tuple[bool, str]:
    """行編集"""
    return _editor.apply_line_edit(content, line_number, new_line)


def insert_lines(content: str, after_line: int, new_lines: List[str]) -> str:
    """行挿入"""
    return _editor.insert_lines(content, after_line, new_lines)


def delete_lines(content: str, start_line: int, end_line: int) -> str:
    """行削除"""
    return _editor.delete_lines(content, start_line, end_line)


# ファイル操作のラッパー関数
def edit_file_with_diff(file_path: Path, diff_text: str) -> Tuple[bool, str]:
    """
    ファイルに差分を適用して保存
    
    Args:
        file_path: 対象ファイルのパス
        diff_text: unified diff形式のパッチ
        
    Returns:
        (成功フラグ, メッセージ)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original = f.read()
        
        success, result = apply_diff(original, diff_text)
        
        if success:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(result)
            return True, f"Successfully patched {file_path}"
        else:
            return False, f"Failed to apply patch: {result}"
            
    except FileNotFoundError:
        return False, f"File not found: {file_path}"
    except Exception as e:
        return False, f"Error editing file: {e}"


def edit_file_with_search_replace(
    file_path: Path,
    search: str,
    replace: str,
    occurrence: int = 1
) -> Tuple[bool, str]:
    """
    ファイルに検索置換を適用して保存
    
    Args:
        file_path: 対象ファイルのパス
        search: 検索文字列
        replace: 置換文字列
        occurrence: 何番目の出現を置換するか
        
    Returns:
        (成功フラグ, メッセージ)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        success, result, count = apply_search_replace(content, search, replace, occurrence)
        
        if success:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(result)
            return True, f"Replaced {count} occurrence(s) in {file_path}"
        else:
            return False, f"Search string not found in {file_path}"
            
    except FileNotFoundError:
        return False, f"File not found: {file_path}"
    except Exception as e:
        return False, f"Error editing file: {e}"


if __name__ == "__main__":
    # テスト
    original = """def hello():
    print("Hello, World!")
    return True

def goodbye():
    print("Goodbye!")
"""
    
    modified = """def hello():
    print("Hello, D-code!")
    return True

def greet(name):
    print(f"Hello, {name}!")
    return True

def goodbye():
    print("Goodbye!")
"""
    
    # 差分を生成
    diff = create_diff(original, modified, "test.py")
    print("Generated diff:")
    print(diff)
    print()
    
    # 差分を適用
    success, result = apply_diff(original, diff)
    print(f"Apply diff success: {success}")
    if success:
        print("Result:")
        print(result)
    
    # 検索置換テスト
    success, result, count = apply_search_replace(original, 'Hello, World!', 'Hello, D-code!')
    print(f"\nSearch/Replace success: {success}, count: {count}")
    if success:
        print("Result:")
        print(result)
