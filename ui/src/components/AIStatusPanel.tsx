import { useStore, AgentStatus } from '../store';
import { 
  Brain, 
  Pause, 
  AlertTriangle, 
  CheckCircle,
  Clock,
  Loader2
} from 'lucide-react';
import clsx from 'clsx';

/**
 * AI Status Panel - AI群ステータスダッシュボード
 * 
 * 各エージェント（Orchestrator, Planner, Worker）の状態を表示
 * - 🧠 思考中（Thinking）
 * - ⏸️ 待機中（Idle）
 * - ⚠️ エラー（Error）
 * - ✅ 完了（Completed）
 * - ⏳ 待機（Waiting）
 */
export default function AIStatusPanel() {
  const { agentStatuses } = useStore();

  return (
    <div className="h-full p-4 overflow-auto">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {agentStatuses.map((agent) => (
          <AgentCard key={agent.id} agent={agent} />
        ))}
      </div>
    </div>
  );
}

/**
 * Status Icon Component
 */
function StatusIcon({ state }: { state: AgentStatus['state'] }) {
  switch (state) {
    case 'thinking':
      return <Loader2 className="w-5 h-5 animate-spin text-dc-accent-primary" />;
    case 'idle':
      return <Pause className="w-5 h-5 text-dc-dark-400" />;
    case 'error':
      return <AlertTriangle className="w-5 h-5 text-dc-accent-danger" />;
    case 'completed':
      return <CheckCircle className="w-5 h-5 text-dc-accent-success" />;
    case 'waiting':
      return <Clock className="w-5 h-5 text-dc-accent-warning" />;
    default:
      return <Brain className="w-5 h-5 text-dc-dark-400" />;
  }
}

/**
 * Status Label Component
 */
function StatusLabel({ state }: { state: AgentStatus['state'] }) {
  const labels: Record<AgentStatus['state'], { text: string; className: string }> = {
    thinking: { text: '思考中', className: 'text-dc-accent-primary' },
    idle: { text: '待機中', className: 'text-dc-dark-400' },
    error: { text: 'エラー', className: 'text-dc-accent-danger' },
    completed: { text: '完了', className: 'text-dc-accent-success' },
    waiting: { text: '待機', className: 'text-dc-accent-warning' },
  };

  const label = labels[state] || { text: state, className: 'text-dc-dark-400' };

  return (
    <span className={clsx('text-xs font-medium', label.className)}>
      {label.text}
    </span>
  );
}

/**
 * Agent Card Component
 */
function AgentCard({ agent }: { agent: AgentStatus }) {
  const isActive = agent.state === 'thinking';
  
  return (
    <div
      className={clsx(
        'p-4 rounded-lg border transition-all duration-200',
        isActive
          ? 'bg-dc-dark-700/80 border-dc-accent-primary/50 shadow-lg shadow-dc-accent-primary/10'
          : 'bg-dc-dark-800 border-dc-dark-700 hover:border-dc-dark-600'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{agent.icon}</span>
          <span className="font-semibold text-white">{agent.name}</span>
        </div>
        <StatusIcon state={agent.state} />
      </div>

      {/* Status */}
      <div className="flex items-center gap-2 mb-2">
        <StatusLabel state={agent.state} />
        {isActive && (
          <div className="flex gap-0.5">
            <span className="w-1.5 h-1.5 bg-dc-accent-primary rounded-full animate-pulse" />
            <span className="w-1.5 h-1.5 bg-dc-accent-primary rounded-full animate-pulse delay-75" />
            <span className="w-1.5 h-1.5 bg-dc-accent-primary rounded-full animate-pulse delay-150" />
          </div>
        )}
      </div>

      {/* Current Task */}
      {agent.currentTask && (
        <div className="text-sm text-dc-dark-400 truncate mt-2">
          <span className="text-dc-dark-500">タスク: </span>
          {agent.currentTask}
        </div>
      )}

      {/* Progress Bar */}
      {agent.progress !== undefined && agent.progress > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-dc-dark-500 mb-1">
            <span>進捗</span>
            <span>{agent.progress}%</span>
          </div>
          <div className="w-full bg-dc-dark-700 rounded-full h-1.5">
            <div
              className={clsx(
                'h-1.5 rounded-full transition-all duration-300',
                agent.state === 'error'
                  ? 'bg-dc-accent-danger'
                  : agent.state === 'completed'
                  ? 'bg-dc-accent-success'
                  : 'bg-dc-accent-primary'
              )}
              style={{ width: `${agent.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Last Activity */}
      {agent.lastActivity && (
        <div className="text-xs text-dc-dark-500 mt-2">
          最終更新: {formatTimeAgo(agent.lastActivity)}
        </div>
      )}
    </div>
  );
}

/**
 * Format time ago helper
 */
function formatTimeAgo(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  
  if (diffSec < 5) return 'たった今';
  if (diffSec < 60) return `${diffSec}秒前`;
  
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}分前`;
  
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}時間前`;
  
  return then.toLocaleDateString('ja-JP');
}
