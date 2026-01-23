import { create } from 'zustand';

/**
 * Types for D-code state management
 */

export interface StreamMessage {
  id: string;
  timestamp: string;
  agent: string;
  agentIcon: string;
  messageType: 'info' | 'success' | 'warning' | 'error' | 'progress' | 'code' | 'thinking';
  content: string;
  metadata?: Record<string, unknown>;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  type: string;
  priority: number;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress?: number;
  engineerId?: string;
}

export interface Engineer {
  id: string;
  name: string;
  icon: string;
  status: 'idle' | 'working' | 'error';
  tasks: Task[];
}

/** AI Agent Status for dashboard */
export interface AgentStatus {
  id: string;
  name: string;
  icon: string;
  state: 'thinking' | 'idle' | 'error' | 'completed' | 'waiting';
  currentTask?: string;
  progress?: number;
  lastActivity?: string;
}

/** Conversation session info */
export interface ConversationSession {
  sessionId: string;
  displayDate: string;
  preview: string;
}

export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'folder';
  children?: FileNode[];
  language?: string;
}

/** Terminal instance */
export interface TerminalInstance {
  id: string;
  name: string;
  output: string[];
  isRunning: boolean;
  command?: string;
  createdAt: number;
  pid?: number;  // Process ID for kill functionality
}

/** AI思考ストリーミング状態 */
export interface StreamingState {
  isStreaming: boolean;
  messageId: string | null;
  currentContent: string;
  agent: string;
}

export interface AppState {
  // Connection state
  isConnected: boolean;
  connectionError: string | null;
  engineRunning: boolean;
  isLoading: boolean; // AI is currently processing a request
  ws: WebSocket | null;

  // Messages from AI agents
  messages: StreamMessage[];

  // AI thinking streaming state
  streaming: StreamingState;

  // Task management
  tasks: Task[];
  engineers: Engineer[];
  currentTaskId: string | null;

  // File explorer
  files: FileNode[];
  selectedFile: string | null;
  fileContent: string;

  // Terminal instances (VSCode-like tabs)
  terminals: TerminalInstance[];
  activeTerminalId: string | null;

  // Legacy terminal output (for backward compatibility and context)
  terminalOutput: string[];

  // AI Agents Status (for AI Status Dashboard)
  agentStatuses: AgentStatus[];

  // Conversation sessions (for chat history)
  conversationSessions: ConversationSession[];
  currentSessionId: string | null;

  // Progress tracking
  progress: {
    current: number;
    total: number;
    percentage: number;
  };

  // Actions
  connect: () => void;
  disconnect: () => void;
  sendMessage: (content: string) => void;
  requestBreak: () => void;
  selectFile: (path: string) => void;
  addMessage: (message: StreamMessage) => void;
  setLoading: (loading: boolean) => void;
  updateProgress: (current: number, total: number) => void;
  setTasks: (tasks: Task[]) => void;
  setEngineers: (engineers: Engineer[]) => void;
  updateTaskStatus: (taskId: string, status: Task['status']) => void;
  
  // Terminal actions
  addTerminalOutput: (terminalId: string, line: string, isRunning?: boolean, pid?: number) => void;
  createTerminal: (id: string, command?: string) => void;
  closeTerminal: (id: string) => void;
  setActiveTerminal: (id: string) => void;
  clearTerminal: (id?: string) => void;
  getAllTerminalOutput: () => string[];
  killTerminalProcess: (terminalId: string) => void;
  
  // Agent status actions
  updateAgentStatus: (agentId: string, update: Partial<AgentStatus>) => void;
  setAgentStatuses: (statuses: AgentStatus[]) => void;
  
  // Conversation session actions
  initConversationManager: (projectRoot: string) => void;
  listConversationSessions: (limit?: number) => void;
  loadConversationSession: (sessionId: string) => void;
  setConversationSessions: (sessions: ConversationSession[]) => void;
  setCurrentSessionId: (sessionId: string | null) => void;
  
  // File editing actions (for diff-based partial updates)
  editFileSearchReplace: (filePath: string, search: string, replace: string, occurrence?: number) => void;
  createDiff: (original: string, modified: string, filename: string) => void;
  
  // File management actions
  deleteFile: (path: string) => void;
  refreshFiles: () => void;
  
  // Terminal input action (user direct input)
  sendTerminalInput: (terminalId: string, input: string) => void;
}

const WS_URL = 'ws://localhost:8765';

// pywebview API type
interface PyWebViewAPI {
  get_status: () => Promise<{ connected: boolean; engineRunning: boolean; apiKeySet: boolean }>;
  get_messages: () => Promise<StreamMessage[]>;
  send_message: (content: string) => Promise<{ success: boolean }>;
  request_break: () => Promise<{ success: boolean }>;
  get_files: () => Promise<FileNode[]>;
  read_file: (path: string) => Promise<{ path: string; content: string; language: string } | { error: string }>;
  set_api_key: (key: string) => Promise<{ success: boolean }>;
}

// Get pywebview API
function getPyWebViewAPI(): PyWebViewAPI | null {
  const win = window as unknown as { pywebview?: { api?: PyWebViewAPI } };
  return win.pywebview?.api || null;
}

// Check if running in wry webview (has window.ipc)
function isWryWebView(): boolean {
  const win = window as unknown as { ipc?: { postMessage: (msg: string) => void } };
  return !!win.ipc?.postMessage;
}

// Send message to Rust via wry IPC
function sendToRust(command: Record<string, unknown>): void {
  const win = window as unknown as { ipc?: { postMessage: (msg: string) => void } };
  if (win.ipc?.postMessage) {
    win.ipc.postMessage(JSON.stringify(command));
  }
}

export const useStore = create<AppState>((set, get) => ({
  // Initial state
  isConnected: false,
  connectionError: null,
  engineRunning: false,
  isLoading: false,
  ws: null,
  messages: [],
  streaming: {
    isStreaming: false,
    messageId: null,
    currentContent: '',
    agent: 'D-code',
  },
  tasks: [],
  engineers: [],
  currentTaskId: null,
  files: [],
  selectedFile: null,
  fileContent: '',
  terminals: [],
  activeTerminalId: null,
  terminalOutput: [],
  // Default AI agent statuses
  agentStatuses: [
    {
      id: 'orchestrator',
      name: 'Orchestrator',
      icon: '🎯',
      state: 'idle',
      currentTask: undefined,
      progress: undefined,
      lastActivity: undefined,
    },
    {
      id: 'planner',
      name: 'Planner',
      icon: '📋',
      state: 'idle',
      currentTask: undefined,
      progress: undefined,
      lastActivity: undefined,
    },
    {
      id: 'worker',
      name: 'Worker',
      icon: '⚙️',
      state: 'idle',
      currentTask: undefined,
      progress: undefined,
      lastActivity: undefined,
    },
  ],
  // Conversation sessions
  conversationSessions: [],
  currentSessionId: null,
  progress: { current: 0, total: 0, percentage: 0 },

  // Connect - supports both WebSocket and pywebview
  connect: () => {
    // Check for wry webview first (desktop mode)
    if (isWryWebView()) {
      console.log('D-code Desktop Mode - Using wry IPC');
      set({ isConnected: true, connectionError: null });
      
      // Listen for connected event from Rust
      window.addEventListener('dcode-connected', ((event: CustomEvent) => {
        console.log('Connected to Rust backend:', event.detail);
        const { pythonAvailable, apiKeySet, workspacePath, debugMode } = event.detail;
        set({ 
          engineRunning: true,
        });
        
        // Show connection status only in debug mode or on error
        if (debugMode || !pythonAvailable) {
          const statusMessage: StreamMessage = {
            id: `status_${Date.now()}`,
            timestamp: new Date().toISOString(),
            agent: 'system',
            agentIcon: pythonAvailable ? '✅' : '⚠️',
            messageType: pythonAvailable ? 'success' : 'warning',
            content: pythonAvailable 
              ? `Python engine ready. API key: ${apiKeySet ? 'Set' : 'Not set'}`
              : 'Python not available - limited functionality',
          };
          set((state) => ({
            messages: [...state.messages, statusMessage],
          }));
        }
        
        // Initialize conversation manager with workspace path
        if (pythonAvailable && workspacePath) {
          console.log('Initializing conversation manager with workspace:', workspacePath);
          get().initConversationManager(workspacePath);
        }
      }) as EventListener);
      
      // Listen for status events from Rust
      window.addEventListener('dcode-status', ((event: CustomEvent) => {
        const status = event.detail;
        set({ 
          engineRunning: status.engine_running,
        });
      }) as EventListener);
      
      // Listen for AI thinking stream chunks (real-time streaming)
      window.addEventListener('dcode-thinking', ((event: CustomEvent) => {
        const { message_id, chunk, agent } = event.detail;
        set((state) => ({
          streaming: {
            isStreaming: true,
            messageId: message_id,
            currentContent: state.streaming.currentContent + chunk,
            agent: agent || 'D-code',
          },
        }));
      }) as EventListener);
      
      // Listen for AI thinking complete
      window.addEventListener('dcode-thinking-complete', ((_event: CustomEvent) => {
        set(() => ({
          streaming: {
            isStreaming: false,
            messageId: null,
            currentContent: '',
            agent: 'D-code',
          },
          isLoading: false,
        }));
      }) as EventListener);
      
      // Listen for agent status updates
      window.addEventListener('dcode-agent-status', ((event: CustomEvent) => {
        const { agent_id, state, current_task, progress } = event.detail;
        get().updateAgentStatus(agent_id, {
          state: state as AgentStatus['state'],
          currentTask: current_task,
          progress: progress,
        });
      }) as EventListener);
      
      // Listen for conversation manager initialized
      window.addEventListener('dcode-conversation-manager-initialized', ((event: CustomEvent) => {
        const { session_id } = event.detail;
        console.log('Conversation manager initialized, session:', session_id);
        set(() => ({ currentSessionId: session_id }));
        // Automatically list previous sessions
        get().listConversationSessions();
      }) as EventListener);
      
      // Listen for conversation sessions list
      window.addEventListener('dcode-conversation-sessions-list', ((event: CustomEvent) => {
        const { sessions } = event.detail;
        console.log('Received conversation sessions:', sessions);
        const convertedSessions: ConversationSession[] = (sessions || []).map((s: any) => ({
          sessionId: s.session_id,
          displayDate: s.display_date,
          preview: s.preview,
        }));
        set(() => ({ conversationSessions: convertedSessions }));
      }) as EventListener);
      
      // Listen for conversation session loaded
      window.addEventListener('dcode-conversation-session-loaded', ((event: CustomEvent) => {
        const { session_id, success, message_count } = event.detail;
        console.log(`Loaded session ${session_id}: success=${success}, messages=${message_count}`);
        if (success) {
          set(() => ({ currentSessionId: session_id }));
          // Add a system message to indicate session loaded
          const message: StreamMessage = {
            id: `session_loaded_${Date.now()}`,
            timestamp: new Date().toISOString(),
            agent: 'System',
            agentIcon: '📁',
            messageType: 'info',
            content: `前回のセッション (${message_count}件のメッセージ) を読み込みました。`,
          };
          set((state) => ({
            messages: [...state.messages, message],
          }));
        }
      }) as EventListener);
      
      // Listen for messages from Rust
      window.addEventListener('dcode-message', ((event: CustomEvent) => {
        const data = event.detail;
        // Clear streaming state when a complete message arrives
        set(() => ({
          streaming: {
            isStreaming: false,
            messageId: null,
            currentContent: '',
            agent: 'D-code',
          },
        }));
        // Convert snake_case to camelCase for compatibility
        const message: StreamMessage = {
          id: data.id,
          timestamp: data.timestamp,
          agent: data.agent,
          agentIcon: data.agent_icon || '🤖',
          messageType: data.message_type || 'info',
          content: data.content,
          metadata: data.metadata,
        };
        set((state) => ({
          messages: [...state.messages, message],
          isLoading: false, // Stop loading when AI responds
        }));
      }) as EventListener);
      
      // Listen for file list from Rust
      window.addEventListener('dcode-files', ((event: CustomEvent) => {
        const { files } = event.detail;
        // Convert to FileNode format
        const convertFiles = (items: any[]): FileNode[] => {
          return items.map(item => ({
            name: item.name,
            path: item.path,
            type: item.type === 'folder' ? 'folder' : 'file',
            children: item.children ? convertFiles(item.children) : undefined,
          }));
        };
        set({ files: convertFiles(files || []) });
      }) as EventListener);
      
      // Listen for file content from Rust
      window.addEventListener('dcode-file-content', ((event: CustomEvent) => {
        const { path, content } = event.detail;
        set({ selectedFile: path, fileContent: content });
      }) as EventListener);
      
      // Listen for errors from Rust
      window.addEventListener('dcode-error', ((event: CustomEvent) => {
        const { message } = event.detail;
        const errorMessage: StreamMessage = {
          id: `error_${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'system',
          agentIcon: '❌',
          messageType: 'error',
          content: message,
        };
        set((state) => ({
          messages: [...state.messages, errorMessage],
          isLoading: false, // Stop loading on error
        }));
      }) as EventListener);
      
      // Listen for terminal output from Rust (updated for multi-terminal support)
      window.addEventListener('dcode-terminal', ((event: CustomEvent) => {
        const { terminal_id, line, is_running, pid } = event.detail;
        if (terminal_id && line !== undefined) {
          // Multi-terminal mode
          set((state) => {
            // Find or create terminal
            let terminals = [...state.terminals];
            let terminalIndex = terminals.findIndex(t => t.id === terminal_id);
            
            if (terminalIndex === -1) {
              // Create new terminal
              const command = line.startsWith('$ ') ? line.slice(2) : undefined;
              terminals.push({
                id: terminal_id,
                name: command ? command.split(' ')[0] : `Terminal ${terminals.length + 1}`,
                output: [],
                isRunning: is_running ?? true,
                command,
                createdAt: Date.now(),
                pid: pid,
              });
              terminalIndex = terminals.length - 1;
            }
            
            // Add output line
            terminals[terminalIndex] = {
              ...terminals[terminalIndex],
              output: [...terminals[terminalIndex].output, line],
              isRunning: is_running ?? terminals[terminalIndex].isRunning,
              pid: pid ?? terminals[terminalIndex].pid,
            };
            
            // Also add to legacy terminalOutput for AI context
            const terminalOutput = [...state.terminalOutput, line];
            
            return {
              terminals,
              activeTerminalId: state.activeTerminalId || terminal_id,
              terminalOutput,
            };
          });
        } else if (line) {
          // Legacy mode (backward compatibility)
          set((state) => ({
            terminalOutput: [...state.terminalOutput, line],
          }));
        }
      }) as EventListener);
      
      // Listen for process killed events
      window.addEventListener('dcode-process-killed', ((event: CustomEvent) => {
        const { terminal_id, success, message } = event.detail;
        console.log(`Process killed for terminal ${terminal_id}: ${success} - ${message}`);
        
        // Update terminal to not running state
        set((state) => {
          const terminals = state.terminals.map(t => 
            t.id === terminal_id 
              ? { ...t, isRunning: false, pid: undefined }
              : t
          );
          return { terminals };
        });
        
        // Add message to terminal output
        set((state) => {
          const terminals = state.terminals.map(t => 
            t.id === terminal_id 
              ? { ...t, output: [...t.output, `[${success ? '✓' : '✗'}] ${message}`] }
              : t
          );
          return { terminals };
        });
      }) as EventListener);
      
      // Listen for file deleted events
      window.addEventListener('dcode-file-deleted', ((event: CustomEvent) => {
        const { path, success, message } = event.detail;
        console.log(`File deleted: ${path} - ${success} - ${message}`);
        
        // Add system message about deletion result
        const deleteMessage: StreamMessage = {
          id: `delete_${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'system',
          agentIcon: success ? '🗑️' : '❌',
          messageType: success ? 'success' : 'error',
          content: success ? `✅ ${path} を削除しました` : `❌ 削除失敗: ${message}`,
        };
        set((state) => ({
          messages: [...state.messages, deleteMessage],
          // Clear selected file if it was deleted
          selectedFile: state.selectedFile === path ? null : state.selectedFile,
          fileContent: state.selectedFile === path ? '' : state.fileContent,
        }));
      }) as EventListener);
      
      // Request initial file list
      setTimeout(() => {
        sendToRust({ type: 'GetFiles' });
      }, 200);
      
      // Add welcome message
      const welcomeMessage: StreamMessage = {
        id: `welcome_${Date.now()}`,
        timestamp: new Date().toISOString(),
        agent: 'system',
        agentIcon: '🚀',
        messageType: 'info',
        content: 'Welcome to D-code! Enter your prompt below to start building.',
      };
      set((state) => ({
        messages: [...state.messages, welcomeMessage],
      }));
      
      return;
    }
    
    const api = getPyWebViewAPI();
    
    if (api) {
      // pywebview mode
      console.log('Using pywebview API');
      set({ isConnected: true, connectionError: null });
      
      // Load initial messages
      api.get_messages().then((messages) => {
        set({ messages });
      }).catch(console.error);
      
      // Load files
      api.get_files().then((files) => {
        set({ files });
      }).catch(console.error);
      
      // Get status
      api.get_status().then((status) => {
        set({ engineRunning: status.engineRunning });
      }).catch(console.error);
      
      // Listen for events from Python
      window.addEventListener('dcode-message', ((event: CustomEvent<StreamMessage>) => {
        const message = event.detail;
        set((state) => ({
          messages: [...state.messages, message],
        }));
      }) as EventListener);
      
      return;
    }
    
    // WebSocket mode (fallback for development)
    const ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      set({ isConnected: true, connectionError: null, ws });
      console.log('Connected to D-code engine');
    };

    ws.onclose = () => {
      set({ isConnected: false, ws: null });
      console.log('Disconnected from D-code engine');
      
      // Auto-reconnect after 3 seconds
      setTimeout(() => {
        if (!get().isConnected) {
          get().connect();
        }
      }, 3000);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      set({ connectionError: 'WebSocket connection failed' });
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data, set, get);
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };
  },

  // Disconnect from WebSocket
  disconnect: () => {
    const { ws } = get();
    if (ws) {
      ws.close();
      set({ isConnected: false, ws: null });
    }
  },

  // Send a user message to the engine
  sendMessage: (content: string) => {
    // Add user message to local state first and set loading
    const userMessage: StreamMessage = {
      id: `user_${Date.now()}`,
      timestamp: new Date().toISOString(),
      agent: 'user',
      agentIcon: '👤',
      messageType: 'info',
      content,
    };
    
    set((state) => ({
      messages: [...state.messages, userMessage],
      isLoading: true, // Start loading when user sends a message
    }));
    
    // Get recent terminal output for context (all terminals, last 100 lines)
    const { getAllTerminalOutput } = get();
    const allOutput = getAllTerminalOutput();
    const terminalContext = allOutput.slice(-100).join('\n');
    
    // Check for wry webview (desktop mode)
    if (isWryWebView()) {
      sendToRust({ 
        type: 'SendMessage', 
        content,
        terminal_context: terminalContext || undefined,
      });
      return;
    }
    
    const api = getPyWebViewAPI();
    
    if (api) {
      // pywebview mode - API handles adding message
      api.send_message(content).catch(console.error);
      return;
    }
    
    // WebSocket mode
    const { ws, isConnected } = get();
    
    if (!isConnected || !ws) {
      console.warn('Not connected to engine');
      return;
    }

    // Send to server
    ws.send(JSON.stringify({
      type: 'user_message',
      content,
    }));
  },

  // Request engine to break/pause
  requestBreak: () => {
    // Add system message
    const breakMessage: StreamMessage = {
      id: `system_${Date.now()}`,
      timestamp: new Date().toISOString(),
      agent: 'system',
      agentIcon: '🛑',
      messageType: 'warning',
      content: 'Break requested - waiting for engine to pause...',
    };
    
    set((state) => ({
      messages: [...state.messages, breakMessage],
    }));
    
    // Check for wry webview (desktop mode)
    if (isWryWebView()) {
      sendToRust({ type: 'BreakRequest' });
      return;
    }
    
    const api = getPyWebViewAPI();
    
    if (api) {
      // pywebview mode
      api.request_break().catch(console.error);
      return;
    }
    
    // WebSocket mode
    const { ws, isConnected } = get();
    
    if (!isConnected || !ws) {
      console.warn('Not connected to engine');
      return;
    }

    ws.send(JSON.stringify({
      type: 'BreakRequest',
    }));
  },

  // Select a file in the explorer
  selectFile: (path: string) => {
    set({ selectedFile: path });
    
    // Check for wry webview (desktop mode)
    if (isWryWebView()) {
      sendToRust({ type: 'ReadFile', path });
      return;
    }
    
    const api = getPyWebViewAPI();
    
    if (api) {
      // pywebview mode
      api.read_file(path).then((result) => {
        if ('content' in result) {
          set({ fileContent: result.content });
        }
      }).catch(console.error);
      return;
    }
    
    // Request file content from server (WebSocket mode)
    const { ws, isConnected } = get();
    if (isConnected && ws) {
      ws.send(JSON.stringify({
        type: 'FileOperation',
        payload: { action: 'read', path },
      }));
    }
  },

  // Add a new message from the stream
  addMessage: (message: StreamMessage) => {
    set((state) => ({
      messages: [...state.messages, message],
      // Stop loading when we receive a response from AI
      isLoading: message.agent === 'user' ? state.isLoading : false,
    }));
  },

  // Set loading state
  setLoading: (loading: boolean) => {
    set({ isLoading: loading });
  },

  // Update progress
  updateProgress: (current: number, total: number) => {
    const percentage = total > 0 ? (current / total) * 100 : 0;
    set({ progress: { current, total, percentage } });
  },

  // Set tasks
  setTasks: (tasks: Task[]) => {
    set({ tasks });
  },

  // Set engineers with their tasks
  setEngineers: (engineers: Engineer[]) => {
    set({ engineers });
  },

  // Update task status
  updateTaskStatus: (taskId: string, status: Task['status']) => {
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === taskId ? { ...task, status } : task
      ),
      currentTaskId: status === 'in_progress' ? taskId : state.currentTaskId,
    }));
  },

  // Add terminal output to a specific terminal
  addTerminalOutput: (terminalId: string, line: string, isRunning?: boolean, pid?: number) => {
    set((state) => {
      const terminals = [...state.terminals];
      const index = terminals.findIndex(t => t.id === terminalId);
      
      if (index === -1) {
        // Create new terminal
        terminals.push({
          id: terminalId,
          name: `Terminal ${terminals.length + 1}`,
          output: [line],
          isRunning: isRunning ?? false,
          createdAt: Date.now(),
          pid: pid,
        });
      } else {
        terminals[index] = {
          ...terminals[index],
          output: [...terminals[index].output, line],
          isRunning: isRunning ?? terminals[index].isRunning,
          pid: pid ?? terminals[index].pid,
        };
      }
      
      return {
        terminals,
        activeTerminalId: state.activeTerminalId || terminalId,
        terminalOutput: [...state.terminalOutput, line],
      };
    });
  },

  // Create a new terminal
  createTerminal: (id: string, command?: string) => {
    set((state) => {
      const terminals = [...state.terminals];
      if (!terminals.find(t => t.id === id)) {
        terminals.push({
          id,
          name: command ? command.split(' ')[0] : `Terminal ${terminals.length + 1}`,
          output: [],
          isRunning: false,
          command,
          createdAt: Date.now(),
          pid: undefined,
        });
      }
      return {
        terminals,
        activeTerminalId: id,
      };
    });
  },

  // Close a terminal
  closeTerminal: (id: string) => {
    set((state) => {
      // Get the terminal being closed to identify its output
      const terminalToClose = state.terminals.find(t => t.id === id);
      const terminals = state.terminals.filter(t => t.id !== id);
      let activeTerminalId = state.activeTerminalId;
      
      // If we closed the active terminal, switch to another
      if (activeTerminalId === id) {
        activeTerminalId = terminals.length > 0 ? terminals[terminals.length - 1].id : null;
      }
      
      // If no terminals left, also clear the legacy terminalOutput
      // Otherwise, remove the closed terminal's output from terminalOutput
      let terminalOutput = state.terminalOutput;
      if (terminals.length === 0) {
        terminalOutput = [];
      } else if (terminalToClose) {
        // Filter out lines from the closed terminal
        // Note: This is a best-effort removal as we can't perfectly track which lines came from which terminal
        // The marker lines like "--- Terminal Name ---" help identify sections
        const terminalMarker = `--- ${terminalToClose.name}`;
        let inClosedTerminal = false;
        terminalOutput = state.terminalOutput.filter(line => {
          if (line.startsWith('--- ') && line.endsWith(' ---')) {
            inClosedTerminal = line.startsWith(terminalMarker);
            return !inClosedTerminal;
          }
          return !inClosedTerminal;
        });
      }
      
      return { terminals, activeTerminalId, terminalOutput };
    });
  },

  // Set active terminal
  setActiveTerminal: (id: string) => {
    set({ activeTerminalId: id });
  },

  // Clear terminal (specific or active)
  clearTerminal: (id?: string) => {
    set((state) => {
      const targetId = id || state.activeTerminalId;
      if (!targetId) {
        return { terminalOutput: [] };
      }
      
      const terminals = state.terminals.map(t =>
        t.id === targetId ? { ...t, output: [] } : t
      );
      
      return { terminals };
    });
  },

  // Get all terminal output combined (for AI context)
  getAllTerminalOutput: () => {
    const { terminals, terminalOutput } = get();
    if (terminals.length === 0) {
      return terminalOutput;
    }
    // Combine all terminal outputs
    const allOutput: string[] = [];
    for (const term of terminals) {
      if (term.output.length > 0) {
        allOutput.push(`--- ${term.name} (${term.command || 'shell'}) ---`);
        allOutput.push(...term.output);
      }
    }
    return allOutput;
  },

  // Kill a running process in a terminal
  killTerminalProcess: (terminalId: string) => {
    if (isWryWebView()) {
      console.log('Sending kill request for terminal:', terminalId);
      sendToRust({ type: 'KillTerminalProcess', terminal_id: terminalId });
    }
  },

  // Update a single agent's status
  updateAgentStatus: (agentId: string, update: Partial<AgentStatus>) => {
    set((state) => ({
      agentStatuses: state.agentStatuses.map((agent) =>
        agent.id === agentId
          ? { ...agent, ...update, lastActivity: new Date().toISOString() }
          : agent
      ),
    }));
  },

  // Set all agent statuses at once
  setAgentStatuses: (statuses: AgentStatus[]) => {
    set(() => ({ agentStatuses: statuses }));
  },

  // Initialize conversation manager with project root
  initConversationManager: (projectRoot: string) => {
    if (isWryWebView()) {
      sendToRust({ type: 'InitConversationManager', project_root: projectRoot });
    }
  },

  // List conversation sessions
  listConversationSessions: (limit?: number) => {
    if (isWryWebView()) {
      sendToRust({ type: 'ListConversationSessions', limit: limit ?? 20 });
    }
  },

  // Load a previous conversation session
  loadConversationSession: (sessionId: string) => {
    if (isWryWebView()) {
      sendToRust({ type: 'LoadConversationSession', session_id: sessionId });
    }
  },

  // Set conversation sessions
  setConversationSessions: (sessions: ConversationSession[]) => {
    set(() => ({ conversationSessions: sessions }));
  },

  // Set current session ID
  setCurrentSessionId: (sessionId: string | null) => {
    set(() => ({ currentSessionId: sessionId }));
  },

  // Edit file with search/replace (diff-based partial update)
  editFileSearchReplace: (filePath: string, search: string, replace: string, occurrence?: number) => {
    if (isWryWebView()) {
      sendToRust({ 
        type: 'EditFileSearchReplace', 
        file_path: filePath,
        search,
        replace,
        occurrence: occurrence ?? 1,
      });
    }
  },

  // Create unified diff between two texts
  createDiff: (original: string, modified: string, filename: string) => {
    if (isWryWebView()) {
      sendToRust({ 
        type: 'CreateDiff', 
        original,
        modified,
        filename,
      });
    }
  },

  // Send user input directly to a terminal
  sendTerminalInput: (terminalId: string, input: string) => {
    if (isWryWebView()) {
      console.log('Sending terminal input to:', terminalId, 'input:', input);
      sendToRust({ 
        type: 'TerminalInput', 
        terminal_id: terminalId,
        input,
      });
      
      // Also add to the terminal's local output for display
      set((state) => {
        const terminals = state.terminals.map(t =>
          t.id === terminalId
            ? { ...t, output: [...t.output, `> ${input}`] }
            : t
        );
        return { terminals };
      });
    }
  },

  // Delete a file or folder
  deleteFile: (path: string) => {
    if (isWryWebView()) {
      console.log('Deleting file:', path);
      sendToRust({ 
        type: 'DeleteFile', 
        path,
      });
    }
  },

  // Refresh file list
  refreshFiles: () => {
    if (isWryWebView()) {
      sendToRust({ type: 'GetFiles' });
    }
  },
}));

/**
 * Handle incoming messages from the server
 */
function handleServerMessage(
  data: Record<string, unknown>,
  set: (fn: (state: AppState) => Partial<AppState>) => void,
  get: () => AppState
) {
  const type = data.type as string;
  const payload = data.payload as Record<string, unknown> | undefined;

  switch (type) {
    case 'AgentMessage': {
      if (payload) {
        const message: StreamMessage = {
          id: payload.id as string,
          timestamp: payload.timestamp as string,
          agent: payload.agent as string,
          agentIcon: payload.agent_icon as string || '🤖',
          messageType: (payload.message_type as StreamMessage['messageType']) || 'info',
          content: payload.content as string,
          metadata: payload.metadata as Record<string, unknown>,
        };
        get().addMessage(message);
      }
      break;
    }

    case 'Progress': {
      if (payload) {
        get().updateProgress(
          payload.current as number,
          payload.total as number
        );
      }
      break;
    }

    case 'Status': {
      if (payload) {
        set(() => ({
          engineRunning: payload.engine_running as boolean,
          currentTaskId: payload.current_task as string | null,
        }));
      }
      break;
    }

    case 'FileContent': {
      if (payload) {
        set(() => ({
          fileContent: payload.content as string,
        }));
      }
      break;
    }

    case 'CodeChange': {
      if (payload) {
        const message: StreamMessage = {
          id: `code_${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'engineer',
          agentIcon: '🔧',
          messageType: 'code',
          content: `${payload.action}: ${payload.file_path}`,
          metadata: payload,
        };
        get().addMessage(message);
      }
      break;
    }

    case 'Error': {
      if (payload) {
        const message: StreamMessage = {
          id: `error_${Date.now()}`,
          timestamp: new Date().toISOString(),
          agent: 'system',
          agentIcon: '⚠️',
          messageType: 'error',
          content: payload.message as string,
        };
        get().addMessage(message);
      }
      break;
    }

    default:
      console.log('Unknown message type:', type, data);
  }
}
