import { useState, useEffect } from 'react';
import { Minus, Square, X, Copy } from 'lucide-react';
import clsx from 'clsx';

// Send command to Rust via IPC
function sendToRust(command: Record<string, unknown>): void {
  const win = window as unknown as { ipc?: { postMessage: (msg: string) => void } };
  if (win.ipc?.postMessage) {
    win.ipc.postMessage(JSON.stringify(command));
  }
}

/**
 * Custom Title Bar Component
 * 
 * カスタムタイトルバー - ネイティブの装飾を置き換え
 * ドラッグ可能領域、最小化/最大化/閉じるボタンを含む
 */
export default function TitleBar() {
  const [isMaximized, setIsMaximized] = useState(false);

  // Listen for maximize state changes from Rust
  useEffect(() => {
    const handleMaximizedChange = (event: CustomEvent<{ isMaximized: boolean }>) => {
      setIsMaximized(event.detail.isMaximized);
    };

    window.addEventListener('dcode-window-maximized', handleMaximizedChange as EventListener);
    
    return () => {
      window.removeEventListener('dcode-window-maximized', handleMaximizedChange as EventListener);
    };
  }, []);

  // Handle minimize
  const handleMinimize = () => {
    sendToRust({ type: 'WindowMinimize' });
  };

  // Handle maximize/restore
  const handleMaximize = () => {
    sendToRust({ type: 'WindowMaximize' });
    // State will be updated by the event listener
  };

  // Handle close
  const handleClose = () => {
    sendToRust({ type: 'WindowClose' });
  };

  // Handle drag start
  const handleMouseDown = (e: React.MouseEvent) => {
    // Only drag on the title bar area itself, not on buttons
    if ((e.target as HTMLElement).closest('.window-control-button')) {
      return;
    }
    // Trigger window drag
    sendToRust({ type: 'WindowDragStart' });
  };

  // Double click to maximize/restore
  const handleDoubleClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.window-control-button')) {
      return;
    }
    handleMaximize();
  };

  return (
    <div
      className="h-8 bg-dc-dark-900 border-b border-dc-dark-950 flex items-center justify-between select-none shrink-0"
      onMouseDown={handleMouseDown}
      onDoubleClick={handleDoubleClick}
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
      {/* Left: App Icon and Title */}
      <div className="flex items-center gap-2 px-3">
        <div className="w-4 h-4 rounded bg-gradient-to-br from-dc-accent-primary to-purple-600 flex items-center justify-center text-[8px] font-bold text-white">
          D
        </div>
        <span className="text-sm font-medium text-dc-dark-300">
          D-code
        </span>
        <span className="text-xs text-dc-dark-500 ml-2">
          AI Development Platform
        </span>
      </div>

      {/* Right: Window Controls */}
      <div 
        className="flex items-center h-full"
        style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
      >
        {/* Minimize */}
        <button
          onClick={handleMinimize}
          className={clsx(
            'window-control-button',
            'h-full px-4 flex items-center justify-center',
            'text-dc-dark-400 hover:text-white hover:bg-dc-dark-700',
            'transition-colors duration-100'
          )}
          title="最小化"
        >
          <Minus className="w-4 h-4" />
        </button>

        {/* Maximize/Restore */}
        <button
          onClick={handleMaximize}
          className={clsx(
            'window-control-button',
            'h-full px-4 flex items-center justify-center',
            'text-dc-dark-400 hover:text-white hover:bg-dc-dark-700',
            'transition-colors duration-100'
          )}
          title={isMaximized ? "元のサイズに戻す" : "最大化"}
        >
          {isMaximized ? (
            // 復元アイコン：重なった2つの四角（Windows標準の復元ボタン風）
            <Copy className="w-3.5 h-3.5" />
          ) : (
            // 最大化アイコン：単一の四角
            <Square className="w-3.5 h-3.5" />
          )}
        </button>

        {/* Close */}
        <button
          onClick={handleClose}
          className={clsx(
            'window-control-button',
            'h-full px-4 flex items-center justify-center',
            'text-dc-dark-400 hover:text-white hover:bg-red-600',
            'transition-colors duration-100'
          )}
          title="閉じる"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
