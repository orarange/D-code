import { useState } from 'react';
import { Square, AlertTriangle } from 'lucide-react';
import { useStore } from '../store';
import clsx from 'clsx';

/**
 * StopButton - Emergency stop button for the AI engine
 * 
 * Features:
 * - Two-click confirmation to prevent accidental stops
 * - Visual feedback (pulsing animation when engine is running)
 * - Disabled state when engine is not running
 */
export default function StopButton() {
  const { requestBreak, engineRunning } = useStore();
  const [confirmState, setConfirmState] = useState<'idle' | 'confirming'>('idle');

  const handleClick = () => {
    if (!engineRunning) return;

    if (confirmState === 'confirming') {
      // Second click - execute break
      requestBreak();
      setConfirmState('idle');
    } else {
      // First click - enter confirmation mode
      setConfirmState('confirming');
      
      // Auto-reset after 3 seconds
      setTimeout(() => {
        setConfirmState('idle');
      }, 3000);
    }
  };

  return (
    <button
      onClick={handleClick}
      disabled={!engineRunning}
      className={clsx(
        'relative flex items-center gap-2 px-6 py-3 rounded-lg font-semibold text-sm transition-all duration-200',
        engineRunning
          ? confirmState === 'confirming'
            ? 'bg-dc-accent-danger text-white shadow-lg shadow-dc-accent-danger/30'
            : 'bg-dc-accent-danger/20 text-dc-accent-danger border border-dc-accent-danger/30 hover:bg-dc-accent-danger hover:text-white hover:shadow-lg hover:shadow-dc-accent-danger/20'
          : 'bg-dc-dark-700 text-dc-dark-500 cursor-not-allowed border border-dc-dark-600'
      )}
    >
      {/* Pulse ring when engine is running */}
      {engineRunning && confirmState === 'idle' && (
        <span className="absolute inset-0 rounded-lg animate-ping bg-dc-accent-danger/20" />
      )}

      {/* Icon */}
      {confirmState === 'confirming' ? (
        <AlertTriangle className="w-5 h-5" />
      ) : (
        <Square className="w-5 h-5" />
      )}

      {/* Text */}
      <span>
        {confirmState === 'confirming'
          ? 'Click Again to Confirm'
          : 'Emergency Stop'}
      </span>
    </button>
  );
}

/**
 * Compact version of the stop button for use in headers/toolbars
 */
export function CompactStopButton() {
  const { requestBreak, engineRunning } = useStore();

  return (
    <button
      onClick={requestBreak}
      disabled={!engineRunning}
      title={engineRunning ? 'Stop AI Engine' : 'Engine not running'}
      className={clsx(
        'p-2 rounded-lg transition-all duration-200',
        engineRunning
          ? 'bg-dc-accent-danger/20 text-dc-accent-danger hover:bg-dc-accent-danger hover:text-white'
          : 'bg-dc-dark-700 text-dc-dark-500 cursor-not-allowed'
      )}
    >
      <Square className="w-4 h-4" />
    </button>
  );
}
