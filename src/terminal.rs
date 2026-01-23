//! terminal.rs - PowerShell埋め込みターミナル管理
//!
//! PowerShellプロセスを子プロセスとして起動し、
//! stdin/stdout/stderrをパイプで接続してインタラクティブに操作する。
//! 
//! Phase 1-1: リアルタイム出力ストリーミング対応
//! Phase 1-2: コマンドツリー管理（将来統合予定）
//! Phase 1-3: PID管理とプロセス制御（将来統合予定）

// Suppress warnings for code that will be used in future phases
#![allow(dead_code)]

use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::sync::mpsc::{self, Receiver};
use std::thread;

/// 出力イベントの型
#[derive(Debug, Clone)]
pub enum OutputEvent {
    /// 標準出力の1行
    Stdout(String),
    /// 標準エラー出力の1行
    Stderr(String),
    /// プロセス終了（終了コード）
    Exit(Option<i32>),
}

/// ストリーミング対応ターミナルインスタンス
pub struct StreamingTerminal {
    /// ターミナルID
    pub id: String,
    /// PowerShellプロセス
    process: Option<Child>,
    /// stdin への書き込み用
    stdin: Option<std::process::ChildStdin>,
    /// 出力イベント受信チャネル
    output_rx: Option<Receiver<OutputEvent>>,
    /// 実行中かどうか
    pub is_running: Arc<Mutex<bool>>,
    /// 作業ディレクトリ
    pub working_dir: PathBuf,
    /// プロセスID
    pub pid: Option<u32>,
}

impl StreamingTerminal {
    /// 新しいストリーミングターミナルを作成
    pub fn new(id: String, working_dir: PathBuf) -> Result<Self, String> {
        // 作業ディレクトリを作成
        let _ = std::fs::create_dir_all(&working_dir);
        
        // PowerShellを起動（インタラクティブモード）
        let mut process = Command::new("powershell")
            .args([
                "-NoLogo",
                "-NoProfile",
                "-NoExit",
            ])
            .current_dir(&working_dir)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn PowerShell: {}", e))?;
        
        let pid = process.id();
        let stdin = process.stdin.take();
        let stdout = process.stdout.take();
        let stderr = process.stderr.take();
        
        // 出力イベント用チャネル
        let (tx, rx) = mpsc::channel::<OutputEvent>();
        let is_running = Arc::new(Mutex::new(true));
        let is_running_stdout = is_running.clone();
        let is_running_stderr = is_running.clone();
        
        // stdout リーダースレッド
        if let Some(stdout) = stdout {
            let tx_stdout = tx.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stdout);
                for line in reader.lines() {
                    if let Ok(running) = is_running_stdout.lock() {
                        if !*running {
                            break;
                        }
                    }
                    match line {
                        Ok(l) => {
                            let _ = tx_stdout.send(OutputEvent::Stdout(l));
                        }
                        Err(_) => break,
                    }
                }
            });
        }
        
        // stderr リーダースレッド
        if let Some(stderr) = stderr {
            let tx_stderr = tx.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines() {
                    if let Ok(running) = is_running_stderr.lock() {
                        if !*running {
                            break;
                        }
                    }
                    match line {
                        Ok(l) => {
                            let _ = tx_stderr.send(OutputEvent::Stderr(l));
                        }
                        Err(_) => break,
                    }
                }
            });
        }
        
        Ok(Self {
            id,
            process: Some(process),
            stdin,
            output_rx: Some(rx),
            is_running,
            working_dir,
            pid: Some(pid),
        })
    }
    
    /// コマンドを送信
    pub fn send_command(&mut self, command: &str) -> Result<(), String> {
        if let Some(ref mut stdin) = self.stdin {
            writeln!(stdin, "{}", command)
                .map_err(|e| format!("Failed to write to stdin: {}", e))?;
            stdin.flush()
                .map_err(|e| format!("Failed to flush stdin: {}", e))?;
            Ok(())
        } else {
            Err("stdin not available".to_string())
        }
    }
    
    /// 出力を受信（ノンブロッキング）
    pub fn try_recv_output(&self) -> Option<OutputEvent> {
        if let Some(ref rx) = self.output_rx {
            rx.try_recv().ok()
        } else {
            None
        }
    }
    
    /// 出力を受信（タイムアウト付き）
    pub fn recv_output_timeout(&self, timeout: std::time::Duration) -> Option<OutputEvent> {
        if let Some(ref rx) = self.output_rx {
            rx.recv_timeout(timeout).ok()
        } else {
            None
        }
    }
    
    /// プロセスを終了
    pub fn kill(&mut self) -> Result<(), String> {
        if let Ok(mut running) = self.is_running.lock() {
            *running = false;
        }
        
        if let Some(ref mut process) = self.process {
            process.kill()
                .map_err(|e| format!("Failed to kill process: {}", e))
        } else {
            Ok(())
        }
    }
    
    /// プロセスIDを取得
    pub fn get_pid(&self) -> Option<u32> {
        self.pid
    }
    
    /// プロセスが実行中かどうか
    pub fn is_alive(&mut self) -> bool {
        if let Some(ref mut process) = self.process {
            match process.try_wait() {
                Ok(Some(_)) => false,
                Ok(None) => true,
                Err(_) => false,
            }
        } else {
            false
        }
    }
}

impl Drop for StreamingTerminal {
    fn drop(&mut self) {
        let _ = self.kill();
    }
}

/// コマンドを非同期で実行し、出力をコールバックで受け取る
pub fn execute_command_async<F>(
    command: &str,
    working_dir: &PathBuf,
    on_output: F,
) -> Result<u32, String>
where
    F: Fn(String, bool) + Send + Clone + 'static,
{
    let command = command.to_string();
    let working_dir = working_dir.clone();
    
    // 作業ディレクトリを作成
    let _ = std::fs::create_dir_all(&working_dir);
    
    // PowerShellプロセスを起動
    let mut process = Command::new("powershell")
        .args(["-NoProfile", "-Command", &command])
        .current_dir(&working_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn PowerShell: {}", e))?;
    
    let pid = process.id();
    
    // stdoutを読み取るスレッド
    if let Some(stdout) = process.stdout.take() {
        let on_output_clone = on_output.clone();
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines().flatten() {
                on_output_clone(line, false);
            }
        });
    }
    
    // stderrを読み取るスレッド
    if let Some(stderr) = process.stderr.take() {
        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines().flatten() {
                on_output(line, true);
            }
        });
    }
    
    // プロセス終了を待つスレッド
    thread::spawn(move || {
        let _ = process.wait();
    });
    
    Ok(pid)
}

/// プロセスIDでプロセスを終了
pub fn kill_process(pid: u32) -> Result<(), String> {
    #[cfg(windows)]
    {
        // Windowsでは taskkill を使用
        let output = Command::new("taskkill")
            .args(["/PID", &pid.to_string(), "/F", "/T"])
            .output()
            .map_err(|e| format!("Failed to execute taskkill: {}", e))?;
        
        if output.status.success() {
            Ok(())
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            Err(format!("taskkill failed: {}", stderr))
        }
    }
    
    #[cfg(not(windows))]
    {
        use std::os::unix::process::CommandExt;
        
        // Unix系ではkillを使用
        let output = Command::new("kill")
            .args(["-9", &pid.to_string()])
            .output()
            .map_err(|e| format!("Failed to execute kill: {}", e))?;
        
        if output.status.success() {
            Ok(())
        } else {
            let stderr = String::from_utf8_lossy(&output.stderr);
            Err(format!("kill failed: {}", stderr))
        }
    }
}

/// 実行中のコマンドを追跡するための構造体
pub struct RunningCommand {
    pub id: String,
    pub pid: u32,
    pub command: String,
    pub terminal_id: String,
    pub started_at: std::time::Instant,
}

/// グローバルな実行中コマンドのトラッカー
pub struct CommandTracker {
    pub commands: Mutex<HashMap<String, RunningCommand>>,
}

impl CommandTracker {
    pub fn new() -> Self {
        Self {
            commands: Mutex::new(HashMap::new()),
        }
    }
    
    pub fn add(&self, id: String, pid: u32, command: String, terminal_id: String) {
        if let Ok(mut commands) = self.commands.lock() {
            commands.insert(id.clone(), RunningCommand {
                id,
                pid,
                command,
                terminal_id,
                started_at: std::time::Instant::now(),
            });
        }
    }
    
    pub fn remove(&self, id: &str) -> Option<RunningCommand> {
        if let Ok(mut commands) = self.commands.lock() {
            commands.remove(id)
        } else {
            None
        }
    }
    
    pub fn get_by_terminal(&self, terminal_id: &str) -> Vec<RunningCommand> {
        if let Ok(commands) = self.commands.lock() {
            commands.values()
                .filter(|c| c.terminal_id == terminal_id)
                .cloned()
                .collect()
        } else {
            Vec::new()
        }
    }
    
    pub fn kill_by_terminal(&self, terminal_id: &str) -> Vec<Result<(), String>> {
        let commands = self.get_by_terminal(terminal_id);
        commands.iter()
            .map(|c| kill_process(c.pid))
            .collect()
    }
}

impl Clone for RunningCommand {
    fn clone(&self) -> Self {
        Self {
            id: self.id.clone(),
            pid: self.pid,
            command: self.command.clone(),
            terminal_id: self.terminal_id.clone(),
            started_at: self.started_at,
        }
    }
}

lazy_static::lazy_static! {
    pub static ref COMMAND_TRACKER: CommandTracker = CommandTracker::new();
    /// グローバルなストリーミングターミナルマネージャー
    pub static ref STREAMING_TERMINALS: Mutex<HashMap<String, StreamingTerminal>> = Mutex::new(HashMap::new());
}

/// ストリーミングターミナルを作成
pub fn create_streaming_terminal(id: &str, working_dir: &PathBuf) -> Result<u32, String> {
    let terminal = StreamingTerminal::new(id.to_string(), working_dir.clone())?;
    let pid = terminal.get_pid().unwrap_or(0);
    
    if let Ok(mut terminals) = STREAMING_TERMINALS.lock() {
        terminals.insert(id.to_string(), terminal);
    }
    
    Ok(pid)
}

/// ストリーミングターミナルにコマンドを送信
pub fn send_to_streaming_terminal(id: &str, command: &str) -> Result<(), String> {
    if let Ok(mut terminals) = STREAMING_TERMINALS.lock() {
        if let Some(terminal) = terminals.get_mut(id) {
            terminal.send_command(command)
        } else {
            Err(format!("Streaming terminal {} not found", id))
        }
    } else {
        Err("Failed to lock terminals".to_string())
    }
}

/// ストリーミングターミナルから出力を取得
pub fn poll_streaming_terminal(id: &str) -> Option<OutputEvent> {
    if let Ok(terminals) = STREAMING_TERMINALS.lock() {
        if let Some(terminal) = terminals.get(id) {
            terminal.try_recv_output()
        } else {
            None
        }
    } else {
        None
    }
}

/// ストリーミングターミナルを終了
pub fn kill_streaming_terminal(id: &str) -> Result<(), String> {
    if let Ok(mut terminals) = STREAMING_TERMINALS.lock() {
        if let Some(mut terminal) = terminals.remove(id) {
            terminal.kill()
        } else {
            Err(format!("Streaming terminal {} not found", id))
        }
    } else {
        Err("Failed to lock terminals".to_string())
    }
}

/// コマンドをリアルタイムストリーミングで実行
/// コールバックは各行が出力されるたびに呼び出される
pub fn execute_command_streaming<F>(
    command: &str,
    working_dir: &PathBuf,
    terminal_id: &str,
    on_line: F,
    on_complete: impl FnOnce(i32) + Send + 'static,
) -> Result<u32, String>
where
    F: Fn(String, bool) + Send + Clone + 'static,
{
    let command = command.to_string();
    let working_dir = working_dir.clone();
    let terminal_id = terminal_id.to_string();
    
    // 作業ディレクトリを作成
    let _ = std::fs::create_dir_all(&working_dir);
    
    // PowerShellプロセスを起動
    let mut process = Command::new("powershell")
        .args(["-NoProfile", "-Command", &command])
        .current_dir(&working_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn PowerShell: {}", e))?;
    
    let pid = process.id();
    
    // COMMAND_TRACKERに登録
    COMMAND_TRACKER.add(terminal_id.clone(), pid, command.clone(), terminal_id.clone());
    
    let on_line_stdout = on_line.clone();
    let on_line_stderr = on_line.clone();
    let term_id_for_cleanup = terminal_id.clone();
    
    // stdoutリーダースレッド
    let stdout_done = Arc::new(Mutex::new(false));
    let stdout_done_clone = stdout_done.clone();
    if let Some(stdout) = process.stdout.take() {
        thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines() {
                match line {
                    Ok(l) => on_line_stdout(l, false),
                    Err(_) => break,
                }
            }
            if let Ok(mut done) = stdout_done_clone.lock() {
                *done = true;
            }
        });
    }
    
    // stderrリーダースレッド
    let stderr_done = Arc::new(Mutex::new(false));
    let stderr_done_clone = stderr_done.clone();
    if let Some(stderr) = process.stderr.take() {
        thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                match line {
                    Ok(l) => on_line_stderr(l, true),
                    Err(_) => break,
                }
            }
            if let Ok(mut done) = stderr_done_clone.lock() {
                *done = true;
            }
        });
    }
    
    // プロセス終了を待つスレッド
    thread::spawn(move || {
        let exit_code = match process.wait() {
            Ok(status) => status.code().unwrap_or(-1),
            Err(_) => -1,
        };
        
        // トラッカーから削除
        COMMAND_TRACKER.remove(&term_id_for_cleanup);
        
        // 完了コールバック
        on_complete(exit_code);
    });
    
    Ok(pid)
}

// =============================================================================
// Phase 1-2: コマンドツリー管理システム
// =============================================================================

/// コマンドの実行ステータス
#[derive(Debug, Clone, PartialEq)]
pub enum CommandStatus {
    /// 待機中
    Pending,
    /// 実行中
    Running,
    /// 完了
    Completed,
    /// 失敗
    Failed,
}

/// コマンドツリーのノード
#[derive(Debug, Clone)]
pub struct CommandNode {
    /// ノードID
    pub id: String,
    /// 実行するコマンド
    pub command: String,
    /// 実行するターミナルID
    pub terminal_id: String,
    /// 親ノードID（ルートの場合はNone）
    pub parent_id: Option<String>,
    /// 子ノードID
    pub children: Vec<String>,
    /// 実行ステータス
    pub status: CommandStatus,
    /// 作業ディレクトリ
    pub working_dir: PathBuf,
    /// プロセスID（実行中の場合）
    pub pid: Option<u32>,
}

/// コマンドツリー
/// 親子関係を持つコマンドを管理する
pub struct CommandTree {
    /// ノードマップ
    nodes: HashMap<String, CommandNode>,
    /// ターミナルごとのルートノード
    terminal_roots: HashMap<String, Vec<String>>,
}

impl CommandTree {
    /// 新しいコマンドツリーを作成
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
            terminal_roots: HashMap::new(),
        }
    }
    
    /// コマンドを追加
    pub fn add_command(
        &mut self,
        command: String,
        terminal_id: String,
        working_dir: PathBuf,
        parent_id: Option<String>,
    ) -> String {
        let id = format!("cmd_{}", uuid::Uuid::new_v4());
        
        let node = CommandNode {
            id: id.clone(),
            command,
            terminal_id: terminal_id.clone(),
            parent_id: parent_id.clone(),
            children: vec![],
            status: CommandStatus::Pending,
            working_dir,
            pid: None,
        };
        
        // 親に子を追加
        if let Some(ref parent) = parent_id {
            if let Some(parent_node) = self.nodes.get_mut(parent) {
                parent_node.children.push(id.clone());
            }
        } else {
            // ルートノードとして登録
            self.terminal_roots
                .entry(terminal_id)
                .or_insert_with(Vec::new)
                .push(id.clone());
        }
        
        self.nodes.insert(id.clone(), node);
        id
    }
    
    /// ノードを取得
    pub fn get_node(&self, id: &str) -> Option<&CommandNode> {
        self.nodes.get(id)
    }
    
    /// ノードを可変で取得
    pub fn get_node_mut(&mut self, id: &str) -> Option<&mut CommandNode> {
        self.nodes.get_mut(id)
    }
    
    /// ステータスを更新
    pub fn update_status(&mut self, id: &str, status: CommandStatus) {
        if let Some(node) = self.nodes.get_mut(id) {
            node.status = status;
        }
    }
    
    /// PIDを設定
    pub fn set_pid(&mut self, id: &str, pid: u32) {
        if let Some(node) = self.nodes.get_mut(id) {
            node.pid = Some(pid);
        }
    }
    
    /// 実行準備ができているコマンドを取得（親が完了しているもの）
    pub fn get_ready_commands(&self, terminal_id: &str) -> Vec<&CommandNode> {
        self.nodes.values()
            .filter(|node| {
                node.terminal_id == terminal_id &&
                node.status == CommandStatus::Pending &&
                node.parent_id.as_ref().map_or(true, |parent_id| {
                    self.nodes.get(parent_id)
                        .map_or(false, |p| p.status == CommandStatus::Completed)
                })
            })
            .collect()
    }
    
    /// ターミナルのすべてのコマンドを取得
    pub fn get_commands_for_terminal(&self, terminal_id: &str) -> Vec<&CommandNode> {
        self.nodes.values()
            .filter(|node| node.terminal_id == terminal_id)
            .collect()
    }
    
    /// ノードを削除
    pub fn remove_node(&mut self, id: &str) -> Option<CommandNode> {
        if let Some(node) = self.nodes.remove(id) {
            // 親から子を削除
            if let Some(parent_id) = &node.parent_id {
                if let Some(parent) = self.nodes.get_mut(parent_id) {
                    parent.children.retain(|c| c != id);
                }
            } else {
                // ルートノードから削除
                if let Some(roots) = self.terminal_roots.get_mut(&node.terminal_id) {
                    roots.retain(|r| r != id);
                }
            }
            Some(node)
        } else {
            None
        }
    }
    
    /// ターミナルのすべてのコマンドを削除
    pub fn clear_terminal(&mut self, terminal_id: &str) {
        let ids: Vec<String> = self.nodes.values()
            .filter(|n| n.terminal_id == terminal_id)
            .map(|n| n.id.clone())
            .collect();
        
        for id in ids {
            self.nodes.remove(&id);
        }
        
        self.terminal_roots.remove(terminal_id);
    }
}

impl Default for CommandTree {
    fn default() -> Self {
        Self::new()
    }
}

lazy_static::lazy_static! {
    /// グローバルなコマンドツリー
    pub static ref COMMAND_TREE: Mutex<CommandTree> = Mutex::new(CommandTree::new());
}

/// コマンドをツリーに追加
pub fn add_command_to_tree(
    command: &str,
    terminal_id: &str,
    working_dir: &PathBuf,
    parent_id: Option<&str>,
) -> Result<String, String> {
    if let Ok(mut tree) = COMMAND_TREE.lock() {
        Ok(tree.add_command(
            command.to_string(),
            terminal_id.to_string(),
            working_dir.clone(),
            parent_id.map(|s| s.to_string()),
        ))
    } else {
        Err("Failed to lock command tree".to_string())
    }
}

/// コマンドの実行準備ができているものを取得
pub fn get_ready_commands(terminal_id: &str) -> Vec<String> {
    if let Ok(tree) = COMMAND_TREE.lock() {
        tree.get_ready_commands(terminal_id)
            .iter()
            .map(|n| n.id.clone())
            .collect()
    } else {
        vec![]
    }
}

/// コマンドのステータスを更新
pub fn update_command_status(id: &str, status: CommandStatus) {
    if let Ok(mut tree) = COMMAND_TREE.lock() {
        tree.update_status(id, status);
    }
}

// =============================================================================
// Phase 1-4: ユーザー直接入力対応
// =============================================================================

/// ユーザー入力をストリーミングターミナルに送信
pub fn send_user_input(terminal_id: &str, input: &str) -> Result<(), String> {
    send_to_streaming_terminal(terminal_id, input)
}

/// ターミナルにユーザー入力を許可するかどうか
pub fn is_user_input_allowed(terminal_id: &str) -> bool {
    if let Ok(terminals) = STREAMING_TERMINALS.lock() {
        terminals.contains_key(terminal_id)
    } else {
        false
    }
}
