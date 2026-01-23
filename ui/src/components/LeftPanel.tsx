import { useState } from 'react';
import { 
  FolderOpen, 
  File, 
  ChevronRight, 
  ChevronDown,
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  PartyPopper,
  Copy,
  Trash2,
  Edit3,
  FilePlus,
  FolderPlus,
  History,
  MessageSquare,
  RefreshCw
} from 'lucide-react';
import { useStore, Task, FileNode, Engineer, ConversationSession } from '../store';
import { ContextMenu, useContextMenu, MenuItem } from './ContextMenu';
import clsx from 'clsx';

/**
 * Left Panel: Project Explorer & Task List & Chat History
 */
export default function LeftPanel() {
  const [activeTab, setActiveTab] = useState<'files' | 'tasks' | 'history'>('tasks');

  return (
    <aside className="w-64 bg-dc-dark-800 border-r border-dc-dark-950 flex flex-col shrink-0">
      {/* Tab Selector */}
      <div className="flex border-b border-dc-dark-950">
        <button
          onClick={() => setActiveTab('files')}
          className={clsx(
            'flex-1 py-2 px-3 text-sm font-medium transition-colors',
            activeTab === 'files'
              ? 'text-white border-b-2 border-dc-accent-primary'
              : 'text-dc-dark-400 hover:text-dc-dark-200'
          )}
          title="ファイル"
        >
          📁
        </button>
        <button
          onClick={() => setActiveTab('tasks')}
          className={clsx(
            'flex-1 py-2 px-3 text-sm font-medium transition-colors',
            activeTab === 'tasks'
              ? 'text-white border-b-2 border-dc-accent-primary'
              : 'text-dc-dark-400 hover:text-dc-dark-200'
          )}
          title="タスク"
        >
          📋
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={clsx(
            'flex-1 py-2 px-3 text-sm font-medium transition-colors',
            activeTab === 'history'
              ? 'text-white border-b-2 border-dc-accent-primary'
              : 'text-dc-dark-400 hover:text-dc-dark-200'
          )}
          title="履歴"
        >
          💬
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto chat-scroll">
        {activeTab === 'files' && <FileExplorer />}
        {activeTab === 'tasks' && <TaskList />}
        {activeTab === 'history' && <ChatHistory />}
      </div>

      {/* Progress Bar */}
      <ProgressBar />
    </aside>
  );
}

/**
 * File Explorer Component
 */
function FileExplorer() {
  const { files, selectedFile, selectFile, deleteFile } = useStore();
  const contextMenu = useContextMenu<FileNode>();

  // Context menu items for files
  const getFileMenuItems = (node: FileNode): MenuItem[] => {
    const isFolder = node.type === 'folder';
    
    return [
      ...(isFolder ? [
        {
          id: 'new-file',
          label: '新規ファイル',
          icon: <FilePlus className="w-4 h-4" />,
          onClick: () => console.log('New file in:', node.path),
        },
        {
          id: 'new-folder',
          label: '新規フォルダ',
          icon: <FolderPlus className="w-4 h-4" />,
          onClick: () => console.log('New folder in:', node.path),
        },
        { id: 'sep1', label: '', separator: true },
      ] : []),
      {
        id: 'copy-path',
        label: 'パスをコピー',
        icon: <Copy className="w-4 h-4" />,
        shortcut: 'Ctrl+Shift+C',
        onClick: () => {
          navigator.clipboard.writeText(node.path);
        },
      },
      {
        id: 'rename',
        label: '名前を変更',
        icon: <Edit3 className="w-4 h-4" />,
        shortcut: 'F2',
        onClick: () => console.log('Rename:', node.path),
      },
      { id: 'sep2', label: '', separator: true },
      {
        id: 'delete',
        label: '削除',
        icon: <Trash2 className="w-4 h-4" />,
        shortcut: 'Delete',
        danger: true,
        onClick: () => {
          // Show confirmation dialog
          const confirmMessage = `「${node.name}」を削除しますか？\n\nこの操作は取り消せません。`;
          if (window.confirm(confirmMessage)) {
            deleteFile(node.path);
          }
        },
      },
    ];
  };

  // Show empty state if no files
  if (files.length === 0) {
    return (
      <div className="p-4 text-center">
        <div className="text-dc-dark-400 text-sm">
          <p className="mb-2">📂 プロジェクトがありません</p>
          <p className="text-xs text-dc-dark-500">
            チャットでリクエストを送信すると、
            <br />
            AIがここにファイルを生成します
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-2">
      {files.map((node) => (
        <FileTreeNode
          key={node.path}
          node={node}
          level={0}
          selectedFile={selectedFile}
          onSelect={selectFile}
          onContextMenu={(e, n) => contextMenu.openMenu(e, n)}
        />
      ))}
      
      {/* Context Menu */}
      {contextMenu.isOpen && contextMenu.data && (
        <ContextMenu
          items={getFileMenuItems(contextMenu.data)}
          position={contextMenu.position}
          onClose={contextMenu.closeMenu}
        />
      )}
    </div>
  );
}

/**
 * File Tree Node Component
 */
function FileTreeNode({
  node,
  level,
  selectedFile,
  onSelect,
  onContextMenu,
}: {
  node: FileNode;
  level: number;
  selectedFile: string | null;
  onSelect: (path: string) => void;
  onContextMenu: (e: React.MouseEvent, node: FileNode) => void;
}) {
  const [isOpen, setIsOpen] = useState(true);
  const isFolder = node.type === 'folder';
  const isSelected = node.path === selectedFile;

  const handleClick = () => {
    if (isFolder) {
      setIsOpen(!isOpen);
    } else {
      onSelect(node.path);
    }
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onContextMenu(e, node);
  };

  return (
    <div>
      <button
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        className={clsx(
          'w-full flex items-center gap-1.5 py-1 px-2 rounded text-sm transition-colors',
          isSelected
            ? 'bg-dc-accent-primary/20 text-white'
            : 'text-dc-dark-300 hover:bg-dc-dark-700 hover:text-white'
        )}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
      >
        {isFolder ? (
          <>
            {isOpen ? (
              <ChevronDown className="w-4 h-4 text-dc-dark-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-dc-dark-400" />
            )}
            <FolderOpen className="w-4 h-4 text-dc-accent-warning" />
          </>
        ) : (
          <>
            <span className="w-4" />
            <File className="w-4 h-4 text-dc-dark-400" />
          </>
        )}
        <span className="truncate">{node.name}</span>
      </button>

      {isFolder && isOpen && node.children && (
        <div>
          {node.children.map((child) => (
            <FileTreeNode
              key={child.path}
              node={child}
              level={level + 1}
              selectedFile={selectedFile}
              onSelect={onSelect}
              onContextMenu={onContextMenu}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Engineer icons mapping
 */
const engineerIcons: Record<string, string> = {
  'engineer_1': '🔧',
  'engineer_2': '⚙️',
  'engineer_3': '🛠️',
  'engineer_4': '🔨',
  'engineer_5': '🔩',
  'engineer_6': '⛏️',
  'engineer_7': '🪛',
  'engineer_8': '🪚',
  'engineer_9': '🔬',
  'engineer_10': '🔭',
};

/**
 * Task List Component - VSCode-like engineer tree
 */
function TaskList() {
  const { engineers, tasks } = useStore();

  // Check if there are any tasks at all
  const allTasks = engineers.length > 0 
    ? engineers.flatMap(e => e.tasks)
    : tasks;
  
  const hasAnyTasks = allTasks.length > 0;
  const allCompleted = hasAnyTasks && allTasks.every(t => t.status === 'completed');

  // If no engineers defined, show completion or empty state
  if (engineers.length === 0) {
    // Show completion message if no tasks or all tasks are done
    if (!hasAnyTasks || allCompleted) {
      return (
        <div className="flex flex-col items-center justify-center h-full p-6 text-center">
          <PartyPopper className="w-12 h-12 text-dc-accent-success mb-4 animate-bounce" />
          <h3 className="text-lg font-bold text-dc-accent-success mb-2">
            All Tasks Complete!!!
          </h3>
          <p className="text-sm text-dc-dark-400">
            Great job! Send a new prompt to start a new project.
          </p>
        </div>
      );
    }

    // Show old-style task list if there are tasks but no engineers
    const completedCount = tasks.filter((t) => t.status === 'completed').length;
    
    return (
      <div className="p-3">
        <div className="text-xs text-dc-dark-400 mb-2">
          {completedCount}/{tasks.length} tasks completed
        </div>
        
        <div className="space-y-1">
          {tasks.map((task) => (
            <TaskItem key={task.id} task={task} />
          ))}
        </div>
      </div>
    );
  }

  // Calculate overall progress
  const totalTasks = engineers.reduce((sum, e) => sum + e.tasks.length, 0);
  const completedTasks = engineers.reduce(
    (sum, e) => sum + e.tasks.filter(t => t.status === 'completed').length, 
    0
  );

  // If all tasks are complete, show celebration
  if (totalTasks > 0 && completedTasks === totalTasks) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center">
        <PartyPopper className="w-12 h-12 text-dc-accent-success mb-4 animate-bounce" />
        <h3 className="text-lg font-bold text-dc-accent-success mb-2">
          All Tasks Complete!!!
        </h3>
        <p className="text-sm text-dc-dark-400 mb-4">
          {totalTasks} tasks finished by {engineers.length} engineers
        </p>
        <p className="text-xs text-dc-dark-500">
          Send a new prompt to start another project.
        </p>
      </div>
    );
  }

  return (
    <div className="p-2">
      <div className="text-xs text-dc-dark-400 mb-3 px-2">
        {completedTasks}/{totalTasks} tasks completed
      </div>
      
      {engineers.map((engineer) => (
        <EngineerSection key={engineer.id} engineer={engineer} />
      ))}
    </div>
  );
}

/**
 * Engineer Section - Collapsible like VSCode explorer
 */
function EngineerSection({ engineer }: { engineer: Engineer }) {
  const [isOpen, setIsOpen] = useState(true);
  
  const completedCount = engineer.tasks.filter(t => t.status === 'completed').length;
  const totalCount = engineer.tasks.length;
  const hasInProgress = engineer.tasks.some(t => t.status === 'in_progress');

  const getStatusColor = () => {
    if (engineer.status === 'error') return 'text-dc-accent-danger';
    if (hasInProgress) return 'text-dc-accent-info';
    if (completedCount === totalCount && totalCount > 0) return 'text-dc-accent-success';
    return 'text-dc-dark-400';
  };

  return (
    <div className="mb-1">
      {/* Engineer Header */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={clsx(
          'w-full flex items-center gap-2 py-1.5 px-2 rounded text-sm transition-colors',
          'hover:bg-dc-dark-700 text-dc-dark-200'
        )}
      >
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-dc-dark-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-dc-dark-400" />
        )}
        
        <span className="text-base">
          {engineer.icon || engineerIcons[engineer.id] || '🤖'}
        </span>
        
        <span className="flex-1 truncate font-medium">
          {engineer.name}
        </span>
        
        <span className={clsx('text-xs', getStatusColor())}>
          {completedCount}/{totalCount}
        </span>
        
        {hasInProgress && (
          <Loader2 className="w-3 h-3 text-dc-accent-info animate-spin" />
        )}
      </button>

      {/* Tasks */}
      {isOpen && (
        <div className="ml-4 border-l border-dc-dark-700">
          {engineer.tasks.length === 0 ? (
            <div className="py-2 px-4 text-xs text-dc-dark-500 italic">
              No tasks assigned
            </div>
          ) : (
            engineer.tasks.map((task) => (
              <TaskItem key={task.id} task={task} indented />
            ))
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Task Item Component
 */
function TaskItem({ task, indented = false }: { task: Task; indented?: boolean }) {
  const getStatusIcon = () => {
    switch (task.status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-dc-accent-success" />;
      case 'in_progress':
        return <Loader2 className="w-4 h-4 text-dc-accent-info animate-spin" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-dc-accent-danger" />;
      default:
        return <Circle className="w-4 h-4 text-dc-dark-500" />;
    }
  };

  return (
    <div
      className={clsx(
        'flex items-center gap-2 py-1.5 rounded text-sm transition-colors',
        indented ? 'px-3 ml-2' : 'p-2',
        task.status === 'in_progress' && 'bg-dc-accent-info/10',
        task.status === 'completed' && 'opacity-60'
      )}
    >
      {getStatusIcon()}
      <span
        className={clsx(
          'flex-1 truncate',
          task.status === 'completed' && 'line-through'
        )}
      >
        {task.title}
      </span>
      {task.progress !== undefined && task.status === 'in_progress' && (
        <span className="text-xs text-dc-dark-400">
          {Math.round(task.progress)}%
        </span>
      )}
    </div>
  );
}

/**
 * Progress Bar Component
 */
function ProgressBar() {
  const { progress, engineers, tasks } = useStore();
  
  // Calculate from engineers if available
  let current = progress.current;
  let total = progress.total;
  
  if (engineers.length > 0) {
    total = engineers.reduce((sum, e) => sum + e.tasks.length, 0);
    current = engineers.reduce(
      (sum, e) => sum + e.tasks.filter(t => t.status === 'completed').length,
      0
    );
  } else if (tasks.length > 0) {
    total = tasks.length;
    current = tasks.filter(t => t.status === 'completed').length;
  }
  
  const percentage = total > 0 ? (current / total) * 100 : 0;

  if (total === 0) {
    return null;
  }

  return (
    <div className="p-3 border-t border-dc-dark-950">
      <div className="flex justify-between text-xs text-dc-dark-400 mb-1">
        <span>Progress</span>
        <span>{current}/{total}</span>
      </div>
      <div className="h-2 bg-dc-dark-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-dc-accent-primary progress-bar rounded-full"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}

/**
 * Chat History Component - 過去の会話セッション一覧
 */
function ChatHistory() {
  const { 
    conversationSessions, 
    currentSessionId, 
    listConversationSessions,
    loadConversationSession 
  } = useStore();

  const handleRefresh = () => {
    listConversationSessions(20);
  };

  const handleLoadSession = (sessionId: string) => {
    if (sessionId !== currentSessionId) {
      loadConversationSession(sessionId);
    }
  };

  return (
    <div className="p-2">
      {/* Header with refresh button */}
      <div className="flex items-center justify-between mb-2 px-2">
        <span className="text-sm font-medium text-dc-dark-300">会話履歴</span>
        <button
          onClick={handleRefresh}
          className="p-1 rounded hover:bg-dc-dark-700 text-dc-dark-400 hover:text-dc-dark-200 transition-colors"
          title="更新"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Sessions list */}
      {conversationSessions.length === 0 ? (
        <div className="text-center py-8">
          <History className="w-12 h-12 text-dc-dark-600 mx-auto mb-2" />
          <p className="text-sm text-dc-dark-500">履歴がありません</p>
          <button
            onClick={handleRefresh}
            className="mt-2 text-xs text-dc-accent-primary hover:text-dc-accent-secondary"
          >
            更新
          </button>
        </div>
      ) : (
        <div className="space-y-1">
          {conversationSessions.map((session) => (
            <SessionItem
              key={session.sessionId}
              session={session}
              isActive={session.sessionId === currentSessionId}
              onLoad={() => handleLoadSession(session.sessionId)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Session Item Component
 */
function SessionItem({
  session,
  isActive,
  onLoad,
}: {
  session: ConversationSession;
  isActive: boolean;
  onLoad: () => void;
}) {
  return (
    <button
      onClick={onLoad}
      className={clsx(
        'w-full text-left p-2 rounded-lg transition-colors group',
        isActive
          ? 'bg-dc-accent-primary/20 border border-dc-accent-primary/30'
          : 'hover:bg-dc-dark-700/50 border border-transparent'
      )}
    >
      <div className="flex items-start gap-2">
        <MessageSquare 
          className={clsx(
            'w-4 h-4 mt-0.5 flex-shrink-0',
            isActive ? 'text-dc-accent-primary' : 'text-dc-dark-500'
          )} 
        />
        <div className="flex-1 min-w-0">
          <div className={clsx(
            'text-xs font-medium',
            isActive ? 'text-dc-accent-primary' : 'text-dc-dark-300'
          )}>
            {session.displayDate}
          </div>
          {session.preview && (
            <div className="text-xs text-dc-dark-500 truncate mt-0.5">
              {session.preview}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}
