import { useEffect } from 'react';
import { useStore } from './store';
import LeftPanel from './components/LeftPanel';
import CenterPanel from './components/CenterPanel';
import RightPanel from './components/RightPanel';
import BottomPanel from './components/BottomPanel';
import TitleBar from './components/TitleBar';

/**
 * D-code Main Application
 * 
 * Discord-style 3-column layout:
 * - Title Bar: Custom window controls
 * - Left: Project Explorer & Task List
 * - Center: Live Code Editor (Monaco)
 * - Right: AI Discussion Stream
 * - Bottom: Command Center (Chat Input, Break Button, Terminal)
 */
export default function App() {
  const { connect, disconnect } = useStore();

  useEffect(() => {
    // Connect to WebSocket on mount
    connect();
    
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return (
    <div className="flex flex-col h-screen bg-dc-dark-900 text-dc-dark-200">
      {/* Custom Title Bar */}
      <TitleBar />

      {/* App Header with status */}
      <header className="h-10 bg-dc-dark-800 border-b border-dc-dark-950 flex items-center px-4 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-lg">🚀</span>
          <span className="text-sm font-medium text-dc-dark-300">プロジェクト</span>
          <span className="text-xs text-dc-dark-500">v0.1.0</span>
        </div>
        <div className="flex-1" />
        <StatusIndicator />
      </header>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel: Project Explorer & Tasks */}
        <LeftPanel />

        {/* Center Panel: Code Editor */}
        <CenterPanel />

        {/* Right Panel: AI Chat Stream */}
        <RightPanel />
      </div>

      {/* Bottom Panel: Command Center */}
      <BottomPanel />
    </div>
  );
}

/**
 * Status indicator showing connection and engine state
 */
function StatusIndicator() {
  const { isConnected, engineRunning } = useStore();

  return (
    <div className="flex items-center gap-3">
      {/* Connection Status */}
      <div className="flex items-center gap-1.5">
        <div 
          className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-dc-accent-success' : 'bg-dc-accent-danger'
          }`}
        />
        <span className="text-xs text-dc-dark-400">
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Engine Status */}
      <div className="flex items-center gap-1.5">
        <div 
          className={`w-2 h-2 rounded-full ${
            engineRunning ? 'bg-dc-accent-info animate-pulse' : 'bg-dc-dark-500'
          }`}
        />
        <span className="text-xs text-dc-dark-400">
          {engineRunning ? 'Engine Running' : 'Engine Idle'}
        </span>
      </div>
    </div>
  );
}
