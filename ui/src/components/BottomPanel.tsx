import { useRef, useEffect, useState } from 'react';
import { useStore, TerminalInstance } from '../store';
import { 
  Terminal as TerminalIcon, 
  ChevronUp,
  ChevronDown,
  Trash2,
  X,
  Loader2,
  Square,
  Activity
} from 'lucide-react';
import clsx from 'clsx';
import AIStatusPanel from './AIStatusPanel';

/** Bottom Panel Tab Types */
type BottomPanelTab = 'terminal' | 'ai-status';

/**
 * Bottom Panel: Terminal Output with VSCode-like tabs
 * 
 * Features:
 * - Multiple terminal tabs
 * - Individual terminal output view
 * - Running indicator
 * - Collapsible panel
 * - AI Status Dashboard
 */
export default function BottomPanel() {
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState<BottomPanelTab>('terminal');
  const { terminals, terminalOutput, agentStatuses } = useStore();

  // Show legacy output if no terminals exist
  const hasTerminals = terminals.length > 0;
  
  // Check if any agent is active
  const hasActiveAgent = agentStatuses.some(a => a.state === 'thinking');

  return (
    <div
      className={clsx(
        'bg-dc-dark-800 border-t border-dc-dark-950 flex flex-col transition-all duration-200',
        isExpanded ? 'h-48' : 'h-10'
      )}
    >
      {/* Tab Bar */}
      <div className="h-10 flex items-center px-2 border-b border-dc-dark-950 shrink-0 overflow-x-auto">
        {/* Main Tabs (Terminal / AI Status) */}
        <div className="flex items-center gap-1 mr-2 pr-2 border-r border-dc-dark-700">
          {/* Terminal Tab */}
          <button
            onClick={() => setActiveTab('terminal')}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors',
              activeTab === 'terminal'
                ? 'bg-dc-dark-700 text-white'
                : 'text-dc-dark-400 hover:text-white hover:bg-dc-dark-700/50'
            )}
          >
            <TerminalIcon className="w-4 h-4" />
            Terminal
          </button>
          
          {/* AI Status Tab */}
          <button
            onClick={() => setActiveTab('ai-status')}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm transition-colors',
              activeTab === 'ai-status'
                ? 'bg-dc-dark-700 text-white'
                : 'text-dc-dark-400 hover:text-white hover:bg-dc-dark-700/50'
            )}
          >
            <Activity className="w-4 h-4" />
            AI Status
            {hasActiveAgent && (
              <span className="w-2 h-2 bg-dc-accent-primary rounded-full animate-pulse" />
            )}
          </button>
        </div>

        {/* Terminal Sub-tabs (only show when Terminal tab is active) */}
        {activeTab === 'terminal' && hasTerminals && (
          <TerminalTabs />
        )}

        <div className="flex-1" />

        {/* Expand/Collapse Toggle */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-1.5 rounded text-dc-dark-400 hover:text-white hover:bg-dc-dark-700 transition-colors ml-2"
        >
          {isExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronUp className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Content */}
      {isExpanded && (
        <div className="flex-1 overflow-hidden">
          {activeTab === 'ai-status' ? (
            <AIStatusPanel />
          ) : hasTerminals ? (
            <ActiveTerminalView />
          ) : (
            <LegacyTerminalView output={terminalOutput} />
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Terminal Tabs Component
 */
function TerminalTabs() {
  const { terminals, activeTerminalId, setActiveTerminal, closeTerminal, killTerminalProcess } = useStore();

  return (
    <div className="flex items-center gap-1 overflow-x-auto">
      {terminals.map((terminal) => (
        <TerminalTab
          key={terminal.id}
          terminal={terminal}
          isActive={terminal.id === activeTerminalId}
          onSelect={() => setActiveTerminal(terminal.id)}
          onClose={() => closeTerminal(terminal.id)}
          onKill={() => killTerminalProcess(terminal.id)}
        />
      ))}
    </div>
  );
}

/**
 * Individual Terminal Tab
 */
function TerminalTab({
  terminal,
  isActive,
  onSelect,
  onClose,
  onKill,
}: {
  terminal: TerminalInstance;
  isActive: boolean;
  onSelect: () => void;
  onClose: () => void;
  onKill: () => void;
}) {
  return (
    <div
      className={clsx(
        'flex items-center gap-1.5 px-3 py-1.5 rounded text-sm cursor-pointer group transition-colors',
        isActive
          ? 'bg-dc-dark-700 text-white'
          : 'text-dc-dark-400 hover:text-white hover:bg-dc-dark-700/50'
      )}
      onClick={onSelect}
    >
      {terminal.isRunning ? (
        <Loader2 className="w-4 h-4 animate-spin text-dc-accent-primary" />
      ) : (
        <TerminalIcon className="w-4 h-4" />
      )}
      <span className="max-w-32 truncate">
        {terminal.command ? terminal.command.split(' ')[0] : terminal.name}
      </span>
      {terminal.isRunning && (
        <>
          <span className="text-xs text-dc-accent-primary">(実行中)</span>
          {/* Kill button for running processes */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onKill();
            }}
            className={clsx(
              'p-0.5 rounded transition-colors',
              'hover:bg-red-500/20 text-red-500 hover:text-red-400'
            )}
            title="プロセスを終了"
          >
            <Square className="w-3 h-3 fill-current" />
          </button>
        </>
      )}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        className={clsx(
          'p-0.5 rounded transition-colors',
          'opacity-0 group-hover:opacity-100',
          'hover:bg-dc-dark-600 text-dc-dark-500 hover:text-white'
        )}
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}

/**
 * Active Terminal View (for multi-terminal mode)
 */
function ActiveTerminalView() {
  const { terminals, activeTerminalId, clearTerminal, killTerminalProcess, sendTerminalInput } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [userInput, setUserInput] = useState('');
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  
  const activeTerminal = terminals.find(t => t.id === activeTerminalId);
  const output = activeTerminal?.output || [];

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [output]);

  if (!activeTerminal) {
    return (
      <div className="h-full flex items-center justify-center text-dc-dark-500">
        ターミナルが選択されていません
      </div>
    );
  }

  const handleKillProcess = () => {
    if (activeTerminal && activeTerminal.isRunning) {
      killTerminalProcess(activeTerminal.id);
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-3 py-1 border-b border-dc-dark-950">
        <div className="flex items-center gap-2">
          <span className="text-xs text-dc-dark-500 font-mono">
            ~/projects
          </span>
          {activeTerminal.command && (
            <span className="text-xs text-dc-dark-400">
              $ {activeTerminal.command}
            </span>
          )}
          {activeTerminal.isRunning && (
            <span className="flex items-center gap-1 text-xs text-dc-accent-primary">
              <Loader2 className="w-3 h-3 animate-spin" />
              実行中...
              {activeTerminal.pid && (
                <span className="text-dc-dark-500">(PID: {activeTerminal.pid})</span>
              )}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Kill Process Button - only shown when running */}
          {activeTerminal.isRunning && (
            <button
              onClick={handleKillProcess}
              className="p-1 rounded text-red-500 hover:text-red-400 hover:bg-red-500/20 transition-colors"
              title="プロセスを終了 (Ctrl+C)"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
            </button>
          )}
          <button
            onClick={() => clearTerminal(activeTerminalId || undefined)}
            className="p-1 rounded text-dc-dark-500 hover:text-white hover:bg-dc-dark-700 transition-colors"
            title="Clear terminal"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto chat-scroll p-3 font-mono text-sm"
      >
        {output.length === 0 ? (
          <div className="text-dc-dark-500">
            {activeTerminal.isRunning 
              ? 'コマンドを実行中...'
              : 'ターミナル出力がここに表示されます。'
            }
          </div>
        ) : (
          output.map((line, i) => (
            <TerminalLine key={i} line={line} />
          ))
        )}
      </div>

      {/* Terminal Input (for streaming terminals) */}
      {activeTerminal.isRunning && (
        <div className="flex items-center gap-2 px-3 py-2 border-t border-dc-dark-950 bg-dc-dark-900">
          <span className="text-dc-accent-success font-mono text-sm">{'>'}</span>
          <input
            ref={inputRef}
            type="text"
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && userInput.trim()) {
                sendTerminalInput(activeTerminal.id, userInput);
                setCommandHistory(prev => [...prev, userInput]);
                setHistoryIndex(-1);
                setUserInput('');
              } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (commandHistory.length > 0 && historyIndex < commandHistory.length - 1) {
                  const newIndex = historyIndex + 1;
                  setHistoryIndex(newIndex);
                  setUserInput(commandHistory[commandHistory.length - 1 - newIndex]);
                }
              } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (historyIndex > 0) {
                  const newIndex = historyIndex - 1;
                  setHistoryIndex(newIndex);
                  setUserInput(commandHistory[commandHistory.length - 1 - newIndex]);
                } else if (historyIndex === 0) {
                  setHistoryIndex(-1);
                  setUserInput('');
                }
              } else if (e.key === 'c' && e.ctrlKey) {
                // Ctrl+C to kill process
                killTerminalProcess(activeTerminal.id);
              }
            }}
            placeholder="コマンドを入力... (Enter で送信, Ctrl+C で中断)"
            className="flex-1 bg-transparent text-dc-dark-200 font-mono text-sm outline-none placeholder-dc-dark-500"
            autoComplete="off"
          />
        </div>
      )}
    </div>
  );
}

/**
 * Legacy Terminal View (for backward compatibility)
 */
function LegacyTerminalView({ output }: { output: string[] }) {
  const { clearTerminal } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [output]);

  return (
    <div className="h-full flex flex-col">
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-3 py-1 border-b border-dc-dark-950">
        <span className="text-xs text-dc-dark-500 font-mono">
          ~/projects
        </span>
        <button
          onClick={() => clearTerminal()}
          className="p-1 rounded text-dc-dark-500 hover:text-white hover:bg-dc-dark-700 transition-colors"
          title="Clear terminal"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Terminal Output */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto chat-scroll p-3 font-mono text-sm"
      >
        {output.length === 0 ? (
          <div className="text-dc-dark-500">
            ターミナル出力がここに表示されます。
            <br />
            AIに「〇〇を実行して」と伝えると、実行結果がここに表示されます。
          </div>
        ) : (
          output.map((line, i) => (
            <TerminalLine key={i} line={line} />
          ))
        )}
      </div>
    </div>
  );
}

/**
 * Terminal Line Component
 */
function TerminalLine({ line }: { line: string }) {
  const isCommand = line.startsWith('$') || line.startsWith('>');
  const isSuccess = line.startsWith('✓') || line.includes('successfully') || line.includes('Success');
  const isError = line.toLowerCase().includes('error') || line.startsWith('✗') || line.includes('failed');
  const isWarning = line.toLowerCase().includes('warning') || line.toLowerCase().includes('warn');

  return (
    <div
      className={clsx(
        'whitespace-pre-wrap',
        isCommand
          ? 'text-dc-accent-success font-semibold'
          : isSuccess
          ? 'text-dc-accent-success'
          : isError
          ? 'text-dc-accent-danger'
          : isWarning
          ? 'text-dc-accent-warning'
          : 'text-dc-dark-300'
      )}
    >
      {line || '\u00A0'}
    </div>
  );
}