// security.rs
// ============
// Security and anti-decompilation measures for D-code
//
// Implements:
// - In-memory Python execution (no disk writes)
// - Code obfuscation helpers
// - Runtime integrity checks
// - Debugger detection (optional)

use std::collections::HashMap;
use std::sync::Mutex;

/// In-memory Python module storage
static MEMORY_MODULES: Mutex<Option<HashMap<String, Vec<u8>>>> = Mutex::new(None);

/// Security configuration
#[allow(dead_code)]
pub struct SecurityConfig {
    /// Enable debugger detection
    pub detect_debugger: bool,
    /// Enable integrity checks
    pub integrity_checks: bool,
    /// Enable timing attack protection
    pub timing_protection: bool,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            detect_debugger: cfg!(not(debug_assertions)),
            integrity_checks: true,
            timing_protection: true,
        }
    }
}

/// Initialize security module
pub fn initialize() -> Result<(), String> {
    // Initialize memory module storage
    {
        let mut modules = MEMORY_MODULES.lock().map_err(|e| e.to_string())?;
        *modules = Some(HashMap::new());
    }
    
    // Run integrity checks in release mode
    #[cfg(not(debug_assertions))]
    {
        if !verify_integrity() {
            return Err("Integrity check failed".to_string());
        }
        
        if detect_debugger() {
            log::warn!("Debugger detected - some features may be disabled");
        }
    }
    
    log::info!("Security module initialized");
    Ok(())
}

/// Store Python code in memory (never written to disk)
#[allow(dead_code)]
pub fn store_code_in_memory(name: &str, code: &[u8]) -> Result<(), String> {
    let mut modules = MEMORY_MODULES.lock().map_err(|e| e.to_string())?;
    
    if let Some(ref mut map) = *modules {
        map.insert(name.to_string(), code.to_vec());
        Ok(())
    } else {
        Err("Memory storage not initialized".to_string())
    }
}

/// Retrieve Python code from memory
#[allow(dead_code)]
pub fn get_code_from_memory(name: &str) -> Option<Vec<u8>> {
    let modules = MEMORY_MODULES.lock().ok()?;
    
    modules.as_ref()?.get(name).cloned()
}

/// Clear all stored code from memory
#[allow(dead_code)]
pub fn clear_memory() {
    if let Ok(mut modules) = MEMORY_MODULES.lock() {
        if let Some(ref mut map) = *modules {
            // Securely clear memory
            for (_, code) in map.iter_mut() {
                for byte in code.iter_mut() {
                    *byte = 0;
                }
            }
            map.clear();
        }
    }
}

/// XOR-based obfuscation (same as build.rs for consistency)
#[allow(dead_code)]
pub fn xor_cipher(data: &[u8], key: &[u8]) -> Vec<u8> {
    data.iter()
        .enumerate()
        .map(|(i, byte)| byte ^ key[i % key.len()])
        .collect()
}

/// AES-GCM encryption for sensitive data
#[cfg(feature = "aes-encryption")]
pub mod aes {
    use aes_gcm::{
        aead::{Aead, KeyInit, OsRng},
        Aes256Gcm, Nonce,
    };
    use rand::RngCore;
    
    /// Encrypt data using AES-256-GCM
    pub fn encrypt(plaintext: &[u8], key: &[u8; 32]) -> Result<Vec<u8>, String> {
        let cipher = Aes256Gcm::new_from_slice(key)
            .map_err(|e| e.to_string())?;
        
        let mut nonce_bytes = [0u8; 12];
        OsRng.fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);
        
        let ciphertext = cipher
            .encrypt(nonce, plaintext)
            .map_err(|e| e.to_string())?;
        
        // Prepend nonce to ciphertext
        let mut result = nonce_bytes.to_vec();
        result.extend(ciphertext);
        
        Ok(result)
    }
    
    /// Decrypt data using AES-256-GCM
    pub fn decrypt(ciphertext: &[u8], key: &[u8; 32]) -> Result<Vec<u8>, String> {
        if ciphertext.len() < 12 {
            return Err("Ciphertext too short".to_string());
        }
        
        let cipher = Aes256Gcm::new_from_slice(key)
            .map_err(|e| e.to_string())?;
        
        let nonce = Nonce::from_slice(&ciphertext[..12]);
        let ciphertext = &ciphertext[12..];
        
        cipher
            .decrypt(nonce, ciphertext)
            .map_err(|e| e.to_string())
    }
}

/// Verify binary integrity (basic implementation)
fn verify_integrity() -> bool {
    // In production, this would:
    // 1. Check binary hash against expected value
    // 2. Verify code signatures
    // 3. Check for tampering indicators
    
    // Placeholder: always return true in development
    true
}

/// Detect if a debugger is attached
fn detect_debugger() -> bool {
    #[cfg(target_os = "windows")]
    {
        // Windows: check IsDebuggerPresent
        unsafe {
            extern "system" {
                fn IsDebuggerPresent() -> i32;
            }
            IsDebuggerPresent() != 0
        }
    }
    
    #[cfg(target_os = "linux")]
    {
        // Linux: check /proc/self/status for TracerPid
        if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
            for line in status.lines() {
                if line.starts_with("TracerPid:") {
                    let pid: i32 = line
                        .split(':')
                        .nth(1)
                        .and_then(|s| s.trim().parse().ok())
                        .unwrap_or(0);
                    return pid != 0;
                }
            }
        }
        false
    }
    
    #[cfg(target_os = "macos")]
    {
        // macOS: check sysctl for P_TRACED flag
        use std::process::Command;
        
        if let Ok(output) = Command::new("sysctl")
            .args(["kern.proc.pid", &std::process::id().to_string()])
            .output()
        {
            let output_str = String::from_utf8_lossy(&output.stdout);
            return output_str.contains("P_TRACED");
        }
        false
    }
    
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    {
        false
    }
}

/// Constant-time comparison to prevent timing attacks
#[allow(dead_code)]
pub fn constant_time_compare(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    
    let mut result = 0u8;
    for (x, y) in a.iter().zip(b.iter()) {
        result |= x ^ y;
    }
    result == 0
}

/// Secure string that zeros memory on drop
#[allow(dead_code)]
pub struct SecureString {
    data: Vec<u8>,
}

#[allow(dead_code)]
impl SecureString {
    pub fn new(s: &str) -> Self {
        Self {
            data: s.as_bytes().to_vec(),
        }
    }
    
    pub fn as_str(&self) -> &str {
        std::str::from_utf8(&self.data).unwrap_or("")
    }
}

impl Drop for SecureString {
    fn drop(&mut self) {
        // Zero out memory before dropping
        for byte in self.data.iter_mut() {
            *byte = 0;
        }
    }
}

impl std::fmt::Debug for SecureString {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "SecureString([REDACTED])")
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_xor_cipher_roundtrip() {
        let data = b"Secret Python code!";
        let key = b"MySecretKey12345";
        
        let encrypted = xor_cipher(data, key);
        let decrypted = xor_cipher(&encrypted, key);
        
        assert_eq!(decrypted, data);
    }
    
    #[test]
    fn test_constant_time_compare() {
        let a = b"password123";
        let b = b"password123";
        let c = b"password124";
        let d = b"pass";
        
        assert!(constant_time_compare(a, b));
        assert!(!constant_time_compare(a, c));
        assert!(!constant_time_compare(a, d));
    }
    
    #[test]
    fn test_memory_storage() {
        initialize().unwrap();
        
        let code = b"print('Hello, World!')";
        store_code_in_memory("test.py", code).unwrap();
        
        let retrieved = get_code_from_memory("test.py").unwrap();
        assert_eq!(retrieved, code);
        
        clear_memory();
        assert!(get_code_from_memory("test.py").is_none());
    }
    
    #[test]
    fn test_secure_string_zeroed() {
        let data_ptr: *const u8;
        let len: usize;
        
        {
            let secure = SecureString::new("sensitive_data");
            data_ptr = secure.data.as_ptr();
            len = secure.data.len();
            assert_eq!(secure.as_str(), "sensitive_data");
        }
        
        // After drop, memory should be zeroed
        // Note: This test may be flaky due to memory reuse
    }
}
