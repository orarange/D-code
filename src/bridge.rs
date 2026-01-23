// bridge.rs
// =========
// Native Desktop WebView Application for D-code
//
// Provides:
// - Native window with embedded WebView
// - IPC communication between UI and Rust engine
// - Custom protocol for serving embedded static files

use std::sync::{Arc, Mutex};
use std::sync::atomic::{AtomicBool, Ordering};

use pyo3::prelude::*;
use rust_embed::Embed;
use serde::{Deserialize, Serialize};
use tao::{
    event::{Event, StartCause, WindowEvent},
    event_loop::{ControlFlow, EventLoop, EventLoopBuilder},
    window::WindowBuilder,
};
use wry::{
    http::{header::CONTENT_TYPE, Response},
    WebViewBuilder,
};

use crate::AppState;

/// Custom event type for communication between IPC handler and event loop
/// Some variants are for future use with streaming AI responses
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub enum AppEvent {
    /// Execute JavaScript in the WebView
    EvaluateScript(String),
    /// Chat response from Python
    ChatResponse { message_id: String, content: String },
    /// Chat request to process in background
    ChatRequest { 
        message_id: String, 
        content: String,
        terminal_context: Option<String>,
    },
    /// AI thinking chunk (streaming)
    AiThinkingChunk {
        message_id: String,
        chunk: String,
        agent: String,
    },
    /// AI thinking complete
    AiThinkingComplete {
        message_id: String,
        full_content: String,
    },
    /// Agent status update
    AgentStatusUpdate {
        agent_id: String,
        state: String,
        current_task: Option<String>,
        progress: Option<u8>,
    },
    /// Terminal command to execute in background
    TerminalCommand {
        terminal_id: String,
        command: String,
        working_dir: std::path::PathBuf,
    },
    /// Terminal command result
    TerminalResult {
        terminal_id: String,
        output: String,
        is_running: bool,
    },
    /// Terminal streaming output (real-time line by line)
    TerminalStreamLine {
        terminal_id: String,
        line: String,
        is_stderr: bool,
    },
    /// Terminal command completed
    TerminalCompleted {
        terminal_id: String,
        exit_code: i32,
    },
    /// Kill a running process by terminal ID
    KillProcess {
        terminal_id: String,
    },
    /// Process kill result
    KillProcessResult {
        terminal_id: String,
        success: bool,
        message: String,
    },
    /// User input to terminal
    TerminalUserInput {
        terminal_id: String,
        input: String,
    },
    /// Window: Minimize
    WindowMinimize,
    /// Window: Maximize/Restore
    WindowMaximize,
    /// Window: Close
    WindowClose,
    /// Window: Start drag
    WindowDragStart,
}

/// Embedded UI assets from the ui/dist folder
#[derive(Embed)]
#[folder = "ui/dist"]
struct UiAssets;

/// Messages from UI to Rust
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum UiCommand {
    /// User sends a message/prompt
    SendMessage { 
        content: String,
        /// Terminal output context (optional)
        #[serde(default)]
        terminal_context: Option<String>,
    },
    /// Request to break/stop the engine
    BreakRequest,
    /// Request current status
    GetStatus,
    /// Read file content
    ReadFile { path: String },
    /// Get file list
    GetFiles,
    /// Set API key
    SetApiKey { key: String },
    /// Run a terminal command
    RunCommand { command: String },
    /// Kill a running process in a terminal
    KillTerminalProcess { terminal_id: String },
    /// User input to a streaming terminal
    TerminalInput { terminal_id: String, input: String },
    /// Window: Minimize
    WindowMinimize,
    /// Window: Maximize/Restore
    WindowMaximize,
    /// Window: Close
    WindowClose,
    /// Window: Start drag (for custom title bar)
    WindowDragStart,
    /// Initialize conversation manager with project root
    InitConversationManager { project_root: String },
    /// List conversation sessions
    ListConversationSessions { limit: Option<u32> },
    /// Load previous conversation session
    LoadConversationSession { session_id: String },
    /// Edit file with search/replace (partial update)
    EditFileSearchReplace { 
        file_path: String, 
        search: String, 
        replace: String,
        #[serde(default = "default_occurrence")]
        occurrence: i32,
    },
    /// Create unified diff between two texts
    CreateDiff { 
        original: String, 
        modified: String, 
        filename: String,
    },
    /// Delete a file or folder
    DeleteFile { path: String },
}

fn default_occurrence() -> i32 { 1 }

/// Messages from Rust to UI
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type")]
pub enum EngineMessage {
    /// Connection established
    Connected { message: String },
    /// Current status update
    Status {
        engine_running: bool,
        python_available: bool,
        current_task: Option<String>,
        error: Option<String>,
        api_key_set: bool,
    },
    /// Agent message in the stream
    AgentMessage {
        id: String,
        timestamp: String,
        agent: String,
        agent_icon: String,
        message_type: String,
        content: String,
    },
    /// AI思考ストリーミングチャンク（リアルタイム表示用）
    AiThinkingChunk {
        message_id: String,
        chunk: String,
        agent: String,
    },
    /// AI思考完了
    AiThinkingComplete {
        message_id: String,
        full_content: String,
    },
    /// エージェントステータス更新
    AgentStatusUpdate {
        agent_id: String,
        state: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        current_task: Option<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        progress: Option<u8>,
    },
    /// Task plan from planner
    TaskPlan {
        tasks: Vec<TaskInfo>,
        total: usize,
    },
    /// Task status update
    TaskUpdate {
        task_id: String,
        status: String,
        progress: Option<f32>,
    },
    /// Code change event
    CodeChange {
        file_path: String,
        content: String,
        language: String,
        action: String,
    },
    /// Terminal output
    TerminalOutput { 
        terminal_id: String,
        line: String,
        is_running: bool,
        #[serde(skip_serializing_if = "Option::is_none")]
        pid: Option<u32>,
    },
    /// Process killed notification
    ProcessKilled {
        terminal_id: String,
        success: bool,
        message: String,
    },
    /// Progress update
    Progress {
        current: usize,
        total: usize,
        message: String,
    },
    /// Error message
    Error { message: String },
    /// File list response
    FileList { files: Vec<FileInfo> },
    /// File content response
    FileContent {
        path: String,
        content: String,
        language: String,
    },
    /// Conversation manager initialized
    ConversationManagerInitialized {
        session_id: String,
    },
    /// Conversation sessions list
    ConversationSessionsList {
        sessions: Vec<ConversationSessionInfo>,
    },
    /// Conversation session loaded
    ConversationSessionLoaded {
        session_id: String,
        success: bool,
        message_count: usize,
    },
    /// File edit result (search/replace)
    FileEditResult {
        file_path: String,
        success: bool,
        message: String,
        replacements: i32,
    },
    /// Diff creation result
    DiffCreated {
        diff: String,
    },
    /// File deleted result
    FileDeleted {
        path: String,
        success: bool,
        message: String,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConversationSessionInfo {
    pub session_id: String,
    pub display_date: String,
    pub preview: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskInfo {
    pub id: String,
    pub title: String,
    pub description: String,
    #[serde(rename = "type")]
    pub task_type: String,
    pub priority: i32,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileInfo {
    pub name: String,
    pub path: String,
    #[serde(rename = "type")]
    pub file_type: String,
    pub children: Option<Vec<FileInfo>>,
}

// Static flag to track window maximized state (needed for decorations=false windows)
static IS_WINDOW_MAXIMIZED: AtomicBool = AtomicBool::new(false);

/// Start the desktop application
pub fn start_desktop_app(state: Arc<Mutex<AppState>>, python_available: bool) {
    let event_loop: EventLoop<AppEvent> = EventLoopBuilder::<AppEvent>::with_user_event().build();
    let event_loop_proxy = event_loop.create_proxy();
    
    let window = WindowBuilder::new()
        .with_title("D-code - AI Development Platform")
        .with_inner_size(tao::dpi::LogicalSize::new(1400.0, 900.0))
        .with_min_inner_size(tao::dpi::LogicalSize::new(800.0, 600.0))
        .with_decorations(false)  // カスタムタイトルバー使用のためネイティブ装飾を無効化
        .build(&event_loop)
        .expect("Failed to create window");

    // Clone state and proxy for the IPC handler
    let ipc_state = state.clone();
    let ipc_python = python_available;
    let ipc_proxy = event_loop_proxy.clone();
    
    // Create a separate proxy for the chat thread
    let chat_proxy = event_loop_proxy.clone();

    let webview = WebViewBuilder::new()
        // Custom protocol to serve embedded files
        .with_custom_protocol("dcode".to_string(), move |_webview_id, request| {
            let path = request.uri().path();
            let path = if path == "/" { "index.html" } else { &path[1..] };
            
            match UiAssets::get(path) {
                Some(content) => {
                    let mime = mime_guess::from_path(path).first_or_octet_stream();
                    Response::builder()
                        .header(CONTENT_TYPE, mime.as_ref())
                        .body(content.data.to_vec().into())
                        .unwrap()
                }
                None => {
                    // SPA fallback - serve index.html for unknown routes
                    match UiAssets::get("index.html") {
                        Some(content) => Response::builder()
                            .header(CONTENT_TYPE, "text/html")
                            .body(content.data.to_vec().into())
                            .unwrap(),
                        None => Response::builder()
                            .status(404)
                            .body("Not Found".as_bytes().to_vec().into())
                            .unwrap(),
                    }
                }
            }
        })
        // IPC handler for JavaScript -> Rust communication
        .with_ipc_handler({
            let chat_proxy_for_ipc = chat_proxy.clone();
            move |request| {
                let body = request.body();
                if let Ok(command) = serde_json::from_str::<UiCommand>(body) {
                    log::debug!("Received IPC command: {:?}", command);
                    // Send command to event loop for processing
                    let response = process_ui_command(&command, &ipc_state, ipc_python, &chat_proxy_for_ipc);
                    // Send response back to UI via event loop
                    if let Some(script) = response {
                        let _ = ipc_proxy.send_event(AppEvent::EvaluateScript(script));
                    }
                } else {
                    log::warn!("Failed to parse IPC command: {}", body);
                }
            }
        })
        // Load the app from custom protocol
        .with_url("dcode://localhost/")
        // Enable devtools in debug mode
        .with_devtools(cfg!(debug_assertions))
        .build(&window)
        .expect("Failed to create webview");

    // Send initial connected message
    // Check if we're in local server mode (no API key needed) or have a key set
    let gemini_key = std::env::var("GEMINI_API_KEY").unwrap_or_default();
    let api_backend = std::env::var("DCODE_API_BACKEND").unwrap_or_default();
    let api_base_url = std::env::var("DCODE_API_BASE_URL").unwrap_or_default();
    
    // API is "set" if using local server OR if GEMINI_API_KEY has a value
    let is_local_mode = api_backend == "openai" || 
                        api_base_url.contains("localhost") || 
                        api_base_url.contains("127.0.0.1");
    let api_key_set = is_local_mode || !gemini_key.is_empty();
    
    log::info!("API mode: local={}, api_key_set={}", is_local_mode, api_key_set);
    
    // Get workspace path for initialization
    let workspace_path = std::env::var("DCODE_WORKSPACE")
        .unwrap_or_else(|_| {
            dirs::document_dir()
                .map(|d| d.join("D-code").to_string_lossy().to_string())
                .unwrap_or_else(|| "./workspace".to_string())
        });
    
    // Check if debug mode is enabled
    let debug_mode = std::env::var("DCODE_DEBUG").unwrap_or_default() == "1" 
        || cfg!(debug_assertions);
    
    let init_script = format!(
        r#"
        (function() {{
            function sendConnected() {{
                console.log('D-code Desktop App - Sending connected event');
                window.dispatchEvent(new CustomEvent('dcode-connected', {{ detail: {{ 
                    connected: true,
                    pythonAvailable: {},
                    apiKeySet: {},
                    localMode: {},
                    workspacePath: "{}",
                    debugMode: {}
                }} }}));
            }}
            
            // Send immediately if DOM is ready, otherwise wait
            if (document.readyState === 'complete' || document.readyState === 'interactive') {{
                setTimeout(sendConnected, 50);
            }} else {{
                document.addEventListener('DOMContentLoaded', function() {{
                    setTimeout(sendConnected, 50);
                }});
            }}
            
            // Also send after a delay as backup
            setTimeout(sendConnected, 500);
        }})();
        "#,
        python_available, api_key_set, is_local_mode, 
        workspace_path.replace("\\", "\\\\"), debug_mode
    );
    let _ = webview.evaluate_script(&init_script);

    log::info!("D-code desktop application started");

    // Store webview reference for later use
    let webview = Arc::new(webview);
    let webview_for_events = webview.clone();
    
    // Clone chat_proxy for the event handler
    let chat_event_proxy = chat_proxy.clone();

    // Event loop
    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;

        match event {
            Event::NewEvents(StartCause::Init) => {
                log::info!("Desktop window initialized");
            }
            Event::UserEvent(app_event) => {
                match app_event {
                    AppEvent::EvaluateScript(script) => {
                        if let Err(e) = webview_for_events.evaluate_script(&script) {
                            log::error!("Failed to evaluate script: {:?}", e);
                        }
                    }
                    AppEvent::ChatRequest { message_id, content, terminal_context } => {
                        // Process chat in a background thread to avoid blocking UI
                        let proxy = chat_event_proxy.clone();
                        let webview_proxy = event_loop_proxy.clone();
                        std::thread::spawn(move || {
                            log::info!("Processing chat request in background thread: {}", message_id);
                            let response = call_gemini_chat(&content, terminal_context.as_deref(), &message_id, webview_proxy);
                            let _ = proxy.send_event(AppEvent::ChatResponse {
                                message_id,
                                content: response,
                            });
                        });
                    }
                    AppEvent::ChatResponse { message_id, content } => {
                        // Parse file operations from AI response
                        let file_ops = parse_file_operations(&content);
                        
                        // Parse terminal commands from AI response
                        let terminal_cmds = parse_terminal_commands(&content);
                        
                        // Extract user-facing message (removes code blocks that will be executed)
                        let user_message = extract_user_message(&content);
                        
                        // Get workspace directory
                        let workspace = std::env::var("DCODE_WORKSPACE")
                            .map(std::path::PathBuf::from)
                            .unwrap_or_else(|_| {
                                dirs::document_dir()
                                    .map(|d| d.join("D-code"))
                                    .unwrap_or_else(|| std::path::PathBuf::from("./workspace"))
                            });
                        let projects_dir = workspace.join("projects");
                        
                        // Execute file operations if any
                        let file_results = if !file_ops.is_empty() {
                            log::info!("Found {} file operations in AI response", file_ops.len());
                            execute_file_operations(&file_ops)
                        } else {
                            Vec::new()
                        };
                        
                        // Send the user-facing message back to UI (without full code blocks)
                        let response = EngineMessage::AgentMessage {
                            id: message_id.clone(),
                            timestamp: chrono_now(),
                            agent: "D-code".to_string(),
                            agent_icon: "🤖".to_string(),
                            message_type: "info".to_string(),
                            content: user_message, // Use extracted user message instead of full content
                        };
                        let json = serde_json::to_string(&response).unwrap_or_default();
                        let script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-message', {{ detail: {} }}));"#,
                            json
                        );
                        if let Err(e) = webview_for_events.evaluate_script(&script) {
                            log::error!("Failed to send chat response to UI: {:?}", e);
                        }
                        
                        // If files were created, send notifications and refresh file list
                        if !file_results.is_empty() {
                            // Build summary of file operations for conversation history
                            let mut file_summary = String::from("ファイル操作の結果:\n");
                            
                            // Notify about each file created
                            for (path, success, msg) in &file_results {
                                // Add to summary for conversation history
                                if *success {
                                    file_summary.push_str(&format!("- ✅ 作成成功: {}\n", path));
                                } else {
                                    file_summary.push_str(&format!("- ❌ 作成失敗: {} ({})\n", path, msg));
                                }
                                
                                let file_msg = EngineMessage::AgentMessage {
                                    id: format!("file_{}_{}", message_id, path.replace("/", "_")),
                                    timestamp: chrono_now(),
                                    agent: "system".to_string(),
                                    agent_icon: if *success { "📄" } else { "❌" }.to_string(),
                                    message_type: if *success { "success" } else { "error" }.to_string(),
                                    content: if *success {
                                        format!("✅ ファイル作成: `{}`", path)
                                    } else {
                                        format!("❌ ファイル作成失敗: `{}` - {}", path, msg)
                                    },
                                };
                                let file_json = serde_json::to_string(&file_msg).unwrap_or_default();
                                let file_script = format!(
                                    r#"window.dispatchEvent(new CustomEvent('dcode-message', {{ detail: {} }}));"#,
                                    file_json
                                );
                                let _ = webview_for_events.evaluate_script(&file_script);
                            }
                            
                            // Add file results to conversation history
                            add_system_result_to_history(&file_summary);
                            
                            // Refresh file list
                            let files = scan_directory(&projects_dir);
                            let file_list_response = EngineMessage::FileList { files };
                            let file_list_json = serde_json::to_string(&file_list_response).unwrap_or_default();
                            let file_list_script = format!(
                                r#"window.dispatchEvent(new CustomEvent('dcode-files', {{ detail: {} }}));"#,
                                file_list_json
                            );
                            let _ = webview_for_events.evaluate_script(&file_list_script);
                        }
                        
                        // Execute terminal commands asynchronously (in background thread)
                        if !terminal_cmds.is_empty() {
                            log::info!("Found {} terminal commands in AI response - executing in background", terminal_cmds.len());
                            for (idx, cmd) in terminal_cmds.into_iter().enumerate() {
                                // Generate unique terminal ID for each command
                                let terminal_id = format!("term_{}_{}",
                                    std::time::SystemTime::now()
                                        .duration_since(std::time::UNIX_EPOCH)
                                        .unwrap_or_default()
                                        .as_millis(),
                                    idx
                                );
                                // Send command to be executed in background
                                let _ = chat_event_proxy.send_event(AppEvent::TerminalCommand {
                                    terminal_id,
                                    command: cmd,
                                    working_dir: projects_dir.clone(),
                                });
                            }
                        }
                        
                        // Parse and execute kill commands if any
                        let kill_cmds = parse_kill_commands(&content);
                        if !kill_cmds.is_empty() {
                            log::info!("Found {} kill commands in AI response", kill_cmds.len());
                            for (target, pid) in kill_cmds {
                                if target == "all" {
                                    // Kill all running processes
                                    log::info!("Killing all running processes");
                                    if let Ok(commands) = crate::terminal::COMMAND_TRACKER.commands.lock() {
                                        for (term_id, _) in commands.iter() {
                                            let _ = chat_event_proxy.send_event(AppEvent::KillProcess {
                                                terminal_id: term_id.clone(),
                                            });
                                        }
                                    }
                                } else if let Some(p) = pid {
                                    // Kill specific PID
                                    log::info!("Killing process with PID: {}", p);
                                    if let Err(e) = crate::terminal::kill_process(p) {
                                        log::error!("Failed to kill process {}: {}", p, e);
                                    }
                                } else {
                                    // Kill by terminal ID
                                    let _ = chat_event_proxy.send_event(AppEvent::KillProcess {
                                        terminal_id: target,
                                    });
                                }
                            }
                        }
                    }
                    AppEvent::AiThinkingChunk { message_id, chunk, agent } => {
                        // Send streaming chunk to UI
                        let chunk_response = EngineMessage::AiThinkingChunk {
                            message_id,
                            chunk,
                            agent,
                        };
                        let chunk_json = serde_json::to_string(&chunk_response).unwrap_or_default();
                        let chunk_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-thinking', {{ detail: {} }}));"#,
                            chunk_json
                        );
                        let _ = webview_for_events.evaluate_script(&chunk_script);
                    }
                    AppEvent::AiThinkingComplete { message_id, full_content } => {
                        // Send completion event - process the full response like ChatResponse
                        // Re-use ChatResponse processing by sending it
                        let _ = chat_event_proxy.send_event(AppEvent::ChatResponse {
                            message_id,
                            content: full_content,
                        });
                    }
                    AppEvent::AgentStatusUpdate { agent_id, state, current_task, progress } => {
                        // Send agent status update to UI
                        let status_response = EngineMessage::AgentStatusUpdate {
                            agent_id,
                            state,
                            current_task,
                            progress,
                        };
                        let status_json = serde_json::to_string(&status_response).unwrap_or_default();
                        let status_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-agent-status', {{ detail: {} }}));"#,
                            status_json
                        );
                        let _ = webview_for_events.evaluate_script(&status_script);
                    }
                    AppEvent::TerminalCommand { terminal_id, command, working_dir } => {
                        // Notify UI that terminal is starting
                        let start_response = EngineMessage::TerminalOutput { 
                            terminal_id: terminal_id.clone(),
                            line: format!("$ {}", command),
                            is_running: true,
                            pid: None,
                        };
                        let start_json = serde_json::to_string(&start_response).unwrap_or_default();
                        let start_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-terminal', {{ detail: {} }}));"#,
                            start_json
                        );
                        let _ = webview_for_events.evaluate_script(&start_script);
                        
                        // Use streaming execution for real-time output
                        let proxy_for_line = chat_event_proxy.clone();
                        let proxy_for_complete = chat_event_proxy.clone();
                        let term_id = terminal_id.clone();
                        let term_id_for_complete = terminal_id.clone();
                        
                        match crate::terminal::execute_command_streaming(
                            &command,
                            &working_dir,
                            &terminal_id,
                            move |line, is_stderr| {
                                // Send each line as it arrives
                                let _ = proxy_for_line.send_event(AppEvent::TerminalStreamLine {
                                    terminal_id: term_id.clone(),
                                    line,
                                    is_stderr,
                                });
                            },
                            move |exit_code| {
                                // Send completion event
                                let _ = proxy_for_complete.send_event(AppEvent::TerminalCompleted {
                                    terminal_id: term_id_for_complete,
                                    exit_code,
                                });
                            },
                        ) {
                            Ok(pid) => {
                                // Send PID info to UI
                                let pid_response = EngineMessage::TerminalOutput {
                                    terminal_id: terminal_id.clone(),
                                    line: format!("PID: {}", pid),
                                    is_running: true,
                                    pid: Some(pid),
                                };
                                let pid_json = serde_json::to_string(&pid_response).unwrap_or_default();
                                let pid_script = format!(
                                    r#"window.dispatchEvent(new CustomEvent('dcode-terminal', {{ detail: {} }}));"#,
                                    pid_json
                                );
                                let _ = webview_for_events.evaluate_script(&pid_script);
                                log::info!("Started streaming command [{}]: PID {}", terminal_id, pid);
                            }
                            Err(e) => {
                                log::error!("Failed to start streaming command: {}", e);
                                let err_response = EngineMessage::TerminalOutput {
                                    terminal_id: terminal_id.clone(),
                                    line: format!("Error: {}", e),
                                    is_running: false,
                                    pid: None,
                                };
                                let err_json = serde_json::to_string(&err_response).unwrap_or_default();
                                let err_script = format!(
                                    r#"window.dispatchEvent(new CustomEvent('dcode-terminal', {{ detail: {} }}));"#,
                                    err_json
                                );
                                let _ = webview_for_events.evaluate_script(&err_script);
                            }
                        }
                    }
                    AppEvent::TerminalStreamLine { terminal_id, line, is_stderr } => {
                        // Send each line to UI in real-time
                        let line_response = EngineMessage::TerminalOutput {
                            terminal_id: terminal_id.clone(),
                            line: if is_stderr { format!("[stderr] {}", line) } else { line },
                            is_running: true,
                            pid: None,
                        };
                        let line_json = serde_json::to_string(&line_response).unwrap_or_default();
                        let line_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-terminal', {{ detail: {} }}));"#,
                            line_json
                        );
                        let _ = webview_for_events.evaluate_script(&line_script);
                    }
                    AppEvent::TerminalCompleted { terminal_id, exit_code } => {
                        // Collect all output for history
                        let completion_msg = if exit_code == 0 {
                            format!("✓ コマンド完了 (exit code: {})", exit_code)
                        } else {
                            format!("✗ コマンド失敗 (exit code: {})", exit_code)
                        };
                        
                        // Send completion to UI
                        let complete_response = EngineMessage::TerminalOutput {
                            terminal_id: terminal_id.clone(),
                            line: completion_msg.clone(),
                            is_running: false,
                            pid: None,
                        };
                        let complete_json = serde_json::to_string(&complete_response).unwrap_or_default();
                        let complete_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-terminal', {{ detail: {} }}));"#,
                            complete_json
                        );
                        let _ = webview_for_events.evaluate_script(&complete_script);
                        
                        // Add to history
                        add_system_result_to_history(&format!("ターミナル ({}) 完了: {}", terminal_id, completion_msg));
                    }
                    AppEvent::TerminalUserInput { terminal_id, input } => {
                        // Send user input to streaming terminal
                        match crate::terminal::send_user_input(&terminal_id, &input) {
                            Ok(_) => {
                                log::info!("Sent user input to terminal {}: {}", terminal_id, input);
                            }
                            Err(e) => {
                                log::error!("Failed to send user input: {}", e);
                            }
                        }
                    }
                    AppEvent::TerminalResult { terminal_id, output, is_running } => {
                        // Add terminal output to conversation history for AI context
                        // Truncate if too long to avoid bloating history
                        let output_for_history = if output.len() > 2000 {
                            format!("{}...\n[出力が長いため省略]", &output[..2000])
                        } else {
                            output.clone()
                        };
                        add_system_result_to_history(&format!("ターミナル出力 ({}):\n{}", terminal_id, output_for_history));
                        
                        // Send terminal output to UI
                        let term_response = EngineMessage::TerminalOutput { 
                            terminal_id,
                            line: output,
                            is_running,
                            pid: None,
                        };
                        let term_json = serde_json::to_string(&term_response).unwrap_or_default();
                        let term_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-terminal', {{ detail: {} }}));"#,
                            term_json
                        );
                        if let Err(e) = webview_for_events.evaluate_script(&term_script) {
                            log::error!("Failed to send terminal output to UI: {:?}", e);
                        }
                    }
                    AppEvent::KillProcess { terminal_id } => {
                        log::info!("Kill process request for terminal: {}", terminal_id);
                        // Get the running commands for this terminal and kill them
                        let results = crate::terminal::COMMAND_TRACKER.kill_by_terminal(&terminal_id);
                        let success = results.iter().all(|r| r.is_ok());
                        let message = if success {
                            "プロセスを終了しました".to_string()
                        } else {
                            "プロセスの終了に失敗しました".to_string()
                        };
                        
                        let kill_response = EngineMessage::ProcessKilled {
                            terminal_id,
                            success,
                            message,
                        };
                        let kill_json = serde_json::to_string(&kill_response).unwrap_or_default();
                        let kill_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-process-killed', {{ detail: {} }}));"#,
                            kill_json
                        );
                        if let Err(e) = webview_for_events.evaluate_script(&kill_script) {
                            log::error!("Failed to send kill response to UI: {:?}", e);
                        }
                    }
                    AppEvent::KillProcessResult { terminal_id, success, message } => {
                        let kill_response = EngineMessage::ProcessKilled {
                            terminal_id,
                            success,
                            message,
                        };
                        let kill_json = serde_json::to_string(&kill_response).unwrap_or_default();
                        let kill_script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-process-killed', {{ detail: {} }}));"#,
                            kill_json
                        );
                        if let Err(e) = webview_for_events.evaluate_script(&kill_script) {
                            log::error!("Failed to send kill response to UI: {:?}", e);
                        }
                    }
                    AppEvent::WindowMinimize => {
                        window.set_minimized(true);
                    }
                    AppEvent::WindowMaximize => {
                        // Windows + decorations(false) 環境での最大化/復元処理
                        // 独自のフラグで状態を追跡（window.is_maximized()は装飾なしウィンドウで正しく機能しないため）
                        let is_maximized = IS_WINDOW_MAXIMIZED.load(Ordering::SeqCst);
                        
                        if is_maximized {
                            // 復元: 元のサイズに戻す
                            log::info!("Restoring window from maximized state");
                            window.set_maximized(false);
                            // 強制的にサイズを設定
                            window.set_inner_size(tao::dpi::LogicalSize::new(1400.0, 900.0));
                            // 中央に配置
                            if let Some(monitor) = window.current_monitor() {
                                let monitor_size = monitor.size();
                                let x = (monitor_size.width as i32 - 1400) / 2;
                                let y = (monitor_size.height as i32 - 900) / 2;
                                window.set_outer_position(tao::dpi::PhysicalPosition::new(x, y.max(0)));
                            }
                            IS_WINDOW_MAXIMIZED.store(false, Ordering::SeqCst);
                        } else {
                            // 最大化
                            log::info!("Maximizing window");
                            // 標準の最大化を試みる
                            window.set_maximized(true);
                            
                            // モニターサイズを取得してウィンドウを拡大（フォールバック）
                            if let Some(monitor) = window.current_monitor() {
                                let size = monitor.size();
                                let position = monitor.position();
                                window.set_outer_position(tao::dpi::PhysicalPosition::new(position.x, position.y));
                                window.set_inner_size(tao::dpi::PhysicalSize::new(size.width, size.height - 40)); // タスクバー考慮
                            }
                            IS_WINDOW_MAXIMIZED.store(true, Ordering::SeqCst);
                        }
                        
                        // UI側に最大化状態を通知
                        let new_maximized_state = !is_maximized;
                        let script = format!(
                            r#"window.dispatchEvent(new CustomEvent('dcode-window-maximized', {{ detail: {{ isMaximized: {} }} }}));"#,
                            new_maximized_state
                        );
                        let _ = webview_for_events.evaluate_script(&script);
                    }
                    AppEvent::WindowClose => {
                        *control_flow = ControlFlow::Exit;
                    }
                    AppEvent::WindowDragStart => {
                        let _ = window.drag_window();
                    }
                }
            }
            Event::WindowEvent {
                event: WindowEvent::CloseRequested,
                ..
            } => {
                log::info!("Window close requested");
                *control_flow = ControlFlow::Exit;
            }
            Event::WindowEvent {
                event: WindowEvent::Resized(_),
                ..
            } => {
                // WebView handles resize automatically
            }
            _ => {}
        }
    });
}

/// Process commands from the UI and return JavaScript to execute
fn process_ui_command(
    command: &UiCommand, 
    state: &Arc<Mutex<AppState>>, 
    python_available: bool,
    event_proxy: &tao::event_loop::EventLoopProxy<AppEvent>,
) -> Option<String> {
    match command {
        UiCommand::SendMessage { content, terminal_context } => {
            log::info!("Received message from UI: {}", content);
            if let Some(ref ctx) = terminal_context {
                log::info!("With terminal context: {} chars", ctx.len());
            }
            
            if !python_available {
                let response = EngineMessage::AgentMessage {
                    id: format!("msg_{}", std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_millis()),
                    timestamp: chrono_now(),
                    agent: "D-code".to_string(),
                    agent_icon: "🤖".to_string(),
                    message_type: "error".to_string(),
                    content: "Python/Gemini API is not available. Please ensure google-generativeai is installed and GEMINI_API_KEY is set.".to_string(),
                };
                let json = serde_json::to_string(&response).unwrap_or_default();
                return Some(format!(
                    r#"window.dispatchEvent(new CustomEvent('dcode-message', {{ detail: {} }}));"#,
                    json
                ));
            }
            
            // Generate a unique message ID
            let message_id = format!("msg_{}", std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis());
            
            // Send the chat request to be processed in a background thread
            let _ = event_proxy.send_event(AppEvent::ChatRequest {
                message_id: message_id.clone(),
                content: content.clone(),
                terminal_context: terminal_context.clone(),
            });
            
            // Return immediately with a "thinking" acknowledgment
            // The actual response will be sent via ChatResponse event
            None
        }
        UiCommand::BreakRequest => {
            log::info!("Break request received");
            if let Ok(mut s) = state.lock() {
                s.break_requested = true;
            }
            
            // Also call Python's request_break function to stop AI processing
            let result = Python::with_gil(|py| -> Result<(), String> {
                let chat_module = py.import("engine.chat").map_err(|e| e.to_string())?;
                let break_fn = chat_module.getattr("request_break").map_err(|e| e.to_string())?;
                break_fn.call0().map_err(|e| e.to_string())?;
                Ok(())
            });
            
            match result {
                Ok(_) => {
                    log::info!("Python break request sent successfully");
                }
                Err(e) => {
                    log::error!("Failed to send break request to Python: {}", e);
                }
            }
            
            // Send confirmation to UI
            let response = EngineMessage::AgentMessage {
                id: format!("break_{}", std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis()),
                timestamp: chrono_now(),
                agent: "system".to_string(),
                agent_icon: "🛑".to_string(),
                message_type: "warning".to_string(),
                content: "AI処理の停止リクエストを送信しました。現在のタスク完了後に停止します。".to_string(),
            };
            let json = serde_json::to_string(&response).unwrap_or_default();
            Some(format!(
                r#"window.dispatchEvent(new CustomEvent('dcode-message', {{ detail: {} }}));"#,
                json
            ))
        }
        UiCommand::GetStatus => {
            let s = state.lock().ok()?;
            let api_key_set = std::env::var("GEMINI_API_KEY").is_ok();
            let response = EngineMessage::Status {
                engine_running: s.engine_running,
                python_available,
                current_task: None,
                error: s.last_error.clone(),
                api_key_set,
            };
            let json = serde_json::to_string(&response).unwrap_or_default();
            Some(format!(
                r#"window.dispatchEvent(new CustomEvent('dcode-status', {{ detail: {} }}));"#,
                json
            ))
        }
        UiCommand::ReadFile { path } => {
            log::info!("ReadFile request for path: {}", path);
            
            // Get workspace path for security check
            let workspace = std::env::var("DCODE_WORKSPACE")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| {
                    dirs::document_dir()
                        .map(|d| d.join("D-code"))
                        .unwrap_or_else(|| std::path::PathBuf::from("./workspace"))
                });
            
            // Convert to absolute path if relative
            let file_path = std::path::Path::new(&path);
            let absolute_path = if file_path.is_absolute() {
                file_path.to_path_buf()
            } else {
                workspace.join("projects").join(file_path)
            };
            
            log::info!("Resolved file path: {}", absolute_path.display());
            
            match std::fs::read_to_string(&absolute_path) {
                Ok(content) => {
                    let language = detect_language(&path);
                    let response = EngineMessage::FileContent {
                        path: path.clone(),
                        content,
                        language,
                    };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-file-content', {{ detail: {} }}));"#,
                        json
                    ))
                }
                Err(e) => {
                    log::error!("Failed to read file '{}': {}", absolute_path.display(), e);
                    let response = EngineMessage::Error {
                        message: format!("ファイルを読み込めませんでした: {} (パス: {})", e, absolute_path.display()),
                    };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-error', {{ detail: {} }}));"#,
                        json
                    ))
                }
            }
        }
        UiCommand::GetFiles => {
            // Get workspace from environment variable (set in main.rs)
            let workspace = std::env::var("DCODE_WORKSPACE")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| {
                    // Fallback to Documents/D-code
                    dirs::document_dir()
                        .map(|d| d.join("D-code"))
                        .unwrap_or_else(|| std::path::PathBuf::from("./workspace"))
                });
            
            log::info!("GetFiles: Workspace path: {}", workspace.display());
            
            // Scan the projects subdirectory
            let projects_dir = workspace.join("projects");
            log::info!("GetFiles: Scanning projects directory: {}", projects_dir.display());
            
            // Create workspace directory if it doesn't exist
            if !projects_dir.exists() {
                log::info!("GetFiles: Creating projects directory");
                let _ = std::fs::create_dir_all(&projects_dir);
            }
            
            let files = scan_directory(&projects_dir);
            log::info!("GetFiles: Found {} items", files.len());
            
            let response = EngineMessage::FileList { files };
            let json = serde_json::to_string(&response).unwrap_or_default();
            Some(format!(
                r#"window.dispatchEvent(new CustomEvent('dcode-files', {{ detail: {} }}));"#,
                json
            ))
        }
        UiCommand::SetApiKey { key } => {
            std::env::set_var("GEMINI_API_KEY", key);
            log::info!("API key updated");
            Some(r#"window.dispatchEvent(new CustomEvent('dcode-api-key-set', { detail: { success: true } }));"#.to_string())
        }
        UiCommand::RunCommand { command } => {
            log::info!("Running command asynchronously: {}", command);
            
            // Get workspace directory for command execution
            let workspace = std::env::var("DCODE_WORKSPACE")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| {
                    dirs::document_dir()
                        .map(|d| d.join("D-code"))
                        .unwrap_or_else(|| std::path::PathBuf::from("./workspace"))
                });
            let projects_dir = workspace.join("projects");
            
            // Generate unique terminal ID
            let terminal_id = format!("term_{}", 
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis()
            );
            
            // Execute command asynchronously in background thread
            let _ = event_proxy.send_event(AppEvent::TerminalCommand {
                terminal_id,
                command: command.clone(),
                working_dir: projects_dir,
            });
            
            // Return immediately - output will be sent via TerminalResult event
            None
        }
        UiCommand::KillTerminalProcess { terminal_id } => {
            log::info!("Kill terminal process request for: {}", terminal_id);
            
            // Send kill event to be processed
            let _ = event_proxy.send_event(AppEvent::KillProcess {
                terminal_id: terminal_id.clone(),
            });
            
            // Return immediately - result will be sent via KillProcessResult event
            None
        }
        UiCommand::TerminalInput { terminal_id, input } => {
            log::info!("Terminal input for {}: {}", terminal_id, input);
            
            // Send user input event
            let _ = event_proxy.send_event(AppEvent::TerminalUserInput {
                terminal_id: terminal_id.clone(),
                input: input.clone(),
            });
            
            None
        }
        UiCommand::WindowMinimize => {
            log::info!("Window minimize request");
            let _ = event_proxy.send_event(AppEvent::WindowMinimize);
            None
        }
        UiCommand::WindowMaximize => {
            log::info!("Window maximize/restore request");
            let _ = event_proxy.send_event(AppEvent::WindowMaximize);
            None
        }
        UiCommand::WindowClose => {
            log::info!("Window close request");
            let _ = event_proxy.send_event(AppEvent::WindowClose);
            None
        }
        UiCommand::WindowDragStart => {
            log::info!("Window drag start request");
            let _ = event_proxy.send_event(AppEvent::WindowDragStart);
            None
        }
        UiCommand::InitConversationManager { project_root } => {
            log::info!("Initializing conversation manager with project root: {}", project_root);
            
            // Pythonエンジンで会話マネージャーを初期化
            let result = Python::with_gil(|py| -> Result<String, String> {
                let chat_module = py.import("engine.chat").map_err(|e| e.to_string())?;
                let init_fn = chat_module.getattr("init_conversation_manager").map_err(|e| e.to_string())?;
                
                let path_module = py.import("pathlib").map_err(|e| e.to_string())?;
                let path_class = path_module.getattr("Path").map_err(|e| e.to_string())?;
                let project_path = path_class.call1((project_root.clone(),)).map_err(|e| e.to_string())?;
                
                let manager = init_fn.call1((project_path,)).map_err(|e| e.to_string())?;
                let session_id = manager.getattr("current_session").map_err(|e| e.to_string())?;
                session_id.extract::<String>().map_err(|e| e.to_string())
            });
            
            match result {
                Ok(session_id) => {
                    let response = EngineMessage::ConversationManagerInitialized { session_id };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-conversation-manager-initialized', {{ detail: {} }}));"#,
                        json
                    ))
                }
                Err(e) => {
                    log::error!("Failed to initialize conversation manager: {}", e);
                    let response = EngineMessage::Error { message: format!("Failed to init conversation manager: {}", e) };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-error', {{ detail: {} }}));"#,
                        json
                    ))
                }
            }
        }
        UiCommand::ListConversationSessions { limit } => {
            log::info!("Listing conversation sessions, limit: {:?}", limit);
            
            let result = Python::with_gil(|py| -> Result<Vec<ConversationSessionInfo>, String> {
                let chat_module = py.import("engine.chat").map_err(|e| e.to_string())?;
                let list_fn = chat_module.getattr("list_conversation_sessions").map_err(|e| e.to_string())?;
                
                let limit_val = limit.unwrap_or(20) as i32;
                let sessions_py = list_fn.call1((limit_val,)).map_err(|e| e.to_string())?;
                
                let mut sessions = Vec::new();
                for item in sessions_py.try_iter().map_err(|e| e.to_string())? {
                    let dict = item.map_err(|e| e.to_string())?;
                    // PyO3 0.23: get_item returns Result<Bound>, not Result<Option>
                    let session_id: String = dict.get_item("session_id")
                        .map_err(|e| e.to_string())?
                        .extract()
                        .map_err(|e| e.to_string())?;
                    let display_date: String = dict.get_item("display_date")
                        .map_err(|e| e.to_string())?
                        .extract()
                        .map_err(|e| e.to_string())?;
                    let preview: String = dict.get_item("preview")
                        .map_err(|e| e.to_string())?
                        .extract()
                        .map_err(|e| e.to_string())?;
                    
                    sessions.push(ConversationSessionInfo {
                        session_id,
                        display_date,
                        preview,
                    });
                }
                
                Ok(sessions)
            });
            
            match result {
                Ok(sessions) => {
                    let response = EngineMessage::ConversationSessionsList { sessions };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-conversation-sessions-list', {{ detail: {} }}));"#,
                        json
                    ))
                }
                Err(e) => {
                    log::error!("Failed to list conversation sessions: {}", e);
                    let response = EngineMessage::Error { message: format!("Failed to list sessions: {}", e) };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-error', {{ detail: {} }}));"#,
                        json
                    ))
                }
            }
        }
        UiCommand::LoadConversationSession { session_id } => {
            log::info!("Loading conversation session: {}", session_id);
            
            let result = Python::with_gil(|py| -> Result<(bool, usize), String> {
                let chat_module = py.import("engine.chat").map_err(|e| e.to_string())?;
                let load_fn = chat_module.getattr("load_previous_session").map_err(|e| e.to_string())?;
                let get_history_fn = chat_module.getattr("get_conversation_history").map_err(|e| e.to_string())?;
                
                let success: bool = load_fn.call1((session_id.clone(),))
                    .map_err(|e| e.to_string())?
                    .extract()
                    .map_err(|e| e.to_string())?;
                
                if success {
                    let history = get_history_fn.call0().map_err(|e| e.to_string())?;
                    let messages = history.getattr("messages").map_err(|e| e.to_string())?;
                    let count: usize = messages.len().map_err(|e| e.to_string())?;
                    Ok((true, count))
                } else {
                    Ok((false, 0))
                }
            });
            
            match result {
                Ok((success, message_count)) => {
                    let response = EngineMessage::ConversationSessionLoaded { 
                        session_id: session_id.clone(),
                        success,
                        message_count,
                    };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-conversation-session-loaded', {{ detail: {} }}));"#,
                        json
                    ))
                }
                Err(e) => {
                    log::error!("Failed to load conversation session: {}", e);
                    let response = EngineMessage::Error { message: format!("Failed to load session: {}", e) };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-error', {{ detail: {} }}));"#,
                        json
                    ))
                }
            }
        }
        UiCommand::EditFileSearchReplace { file_path, search, replace, occurrence } => {
            log::info!("Edit file with search/replace: {}", file_path);
            
            let result = Python::with_gil(|py| -> Result<(bool, String, i32), String> {
                let editor_module = py.import("engine.code_editor").map_err(|e| e.to_string())?;
                let edit_fn = editor_module.getattr("edit_file_with_search_replace").map_err(|e| e.to_string())?;
                
                let path_module = py.import("pathlib").map_err(|e| e.to_string())?;
                let path_class = path_module.getattr("Path").map_err(|e| e.to_string())?;
                let file_path_obj = path_class.call1((file_path.clone(),)).map_err(|e| e.to_string())?;
                
                let result = edit_fn.call1((file_path_obj, search.clone(), replace.clone(), *occurrence))
                    .map_err(|e| e.to_string())?;
                
                // Result is a tuple (bool, str, int) or (bool, str)
                let success: bool = result.get_item(0).map_err(|e| e.to_string())?.extract().map_err(|e| e.to_string())?;
                let message: String = result.get_item(1).map_err(|e| e.to_string())?.extract().map_err(|e| e.to_string())?;
                
                // Try to get count, default to 1 if success
                let count = if success { 1 } else { 0 };
                
                Ok((success, message, count))
            });
            
            match result {
                Ok((success, message, replacements)) => {
                    let response = EngineMessage::FileEditResult {
                        file_path: file_path.clone(),
                        success,
                        message,
                        replacements,
                    };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-file-edit-result', {{ detail: {} }}));"#,
                        json
                    ))
                }
                Err(e) => {
                    log::error!("Failed to edit file: {}", e);
                    let response = EngineMessage::Error { message: format!("Failed to edit file: {}", e) };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-error', {{ detail: {} }}));"#,
                        json
                    ))
                }
            }
        }
        UiCommand::CreateDiff { original, modified, filename } => {
            log::info!("Creating diff for: {}", filename);
            
            let result = Python::with_gil(|py| -> Result<String, String> {
                let editor_module = py.import("engine.code_editor").map_err(|e| e.to_string())?;
                let diff_fn = editor_module.getattr("create_diff").map_err(|e| e.to_string())?;
                
                let diff: String = diff_fn.call1((original.clone(), modified.clone(), filename.clone()))
                    .map_err(|e| e.to_string())?
                    .extract()
                    .map_err(|e| e.to_string())?;
                
                Ok(diff)
            });
            
            match result {
                Ok(diff) => {
                    let response = EngineMessage::DiffCreated { diff };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-diff-created', {{ detail: {} }}));"#,
                        json
                    ))
                }
                Err(e) => {
                    log::error!("Failed to create diff: {}", e);
                    let response = EngineMessage::Error { message: format!("Failed to create diff: {}", e) };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-error', {{ detail: {} }}));"#,
                        json
                    ))
                }
            }
        }
        UiCommand::DeleteFile { path } => {
            log::info!("Delete file request for: {}", path);
            
            // Get workspace path for security check
            let workspace = std::env::var("DCODE_WORKSPACE")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| {
                    dirs::document_dir()
                        .map(|d| d.join("D-code"))
                        .unwrap_or_else(|| std::path::PathBuf::from("./workspace"))
                });
            
            // Convert to absolute path if relative
            let file_path = std::path::Path::new(&path);
            let absolute_path = if file_path.is_absolute() {
                file_path.to_path_buf()
            } else {
                workspace.join("projects").join(file_path)
            };
            
            // Security check: ensure the path is within the workspace
            let canonical_workspace = workspace.canonicalize().unwrap_or(workspace.clone());
            let canonical_path = absolute_path.canonicalize().unwrap_or(absolute_path.clone());
            
            if !canonical_path.starts_with(&canonical_workspace) {
                log::error!("Security: Attempted to delete file outside workspace: {}", path);
                let response = EngineMessage::FileDeleted {
                    path: path.clone(),
                    success: false,
                    message: "セキュリティエラー: ワークスペース外のファイルは削除できません".to_string(),
                };
                let json = serde_json::to_string(&response).unwrap_or_default();
                return Some(format!(
                    r#"window.dispatchEvent(new CustomEvent('dcode-file-deleted', {{ detail: {} }}));"#,
                    json
                ));
            }
            
            // Perform deletion
            let result = if absolute_path.is_dir() {
                std::fs::remove_dir_all(&absolute_path)
            } else {
                std::fs::remove_file(&absolute_path)
            };
            
            match result {
                Ok(_) => {
                    log::info!("Successfully deleted: {}", absolute_path.display());
                    let response = EngineMessage::FileDeleted {
                        path: path.clone(),
                        success: true,
                        message: "ファイルを削除しました".to_string(),
                    };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    
                    // Also refresh file list
                    let projects_dir = workspace.join("projects");
                    let files = scan_directory(&projects_dir);
                    let file_list_response = EngineMessage::FileList { files };
                    let file_list_json = serde_json::to_string(&file_list_response).unwrap_or_default();
                    
                    // Return both events
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-file-deleted', {{ detail: {} }}));
                        window.dispatchEvent(new CustomEvent('dcode-files', {{ detail: {} }}));"#,
                        json, file_list_json
                    ))
                }
                Err(e) => {
                    log::error!("Failed to delete file '{}': {}", absolute_path.display(), e);
                    let response = EngineMessage::FileDeleted {
                        path: path.clone(),
                        success: false,
                        message: format!("削除に失敗しました: {}", e),
                    };
                    let json = serde_json::to_string(&response).unwrap_or_default();
                    Some(format!(
                        r#"window.dispatchEvent(new CustomEvent('dcode-file-deleted', {{ detail: {} }}));"#,
                        json
                    ))
                }
            }
        }
    }
}

/// Scan directory and return file tree
fn scan_directory(path: &std::path::Path) -> Vec<FileInfo> {
    let mut files = Vec::new();
    
    if let Ok(entries) = std::fs::read_dir(path) {
        for entry in entries.flatten() {
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().to_string();
            
            // Skip hidden files and common ignored directories
            if name.starts_with('.') || name == "node_modules" || name == "target" {
                continue;
            }
            
            if path.is_dir() {
                let children = scan_directory(&path);
                files.push(FileInfo {
                    name,
                    path: path.to_string_lossy().to_string(),
                    file_type: "folder".to_string(),
                    children: Some(children),
                });
            } else {
                files.push(FileInfo {
                    name,
                    path: path.to_string_lossy().to_string(),
                    file_type: "file".to_string(),
                    children: None,
                });
            }
        }
    }
    
    // Sort: folders first, then alphabetically
    files.sort_by(|a, b| {
        match (&a.file_type[..], &b.file_type[..]) {
            ("folder", "file") => std::cmp::Ordering::Less,
            ("file", "folder") => std::cmp::Ordering::Greater,
            _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
        }
    });
    
    files
}

/// Detect programming language from file extension
fn detect_language(path: &str) -> String {
    let ext = path.rsplit('.').next().unwrap_or("");
    match ext.to_lowercase().as_str() {
        "rs" => "rust",
        "py" => "python",
        "js" => "javascript",
        "ts" => "typescript",
        "tsx" => "typescriptreact",
        "jsx" => "javascriptreact",
        "json" => "json",
        "html" => "html",
        "css" => "css",
        "md" => "markdown",
        "toml" => "toml",
        "yaml" | "yml" => "yaml",
        "sh" | "bash" => "shell",
        "sql" => "sql",
        "go" => "go",
        "java" => "java",
        "cpp" | "cc" | "cxx" => "cpp",
        "c" => "c",
        "h" | "hpp" => "cpp",
        _ => "plaintext",
    }
    .to_string()
}

/// Get current timestamp in ISO format
fn chrono_now() -> String {
    let now = std::time::SystemTime::now();
    let duration = now
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    
    // Convert to ISO 8601 format manually
    let secs = duration.as_secs();
    let millis = duration.subsec_millis();
    
    // Calculate date/time components (simplified UTC calculation)
    const SECS_PER_DAY: u64 = 86400;
    const SECS_PER_HOUR: u64 = 3600;
    const SECS_PER_MIN: u64 = 60;
    
    let days_since_epoch = secs / SECS_PER_DAY;
    let time_of_day = secs % SECS_PER_DAY;
    
    let hours = time_of_day / SECS_PER_HOUR;
    let minutes = (time_of_day % SECS_PER_HOUR) / SECS_PER_MIN;
    let seconds = time_of_day % SECS_PER_MIN;
    
    // Calculate year, month, day from days since epoch (1970-01-01)
    let mut remaining_days = days_since_epoch as i64;
    let mut year = 1970i32;
    
    loop {
        let days_in_year = if year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) { 366 } else { 365 };
        if remaining_days < days_in_year {
            break;
        }
        remaining_days -= days_in_year;
        year += 1;
    }
    
    let is_leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    let days_in_months: [i64; 12] = if is_leap {
        [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    } else {
        [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    };
    
    let mut month = 1u32;
    for &days in &days_in_months {
        if remaining_days < days {
            break;
        }
        remaining_days -= days;
        month += 1;
    }
    let day = remaining_days + 1;
    
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:03}Z",
        year, month, day, hours, minutes, seconds, millis
    )
}

/// Call the Gemini chat API via Python with optional streaming
fn call_gemini_chat(
    message: &str, 
    terminal_context: Option<&str>,
    message_id: &str,
    event_proxy: tao::event_loop::EventLoopProxy<AppEvent>,
) -> String {
    // Safely truncate message for logging (handle multi-byte characters)
    let preview: String = message.chars().take(50).collect();
    log::info!("call_gemini_chat: Starting Python call for message: {}", preview);
    if let Some(ctx) = terminal_context {
        log::info!("call_gemini_chat: Terminal context provided: {} chars", ctx.len());
    }
    
    // Store event_proxy and message_id in thread-local storage for the streaming callback
    let msg_id = message_id.to_string();
    
    Python::with_gil(|py| {
        log::info!("call_gemini_chat: Got Python GIL");
        
        // Try to import our chat module
        match py.import("engine.chat") {
            Ok(chat_module) => {
                log::info!("call_gemini_chat: Successfully imported engine.chat");
                
                // Set up streaming callback if available
                if let Ok(set_streaming_callback) = chat_module.getattr("set_streaming_callback") {
                    // Create a Python callback that sends chunks to the UI
                    let proxy_clone = event_proxy.clone();
                    let callback = pyo3::types::PyCFunction::new_closure(
                        py,
                        None,  // name
                        None,  // doc
                        move |args: &pyo3::Bound<'_, pyo3::types::PyTuple>, _kwargs: Option<&pyo3::Bound<'_, pyo3::types::PyDict>>| -> pyo3::PyResult<()> {
                            use pyo3::prelude::*;
                            if args.len() >= 3 {
                                let chunk_msg_id: String = args.get_item(0)?.extract()?;
                                let chunk: String = args.get_item(1)?.extract()?;
                                let agent: String = args.get_item(2)?.extract()?;
                                
                                // Send chunk to UI via event proxy
                                let _ = proxy_clone.send_event(AppEvent::AiThinkingChunk {
                                    message_id: chunk_msg_id,
                                    chunk,
                                    agent,
                                });
                            }
                            Ok(())
                        },
                    );
                    
                    match callback {
                        Ok(cb) => {
                            if let Err(e) = set_streaming_callback.call1((cb,)) {
                                log::warn!("Failed to set streaming callback: {}", e);
                            } else {
                                log::info!("Streaming callback set successfully");
                            }
                        }
                        Err(e) => {
                            log::warn!("Failed to create streaming callback closure: {}", e);
                        }
                    }
                }
                
                // Get the chat_sync function
                match chat_module.getattr("chat_sync") {
                    Ok(chat_fn) => {
                        log::info!("call_gemini_chat: Got chat_sync function");
                        
                        // Build kwargs for the call
                        let kwargs = pyo3::types::PyDict::new(py);
                        kwargs.set_item("message", message).unwrap();
                        if let Some(ctx) = terminal_context {
                            kwargs.set_item("terminal_context", ctx).unwrap();
                        }
                        kwargs.set_item("message_id", &msg_id).unwrap();
                        
                        // Call the function with kwargs
                        match chat_fn.call((), Some(&kwargs)) {
                            Ok(result) => {
                                log::info!("call_gemini_chat: chat_sync returned");
                                
                                // Clear the streaming callback after use
                                if let Ok(set_streaming_callback) = chat_module.getattr("set_streaming_callback") {
                                    let _ = set_streaming_callback.call1((py.None(),));
                                }
                                
                                // Extract string result
                                match result.extract::<String>() {
                                    Ok(response) => {
                                        log::info!("call_gemini_chat: Response length: {}", response.len());
                                        response
                                    }
                                    Err(e) => {
                                        let err = format!("Error extracting response: {}", e);
                                        log::error!("call_gemini_chat: {}", err);
                                        err
                                    }
                                }
                            }
                            Err(e) => {
                                let err = format!("Error calling chat_sync: {}", e);
                                log::error!("call_gemini_chat: {}", err);
                                err
                            }
                        }
                    }
                    Err(e) => {
                        let err = format!("Error getting chat_sync function: {}", e);
                        log::error!("call_gemini_chat: {}", err);
                        err
                    }
                }
            }
            Err(e) => {
                let err = format!("Error importing engine.chat module: {}", e);
                log::error!("call_gemini_chat: {}", err);
                err
            }
        }
    })
}

/// Add system result to conversation history (file creation, command output, etc.)
fn add_system_result_to_history(result: &str) {
    Python::with_gil(|py| {
        match py.import("engine.chat") {
            Ok(chat_module) => {
                match chat_module.getattr("add_system_result_to_history") {
                    Ok(add_fn) => {
                        if let Err(e) = add_fn.call1((result,)) {
                            log::warn!("Failed to add system result to history: {}", e);
                        } else {
                            log::info!("Added system result to conversation history");
                        }
                    }
                    Err(e) => log::warn!("add_system_result_to_history not found: {}", e),
                }
            }
            Err(e) => log::warn!("Could not import engine.chat: {}", e),
        }
    });
}

/// Clear conversation history (call when starting a new session)
#[allow(dead_code)]
fn clear_conversation_history() {
    Python::with_gil(|py| {
        match py.import("engine.chat") {
            Ok(chat_module) => {
                match chat_module.getattr("clear_conversation_history") {
                    Ok(clear_fn) => {
                        if let Err(e) = clear_fn.call0() {
                            log::warn!("Failed to clear conversation history: {}", e);
                        } else {
                            log::info!("Conversation history cleared");
                        }
                    }
                    Err(e) => log::warn!("clear_conversation_history not found: {}", e),
                }
            }
            Err(e) => log::warn!("Could not import engine.chat: {}", e),
        }
    });
}

/// Extract user-facing message from AI response (removes file content blocks)
fn extract_user_message(response: &str) -> String {
    Python::with_gil(|py| {
        // Try to use Python parser
        match py.import("engine.response_parser") {
            Ok(parser_module) => {
                match parser_module.getattr("extract_user_message") {
                    Ok(extract_fn) => {
                        match extract_fn.call1((response,)) {
                            Ok(result) => {
                                match result.extract::<String>() {
                                    Ok(msg) => return msg,
                                    Err(_) => {}
                                }
                            }
                            Err(_) => {}
                        }
                    }
                    Err(_) => {}
                }
            }
            Err(_) => {}
        }
        
        // Fallback: simple regex-based extraction
        extract_user_message_fallback(response)
    })
}

/// Fallback user message extraction (pure Rust)
fn extract_user_message_fallback(response: &str) -> String {
    let mut result = response.to_string();
    
    // Remove file operation blocks: ```language::path\ncontent```
    let file_pattern = regex::Regex::new(r"```\w+::[^\n]+\n[\s\S]*?```").unwrap_or_else(|_| {
        return regex::Regex::new(r".*").unwrap();
    });
    
    // Replace file blocks with notification
    let mut replacements = Vec::new();
    for cap in file_pattern.captures_iter(&result) {
        if let Some(m) = cap.get(0) {
            let full_match = m.as_str();
            // Extract path from the match
            if let Some(path_start) = full_match.find("::") {
                if let Some(newline) = full_match[path_start..].find('\n') {
                    let path = &full_match[path_start + 2..path_start + newline].trim();
                    let path_lower = path.to_lowercase();
                    // Don't replace bash::run or bash::kill commands here (they're handled separately)
                    if !path_lower.eq("run") && !path_lower.eq("kill") {
                        replacements.push((full_match.to_string(), format!("\n📄 **ファイル作成:** `{}`\n", path)));
                    }
                }
            }
        }
    }
    
    for (old, new) in replacements {
        result = result.replace(&old, &new);
    }
    
    // Remove command blocks: ```bash::run\ncommand```
    let cmd_pattern = regex::Regex::new(r"```(?:bash|shell|cmd|powershell)::run\n(.*?)```").unwrap_or_else(|_| {
        return regex::Regex::new(r".*").unwrap();
    });
    
    let mut cmd_replacements = Vec::new();
    for cap in cmd_pattern.captures_iter(&result) {
        if let Some(m) = cap.get(0) {
            let full_match = m.as_str();
            if let Some(cmd) = cap.get(1) {
                let cmd_str = cmd.as_str().trim();
                let preview = if cmd_str.len() > 50 {
                    format!("{}...", &cmd_str[..50])
                } else {
                    cmd_str.to_string()
                };
                cmd_replacements.push((full_match.to_string(), format!("\n⚡ **コマンド実行:** `{}`\n", preview)));
            }
        }
    }
    
    for (old, new) in cmd_replacements {
        result = result.replace(&old, &new);
    }
    
    // Remove kill blocks: ```bash::kill\ntarget```
    let kill_pattern = regex::Regex::new(r"```(?:bash|shell|cmd|powershell)::kill\s*\n?(.*?)```").unwrap_or_else(|_| {
        return regex::Regex::new(r".*").unwrap();
    });
    
    let mut kill_replacements = Vec::new();
    for cap in kill_pattern.captures_iter(&result) {
        if let Some(m) = cap.get(0) {
            let full_match = m.as_str();
            let target = cap.get(1).map(|t| t.as_str().trim()).unwrap_or("all");
            kill_replacements.push((full_match.to_string(), format!("\n🛑 **プロセス終了:** `{}`\n", target)));
        }
    }
    
    for (old, new) in kill_replacements {
        result = result.replace(&old, &new);
    }
    
    // Clean up excessive newlines
    let newline_pattern = regex::Regex::new(r"\n{4,}").unwrap_or_else(|_| {
        return regex::Regex::new(r".*").unwrap();
    });
    result = newline_pattern.replace_all(&result, "\n\n\n").to_string();
    
    result.trim().to_string()
}

/// Represents a file operation extracted from AI response
#[derive(Debug)]
#[allow(dead_code)]
struct FileOperation {
    path: String,
    content: String,
    language: String,
}

/// Parse AI response and extract file operations
/// Looks for code blocks with format: ```language::path or ```[language]::path
/// Excludes terminal commands (bash::run, shell::run, etc.)
fn parse_file_operations(response: &str) -> Vec<FileOperation> {
    let mut operations = Vec::new();
    
    // Regex pattern to match code blocks with file path
    // Supports both formats:
    //   ```python::src/main.py
    //   ```[python]::src/main.py
    let re = regex::Regex::new(r"```\[?(\w+)\]?::([^\n]+)\n([\s\S]*?)```").unwrap_or_else(|_| {
        // Fallback: simpler pattern without regex crate
        return regex::Regex::new(r".*").unwrap();
    });
    
    for cap in re.captures_iter(response) {
        if let (Some(lang), Some(path), Some(content)) = (cap.get(1), cap.get(2), cap.get(3)) {
            let language = lang.as_str().to_string().to_lowercase();
            let file_path = path.as_str().trim().to_string();
            let file_content = content.as_str().to_string();
            
            // Skip terminal commands (bash::run, shell::run, cmd::run, powershell::run)
            // Also skip kill commands (bash::kill, etc.)
            let is_shell_lang = language == "bash" || language == "shell" || language == "cmd" || language == "powershell";
            let is_command = file_path.to_lowercase() == "run" || file_path.to_lowercase() == "kill";
            
            if is_shell_lang && is_command {
                log::info!("Skipping terminal/kill command block: {}::{}", language, file_path);
                continue;
            }
            
            // Only add valid operations
            if !file_path.is_empty() && !file_content.is_empty() {
                log::info!("Found file operation: {} ({})", file_path, language);
                operations.push(FileOperation {
                    path: file_path,
                    content: file_content,
                    language,
                });
            }
        }
    }
    
    operations
}

/// Execute file operations (create/update files)
fn execute_file_operations(operations: &[FileOperation]) -> Vec<(String, bool, String)> {
    let workspace = std::env::var("DCODE_WORKSPACE")
        .map(std::path::PathBuf::from)
        .unwrap_or_else(|_| {
            dirs::document_dir()
                .map(|d| d.join("D-code"))
                .unwrap_or_else(|| std::path::PathBuf::from("./workspace"))
        });
    
    let projects_dir = workspace.join("projects");
    let mut results = Vec::new();
    
    for op in operations {
        // Resolve full path
        let full_path = projects_dir.join(&op.path);
        
        // Create parent directories if needed
        if let Some(parent) = full_path.parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                log::error!("Failed to create directory {:?}: {}", parent, e);
                results.push((op.path.clone(), false, format!("Failed to create directory: {}", e)));
                continue;
            }
        }
        
        // Write the file
        match std::fs::write(&full_path, &op.content) {
            Ok(_) => {
                log::info!("Created file: {}", full_path.display());
                results.push((op.path.clone(), true, "Created".to_string()));
            }
            Err(e) => {
                log::error!("Failed to write file {:?}: {}", full_path, e);
                results.push((op.path.clone(), false, format!("Failed to write: {}", e)));
            }
        }
    }
    
    results
}

/// Execute a terminal command and return output
/// Note: This is a synchronous version - prefer execute_command_streaming for real-time output
#[allow(dead_code)]
fn execute_terminal_command(command: &str, working_dir: &std::path::Path) -> String {
    use std::process::Command;
    
    log::info!("Executing command in {:?}: {}", working_dir, command);
    
    // Create working directory if it doesn't exist
    let _ = std::fs::create_dir_all(working_dir);
    
    // Use PowerShell on Windows, sh on other platforms
    #[cfg(windows)]
    let result = Command::new("powershell")
        .args(["-NoProfile", "-Command", command])
        .current_dir(working_dir)
        .output();
    
    #[cfg(not(windows))]
    let result = Command::new("sh")
        .args(["-c", command])
        .current_dir(working_dir)
        .output();
    
    match result {
        Ok(output) => {
            let stdout = String::from_utf8_lossy(&output.stdout);
            let stderr = String::from_utf8_lossy(&output.stderr);
            
            let mut result = String::new();
            result.push_str(&format!("$ {}\n", command));
            
            if !stdout.is_empty() {
                result.push_str(&stdout);
            }
            if !stderr.is_empty() {
                if !stdout.is_empty() {
                    result.push('\n');
                }
                result.push_str(&stderr);
            }
            
            if output.status.success() {
                log::info!("Command succeeded");
            } else {
                log::warn!("Command failed with status: {:?}", output.status);
            }
            
            result
        }
        Err(e) => {
            log::error!("Failed to execute command: {}", e);
            format!("$ {}\nError: Failed to execute command: {}", command, e)
        }
    }
}

/// Execute a terminal command and return output with PID
/// Returns (output, Option<pid>)
/// Note: This is a synchronous version - prefer execute_command_streaming for real-time output
#[allow(dead_code)]
fn execute_terminal_command_with_pid(command: &str, working_dir: &std::path::Path) -> (String, Option<u32>) {
    use std::process::{Command, Stdio};
    use std::io::{BufRead, BufReader};
    
    log::info!("Executing command with PID tracking in {:?}: {}", working_dir, command);
    
    // Create working directory if it doesn't exist
    let _ = std::fs::create_dir_all(working_dir);
    
    // Use PowerShell on Windows, sh on other platforms
    #[cfg(windows)]
    let mut child = match Command::new("powershell")
        .args(["-NoProfile", "-Command", command])
        .current_dir(working_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            log::error!("Failed to spawn command: {}", e);
            return (format!("$ {}\nError: Failed to execute command: {}", command, e), None);
        }
    };
    
    #[cfg(not(windows))]
    let mut child = match Command::new("sh")
        .args(["-c", command])
        .current_dir(working_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            log::error!("Failed to spawn command: {}", e);
            return (format!("$ {}\nError: Failed to execute command: {}", command, e), None);
        }
    };
    
    let pid = child.id();
    log::info!("Started process with PID: {}", pid);
    
    // Collect stdout
    let stdout = child.stdout.take();
    let stdout_handle = std::thread::spawn(move || {
        let mut output = String::new();
        if let Some(stdout) = stdout {
            let reader = BufReader::new(stdout);
            for line in reader.lines().flatten() {
                output.push_str(&line);
                output.push('\n');
            }
        }
        output
    });
    
    // Collect stderr
    let stderr = child.stderr.take();
    let stderr_handle = std::thread::spawn(move || {
        let mut output = String::new();
        if let Some(stderr) = stderr {
            let reader = BufReader::new(stderr);
            for line in reader.lines().flatten() {
                output.push_str(&line);
                output.push('\n');
            }
        }
        output
    });
    
    // Wait for process to complete
    let status = child.wait();
    
    // Collect output
    let stdout_output = stdout_handle.join().unwrap_or_default();
    let stderr_output = stderr_handle.join().unwrap_or_default();
    
    let mut result = format!("$ {}\n", command);
    if !stdout_output.is_empty() {
        result.push_str(&stdout_output);
    }
    if !stderr_output.is_empty() {
        result.push_str(&stderr_output);
    }
    
    match status {
        Ok(s) if s.success() => {
            log::info!("Command succeeded (PID: {})", pid);
        }
        Ok(s) => {
            log::warn!("Command failed with status: {:?} (PID: {})", s, pid);
        }
        Err(e) => {
            log::error!("Failed to wait for command: {} (PID: {})", e, pid);
        }
    }
    
    (result, Some(pid))
}

/// Parse AI response and extract terminal commands
/// Looks for code blocks with format: ```bash::run or ```shell::run
fn parse_terminal_commands(response: &str) -> Vec<String> {
    let mut commands = Vec::new();
    
    // Pattern: ```bash::run or ```shell::run or ```cmd::run
    let re = regex::Regex::new(r"```(?:bash|shell|cmd|powershell)::run\n([\s\S]*?)```").unwrap_or_else(|_| {
        return regex::Regex::new(r".*").unwrap();
    });
    
    for cap in re.captures_iter(response) {
        if let Some(cmd) = cap.get(1) {
            let command = cmd.as_str().trim().to_string();
            if !command.is_empty() {
                log::info!("Found terminal command: {}", command);
                commands.push(command);
            }
        }
    }
    
    commands
}

/// Parse AI response and extract kill commands
/// Looks for code blocks with format: ```bash::kill or similar
/// Returns Vec<(terminal_id or "all", optional_pid)>
fn parse_kill_commands(response: &str) -> Vec<(String, Option<u32>)> {
    let mut commands = Vec::new();
    
    // Pattern: ```bash::kill or similar with optional target
    let re = regex::Regex::new(r"```(?:bash|shell|cmd|powershell)::kill\s*\n?([\s\S]*?)```").unwrap_or_else(|_| {
        return regex::Regex::new(r".*").unwrap();
    });
    
    for cap in re.captures_iter(response) {
        if let Some(target) = cap.get(1) {
            let target_str = target.as_str().trim();
            if target_str.is_empty() || target_str == "all" {
                // Kill all running processes
                log::info!("Found kill all command");
                commands.push(("all".to_string(), None));
            } else if let Ok(pid) = target_str.parse::<u32>() {
                // Kill specific PID
                log::info!("Found kill PID command: {}", pid);
                commands.push(("pid".to_string(), Some(pid)));
            } else {
                // Kill by terminal ID
                log::info!("Found kill terminal command: {}", target_str);
                commands.push((target_str.to_string(), None));
            }
        }
    }
    
    commands
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_language_detection() {
        assert_eq!(detect_language("main.rs"), "rust");
        assert_eq!(detect_language("script.py"), "python");
        assert_eq!(detect_language("app.tsx"), "typescriptreact");
        assert_eq!(detect_language("unknown.xyz"), "plaintext");
    }
}
