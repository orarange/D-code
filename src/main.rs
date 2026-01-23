// main.rs
// ========
// D-code Application Entry Point
//
// Responsibilities:
// 1. Initialize Python interpreter with embedded code
// 2. Launch WebView UI (Tauri)
// 3. Bridge communication between UI and Python engine
// 4. Handle application lifecycle

mod bridge;
mod security;
mod terminal;

use std::sync::{Arc, Mutex};
use std::io::Write;
use std::fs::OpenOptions;
use std::path::PathBuf;

// Include the generated embedded Python code
include!(concat!(env!("OUT_DIR"), "/embedded_python.rs"));

/// Application state shared across threads
pub struct AppState {
    /// Flag indicating if the engine is running
    pub engine_running: bool,
    /// Flag for break request
    pub break_requested: bool,
    /// Last error message
    pub last_error: Option<String>,
    /// WebSocket port for streaming
    pub ws_port: u16,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            engine_running: false,
            break_requested: false,
            last_error: None,
            ws_port: 8765,
        }
    }
}

/// Get the log file path
fn get_log_file_path() -> PathBuf {
    let log_dir = if let Some(docs) = dirs::document_dir() {
        docs.join("D-code").join("logs")
    } else if let Some(data) = dirs::data_local_dir() {
        data.join("D-code").join("logs")
    } else {
        PathBuf::from("./logs")
    };
    
    // Ensure directory exists
    let _ = std::fs::create_dir_all(&log_dir);
    
    // Create timestamped log file
    let timestamp = chrono::Local::now().format("%Y%m%d_%H%M%S");
    log_dir.join(format!("dcode_{}.log", timestamp))
}

/// Setup logging to both console and file
fn setup_logging(log_file: &PathBuf) -> Result<(), fern::InitError> {
    let file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_file)?;
    
    fern::Dispatch::new()
        .format(|out, message, record| {
            out.finish(format_args!(
                "[{}][{}][{}] {}",
                chrono::Local::now().format("%Y-%m-%d %H:%M:%S%.3f"),
                record.level(),
                record.target(),
                message
            ))
        })
        .level(log::LevelFilter::Info)
        .level_for("wry", log::LevelFilter::Warn)
        .level_for("tao", log::LevelFilter::Warn)
        .chain(std::io::stderr())
        .chain(file)
        .apply()?;
    
    Ok(())
}

/// Setup panic handler to log crashes
fn setup_panic_handler(log_file: PathBuf) {
    std::panic::set_hook(Box::new(move |panic_info| {
        let backtrace = std::backtrace::Backtrace::force_capture();
        
        let crash_msg = format!(
            "\n\
            ╔══════════════════════════════════════════════════════════════╗\n\
            ║                    D-CODE CRASH REPORT                       ║\n\
            ╠══════════════════════════════════════════════════════════════╣\n\
            ║ Time: {}\n\
            ║ Panic: {}\n\
            ╠══════════════════════════════════════════════════════════════╣\n\
            ║ Backtrace:\n{}\n\
            ╚══════════════════════════════════════════════════════════════╝\n",
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
            panic_info,
            backtrace
        );
        
        // Log to stderr
        eprintln!("{}", crash_msg);
        
        // Also write to crash log file
        let crash_file = log_file.with_extension("crash.log");
        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&crash_file)
        {
            let _ = writeln!(file, "{}", crash_msg);
            eprintln!("Crash log written to: {}", crash_file.display());
        }
        
        // Write to general log file too
        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_file)
        {
            let _ = writeln!(file, "{}", crash_msg);
        }
    }));
}

/// Initialize the Python interpreter and load embedded modules
fn initialize_python() -> Result<(), String> {
    use pyo3::prelude::*;
    use pyo3::types::{PyDict, PyList};
    use std::ffi::CString;
    
    Python::with_gil(|py| {
        // Get sys module first
        let sys = py.import("sys").map_err(|e| e.to_string())?;
        
        // Add site-packages paths to sys.path for finding installed packages
        let sys_path = sys.getattr("path").map_err(|e| e.to_string())?;
        let sys_path: &Bound<'_, PyList> = sys_path.downcast().map_err(|e| e.to_string())?;
        
        // Get the executable's directory
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                // Add .venv paths relative to executable
                let venv_site_packages = exe_dir.join(".venv/Lib/site-packages");
                if venv_site_packages.exists() {
                    let path_str = venv_site_packages.to_string_lossy().to_string();
                    sys_path.insert(0, &path_str).ok();
                    log::info!("Added venv site-packages: {}", path_str);
                }
            }
        }
        
        // Also try current working directory's .venv
        if let Ok(cwd) = std::env::current_dir() {
            let venv_site_packages = cwd.join(".venv/Lib/site-packages");
            if venv_site_packages.exists() {
                let path_str = venv_site_packages.to_string_lossy().to_string();
                // Check if already in path
                let path_str_py = path_str.as_str();
                let already_exists = (0..sys_path.len())
                    .any(|i| {
                        sys_path.get_item(i)
                            .ok()
                            .and_then(|item| item.extract::<String>().ok())
                            .map(|s| s == path_str_py)
                            .unwrap_or(false)
                    });
                if !already_exists {
                    sys_path.insert(0, &path_str).ok();
                    log::info!("Added cwd venv site-packages: {}", path_str);
                }
            }
            
            // Add engine directory to path for imports
            let engine_path = cwd.join("engine");
            if engine_path.exists() {
                let path_str = cwd.to_string_lossy().to_string();
                sys_path.insert(0, &path_str).ok();
                log::info!("Added project root to path: {}", path_str);
            }
        }
        
        // Try to find and add user site-packages (for global pip installs)
        if let Ok(site) = py.import("site") {
            if let Ok(user_site) = site.call_method0("getusersitepackages") {
                if let Ok(user_site_str) = user_site.extract::<String>() {
                    if std::path::Path::new(&user_site_str).exists() {
                        sys_path.append(&user_site_str).ok();
                        log::info!("Added user site-packages: {}", user_site_str);
                    }
                }
            }
        }
        
        // Create a virtual module namespace for our embedded code
        let modules = sys
            .getattr("modules")
            .map_err(|e| e.to_string())?;
        let modules: &Bound<'_, PyDict> = modules
            .downcast()
            .map_err(|e| e.to_string())?;
        
        // Get builtins for global namespace
        let builtins = py.import("builtins").map_err(|e| e.to_string())?;
        let types = py.import("types").map_err(|e| e.to_string())?;
        let module_type = types.getattr("ModuleType").map_err(|e| e.to_string())?;
        
        // First, create the 'engine' parent package
        let engine_module = module_type
            .call1(("engine",))
            .map_err(|e| e.to_string())?;
        let engine_dict = engine_module.getattr("__dict__").map_err(|e| e.to_string())?;
        let engine_dict: &Bound<'_, PyDict> = engine_dict
            .downcast()
            .map_err(|e| e.to_string())?;
        engine_dict.set_item("__builtins__", &builtins).map_err(|e: pyo3::PyErr| e.to_string())?;
        engine_dict.set_item("__name__", "engine").map_err(|e: pyo3::PyErr| e.to_string())?;
        engine_dict.set_item("__path__", Vec::<String>::new()).map_err(|e: pyo3::PyErr| e.to_string())?;
        engine_dict.set_item("__package__", "engine").map_err(|e: pyo3::PyErr| e.to_string())?;
        modules.set_item("engine", &engine_module).map_err(|e: pyo3::PyErr| e.to_string())?;
        log::info!("Created engine parent package");
        
        // Load each embedded Python file
        for module_name in get_module_names() {
            if let Some(code) = get_python_code(module_name) {
                // Convert filename to module name (e.g., "main_agent.py" -> "engine.main_agent")
                let mod_name = module_name
                    .trim_end_matches(".py")
                    .replace('/', ".");
                let full_mod_name = format!("engine.{}", mod_name);
                
                // Create module object
                let module = module_type
                    .call1((&full_mod_name,))
                    .map_err(|e| e.to_string())?;
                
                // Get module dict and set up proper namespace
                let module_dict = module.getattr("__dict__").map_err(|e| e.to_string())?;
                let module_dict: &Bound<'_, PyDict> = module_dict
                    .downcast()
                    .map_err(|e| e.to_string())?;
                
                // Set __builtins__ and other required attributes
                module_dict.set_item("__builtins__", &builtins).map_err(|e: pyo3::PyErr| e.to_string())?;
                module_dict.set_item("__name__", &full_mod_name).map_err(|e: pyo3::PyErr| e.to_string())?;
                module_dict.set_item("__file__", module_name).map_err(|e: pyo3::PyErr| e.to_string())?;
                module_dict.set_item("__package__", "engine").map_err(|e: pyo3::PyErr| e.to_string())?;
                
                // Register module BEFORE executing (needed for relative imports)
                modules.set_item(&full_mod_name, &module).map_err(|e: pyo3::PyErr| e.to_string())?;
                
                // Also register as attribute of engine package
                let attr_name = mod_name.replace('.', "_");
                engine_dict.set_item(&attr_name, &module).map_err(|e: pyo3::PyErr| e.to_string())?;
                
                // Use run_bound with CString for the code
                let code_cstr = CString::new(code.as_str()).map_err(|e| e.to_string())?;
                py.run(&code_cstr, Some(module_dict), Some(module_dict))
                    .map_err(|e| e.to_string())?;
                
                log::info!("Loaded embedded module: {}", full_mod_name);
            }
        }
        
        Ok(())
    })
}

/// Start the D-code engine in a background thread
#[allow(dead_code)]
fn start_engine(state: Arc<Mutex<AppState>>, api_key: String, workspace: String) {
    std::thread::spawn(move || {
        use pyo3::prelude::*;
        
        // Update state
        {
            let mut s = state.lock().unwrap();
            s.engine_running = true;
        }
        
        let result = Python::with_gil(|py| -> PyResult<()> {
            // Import our engine module
            let engine_module = py.import("engine.main_agent")?;
            
            // Create engine instance
            let create_engine = engine_module.getattr("create_engine")?;
            let engine = create_engine.call1((&api_key, &workspace))?;
            
            // Set up break check callback (for future use)
            let _check_break = {
                let state_clone = state.clone();
                move || -> bool {
                    state_clone.lock().map(|s| s.break_requested).unwrap_or(false)
                }
            };
            
            // Run the engine (this would be async in practice)
            engine.call_method0("compile")?;
            
            log::info!("D-code engine started successfully");
            
            Ok(())
        });
        
        // Handle result
        {
            let mut s = state.lock().unwrap();
            s.engine_running = false;
            if let Err(e) = result {
                s.last_error = Some(e.to_string());
                log::error!("Engine error: {}", e);
            }
        }
    });
}

/// Request the engine to break/pause
#[allow(dead_code)]
fn request_break(state: &Arc<Mutex<AppState>>) {
    if let Ok(mut s) = state.lock() {
        s.break_requested = true;
        log::info!("Break requested");
    }
}

/// Main entry point
fn main() {
    // Setup logging first (to file and console)
    let log_file = get_log_file_path();
    if let Err(e) = setup_logging(&log_file) {
        eprintln!("Warning: Failed to setup file logging: {}", e);
        // Fallback to env_logger
        env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
            .init();
    } else {
        eprintln!("Log file: {}", log_file.display());
    }
    
    // Setup panic handler for crash reports
    setup_panic_handler(log_file.clone());
    
    log::info!("=== D-code Starting ===");
    log::info!("Log file: {}", log_file.display());
    
    // Load environment variables from .env file (if it exists)
    // Try multiple locations: current directory, executable directory
    let mut env_loaded = false;
    
    // First, try loading from current directory
    if let Err(e) = dotenvy::dotenv() {
        log::debug!(".env not in current directory: {}", e);
        
        // Try loading from executable's directory
        if let Ok(exe_path) = std::env::current_exe() {
            if let Some(exe_dir) = exe_path.parent() {
                let env_path = exe_dir.join(".env");
                if env_path.exists() {
                    if let Err(e) = dotenvy::from_path(&env_path) {
                        log::warn!(".env in exe directory failed to load: {}", e);
                    } else {
                        log::info!("Loaded .env from: {}", env_path.display());
                        env_loaded = true;
                    }
                }
            }
        }
    } else {
        env_loaded = true;
        log::info!("Loaded .env from current directory");
    }
    
    if !env_loaded {
        log::info!("No .env file loaded - using system environment variables");
    }
    
    // Debug: Print key environment variables
    log::info!("=== Environment Variables ===");
    log::info!("DCODE_API_BASE_URL: {:?}", std::env::var("DCODE_API_BASE_URL").ok());
    log::info!("DCODE_API_BACKEND: {:?}", std::env::var("DCODE_API_BACKEND").ok());
    log::info!("GEMINI_API_KEY: {}", if std::env::var("GEMINI_API_KEY").is_ok() { "set" } else { "not set" });
    log::info!("DCODE_CHAT_MODEL: {:?}", std::env::var("DCODE_CHAT_MODEL").ok());
    log::info!("=============================");
    
    log::info!("D-code v{} starting...", env!("CARGO_PKG_VERSION"));
    
    // Initialize security module
    if let Err(e) = security::initialize() {
        log::error!("Security initialization failed: {}", e);
        return;
    }
    
    // Initialize workspace directory in Documents folder
    let workspace = initialize_workspace();
    log::info!("Workspace initialized at: {}", workspace.display());
    
    // Initialize Python interpreter (optional - may fail if dependencies missing)
    log::info!("Initializing Python interpreter...");
    let python_available = match initialize_python() {
        Ok(()) => {
            log::info!("Python interpreter initialized with {} embedded modules", 
                       get_module_names().len());
            true
        }
        Err(e) => {
            log::warn!("Python initialization failed (AI features unavailable): {}", e);
            log::info!("To enable AI features, install Python dependencies:");
            log::info!("  pip install google-genai langgraph pydantic");
            false
        }
    };
    
    // Create shared application state
    let state = Arc::new(Mutex::new(AppState::default()));
    
    // Get configuration from environment
    let api_key = std::env::var("GEMINI_API_KEY").unwrap_or_default();
    
    if api_key.is_empty() {
        log::info!("GEMINI_API_KEY not set - using local LM Studio mode");
    }
    
    // Set workspace path as environment variable for Python access
    std::env::set_var("DCODE_WORKSPACE", workspace.to_string_lossy().as_ref());
    
    // Print startup info
    let python_status = if python_available { "Ready" } else { "Unavailable" };
    let workspace_str = workspace.to_string_lossy();
    println!();
    println!("╔════════════════════════════════════════════╗");
    println!("║            D-code Engine Ready             ║");
    println!("╠════════════════════════════════════════════╣");
    println!("║  Mode:      Desktop Application           ║");
    println!("║  Workspace: {}  ║", if workspace_str.len() > 28 { "..." } else { &workspace_str });
    println!("║  Python:    {:<29}║", python_status);
    println!("║  Modules:   {} embedded                    ║", get_module_names().len());
    println!("║  Log:       {}  ║", log_file.file_name().unwrap_or_default().to_string_lossy());
    println!("╚════════════════════════════════════════════╝");
    println!();
    
    log::info!("Starting desktop application...");
    
    // Start the desktop application (this blocks until window is closed)
    bridge::start_desktop_app(state, python_available);
    
    log::info!("D-code application exited normally.");
}

/// Initialize workspace directory in user's Documents folder
fn initialize_workspace() -> std::path::PathBuf {
    // Try to get Documents folder, fall back to AppData/Local
    let workspace = if let Some(docs) = dirs::document_dir() {
        docs.join("D-code")
    } else if let Some(data) = dirs::data_local_dir() {
        data.join("D-code")
    } else {
        // Ultimate fallback: current directory
        std::env::current_dir()
            .unwrap_or_else(|_| std::path::PathBuf::from("."))
            .join("workspace")
    };
    
    // Create workspace directory structure
    let projects_dir = workspace.join("projects");
    let logs_dir = workspace.join("logs");
    
    // Create directories if they don't exist
    if let Err(e) = std::fs::create_dir_all(&projects_dir) {
        log::warn!("Failed to create projects directory: {}", e);
    }
    if let Err(e) = std::fs::create_dir_all(&logs_dir) {
        log::warn!("Failed to create logs directory: {}", e);
    }
    
    // Create a README if this is first run
    let readme_path = workspace.join("README.md");
    if !readme_path.exists() {
        let readme_content = r#"# D-code Workspace

This is the D-code AI development workspace.

## Directory Structure

- `projects/` - Your AI-assisted development projects
- `logs/` - Engine logs and session history

## Getting Started

1. Start D-code application
2. Type your project requirements in the chat
3. Watch as the AI team builds your project!

---
*This folder was created automatically by D-code on first launch.*
"#;
        if let Err(e) = std::fs::write(&readme_path, readme_content) {
            log::warn!("Failed to create README: {}", e);
        }
    }
    
    workspace
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_embedded_modules_exist() {
        let modules = get_module_names();
        assert!(!modules.is_empty(), "No embedded modules found");
    }
    
    #[test]
    fn test_deobfuscation() {
        let test_data = b"Hello, World!";
        let obfuscated: Vec<u8> = test_data
            .iter()
            .enumerate()
            .map(|(i, b)| b ^ OBFUSCATION_KEY[i % OBFUSCATION_KEY.len()])
            .collect();
        
        let deobfuscated = deobfuscate(&obfuscated);
        assert_eq!(deobfuscated, test_data);
    }
}
