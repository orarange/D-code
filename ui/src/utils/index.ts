/**
 * D-code UI Utility Functions
 */

/**
 * Format a timestamp for display
 */
export function formatTimestamp(date: Date | string | number): string {
  const d = new Date(date);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) {
    return 'just now';
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffHours < 24) {
    return `${diffHours}h ago`;
  } else if (diffDays < 7) {
    return `${diffDays}d ago`;
  } else {
    return d.toLocaleDateString();
  }
}

/**
 * Format a time for display (HH:MM)
 */
export function formatTime(date: Date | string | number): string {
  const d = new Date(date);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * Format bytes for display
 */
export function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Truncate a string with ellipsis
 */
export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + '...';
}

/**
 * Get file extension from a path
 */
export function getFileExtension(path: string): string {
  const parts = path.split('.');
  return parts.length > 1 ? parts.pop() || '' : '';
}

/**
 * Get filename from a path
 */
export function getFileName(path: string): string {
  const parts = path.split(/[/\\]/);
  return parts.pop() || path;
}

/**
 * Get directory from a path
 */
export function getDirectory(path: string): string {
  const parts = path.split(/[/\\]/);
  parts.pop();
  return parts.join('/');
}

/**
 * Get the language ID from a file path for Monaco editor
 */
export function getLanguageFromPath(path: string): string {
  const ext = getFileExtension(path).toLowerCase();
  const languageMap: Record<string, string> = {
    // Programming languages
    js: 'javascript',
    jsx: 'javascript',
    ts: 'typescript',
    tsx: 'typescript',
    py: 'python',
    rs: 'rust',
    go: 'go',
    java: 'java',
    kt: 'kotlin',
    swift: 'swift',
    c: 'c',
    cpp: 'cpp',
    cc: 'cpp',
    cxx: 'cpp',
    h: 'c',
    hpp: 'cpp',
    cs: 'csharp',
    rb: 'ruby',
    php: 'php',
    scala: 'scala',
    r: 'r',
    lua: 'lua',
    perl: 'perl',
    pl: 'perl',
    sh: 'shell',
    bash: 'shell',
    zsh: 'shell',
    ps1: 'powershell',
    psm1: 'powershell',
    
    // Markup & Data
    html: 'html',
    htm: 'html',
    xml: 'xml',
    svg: 'xml',
    css: 'css',
    scss: 'scss',
    sass: 'scss',
    less: 'less',
    json: 'json',
    yaml: 'yaml',
    yml: 'yaml',
    toml: 'toml',
    md: 'markdown',
    markdown: 'markdown',
    
    // Config files
    dockerfile: 'dockerfile',
    makefile: 'makefile',
    gitignore: 'ignore',
    env: 'dotenv',
    
    // Other
    sql: 'sql',
    graphql: 'graphql',
    gql: 'graphql',
  };

  return languageMap[ext] || 'plaintext';
}

/**
 * Get icon name for a file type (for lucide-react)
 */
export function getFileIcon(path: string): string {
  const ext = getFileExtension(path).toLowerCase();
  const fileName = getFileName(path).toLowerCase();

  // Special filenames
  if (fileName === 'package.json') return 'Package';
  if (fileName === 'cargo.toml') return 'Package';
  if (fileName === 'dockerfile') return 'Container';
  if (fileName.includes('readme')) return 'BookOpen';
  if (fileName.includes('license')) return 'Scale';
  if (fileName.includes('.env')) return 'KeyRound';
  if (fileName.includes('.git')) return 'GitBranch';

  // By extension
  const iconMap: Record<string, string> = {
    // Code
    js: 'FileCode',
    jsx: 'FileCode',
    ts: 'FileCode',
    tsx: 'FileCode',
    py: 'FileCode',
    rs: 'FileCode',
    go: 'FileCode',
    java: 'FileCode',
    
    // Data
    json: 'Braces',
    yaml: 'FileText',
    yml: 'FileText',
    toml: 'FileText',
    xml: 'FileCode',
    
    // Style
    css: 'Palette',
    scss: 'Palette',
    sass: 'Palette',
    less: 'Palette',
    
    // Docs
    md: 'FileText',
    txt: 'FileText',
    
    // Images
    png: 'Image',
    jpg: 'Image',
    jpeg: 'Image',
    gif: 'Image',
    svg: 'Image',
    webp: 'Image',
    
    // Archives
    zip: 'FileArchive',
    tar: 'FileArchive',
    gz: 'FileArchive',
    
    // Default
    default: 'File',
  };

  return iconMap[ext] || iconMap.default;
}

/**
 * Generate a unique ID
 */
export function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Deep clone an object
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

/**
 * Debounce a function
 */
export function debounce<T extends (...args: Parameters<T>) => ReturnType<T>>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return function (this: ThisParameterType<T>, ...args: Parameters<T>) {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func.apply(this, args);
    }, wait);
  };
}

/**
 * Throttle a function
 */
export function throttle<T extends (...args: Parameters<T>) => ReturnType<T>>(
  func: T,
  limit: number
): (...args: Parameters<T>) => void {
  let inThrottle = false;

  return function (this: ThisParameterType<T>, ...args: Parameters<T>) {
    if (!inThrottle) {
      func.apply(this, args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  };
}

/**
 * Sleep for a specified duration
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Check if a value is empty (null, undefined, empty string, empty array, empty object)
 */
export function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '';
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === 'object') return Object.keys(value).length === 0;
  return false;
}

/**
 * Capitalize the first letter of a string
 */
export function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

/**
 * Convert a string to kebab-case
 */
export function toKebabCase(str: string): string {
  return str
    .replace(/([a-z])([A-Z])/g, '$1-$2')
    .replace(/[\s_]+/g, '-')
    .toLowerCase();
}

/**
 * Convert a string to camelCase
 */
export function toCamelCase(str: string): string {
  return str
    .replace(/[-_\s]+(.)?/g, (_, c) => (c ? c.toUpperCase() : ''))
    .replace(/^(.)/, (c) => c.toLowerCase());
}

/**
 * Parse an error into a user-friendly message
 */
export function parseError(error: unknown): string {
  if (typeof error === 'string') return error;
  if (error instanceof Error) return error.message;
  if (typeof error === 'object' && error !== null) {
    if ('message' in error) return String((error as { message: unknown }).message);
    return JSON.stringify(error);
  }
  return 'An unknown error occurred';
}

/**
 * Agent colors for the chat UI
 */
export const agentColors: Record<string, { bg: string; text: string; border: string }> = {
  orchestrator: {
    bg: 'bg-purple-500/20',
    text: 'text-purple-400',
    border: 'border-purple-500/30',
  },
  planner: {
    bg: 'bg-blue-500/20',
    text: 'text-blue-400',
    border: 'border-blue-500/30',
  },
  engineer: {
    bg: 'bg-green-500/20',
    text: 'text-green-400',
    border: 'border-green-500/30',
  },
  streamer: {
    bg: 'bg-yellow-500/20',
    text: 'text-yellow-400',
    border: 'border-yellow-500/30',
  },
  system: {
    bg: 'bg-gray-500/20',
    text: 'text-gray-400',
    border: 'border-gray-500/30',
  },
  user: {
    bg: 'bg-dc-accent-primary/20',
    text: 'text-dc-accent-primary',
    border: 'border-dc-accent-primary/30',
  },
};

/**
 * Get agent avatar emoji
 */
export function getAgentAvatar(agent: string): string {
  const avatars: Record<string, string> = {
    orchestrator: '🎭',
    planner: '📋',
    engineer: '🔧',
    streamer: '📡',
    system: '⚙️',
    user: '👤',
  };
  return avatars[agent.toLowerCase()] || '🤖';
}
