import { useEffect, useRef, useState, useMemo } from 'react';
import { useStore, StreamMessage } from '../store';
import { Send, Square, ChevronDown, ChevronRight, Brain } from 'lucide-react';
import clsx from 'clsx';

/**
 * Right Panel: AI Discussion Stream (Discord-style)
 * 
 * Features:
 * - Real-time agent messages
 * - Agent avatars/icons
 * - Message type styling (info, success, warning, error)
 * - Auto-scroll to latest message
 * - Chat input at bottom
 */
export default function RightPanel() {
  const { messages } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Demo messages for development
  const demoMessages: StreamMessage[] = messages.length > 0 ? messages : [
    {
      id: '1',
      timestamp: new Date(Date.now() - 60000).toISOString(),
      agent: 'system',
      agentIcon: '💻',
      messageType: 'info',
      content: 'D-code engine initialized. Ready to receive instructions.',
    },
    {
      id: '2',
      timestamp: new Date(Date.now() - 50000).toISOString(),
      agent: 'orchestrator',
      agentIcon: '🎯',
      messageType: 'info',
      content: '🚀 Starting D-code engine with your request...',
    },
    {
      id: '3',
      timestamp: new Date(Date.now() - 40000).toISOString(),
      agent: 'planner',
      agentIcon: '📋',
      messageType: 'info',
      content: '📝 Analyzing requirements and generating task plan...',
    },
    {
      id: '4',
      timestamp: new Date(Date.now() - 30000).toISOString(),
      agent: 'planner',
      agentIcon: '📋',
      messageType: 'success',
      content: '✅ Plan created: 5 tasks, ~45 min total estimated time.',
    },
    {
      id: '5',
      timestamp: new Date(Date.now() - 20000).toISOString(),
      agent: 'engineer_0',
      agentIcon: '🔧',
      messageType: 'info',
      content: '🔧 Starting task: Setup project structure',
    },
    {
      id: '6',
      timestamp: new Date(Date.now() - 10000).toISOString(),
      agent: 'engineer_0',
      agentIcon: '🔧',
      messageType: 'code',
      content: '📄 Created: src/main.py',
    },
    {
      id: '7',
      timestamp: new Date().toISOString(),
      agent: 'streamer',
      agentIcon: '📡',
      messageType: 'progress',
      content: '📊 Progress: [████░░░░░░░░░░░░░░░░] 20.0% (1/5 tasks)',
    },
  ];

  return (
    <aside className="w-80 bg-dc-dark-800 border-l border-dc-dark-950 flex flex-col shrink-0">
      {/* Header */}
      <div className="h-10 border-b border-dc-dark-950 flex items-center px-4">
        <span className="text-sm font-medium text-dc-dark-200">
          🤖 AI Discussion
        </span>
        <div className="flex-1" />
        <span className="text-xs text-dc-dark-500">
          {demoMessages.length} messages
        </span>
      </div>

      {/* Messages Container */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto chat-scroll p-3 space-y-3"
      >
        {demoMessages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        
        {/* Typing Indicator (when engine is thinking) */}
        <TypingIndicator />
      </div>
      
      {/* Chat Input at Bottom */}
      <ChatInput />
    </aside>
  );
}

/**
 * Message Bubble Component
 */
function MessageBubble({ message }: { message: StreamMessage }) {
  const formatTime = (timestamp: string) => {
    if (!timestamp) return '';
    
    // Handle Unix timestamp (seconds since epoch as string)
    if (/^\d+Z?$/.test(timestamp)) {
      const secs = parseInt(timestamp.replace('Z', ''), 10);
      const date = new Date(secs * 1000);
      if (!isNaN(date.getTime())) {
        return date.toLocaleTimeString('ja-JP', {
          hour: '2-digit',
          minute: '2-digit',
        });
      }
    }
    
    // Handle ISO format
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      return '';
    }
    return date.toLocaleTimeString('ja-JP', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getAgentColor = (agent: string): string => {
    const colors: Record<string, string> = {
      orchestrator: 'text-purple-400',
      planner: 'text-blue-400',
      engineer: 'text-green-400',
      engineer_0: 'text-green-400',
      engineer_1: 'text-emerald-400',
      engineer_2: 'text-teal-400',
      streamer: 'text-cyan-400',
      system: 'text-gray-400',
      user: 'text-yellow-400',
    };
    return colors[agent] || colors[agent.split('_')[0]] || 'text-dc-dark-300';
  };

  const getMessageStyle = (type: StreamMessage['messageType']) => {
    switch (type) {
      case 'success':
        return 'border-l-dc-accent-success bg-dc-accent-success/5';
      case 'warning':
        return 'border-l-dc-accent-warning bg-dc-accent-warning/5';
      case 'error':
        return 'border-l-dc-accent-danger bg-dc-accent-danger/5';
      case 'progress':
        return 'border-l-dc-accent-info bg-dc-accent-info/5';
      case 'code':
        return 'border-l-dc-accent-primary bg-dc-accent-primary/5';
      case 'thinking':
        return 'border-l-purple-500 bg-purple-500/5';
      default:
        return 'border-l-dc-dark-600 bg-dc-dark-700/50';
    }
  };

  const agentDisplayName = message.agent
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');

  return (
    <div className="message-enter">
      {/* Agent Header */}
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg">{message.agentIcon}</span>
        <span className={clsx('text-sm font-medium', getAgentColor(message.agent))}>
          {agentDisplayName}
        </span>
        <span className="text-xs text-dc-dark-500">
          {formatTime(message.timestamp)}
        </span>
      </div>

      {/* Message Content */}
      <div
        className={clsx(
          'ml-7 pl-3 border-l-2 rounded-r py-1.5 pr-2',
          getMessageStyle(message.messageType)
        )}
      >
        <ThinkBlockContent content={message.content} />
      </div>
    </div>
  );
}

/**
 * Parse content and render with collapsible think blocks
 */
interface ContentPart {
  type: 'text' | 'think';
  content: string;
}

function parseThinkBlocks(content: string): ContentPart[] {
  const parts: ContentPart[] = [];
  const thinkRegex = /<think>([\s\S]*?)<\/think>/gi;
  let lastIndex = 0;
  let match;

  while ((match = thinkRegex.exec(content)) !== null) {
    // Add text before the think block
    if (match.index > lastIndex) {
      const textBefore = content.slice(lastIndex, match.index).trim();
      if (textBefore) {
        parts.push({ type: 'text', content: textBefore });
      }
    }
    // Add the think block
    parts.push({ type: 'think', content: match[1].trim() });
    lastIndex = thinkRegex.lastIndex;
  }

  // Add remaining text after last think block
  if (lastIndex < content.length) {
    const remaining = content.slice(lastIndex).trim();
    if (remaining) {
      parts.push({ type: 'text', content: remaining });
    }
  }

  // If no think blocks found, return the original content
  if (parts.length === 0) {
    parts.push({ type: 'text', content: content });
  }

  return parts;
}

function ThinkBlockContent({ content }: { content: string }) {
  const parts = useMemo(() => parseThinkBlocks(content), [content]);

  return (
    <div className="space-y-2">
      {parts.map((part, index) => (
        part.type === 'think' ? (
          <CollapsibleThinkBlock key={index} content={part.content} />
        ) : (
          <p key={index} className="text-sm text-dc-dark-200 whitespace-pre-wrap break-words">
            {part.content}
          </p>
        )
      ))}
    </div>
  );
}

/**
 * Collapsible Think Block Component
 */
function CollapsibleThinkBlock({ content }: { content: string }) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Truncate preview text
  const previewText = content.length > 80 
    ? content.slice(0, 80).trim() + '...' 
    : content;

  return (
    <div className="bg-purple-900/20 border border-purple-500/30 rounded overflow-hidden">
      {/* Toggle Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-1.5 px-2 py-1 text-left hover:bg-purple-500/10 transition-colors"
      >
        {isExpanded ? (
          <ChevronDown className="w-3 h-3 text-purple-400 shrink-0" />
        ) : (
          <ChevronRight className="w-3 h-3 text-purple-400 shrink-0" />
        )}
        <Brain className="w-3 h-3 text-purple-400 shrink-0" />
        <span className="text-[10px] font-medium text-purple-400">思考プロセス</span>
        {!isExpanded && (
          <span className="text-[10px] text-dc-dark-400 truncate ml-1">
            {previewText}
          </span>
        )}
      </button>
      
      {/* Expandable Content */}
      {isExpanded && (
        <div className="px-2 pb-2 border-t border-purple-500/20">
          <p className="text-dc-dark-300 whitespace-pre-wrap break-words mt-1.5 font-mono text-[10px] leading-relaxed">
            {content}
          </p>
        </div>
      )}
    </div>
  );
}

/**
 * Typing Indicator Component
 * Shows streaming content or loading dots when AI is processing
 */
function TypingIndicator() {
  const { isLoading, streaming } = useStore();

  // If streaming, show the current content
  if (streaming.isStreaming && streaming.currentContent) {
    return (
      <div className="message-enter">
        {/* Agent Header */}
        <div className="flex items-center gap-2 mb-1">
          <span className="text-lg">🤖</span>
          <span className="text-sm font-medium text-purple-400">
            {streaming.agent}
          </span>
          <span className="text-xs text-dc-dark-500">
            typing...
          </span>
        </div>

        {/* Streaming Content */}
        <div className="ml-7 pl-3 border-l-2 border-l-purple-500 bg-purple-500/5 rounded-r py-1.5 pr-2">
          <p className="text-sm text-dc-dark-200 whitespace-pre-wrap break-words">
            {streaming.currentContent}
            <span className="inline-block w-2 h-4 bg-purple-500 ml-0.5 animate-pulse" />
          </p>
        </div>
      </div>
    );
  }

  // If loading but not streaming, show typing dots
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 ml-7 mt-2">
        <div className="flex gap-1">
          <span className="typing-dot w-2 h-2 bg-dc-dark-400 rounded-full" />
          <span className="typing-dot w-2 h-2 bg-dc-dark-400 rounded-full" />
          <span className="typing-dot w-2 h-2 bg-dc-dark-400 rounded-full" />
        </div>
        <span className="text-xs text-dc-dark-500">AI is thinking...</span>
      </div>
    );
  }

  return null;
}

/**
 * Chat Input Component (Discord-style at bottom of chat)
 */
function ChatInput() {
  const { sendMessage, isConnected, engineRunning, requestBreak } = useStore();
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    
    if (!input.trim() || !isConnected) return;
    
    sendMessage(input.trim());
    setInput('');
    
    // Focus back to textarea
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 80)}px`;
    }
  }, [input]);

  return (
    <div className="border-t border-dc-dark-950 p-3">
      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isConnected
                ? engineRunning
                  ? 'Send instructions...'
                  : 'Type your message...'
                : 'Connecting...'
            }
            disabled={!isConnected}
            className={clsx(
              'flex-1 bg-dc-dark-700 border border-dc-dark-600 rounded-lg px-3 py-2',
              'text-sm text-dc-dark-200 placeholder-dc-dark-500',
              'focus:outline-none focus:border-dc-accent-primary focus:ring-1 focus:ring-dc-accent-primary/30',
              'resize-none transition-colors',
              !isConnected && 'opacity-50 cursor-not-allowed'
            )}
            rows={1}
          />
          
          <button
            type="submit"
            disabled={!input.trim() || !isConnected}
            className={clsx(
              'px-3 rounded-lg flex items-center justify-center transition-all',
              input.trim() && isConnected
                ? 'bg-dc-accent-primary text-white hover:bg-dc-accent-primary/80'
                : 'bg-dc-dark-700 text-dc-dark-500 cursor-not-allowed'
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        
        {/* Break Button - show when engine is running */}
        {engineRunning && (
          <button
            type="button"
            onClick={requestBreak}
            className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg font-medium text-xs transition-all bg-dc-accent-danger/20 text-dc-accent-danger hover:bg-dc-accent-danger hover:text-white"
          >
            <Square className="w-3 h-3" />
            Stop AI
          </button>
        )}
      </form>
    </div>
  );
}
