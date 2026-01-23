import { useState } from 'react';
import Editor from '@monaco-editor/react';
import { useStore } from '../store';
import { Code2, GitCompare, Copy, Check } from 'lucide-react';
import clsx from 'clsx';

/**
 * Center Panel: Live Code Editor
 * 
 * Features:
 * - Monaco Editor for code display
 * - Real-time updates as AI writes code
 * - Diff view mode
 * - Syntax highlighting
 */
export default function CenterPanel() {
  const { selectedFile, fileContent } = useStore();
  const [viewMode, setViewMode] = useState<'code' | 'diff'>('code');
  const [copied, setCopied] = useState(false);

  // Determine language from file extension
  const getLanguage = (filename: string | null): string => {
    if (!filename) return 'plaintext';
    const ext = filename.split('.').pop()?.toLowerCase();
    const langMap: Record<string, string> = {
      py: 'python',
      rs: 'rust',
      js: 'javascript',
      ts: 'typescript',
      tsx: 'typescriptreact',
      jsx: 'javascriptreact',
      json: 'json',
      html: 'html',
      css: 'css',
      md: 'markdown',
      toml: 'toml',
      yaml: 'yaml',
      yml: 'yaml',
    };
    return langMap[ext || ''] || 'plaintext';
  };

  const handleCopy = async () => {
    if (fileContent) {
      await navigator.clipboard.writeText(fileContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // Demo content for when no file is selected
  const demoContent = `# D-code AI Engine
# ================
# This is where the live code will appear as AI agents work.

def main():
    """
    Main entry point for the generated application.
    """
    print("Hello from D-code! 🚀")
    
    # AI will fill in the implementation here
    pass

if __name__ == "__main__":
    main()
`;

  const displayContent = fileContent || demoContent;
  const displayLanguage = getLanguage(selectedFile) || 'python';

  return (
    <main className="flex-1 flex flex-col bg-dc-dark-900 min-w-0">
      {/* Editor Header */}
      <div className="h-10 bg-dc-dark-800 border-b border-dc-dark-950 flex items-center px-3 shrink-0">
        {/* File Name */}
        <div className="flex items-center gap-2 text-sm">
          <Code2 className="w-4 h-4 text-dc-dark-400" />
          <span className="text-dc-dark-200">
            {selectedFile || 'workspace/main.py'}
          </span>
          <span className="text-xs text-dc-dark-500">
            ({displayLanguage})
          </span>
        </div>

        <div className="flex-1" />

        {/* View Mode Toggle */}
        <div className="flex items-center gap-1 mr-3">
          <button
            onClick={() => setViewMode('code')}
            className={clsx(
              'p-1.5 rounded transition-colors',
              viewMode === 'code'
                ? 'bg-dc-accent-primary text-white'
                : 'text-dc-dark-400 hover:text-white hover:bg-dc-dark-700'
            )}
            title="Code View"
          >
            <Code2 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('diff')}
            className={clsx(
              'p-1.5 rounded transition-colors',
              viewMode === 'diff'
                ? 'bg-dc-accent-primary text-white'
                : 'text-dc-dark-400 hover:text-white hover:bg-dc-dark-700'
            )}
            title="Diff View"
          >
            <GitCompare className="w-4 h-4" />
          </button>
        </div>

        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className="p-1.5 rounded text-dc-dark-400 hover:text-white hover:bg-dc-dark-700 transition-colors"
          title="Copy code"
        >
          {copied ? (
            <Check className="w-4 h-4 text-dc-accent-success" />
          ) : (
            <Copy className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* Monaco Editor */}
      <div className="flex-1 min-h-0">
        <Editor
          height="100%"
          language={displayLanguage}
          value={displayContent}
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: true, scale: 1 },
            fontSize: 14,
            fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
            lineNumbers: 'on',
            renderLineHighlight: 'all',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            automaticLayout: true,
            padding: { top: 10 },
            smoothScrolling: true,
            cursorBlinking: 'smooth',
          }}
          onMount={(_editor, monaco) => {
            // Custom theme configuration
            monaco.editor.defineTheme('d-code-dark', {
              base: 'vs-dark',
              inherit: true,
              rules: [
                { token: 'comment', foreground: '6A9955' },
                { token: 'keyword', foreground: 'C586C0' },
                { token: 'string', foreground: 'CE9178' },
                { token: 'number', foreground: 'B5CEA8' },
                { token: 'function', foreground: 'DCDCAA' },
              ],
              colors: {
                'editor.background': '#1e1f22',
                'editor.foreground': '#D4D4D4',
                'editor.lineHighlightBackground': '#2a2d32',
                'editorLineNumber.foreground': '#4f545c',
                'editorLineNumber.activeForeground': '#8e9297',
                'editor.selectionBackground': '#5865f240',
                'editor.inactiveSelectionBackground': '#5865f220',
              },
            });
            monaco.editor.setTheme('d-code-dark');
          }}
        />
      </div>

      {/* Live Update Indicator */}
      <LiveUpdateIndicator />
    </main>
  );
}

/**
 * Live Update Indicator
 * Shows when AI is actively writing to this file
 */
function LiveUpdateIndicator() {
  const { engineRunning, currentTaskId } = useStore();
  const isActive = engineRunning && currentTaskId;

  if (!isActive) {
    return null;
  }

  return (
    <div className="absolute bottom-4 right-4 flex items-center gap-2 bg-dc-dark-800 rounded-full px-3 py-1.5 shadow-lg border border-dc-dark-700">
      <div className="w-2 h-2 bg-dc-accent-success rounded-full animate-pulse" />
      <span className="text-xs text-dc-dark-300">AI is writing...</span>
    </div>
  );
}
