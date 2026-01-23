# D-code 実装機能ドキュメント

現在実装されている全機能の詳細記述。AIが実行可能なアクション、ミドルウェア処理、UIコンポーネント設定までをカバー。

---

## 1. ファイル削除機能（確認ダイアログ付き）

### 概要
ファイルエクスプローラーから選択したファイル/フォルダを安全に削除する機能。削除前に確認ダイアログを表示し、ワークスペース範囲外への削除を防止するセキュリティ機構を実装。

### 実装フロー
```
LeftPanel.tsx (Menu Click)
  ↓ window.confirm()表示 (ユーザー確認)
  ↓ deleteFile(path) 呼び出し (Zustand action)
  ↓ store.ts / sendToRust({ type: 'DeleteFile', path })
  ↓ bridge.rs / UiCommand::DeleteFile ハンドラ
  ↓ std::fs::canonicalize() (パス検証)
  ↓ canonicalize(DCODE_WORKSPACE) で範囲チェック
  ↓ std::fs::remove_dir_all() または std::fs::remove_file()
  ↓ dcode-file-deleted イベント発火 (UI更新)
```

### LeftPanel.tsx コンポーネント
**削除メニュー項目:**
```typescript
{
  label: 'Delete',
  onClick: () => {
    const confirmMessage = `「${node.name}」を削除しますか？\n\nこの操作は取り消せません。`;
    if (window.confirm(confirmMessage)) {
      deleteFile(node.path);  // store.tsから destructure
    }
  }
}
```
- ユーザーへの日本語確認メッセージ
- キャンセル時は何もしない
- 承認時のみRust削除処理へ

### store.ts - Zustand Action
```typescript
deleteFile: (path: string) => void
  → IPC: sendToRust({ type: 'DeleteFile', path })
```
- ファイルパスをRust側へ転送
- レスポンス待機（非同期）

### bridge.rs - Rust ハンドラ処理
**セキュリティレイヤ:**
```rust
UiCommand::DeleteFile { path }:
1. let canonical_path = std::fs::canonicalize(&path)?;
   ↓ 実際のディスク上の絶対パスに正規化
2. let workspace_canonical = std::fs::canonicalize(DCODE_WORKSPACE)?;
   ↓ ワークスペース絶対パス取得
3. if !canonical_path.starts_with(workspace_canonical):
   ↓ ワークスペース外ならエラー
4. std::fs::remove_dir_all(&canonical_path) または remove_file(&canonical_path)
   ↓ 再帰的に削除（フォルダ内全ファイルを含む）
```

**IPC応答:**
```rust
send_message(UiMessage::FileDeleted {
  path: path.clone(),
  success: true,
  message: format!("「{}」を削除しました", filename)
})
```

### UI 反映
**store.ts イベントリスナー:**
```typescript
'dcode-file-deleted':
  1. 成功時: messages配列に削除完了メッセージを追加
  2. 選択ファイルが削除されたファイルの場合:
     - selectedFile = null でクリア
     - エディタ内容クリア
     - File Not Found メッセージ表示
```

### セキュリティ特性
- ✅ パス正規化による シンボリックリンク攻撃対策
- ✅ ワークスペース範囲チェック（外側のファイル保護）
- ✅ 再帰削除対応（フォルダ選択時）
- ✅ ユーザー確認ダイアログ（誤操作防止）

---

## 2. ウィンドウ最大化/復元機能（状態トラッキング）

### 概要
タイトルバー最大化ボタンでウィンドウ全体を最大化/復元。`decorations=false`設定下での`is_maximized()`バグをAtomicBool静的変数で回避。

### 実装フロー
```
TitleBar.tsx (Maximize Button Click)
  ↓ sendToRust({ type: 'WindowMaximize' })
  ↓ bridge.rs / AppEvent::WindowMaximize ハンドラ
  ↓ IS_WINDOW_MAXIMIZED.load(Ordering::SeqCst)
  ↓ 状態に応じて復元 または 最大化処理
  ↓ dcode-window-maximized イベント（UI状態同期）
```

### bridge.rs - 静的状態トラッキング
```rust
static IS_WINDOW_MAXIMIZED: AtomicBool = AtomicBool::new(false);
```
**理由:** `decorations=false` (カスタムタイトルバー)では
- `window.is_maximized()` が正確な状態を返さない
- Rust側で状態を手動管理する必要がある

### ウィンドウ復元処理
```rust
// IS_WINDOW_MAXIMIZED が true → false へ
set_maximized(false);           // ウィンドウモード解除
set_inner_size((1400, 900));    // デフォルトサイズ
center_window();                // モニタ中央へ配置
IS_WINDOW_MAXIMIZED.store(false, Ordering::SeqCst);
```

### ウィンドウ最大化処理
```rust
// IS_WINDOW_MAXIMIZED が false → true へ
let monitor_size = window.primary_monitor().size();
set_maximized(true);
let adjusted_width = monitor_size.width - 40;  // タスクバー考慮
let adjusted_height = monitor_size.height - 40;
set_inner_size((adjusted_width, adjusted_height));
IS_WINDOW_MAXIMIZED.store(true, Ordering::SeqCst);
```

### TitleBar.tsx - UI反映
**状態管理:**
```typescript
const [isMaximized, setIsMaximized] = useState(false);
```

**イベントリスナー:**
```typescript
window.addEventListener('dcode-window-maximized', (e: CustomEvent) => {
  setIsMaximized(e.detail.isMaximized);
});
```

**アイコン表示ロジック:**
```typescript
{isMaximized ? (
  <Copy className="w-3.5 h-3.5" />   // 復元アイコン
) : (
  <Square className="w-3.5 h-3.5" /> // 最大化アイコン
)}
```

**ボタンクリックハンドラ:**
```typescript
const handleMaximize = () => {
  sendToRust({ type: 'WindowMaximize' });
};
```

**ダブルクリック対応:**
```typescript
onDoubleClick={handleMaximize}  // タイトルバー部分
```

### スタイリング
```typescript
className="hover:bg-dc-dark-700 transition-colors"
// 最大化ボタン
p-1.5 rounded hover:bg-dc-dark-700 transition-colors
```

---

## 3. 思考プロセス折りたたみ機能（`<think>` タグ対応）

### 概要
AIレスポンス内の `<think>...</think>` タグを正規表現で抽出し、折りたたみ可能なUIコンポーネントとして表示。展開/縮小をトグルで制御。

### 実装フロー
```
RightPanel.tsx / ThinkBlockContent
  ↓ parseThinkBlocks(content) 正規表現処理
  ↓ テキストと<think>ブロックに分割
  ↓ map() で各セグメント描画
    - type:'text' → 通常段落 <p>
    - type:'think' → CollapsibleThinkBlock
  ↓ CollapsibleThinkBlock
    ↓ isExpanded 状態管理
    ↓ ヘッダークリック → トグル
    ↓ 展開時に全文表示
```

### RightPanel.tsx - parseThinkBlocks 関数
**正規表現パターン:**
```typescript
const parseThinkBlocks = (content: string): ContentPart[] => {
  const parts: ContentPart[] = [];
  const regex = /<think>([\s\S]*?)<\/think>/gi;
  let lastIndex = 0;
  let match;

  while ((match = regex.exec(content)) !== null) {
    // <think> 前のテキスト
    if (match.index > lastIndex) {
      parts.push({
        type: 'text',
        content: content.substring(lastIndex, match.index)
      });
    }
    // <think> ブロック内容
    parts.push({
      type: 'think',
      content: match[1]  // キャプチャグループ
    });
    lastIndex = regex.lastIndex;
  }
  // 最後のテキスト
  if (lastIndex < content.length) {
    parts.push({
      type: 'text',
      content: content.substring(lastIndex)
    });
  }
  return parts;
};
```

**interface定義:**
```typescript
interface ContentPart {
  type: 'text' | 'think';
  content: string;
}
```

### ThinkBlockContent コンポーネント
```typescript
const ThinkBlockContent = ({ content }: { content: string }) => {
  const parts = useMemo(() => parseThinkBlocks(content), [content]);

  return (
    <div>
      {parts.map((part, idx) => 
        part.type === 'text' ? (
          <p key={idx} className="text-white/80">
            {part.content}
          </p>
        ) : (
          <CollapsibleThinkBlock key={idx} content={part.content} />
        )
      )}
    </div>
  );
};
```

### CollapsibleThinkBlock コンポーネント
**状態管理:**
```typescript
const [isExpanded, setIsExpanded] = useState(false);
```

**ヘッダーレイアウト:**
```typescript
<button
  onClick={() => setIsExpanded(!isExpanded)}
  className="w-full px-2 py-1 bg-purple-900/20 border border-purple-500/30 
             rounded hover:bg-purple-500/10 transition-colors"
>
  <div className="flex items-center gap-1 text-left">
    {/* 折りたたみアイコン */}
    {isExpanded ? (
      <ChevronDown className="w-3 h-3 text-purple-400" />
    ) : (
      <ChevronRight className="w-3 h-3 text-purple-400" />
    )}
    
    {/* 脳アイコン */}
    <Brain className="w-3 h-3 text-purple-400" />
    
    {/* ラベル */}
    <span className="text-[10px] font-medium text-purple-400">
      思考プロセス
    </span>
    
    {/* プレビュー (最初の80文字) */}
    <span className="text-[10px] text-purple-300/60 flex-1">
      {content.substring(0, 80).replace(/\n/g, ' ')}...
    </span>
  </div>
</button>
```

**展開時コンテンツ:**
```typescript
{isExpanded && (
  <div className="mt-1.5 p-2 bg-purple-900/10 border border-purple-500/20 rounded">
    <pre className="font-mono text-[10px] text-purple-200 whitespace-pre-wrap 
                    leading-relaxed overflow-x-auto">
      {content}
    </pre>
  </div>
)}
```

### スタイリング詳細
**コンテナ:**
- `bg-purple-900/20` - 薄紫背景
- `border-purple-500/30` - 紫枠線（半透明）
- `rounded` - 角丸
- `px-2 py-1` - 内部余白（コンパクト）

**アイコン:**
- `w-3 h-3` - 小さめサイズ
- `text-purple-400` - 紫色

**テキスト:**
- `text-[10px]` - 小さめフォント
- `text-purple-400` / `text-purple-300/60` - 紫系カラー

**展開状態:**
- `mt-1.5` - 上部マージン
- `font-mono` - 等幅フォント
- `whitespace-pre-wrap` - 改行を保持
- `leading-relaxed` - 行間広め

### Lucide React 依存関係
```typescript
import { Brain, ChevronDown, ChevronRight } from 'lucide-react';
```

---

## 4. OpenAI ストリーミング応答実装

### 概要
OpenAI APIから逐次的にレスポンステキストをストリーミング受信し、リアルタイムでUI表示。Pythonコールバック機構とRust経由でイベント駆動化。

### 実装フロー
```
Python (engine/chat.py)
  ↓ _streaming_callback グローバル変数で Callable保持
  ↓ set_streaming_callback(callback) で Rust closure登録
  ↓ _chat_openai() で stream=True モード
  ↓ OpenAI API → for chunk in stream:
  ↓ _emit_streaming_chunk(message_id, chunk, agent)
  ↓ callback(message_id, chunk, agent) → Rust closure呼び出し
  ↓ Rust: AppEvent::AiThinkingChunk 生成
  ↓ UI: RightPanel.tsx リアルタイム更新
```

### engine/chat.py - ストリーミング基盤
**グローバルコールバック変数:**
```python
from typing import Optional, Callable

_streaming_callback: Optional[Callable[[str, str, str], None]] = None
```

**コールバック登録関数:**
```python
def set_streaming_callback(callback: Optional[Callable[[str, str, str], None]]) -> None:
    """Rust側から呼ばれるコールバック登録"""
    global _streaming_callback
    _streaming_callback = callback
```

**チャンク発火関数:**
```python
def _emit_streaming_chunk(message_id: str, chunk: str, agent: str) -> None:
    """ストリーミングチャンクをコールバック経由で発火"""
    global _streaming_callback
    if _streaming_callback is not None:
        _streaming_callback(message_id, chunk, agent)
```

**chat_sync() 拡張:**
```python
def chat_sync(
    messages: list[dict],
    model_name: str = "gemini-2.0-flash",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    message_id: str = ""  # ← 新規パラメータ（ストリーミング用）
) -> str:
    """
    message_id: ストリーミングチャンク識別用ID
    """
    if "openai" in model_name.lower():
        return _chat_openai(messages, model_name, temperature, max_tokens, message_id)
    else:
        return _chat_gemini(messages, model_name, temperature, max_tokens)
```

**_chat_openai() 実装:**
```python
def _chat_openai(
    messages: list[dict],
    model_name: str,
    temperature: float,
    max_tokens: int,
    message_id: str = ""
) -> str:
    """OpenAI API ストリーミングモード"""
    
    # OpenAIクライアント初期化（APIキー取得）
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    
    full_response = ""
    
    if _streaming_callback is not None:
        # ストリーミングモード
        stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True  # ← ストリーミング有効化
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                delta_content = chunk.choices[0].delta.content
                full_response += delta_content
                
                # Rust側へチャンク通知
                _emit_streaming_chunk(
                    message_id,
                    delta_content,
                    model_name
                )
    else:
        # 非ストリーミングモード（フォールバック）
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )
        full_response = response.choices[0].message.content
    
    return full_response
```

### bridge.rs - コールバック設定とイベント処理
**コールバック関数型:**
```rust
use pyo3::types::PyCFunction;
use pyo3::PyFunction;
```

**call_gemini_chat 実装:**
```rust
fn call_gemini_chat(
    message: &str,
    terminal_context: Option<&str>,
    message_id: &str,
    event_proxy: EventLoopProxy<AppEvent>
) {
    Python::with_gil(|py| {
        let chat_module = py.import_bound("engine.chat").unwrap();
        
        // ストリーミングコールバック closure を定義
        let callback = PyFunction::new_closure(
            py,
            None,
            None,
            |args: &Bound<'_, PyTuple>, _kwargs| {
                // コールバック受け取り引数の抽出
                let message_id: String = args.get_item(0)?.extract()?;
                let chunk: String = args.get_item(1)?.extract()?;
                let agent: String = args.get_item(2)?.extract()?;
                
                // Rust側でイベント生成
                event_proxy.send_event(
                    AppEvent::AiThinkingChunk {
                        message_id: message_id.clone(),
                        chunk: chunk.clone(),
                        agent: agent.clone(),
                    }
                ).ok();
                
                Ok(py.None())
            }
        )?;
        
        // Python側へコールバック登録
        chat_module.call_method1("set_streaming_callback", (callback,))?;
        
        // チャット処理実行
        let response = chat_module.call_method(
            "chat_sync",
            (messages, "gpt-4o-mini", message_id),  // ← message_id 渡す
            None
        )?;
        
        // 完了後、コールバッククリア
        chat_module.call_method1("set_streaming_callback", (py.None(),))?;
        
        Ok::<(), PyErr>(())
    });
}
```

**AppEvent enum (拡張):**
```rust
pub enum AppEvent {
    AiThinkingChunk {
        message_id: String,
        chunk: String,
        agent: String,
    },
    // ... 他のイベント
}
```

### UI ハンドリング
**store.ts イベントリスナー (準備済み):**
```typescript
window.addEventListener('dcode-ai-thinking-chunk', (e: CustomEvent) => {
  const { message_id, chunk, agent } = e.detail;
  
  // messages配列で message_id に合致するメッセージを検索
  setMessages(prev => {
    const updated = [...prev];
    const msgIdx = updated.findIndex(m => m.id === message_id);
    if (msgIdx !== -1) {
      // 既存メッセージにチャンク追加
      updated[msgIdx].content += chunk;
    }
    return updated;
  });
});
```

### 特性と詳細
- ✅ リアルタイムテキスト表示（遅延なし）
- ✅ メッセージIDで複数同時チャット対応
- ✅ コールバック登録/解除で状態管理（メモリリーク防止）
- ✅ フォールバック: コールバック未登録時は通常モード

---

## 5. AI 処理停止機能（Stop AI ボタン）

### 概要
実行中のAI処理を途中で中断。Python側の `request_break()` 関数呼び出しで処理を停止。

### 実装フロー
```
UI: Stop AI ボタンクリック
  ↓ sendToRust({ type: 'BreakRequest' })
  ↓ bridge.rs / UiCommand::BreakRequest ハンドラ
  ↓ Python: chat_module.call_method("request_break")
  ↓ engine/chat.py / request_break() 実行
  ↓ グローバルフラグ _break_requested = True
  ↓ 処理ループで定期チェック → 処理終了
```

### bridge.rs - BreakRequest ハンドラ
```rust
UiCommand::BreakRequest => {
    let message_sent = Python::with_gil(|py| {
        if let Ok(chat_module) = py.import_bound("engine.chat") {
            chat_module.call_method0("request_break").ok();
            true
        } else {
            false
        }
    });
    
    if message_sent {
        send_message(UiMessage::SystemMessage {
            content: "AI処理を停止中...".to_string(),
        });
    }
}
```

### engine/chat.py - 停止機構
```python
_break_requested = False

def request_break() -> None:
    """AI処理停止リクエスト"""
    global _break_requested
    _break_requested = True

def _is_break_requested() -> bool:
    """停止フラグチェック"""
    return _break_requested

def chat_sync(...):
    """...処理ループ内..."""
    global _break_requested
    _break_requested = False  # リセット
    
    # チャット処理
    result = _chat_openai(...)
    
    if _break_requested:
        return "<!-- AI処理が中断されました -->"
```

---

## 6. ターミナル直接入力機能

### 概要
RightPanel のターミナル領域でコマンド直接入力。Pythonワーカーへリアルタイム送信。

### RightPanel.tsx - ターミナル入力フォーム
```typescript
const [terminalInput, setTerminalInput] = useState('');

const handleTerminalSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  if (terminalInput.trim()) {
    sendToRust({
      type: 'WorkerInput',
      input: terminalInput.trim()
    });
    setTerminalInput('');
  }
};

// UI
<form onSubmit={handleTerminalSubmit}>
  <input
    type="text"
    value={terminalInput}
    onChange={(e) => setTerminalInput(e.target.value)}
    placeholder="コマンドを入力..."
    className="w-full bg-dc-dark-800 text-white px-3 py-2 rounded"
  />
</form>
```

### bridge.rs - ワーカー入力ハンドラ
```rust
UiCommand::WorkerInput { input } => {
    // ワーカーのキューへ入力を追加
    worker_queue.push(input);
}
```

---

## 7. ターミナル削除時のUI出力クリア

### 概要
ターミナルセッションを閉じる際、表示済みの出力メッセージをUIから削除。

### 実装フロー
```
TitleBar: Close Terminal Button
  ↓ sendToRust({ type: 'CloseTerminal' })
  ↓ bridge.rs / UiCommand::CloseTerminal
  ↓ dcode-close-terminal イベント発火
  ↓ store.ts リスナー
    - messages 配列をクリア
    - terminalOutput をリセット
```

### store.ts - closeTerminal アクション
```typescript
closeTerminal: () => {
  setMessages([]);  // メッセージクリア
  setTerminalOutput('');  // 出力クリア
},

// イベント
'dcode-close-terminal': () => {
  closeTerminal();
}
```

---

## 8. UI スタイリング詳細（思考ブロック最適化）

### 折りたたみブロックのサイズ調整
**最適化されたパラメータ:**

| 要素 | 値 | 用途 |
|------|-----|------|
| ボタン高さ | `py-1` (4px上下) | コンパクト表示 |
| 横余白 | `px-2` (8px左右) | バランス調整 |
| アイコンサイズ | `w-3 h-3` (12px) | 小型で統一 |
| フォントサイズ | `text-[10px]` | 細かい表示 |
| 枠線透明度 | `border-purple-500/30` | 控えめな強調 |
| 背景透明度 | `bg-purple-900/20` | 目立たない |
| ホバー効果 | `hover:bg-purple-500/10` | 軽い視覚フィードバック |
| 展開内容余白 | `mt-1.5 p-2` | 適度な間隔 |

**結果:** 複数の思考ブロックが表示されても、UI上で場所を取りすぎず、段落テキストとの視覚的なバランスが維持される。

---

## 実装チェックリスト

- [x] ファイル削除機能（ダイアログ + セキュリティチェック）
- [x] ウィンドウ最大化/復元（AtomicBool状態管理）
- [x] 思考ブロック折りたたみ（正規表現 + コンポーネント）
- [x] OpenAI ストリーミング（コールバック + イベント駆動）
- [x] Stop AI ボタン（request_break統合）
- [x] ターミナル直接入力（WorkerInput IPC）
- [x] ターミナル削除時UI清掃（closeTerminal）
- [x] UI最適化スタイリング

---

## 技術スタック詳細

### Rust (bridge.rs)
```
- pyo3 0.23: Python連携（PyFunction::new_closure + Bound<'_, PyTuple>）
- tao 0.33: ウィンドウ管理
- std::sync::atomic::AtomicBool: 状態トラッキング
- std::fs::{canonicalize, remove_dir_all, remove_file}: ファイル操作
```

### Python (engine/chat.py)
```
- OpenAI SDK: ストリーミングチャット
- Callable[[str, str, str], None]: コールバック型
- Optional[Callable]: None許容の型安全性
```

### React (ui/)
```
- TypeScript 5.6+
- React Hooks: useState, useMemo
- Zustand: 状態管理
- Tailwind CSS: スタイリング
- Lucide React: アイコン (Brain, ChevronDown, ChevronRight, Copy, Square)
- 正規表現: /<think>([\s\S]*?)<\/think>/gi
```

---

## セキュリティ & パフォーマンス特性

### セキュリティ
- ✅ パス正規化（canonicalize）でシンボリックリンク対策
- ✅ ワークスペース範囲チェック（ファイル保護）
- ✅ ユーザー確認ダイアログ（誤操作防止）
- ✅ APIキー環境変数化（硬化防止）

### パフォーマンス
- ✅ ストリーミング: リアルタイム表示で体感速度向上
- ✅ メモ化（useMemo）: parseThinkBlocks 再計算防止
- ✅ 状態分離: UI・ウィンドウ・ファイル操作の独立トラッキング
- ✅ 非同期IPC: ブロッキングなし

---

## デバッグ・トラブルシューティング

### <think> タグが表示されない
- → `<think>` `</think>` が全て小文字か確認
- → 改行を含むか確認（`[\s\S]*?` で対応）

### ウィンドウ復元がおかしい
- → IS_WINDOW_MAXIMIZED の AtomicBool が同期しているか確認
- → dcode-window-maximized イベントがTitleBarに届いているか確認

### OpenAI ストリーミングが動作しない
- → OPENAI_API_KEY 環境変数が設定されているか確認
- → set_streaming_callback(None) で登録解除されているか確認

### ファイル削除が失敗する
- → パスがワークスペース外でないか確認
- → 削除対象がディレクトリの場合、内部にファイルがあるか確認
- → ファイルロックされていないか確認

