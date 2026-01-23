import { useState, useCallback } from 'react';
import Editor, { DiffEditor, Monaco } from '@monaco-editor/react';
import { 
  Copy, 
  Check, 
  Maximize2, 
  Minimize2, 
  FileCode, 
  GitCompare,
  Download,
  RotateCcw
} from 'lucide-react';
import clsx from 'clsx';
import { getLanguageFromPath, getFileName } from '../utils';

interface CodeViewProps {
  /** File path or name for language detection */
  filePath?: string;
  /** Current code content */
  code: string;
  /** Original code for diff view */
  originalCode?: string;
  /** Whether the code is read-only */
  readOnly?: boolean;
  /** Callback when code changes */
  onChange?: (value: string | undefined) => void;
  /** Show line numbers */
  showLineNumbers?: boolean;
  /** Show minimap */
  showMinimap?: boolean;
  /** Custom height (defaults to 100%) */
  height?: string;
  /** Custom class name */
  className?: string;
}

/**
 * CodeView - Monaco Editor wrapper with diff support
 * 
 * Features:
 * - Syntax highlighting for multiple languages
 * - Diff view for comparing original vs modified code
 * - Copy to clipboard
 * - Fullscreen toggle
 * - Discord-style dark theme
 */
export default function CodeView({
  filePath = 'untitled.txt',
  code,
  originalCode,
  readOnly = true,
  onChange,
  showLineNumbers = true,
  showMinimap = false,
  height = '100%',
  className,
}: CodeViewProps) {
  const [copied, setCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [viewMode, setViewMode] = useState<'code' | 'diff'>(
    originalCode ? 'diff' : 'code'
  );

  const language = getLanguageFromPath(filePath);
  const fileName = getFileName(filePath);

  // Monaco editor options
  const editorOptions = {
    readOnly,
    minimap: { enabled: showMinimap },
    lineNumbers: showLineNumbers ? 'on' as const : 'off' as const,
    scrollBeyondLastLine: false,
    fontSize: 13,
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    fontLigatures: true,
    tabSize: 2,
    wordWrap: 'on' as const,
    automaticLayout: true,
    padding: { top: 12, bottom: 12 },
    renderLineHighlight: 'line' as const,
    cursorBlinking: 'smooth' as const,
    smoothScrolling: true,
    contextmenu: true,
    scrollbar: {
      vertical: 'auto' as const,
      horizontal: 'auto' as const,
      verticalScrollbarSize: 10,
      horizontalScrollbarSize: 10,
    },
  };

  // Configure Monaco theme
  const handleEditorMount = useCallback((_editor: unknown, monaco: Monaco) => {
    // Define Discord-inspired dark theme
    monaco.editor.defineTheme('dcode-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'comment', foreground: '6b7280', fontStyle: 'italic' },
        { token: 'keyword', foreground: 'f472b6' },
        { token: 'string', foreground: '86efac' },
        { token: 'number', foreground: 'fcd34d' },
        { token: 'type', foreground: '93c5fd' },
        { token: 'function', foreground: 'c4b5fd' },
        { token: 'variable', foreground: 'e2e8f0' },
        { token: 'operator', foreground: '94a3b8' },
      ],
      colors: {
        'editor.background': '#1e1f22',
        'editor.foreground': '#e2e8f0',
        'editor.lineHighlightBackground': '#2d2f34',
        'editor.selectionBackground': '#4f46e54d',
        'editorCursor.foreground': '#5865f2',
        'editorLineNumber.foreground': '#4b5563',
        'editorLineNumber.activeForeground': '#9ca3af',
        'editor.inactiveSelectionBackground': '#4f46e533',
        'editorIndentGuide.background1': '#374151',
        'editorIndentGuide.activeBackground1': '#4b5563',
      },
    });
    monaco.editor.setTheme('dcode-dark');
  }, []);

  // Copy code to clipboard
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  }, [code]);

  // Download code as file
  const handleDownload = useCallback(() => {
    const blob = new Blob([code], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [code, fileName]);

  // Toggle fullscreen
  const toggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
  }, []);

  // Toggle diff/code view
  const toggleViewMode = useCallback(() => {
    setViewMode((prev) => (prev === 'code' ? 'diff' : 'code'));
  }, []);

  return (
    <div
      className={clsx(
        'flex flex-col bg-dc-dark-700 rounded-lg overflow-hidden border border-dc-dark-600',
        isFullscreen && 'fixed inset-4 z-50',
        className
      )}
      style={{ height: isFullscreen ? 'auto' : height }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-dc-dark-800 border-b border-dc-dark-600">
        {/* File info */}
        <div className="flex items-center gap-2">
          <FileCode className="w-4 h-4 text-dc-dark-400" />
          <span className="text-sm font-medium text-dc-text-primary">
            {fileName}
          </span>
          <span className="text-xs text-dc-dark-500 bg-dc-dark-700 px-1.5 py-0.5 rounded">
            {language}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          {/* View mode toggle (only if originalCode exists) */}
          {originalCode && (
            <button
              onClick={toggleViewMode}
              className={clsx(
                'p-1.5 rounded transition-colors',
                viewMode === 'diff'
                  ? 'bg-dc-accent-primary/20 text-dc-accent-primary'
                  : 'text-dc-dark-400 hover:text-dc-text-primary hover:bg-dc-dark-700'
              )}
              title={viewMode === 'diff' ? 'Show code' : 'Show diff'}
            >
              <GitCompare className="w-4 h-4" />
            </button>
          )}

          {/* Reset (only if onChange exists) */}
          {onChange && originalCode && (
            <button
              onClick={() => onChange(originalCode)}
              className="p-1.5 rounded text-dc-dark-400 hover:text-dc-text-primary hover:bg-dc-dark-700 transition-colors"
              title="Reset to original"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          )}

          {/* Download */}
          <button
            onClick={handleDownload}
            className="p-1.5 rounded text-dc-dark-400 hover:text-dc-text-primary hover:bg-dc-dark-700 transition-colors"
            title="Download file"
          >
            <Download className="w-4 h-4" />
          </button>

          {/* Copy */}
          <button
            onClick={handleCopy}
            className={clsx(
              'p-1.5 rounded transition-colors',
              copied
                ? 'text-dc-accent-success bg-dc-accent-success/20'
                : 'text-dc-dark-400 hover:text-dc-text-primary hover:bg-dc-dark-700'
            )}
            title={copied ? 'Copied!' : 'Copy to clipboard'}
          >
            {copied ? (
              <Check className="w-4 h-4" />
            ) : (
              <Copy className="w-4 h-4" />
            )}
          </button>

          {/* Fullscreen */}
          <button
            onClick={toggleFullscreen}
            className="p-1.5 rounded text-dc-dark-400 hover:text-dc-text-primary hover:bg-dc-dark-700 transition-colors"
            title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 min-h-0">
        {viewMode === 'diff' && originalCode ? (
          <DiffEditor
            original={originalCode}
            modified={code}
            language={language}
            theme="dcode-dark"
            options={{
              ...editorOptions,
              renderSideBySide: true,
              enableSplitViewResizing: true,
            }}
            onMount={handleEditorMount}
          />
        ) : (
          <Editor
            value={code}
            language={language}
            theme="dcode-dark"
            options={editorOptions}
            onChange={onChange}
            onMount={handleEditorMount}
          />
        )}
      </div>

      {/* Fullscreen backdrop */}
      {isFullscreen && (
        <div
          className="fixed inset-0 bg-black/80 -z-10"
          onClick={toggleFullscreen}
        />
      )}
    </div>
  );
}

/**
 * Inline code snippet component for chat messages
 */
export function InlineCode({
  children,
  language = 'plaintext',
}: {
  children: string;
  language?: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  return (
    <div className="relative group my-2">
      <pre className="bg-dc-dark-800 rounded-lg p-3 overflow-x-auto text-sm">
        <code className={`language-${language}`}>{children}</code>
      </pre>
      <button
        onClick={handleCopy}
        className={clsx(
          'absolute top-2 right-2 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity',
          copied
            ? 'bg-dc-accent-success/20 text-dc-accent-success'
            : 'bg-dc-dark-700 text-dc-dark-400 hover:text-dc-text-primary'
        )}
      >
        {copied ? (
          <Check className="w-3.5 h-3.5" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  );
}
