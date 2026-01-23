

## コンテキスト情報

あなたはD-codeというマルチエージェントAI開発プラットフォームのターミナルシステムを実装します。

**プロジェクト構成:**
- **Rust (src/)**: pyo3でPythonを埋め込み、wryでWebViewを表示
- **Python (engine/)**: AI エージェント、FastAPI + WebSocket通信
- **React (ui/)**: Discord風3カラムUI、Tailwind CSS、Monaco Editor

**既存の仕様 (tech.md):**
- AIが `bash::run <command>` 形式で出力するとコマンドを実行
- 現在は単発のコマンド実行のみ対応
- ターミナル出力は一度きりの表示

**実装目標:**
PowerShellプロセスを埋め込み、AIとユーザーがリアルタイムで出力を監視・入力できるインタラクティブなターミナルを実装する。

---

## 実装要件

### 1. Rust側の実装 (`src/terminal.rs` を新規作成)

**要求仕様:**
- `std::process::Command` でPowerShell.exeを子プロセスとして起動
- stdin/stdout/stderrをパイプで接続し、非同期で読み書き
- `tokio::sync::mpsc` チャネルで入出力をストリーミング
- WebSocket経由でUI/Pythonと通信

**気を付けること:**
- ⚠️ **バッファリングを無効化**: PowerShellの出力が遅延しないよう、`-NoLogo` オプションを使用
- ⚠️ **非同期処理の徹底**: `tokio::spawn` で各ストリーム（stdin/stdout/stderr）を別タスクで処理
- ⚠️ **エラーハンドリング**: プロセスが予期せず終了した場合の再起動ロジック
- ⚠️ **PIDの保存**: プロセス終了機能のために `child.id()` でPIDを取得・保存
- ⚠️ **クロスプラットフォーム対応**: WindowsはPowerShell、macOS/Linuxはbashを使い分け

**必要な依存関係 (Cargo.toml):**
```toml
[dependencies]
tokio = { version = "1.0", features = ["full"] }
uuid = { version = "1.0", features = ["v4"] }
```

**実装すべき構造:**
```rust
pub struct Terminal {
    process: Child,
    stdin_tx: mpsc::Sender<String>,
    stdout_rx: mpsc::Receiver<String>,
    stderr_rx: mpsc::Receiver<String>,
    pid: u32,
}

impl Terminal {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error>>;
    pub async fn execute(&mut self, command: String) -> Result<(), Box<dyn std::error::Error>>;
    pub async fn recv_output(&mut self) -> Option<(String, bool)>; // (出力, is_error)
    pub fn get_pid(&self) -> u32;
}
```

---

### 2. Rust側のWebSocket統合 (`src/main.rs` または `src/bridge.rs` を修正)

**要求仕様:**
- UIから `terminal_input` メッセージを受信したらTerminalに送信
- Terminalからのstdout/stderrを `terminal_output` メッセージとしてUIに送信
- Pythonエンジンにも同じ出力を送信（AI監視用）

**気を付けること:**
- ⚠️ **メッセージ型の統一**: JSON形式で `{ "type": "terminal_input", "data": { "command": "..." } }` のように明確に定義
- ⚠️ **並行処理**: WebSocketメッセージ受信とTerminal出力受信を `tokio::select!` で並列処理
- ⚠️ **デッドロックの回避**: 送信と受信を別タスクで実行

**実装例:**
```rust
// WebSocketメッセージ受信ループ内
match msg_type.as_str() {
    "terminal_input" => {
        let command = msg["data"]["command"].as_str().unwrap();
        terminal.execute(command.to_string()).await?;
    }
    _ => {}
}

// Terminal出力をポーリング（別タスク）
tokio::spawn(async move {
    while let Some((line, is_error)) = terminal.recv_output().await {
        let msg = json!({
            "type": "terminal_output",
            "data": {
                "line": line,
                "is_error": is_error,
                "timestamp": chrono::Utc::now().to_rfc3339()
            }
        });
        // UIとPythonの両方に送信
        webview.send_message(&msg);
        python_bridge.send_to_engine(&msg);
    }
});
```

---

### 3. UI側の実装 (`ui/src/components/Terminal.tsx`)

**要求仕様:**
- Xterm.jsを使用してターミナルUIを実装
- WebSocketから `terminal_output` を受信して表示
- ユーザーのキーボード入力を `terminal_input` としてRust側に送信

**気を付けること:**
- ⚠️ **Xterm.jsのインストール**: `npm install xterm @types/xterm` を実行
- ⚠️ **CSSのインポート**: `import 'xterm/css/xterm.css'` を忘れずに
- ⚠️ **メモリリーク対策**: `useEffect` のクリーンアップで `term.dispose()` を呼ぶ
- ⚠️ **改行コード**: Windowsの `\r\n` に対応するため `\r\n` で出力

**実装例:**
```typescript
import { useEffect, useRef } from 'react';
import { Terminal as XTerm } from 'xterm';
import 'xterm/css/xterm.css';

export function TerminalPanel() {
  const termRef = useRef<XTerm | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    if (!containerRef.current) return;
    
    const term = new XTerm({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Consolas, monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
      },
    });
    
    term.open(containerRef.current);
    termRef.current = term;
    
    // WebSocket接続（既存のuseWebSocketフックを使用）
    const ws = window.__DCODE_WS__;
    
    ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'terminal_output') {
        const line = msg.data.line;
        term.write(line + '\r\n');
      }
    });
    
    // ユーザー入力をRust側に送信
    term.onData((data) => {
      ws.send(JSON.stringify({
        type: 'terminal_input',
        data: { command: data }
      }));
    });
    
    return () => {
      term.dispose();
    };
  }, []);
  
  return (
    <div 
      ref={containerRef} 
      className="h-full w-full bg-[#1e1e1e]"
    />
  );
}
```

---

### 4. Python側の実装 (`engine/terminal_handler.py` を新規作成)

**要求仕様:**
- Rust側からWebSocket経由でターミナル出力を受信
- AIエージェントが出力を監視できるようにバッファリング
- エラー検知時に自律復旧トリガーを発火

**気を付けること:**
- ⚠️ **エラーパターンの定義**: "Error", "Exception", "Failed" などのキーワードでエラー検知
- ⚠️ **バッファサイズの制限**: 最新1000行のみ保持してメモリ使用量を抑える
- ⚠️ **非同期処理**: `asyncio` で他の処理をブロックしない

**実装例:**
```python
from typing import Callable, List
import asyncio
from datetime import datetime

class TerminalHandler:
    """AIがターミナル出力を監視・制御するためのハンドラー"""
    
    def __init__(self, websocket_send: Callable):
        self.ws_send = websocket_send
        self.output_buffer: List[str] = []
        self.max_buffer_size = 1000
        self.error_keywords = ["Error", "Exception", "Failed", "fatal"]
        
    async def on_output_received(self, line: str, is_error: bool):
        """ターミナル出力を受信したときの処理"""
        # バッファに追加
        self.output_buffer.append(line)
        if len(self.output_buffer) > self.max_buffer_size:
            self.output_buffer.pop(0)
        
        # エラー検知
        if is_error or any(keyword in line for keyword in self.error_keywords):
            await self._handle_error_detected(line)
    
    async def _handle_error_detected(self, error_line: str):
        """エラー検知時の処理"""
        # Orchestratorに通知して自律復旧を開始
        await self.ws_send({
            "type": "error_detected",
            "data": {
                "error": error_line,
                "context": self.get_recent_output(10),
                "timestamp": datetime.now().isoformat()
            }
        })
    
    def get_recent_output(self, lines: int = 50) -> List[str]:
        """直近のターミナル出力を取得（AI思考用）"""
        return self.output_buffer[-lines:]
```

---

## 統合テスト手順

実装完了後、以下の手順でテストしてください：

1. **Rustのビルド**: `cargo build --release`
2. **UIのビルド**: `cd ui && npm run build`
3. **D-codeを起動**: 実行ファイルを起動
4. **ターミナルでコマンド実行**:
   - UIのターミナルに `Get-Date` と入力
   - リアルタイムで日時が表示されることを確認
5. **エラー検知テスト**:
   - `Get-NonexistentCommand` と入力
   - エラーメッセージが赤色で表示されることを確認
   - Python側でエラーが検知されることを確認

---

## トラブルシューティング

### 問題: PowerShellの出力が表示されない
**原因**: バッファリングによる遅延
**解決策**: PowerShell起動時に `-NoLogo -NoExit` オプションを追加

### 問題: 日本語が文字化けする
**原因**: エンコーディングの不一致
**解決策**: PowerShell起動時に `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8` を実行

### 問題: WebSocketの接続が切れる
**原因**: 長時間の無通信
**解決策**: 定期的にping/pongメッセージを送信

---

この実装が完了したら、次のメッセージで「Phase 1-2: コマンドツリー管理システム」のプロンプトを送信してください。

---
---

# 📌 Phase 1-2: コマンドツリー管理システム

## コンテキスト情報

Phase 1-1でPowerShellターミナルの基本機能が実装されました。
次は、親子関係を持つコマンド実行を管理するシステムを構築します。

**実装目標:**
`cd backend` (親) → `npm install` (子) のように、親コマンドが実行されたターミナルで子コマンドを実行できるようにする。

---

## 実装要件

### 1. Rust側の実装 (`src/command_tree.rs` を新規作成)

**要求仕様:**
- コマンドをツリー構造で管理
- 各コマンドに一意のIDを割り当て
- 親コマンドと同じターミナルで子コマンドを実行

**気を付けること:**
- ⚠️ **UUIDの生成**: `uuid` クレートで一意なIDを生成
- ⚠️ **所有権の管理**: `HashMap` で管理する際の借用エラーに注意
- ⚠️ **スレッドセーフ**: `Arc<Mutex<CommandTree>>` で複数タスクから安全にアクセス
- ⚠️ **孤児コマンドの検知**: 親コマンドが失敗した場合、子コマンドを実行しない

**実装すべき構造:**
```rust
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, PartialEq)]
pub enum CommandStatus {
    Pending,
    Running,
    Completed,
    Failed,
}

#[derive(Debug, Clone)]
pub struct CommandNode {
    pub id: String,
    pub command: String,
    pub terminal_id: String,
    pub parent_id: Option<String>,
    pub children: Vec<String>,
    pub status: CommandStatus,
}

pub struct CommandTree {
    nodes: HashMap<String, CommandNode>,
    terminal_commands: HashMap<String, Vec<String>>, // terminal_id -> command_ids
}

impl CommandTree {
    pub fn new() -> Self;
    pub fn add_command(&mut self, command: String, terminal_id: String, parent_id: Option<String>) -> String;
    pub fn update_status(&mut self, command_id: &str, status: CommandStatus);
    pub fn get_terminal_id(&self, command_id: &str) -> Option<String>;
    pub fn can_execute_child(&self, parent_id: &str) -> bool; // 親が成功したかチェック
}
```

**実装例:**
```rust
impl CommandTree {
    pub fn add_command(&mut self, command: String, terminal_id: String, parent_id: Option<String>) -> String {
        let id = Uuid::new_v4().to_string();
        
        let node = CommandNode {
            id: id.clone(),
            command,
            terminal_id: terminal_id.clone(),
            parent_id: parent_id.clone(),
            children: vec![],
            status: CommandStatus::Pending,
        };
        
        // 親ノードに子を追加
        if let Some(parent) = &parent_id {
            if let Some(parent_node) = self.nodes.get_mut(parent) {
                parent_node.children.push(id.clone());
            }
        }
        
        self.nodes.insert(id.clone(), node);
        self.terminal_commands
            .entry(terminal_id)
            .or_insert_with(Vec::new)
            .push(id.clone());
        
        id
    }
    
    pub fn can_execute_child(&self, parent_id: &str) -> bool {
        self.nodes
            .get(parent_id)
            .map(|n| n.status == CommandStatus::Completed)
            .unwrap_or(false)
    }
}
```

---

### 2. Rust側のメイン統合 (`src/main.rs`)

**要求仕様:**
- `CommandTree` をグローバル状態として保持
- AIが `bash::run` 形式でコマンドを出力した際、親子関係をパース
- 親コマンドが完了してから子コマンドを実行

**気を付けること:**
- ⚠️ **正規表現でパース**: `bash::run cd backend && npm install` のような連続コマンドを検出
- ⚠️ **非同期実行**: 子コマンドの待機中も他の処理をブロックしない
- ⚠️ **エラー伝播**: 親が失敗したら子は実行せず、Failedステータスを設定

**実装例:**
```rust
use regex::Regex;
use std::sync::Arc;
use tokio::sync::Mutex;

lazy_static::lazy_static! {
    static ref COMMAND_TREE: Arc<Mutex<CommandTree>> = Arc::new(Mutex::new(CommandTree::new()));
}

async fn handle_bash_command(command: String, terminal_id: String) {
    let re = Regex::new(r"bash::run\s+(.+?)(?:\s+&&\s+(.+))?").unwrap();
    
    if let Some(caps) = re.captures(&command) {
        let parent_cmd = caps.get(1).unwrap().as_str();
        let child_cmd = caps.get(2).map(|m| m.as_str());
        
        let mut tree = COMMAND_TREE.lock().await;
        
        // 親コマンドを追加
        let parent_id = tree.add_command(
            parent_cmd.to_string(),
            terminal_id.clone(),
            None
        );
        
        // 親コマンドを実行
        tree.update_status(&parent_id, CommandStatus::Running);
        drop(tree); // ロック解放
        
        let result = execute_in_terminal(&terminal_id, parent_cmd).await;
        
        let mut tree = COMMAND_TREE.lock().await;
        if result.is_ok() {
            tree.update_status(&parent_id, CommandStatus::Completed);
            
            // 子コマンドがあれば実行
            if let Some(child) = child_cmd {
                if tree.can_execute_child(&parent_id) {
                    let child_id = tree.add_command(
                        child.to_string(),
                        terminal_id.clone(),
                        Some(parent_id.clone())
                    );
                    
                    tree.update_status(&child_id, CommandStatus::Running);
                    drop(tree);
                    
                    let child_result = execute_in_terminal(&terminal_id, child).await;
                    
                    let mut tree = COMMAND_TREE.lock().await;
                    tree.update_status(&child_id, 
                        if child_result.is_ok() { 
                            CommandStatus::Completed 
                        } else { 
                            CommandStatus::Failed 
                        }
                    );
                }
            }
        } else {
            tree.update_status(&parent_id, CommandStatus::Failed);
        }
    }
}
```

---

### 3. UI側の実装 (既存のTerminalPanelを拡張)

**要求仕様:**
- コマンド実行前に親子関係を視覚的に表示
- ツリー構造でコマンド履歴を表示

**気を付けること:**
- ⚠️ **インデント表示**: 子コマンドは親より1段階インデント
- ⚠️ **ステータスアイコン**: 実行中は⏳、完了は✅、失敗は❌を表示
- ⚠️ **リアルタイム更新**: WebSocketで `command_status_update` を受信して即座に反映

**実装例:**
```typescript
interface CommandTreeNode {
  id: string;
  command: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  children: CommandTreeNode[];
}

function CommandTreeView({ nodes }: { nodes: CommandTreeNode[] }) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return '⏳';
      case 'completed': return '✅';
      case 'failed': return '❌';
      default: return '⏸️';
    }
  };
  
  return (
    <div className="font-mono text-sm">
      {nodes.map(node => (
        <div key={node.id}>
          <div className="flex items-center gap-2">
            <span>{getStatusIcon(node.status)}</span>
            <span className="text-gray-300">{node.command}</span>
          </div>
          {node.children.length > 0 && (
            <div className="ml-6">
              <CommandTreeView nodes={node.children} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## 統合テスト手順

1. **連続コマンドのテスト**:
   - `bash::run cd ui && npm install` を実行
   - `cd ui` が成功してから `npm install` が実行されることを確認

2. **エラー伝播のテスト**:
   - `bash::run cd nonexistent && npm install` を実行
   - `cd` が失敗したため `npm install` が実行されないことを確認

3. **ツリー表示のテスト**:
   - UIでコマンド履歴がツリー形式で表示されることを確認

---

この実装が完了したら、次のメッセージで「Phase 1-3: PID管理とプロセス制御」のプロンプトを送信してください。

---
---

# 📌 Phase 1-3: PID管理とプロセス制御

## コンテキスト情報

Phase 1-2でコマンドツリー管理が実装されました。
次は、実行中のプロセスをPIDで追跡し、AIが自然言語指示から対象を推測して終了できるようにします。

**実装目標:**
- 実行中の全プロセスをグローバルに管理
- ユーザーが「サーバーを止めて」と言ったら、AIが該当プロセスを推測して終了

---

## 実装要件

### 1. Rust側の実装 (`src/process_manager.rs` を新規作成)

**要求仕様:**
- 実行中のプロセスをPIDで追跡
- キーワード検索でプロセスを特定
- Windows/macOS/Linuxでプロセスを終了

**気を付けること:**
- ⚠️ **クロスプラットフォーム対応**: Windowsは `taskkill`、Unix系は `SIGTERM` を使用
- ⚠️ **強制終了のリスク**: データ損失を防ぐため、まず `SIGTERM` を送り、5秒後に `SIGKILL`
- ⚠️ **権限エラー**: 管理者権限が必要なプロセスの終了に失敗した場合のエラーメッセージ
- ⚠️ **孤児プロセスの検知**: 親プロセスが終了しても子プロセスが残る場合の処理

**必要な依存関係 (Cargo.toml):**
```toml
[dependencies]
sysinfo = "0.30"
nix = "0.27" # Unix系プラットフォーム用
chrono = "0.4"
```

**実装例:**
```rust
use std::collections::HashMap;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone)]
pub struct ProcessInfo {
    pub pid: u32,
    pub command: String,
    pub terminal_id: String,
    pub started_at: DateTime<Utc>,
}

pub struct ProcessManager {
    processes: HashMap<u32, ProcessInfo>,
}

impl ProcessManager {
    pub fn new() -> Self {
        Self {
            processes: HashMap::new(),
        }
    }
    
    pub fn register(&mut self, pid: u32, command: String, terminal_id: String) {
        self.processes.insert(pid, ProcessInfo {
            pid,
            command,
            terminal_id,
            started_at: Utc::now(),
        });
    }
    
    pub fn unregister(&mut self, pid: u32) {
        self.processes.remove(&pid);
    }
    
    pub fn find_by_keyword(&self, keyword: &str) -> Vec<u32> {
        self.processes
            .iter()
            .filter(|(_, info)| {
                info.command.to_lowercase().contains(&keyword.to_lowercase())
            })
            .map(|(pid, _)| *pid)
            .collect()
    }
    
    pub fn kill(&mut self, pid: u32) -> Result<(), String> {
        #[cfg(target_os = "windows")]
        {
            let output = std::process::Command::new("taskkill")
                .args(&["/PID", &pid.to_string(), "/F"])
                .output()
                .map_err(|e| format!("Failed to kill process: {}", e))?;
            
            if !output.status.success() {
                return Err(format!("taskkill failed: {}", 
                    String::from_utf8_lossy(&output.stderr)));
            }
        }
        
        #[cfg(not(target_os = "windows"))]
        {
            use nix::sys::signal::{kill, Signal};
            use nix::unistd::Pid;
            
            // まずSIGTERMを送信（優雅な終了）
            kill(Pid::from_raw(pid as i32), Signal::SIGTERM)
                .map_err(|e| format!("Failed to send SIGTERM: {}", e))?;
            
            // 5秒待っても終了しなければSIGKILL
            std::thread::sleep(std::time::Duration::from_secs(5));
            let _ = kill(Pid::from_raw(pid as i32), Signal::SIGKILL);
        }
        
        self.unregister(pid);
        Ok(())
    }
    
    pub fn list_all(&self) -> Vec<ProcessInfo> {
        self.processes.values().cloned().collect()
    }
}
```

---

### 2. Python側の実装 (`engine/process_controller.py` を新規作成)

**要求仕様:**
- ユーザーの自然言語指示からプロセスを推測
- LLMでキーワードを抽出
- Rust側のProcessManagerと連携

**気を付けること:**
- ⚠️ **曖昧性の処理**: 候補が複数ある場合は確認ダイアログを表示
- ⚠️ **誤終了の防止**: 重要なシステムプロセスは終了候補から除外
- ⚠️ **ログ記録**: プロセス終了の履歴をデバッグログに記録

**実装例:**
```python
from typing import List, Optional
import json

class ProcessController:
    """AIがプロセスを制御するためのコントローラー"""
    
    def __init__(self, llm, websocket_send):
        self.llm = llm
        self.ws_send = websocket_send
        
    async def kill_by_description(self, user_instruction: str):
        """
        ユーザーの指示からプロセスを推測して終了
        
        例:
        - 「サーバーを止めて」→ "npm run dev" を終了
        - 「ビルドを中断して」→ "cargo build" を終了
        """
        # LLMでキーワード抽出
        keywords = await self._extract_keywords(user_instruction)
        
        # Rust側に問い合わせ
        response = await self.ws_send({
            "type": "find_processes",
            "data": {"keywords": keywords}
        })
        
        candidates = response.get("candidates", [])
        
        if len(candidates) == 0:
            await self.ws_send({
                "type": "chat_message",
                "data": {
                    "agent": "System",
                    "message": "該当するプロセスが見つかりませんでした。"
                }
            })
        elif len(candidates) == 1:
            # 候補が1つなら自動終了
            pid = candidates[0]["pid"]
            await self._kill_process(pid, candidates[0]["command"])
        else:
            # 複数候補があれば確認
            await self.ws_send({
                "type": "confirm_kill",
                "data": {"candidates": candidates}
            })
    
    async def _extract_keywords(self, instruction: str) -> List[str]:
        """LLMで指示からキーワードを抽出"""
        prompt = f"""
以下のユーザー指示から、終了すべきプロセスのキーワードを抽出してください。
キーワードはJSON配列で返してください。

ユーザー指示: {instruction}

例:
- 「サーバーを止めて」→ ["server", "npm", "dev"]
- 「ビルドを中断」→ ["build", "cargo", "rustc"]

JSON配列のみを返してください:
"""
        
        response = await self.llm.generate(prompt)
        keywords = json.loads(response)
        return keywords
    
    async def _kill_process(self, pid: int, command: str):
        """プロセスを終了"""
        await self.ws_send({
            "type": "kill_process",
            "data": {"pid": pid}
        })
        
        await self.ws_send({
            "type": "chat_message",
            "data": {
                "agent": "System",
                "message": f"プロセス「{command}」(PID: {pid})を終了しました。"
            }
        })
```

---

### 3. UI側の実装 (`ui/src/components/ProcessList.tsx` を新規作成)

**要求仕様:**
- 実行中のプロセス一覧を表示
- 各プロセスに「終了」ボタンを配置
- 複数候補がある場合の確認ダイアログ

**気を付けること:**
- ⚠️ **リアルタイム更新**: 新しいプロセスが起動/終了したら即座に反映
- ⚠️ **アイコン表示**: プロセスの種類に応じたアイコン（npm→📦、cargo→🦀、python→🐍）
- ⚠️ **危険なプロセスの警告**: システムプロセスを終了しようとした場合の警告

**実装例:**
```typescript
import { Trash2 } from 'lucide-react';

interface Process {
  pid: number;
  command: string;
  terminal_id: string;
  started_at: string;
}

export function ProcessList() {
  const [processes, setProcesses] = useState<Process[]>([]);
  const { ws } = useWebSocket();
  
  useEffect(() => {
    ws?.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      
      if (msg.type === 'process_list_update') {
        setProcesses(msg.data.processes);
      }
    });
    
    // 初回ロード
    ws?.send(JSON.stringify({ type: 'get_process_list' }));
  }, [ws]);
  
  const handleKill = (pid: number) => {
    if (confirm(`プロセス (PID: ${pid}) を終了しますか?`)) {
      ws?.send(JSON.stringify({
        type: 'kill_process',
        data: { pid }
      }));
    }
  };
  
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-400">実行中のプロセス</h3>
      {processes.map(proc => (
        <div 
          key={proc.pid} 
          className="flex items-center justify-between p-2 bg-gray-800 rounded"
        >
          <div className="flex-1">
            <div className="text-sm font-mono text-gray-200">
              {proc.command}
            </div>
            <div className="text-xs text-gray-500">
              PID: {proc.pid} | Started: {new Date(proc.started_at).toLocaleTimeString()}
            </div>
          </div>
          <button
            onClick={() => handleKill(proc.pid)}
            className="p-2 hover:bg-red-600 rounded transition"
          >
            <Trash2 size={16} />
          </button>
        </div>
      ))}
    </div>
  );
}
```

---

## 統合テスト手順

1. **プロセス登録のテスト**:
   - `bash::run npm run dev` を実行
   - ProcessListにプロセスが表示されることを確認

2. **キーワード検索のテスト**:
   - チャットで「サーバーを止めて」と入力
   - AIが `npm run dev` を推測して終了することを確認

3. **複数候補のテスト**:
   - `npm run dev` と `npm run build` を同時実行
   - 「npmを止めて」と入力
   - 確認ダイアログが表示されることを確認

---

この実装が完了したら、次のメッセージで「Phase 1-4: ユーザーによる直接コマンド入力」のプロンプトを送信してください。

---
---

# 📌 Phase 1-4: ユーザーによる直接コマンド入力

## コンテキスト情報

Phase 1-3でPID管理が完了しました。
最後に、ユーザーがターミナルに直接コマンドを入力できる機能を実装します。

**実装目標:**
- AIが作成したターミナルにユーザーが直接入力可能
- 入力履歴の保存と補完機能

---

## 実装要件

### 1. UI側の実装 (既存のTerminalPanelを拡張)

**要求仕様:**
- Xterm.jsでキーボード入力を有効化
- 入力したコマンドをRust側に送信
- コマンド履歴の保存と↑↓キーでの呼び出し

**気を付けること:**
- ⚠️ **Enterキーの処理**: `\r` を検出してコマンド実行
- ⚠️ **特殊キーの処理**: Ctrl+C（中断）、Ctrl+D（EOF）をサポート
- ⚠️ **履歴の保存**: LocalStorageに最大100件保存
- ⚠️ **プロンプト表示**: `PS C:\>` のようなプロンプトを表示

**実装例:**
```typescript
export function TerminalPanel() {
  const termRef = useRef<XTerm | null>(null);
  const commandHistory = useRef<string[]>([]);
  const historyIndex = useRef<number>(-1);
  const currentInput = useRef<string>('');
  
  useEffect(() => {
    const term = new XTerm({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Consolas, monospace',
    });
    
    term.open(containerRef.current!);
    termRef.current = term;
    
    // プロンプト表示
    term.write('PS C:\\> ');
    
    // キーボード入力処理
    term.onData((data) => {
      const code = data.charCodeAt(0);
      
      // Enter: コマンド実行
      if (code === 13) {
        term.write('\r\n');
        executeCommand(currentInput.current);
        commandHistory.current.push(currentInput.current);
        currentInput.current = '';
        historyIndex.current = -1;
        term.write('PS C:\\> ');
      }
      // Backspace: 文字削除
      else if (code === 127) {
        if (currentInput.current.length > 0) {
          currentInput.current = currentInput.current.slice(0, -1);
          term.write('\b \b');
        }
      }
      // ↑キー: 履歴を遡る
      else if (data === '\x1b[A') {
        if (historyIndex.current < commandHistory.current.length - 1) {
          historyIndex.current++;
          const cmd = commandHistory.current[
            commandHistory.current.length - 1 - historyIndex.current
          ];
          clearCurrentLine(term);
          term.write('PS C:\\> ' + cmd);
          currentInput.current = cmd;
        }
      }
      // ↓キー: 履歴を進む
      else if (data === '\x1b[B') {
        if (historyIndex.current > 0) {
          historyIndex.current--;
          const cmd = commandHistory.current[
            commandHistory.current.length - 1 - historyIndex.current
          ];
          clearCurrentLine(term);
          term.write('PS C:\\> ' + cmd);
          currentInput.current = cmd;
        } else if (historyIndex.current === 0) {
          historyIndex.current = -1;
          clearCurrentLine(term);
          term.write('PS C:\\> ');
          currentInput.current = '';
        }
      }
      // 通常の文字入力
      else if (code >= 32 && code < 127) {
        currentInput.current += data;
        term.write(data);
      }
    });
  }, []);
  
  const clearCurrentLine = (term: XTerm) => {
    term.write('\r\x1b[K');
  };
  
  const executeCommand = (cmd: string) => {
    ws?.send(JSON.stringify({
      type: 'terminal_input',
      data: { command: cmd }
    }));
  };
  
  return <div ref={containerRef} className="h-full" />;
}
```

---

## 統合テスト手順

1. **直接入力のテスト**:
   - ターミナルに `Get-Date` と入力してEnter
   - 日時が表示されることを確認

2. **履歴機能のテスト**:
   - 複数のコマンドを実行
   - ↑キーで過去のコマンドが表示されることを確認

3. **AIとの共存テスト**:
   - AIが `bash::run` でコマンド実行中にユーザーが入力
   - 両方の出力が正しく表示されることを確認

---

**Phase 1完了！** 次は「Phase 2-1: リアルタイム思考ストリーミング」のプロンプトを送信してください。

---
---

# 📌 Phase 2-1: リアルタイム思考ストリーミング

## コンテキスト情報

Phase 1でターミナルシステムが完成しました。
次は、AIの思考プロセスをGemini/ChatGPTのようにリアルタイムでストリーミング表示します。

**実装目標:**
- AIの応答を1文字ずつ（またはチャンク単位で）表示
- ストリーミング中は「考え中...」インジケータを表示

---

## 実装要件

### 1. Python側の実装 (`engine/agents/base_agent.py` を修正)

**要求仕様:**
- LLMのストリーミングAPIを使用
- 各チャンクをWebSocket経由でUIに送信
- ストリーミング完了後にメッセージ全体を保存

**気を付けること:**
- ⚠️ **API選択**: OpenAI互換APIは `stream=True`、Gemini APIは `stream()` メソッドを使用
- ⚠️ **エラーハンドリング**: ストリーミング中断時の処理
- ⚠️ **レート制限**: 送信頻度を制限してWebSocketの負荷を軽減（50ms間隔など）

**実装例:**
```python
import asyncio
from typing import AsyncGenerator

class BaseAgent:
    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        """AIの応答をストリーミング"""
        try:
            # OpenAI互換API
            if self.api_backend == "openai":
                response = await self.llm.astream(prompt)
                async for chunk in response:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                        await asyncio.sleep(0.05)  # レート制限
            
            # Gemini API
            elif self.api_backend == "gemini":
                response = await self.llm.generate_content_async(
                    prompt,
                    stream=True
                )
                async for chunk in response:
                    if chunk.text:
                        yield chunk.text
                        await asyncio.sleep(0.05)
        
        except Exception as e:
            yield f"\n[Error: {str(e)}]"
    
    async def think_and_respond(self, user_input: str):
        """思考プロセスをストリーミング表示しながら応答"""
        full_response = ""
        
        async for chunk in self.stream_response(user_input):
            full_response += chunk
            
            # UIに送信
            await self.ws_send({
                "type": "ai_thinking",
                "data": {
                    "agent": self.name,
                    "chunk": chunk,
                    "timestamp": datetime.now().isoformat()
                }
            })
        
        # 完了通知
        await self.ws_send({
            "type": "ai_complete",
            "data": {
                "agent": self.name,
                "full_response": full_response
            }
        })
```

---

### 2. UI側の実装 (`ui/src/components/ChatPanel.tsx` を修正)

**要求仕様:**
- ストリーミング中のメッセージを別枠で表示
- 1文字ずつ追加されるアニメーション
- 完了後に通常のメッセージ履歴に追加

**気を付けること:**
- ⚠️ **パフォーマンス**: 頻繁なDOM更新を避けるため、`useRef` で管理
- ⚠️ **スクロール自動追従**: 新しいチャンクが追加されたら自動スクロール
- ⚠️ **マークダウンレンダリング**: コードブロックやリストを適切に表示

**実装例:**
```typescript
import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  const [isStreaming, setIsStreaming] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    ws?.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      
      if (msg.type === 'ai_thinking') {
        setIsStreaming(true);
        setStreamingMessage(prev => prev + msg.data.chunk);
      } 
      else if (msg.type === 'ai_complete') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          agent: msg.data.agent,
          content: msg.data.full_response,
          timestamp: new Date().toISOString()
        }]);
        setStreamingMessage('');
        setIsStreaming(false);
      }
    });
  }, [ws]);
  
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);
  
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className="flex gap-3">
            <div className="flex-shrink-0">
              <AgentAvatar agent={msg.agent} />
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-gray-300">
                {msg.agent}
              </div>
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
            </div>
          </div>
        ))}
        
        {isStreaming && (
          <div className="flex gap-3 animate-fade-in">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
                <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
              </div>
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-gray-300 mb-1">
                AI (思考中...)
              </div>
              <div className="prose prose-invert prose-sm max-w-none">
                <ReactMarkdown>{streamingMessage}</ReactMarkdown>
                <span className="inline-block w-2 h-4 bg-blue-500 animate-pulse ml-1" />
              </div>
            </div>
          </div>
        )}
        
        <div ref={chatEndRef} />
      </div>
    </div>
  );
}
