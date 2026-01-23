# D-code 実装 | GitHub Copilot Beastmode 3.1 プロンプト

## 📌 プロジェクト基本情報

**プロジェクト名**: D-code (マルチエージェントAI開発プラットフォーム)

**技術スタック**:
- **Rust**: pyo3, tao, wry, tokio, serde, uuid, sysinfo, chrono
- **Python 3.13+**: langgraph, fastapi, websockets, watchdog, pydantic, aiofiles
- **React 18 + TypeScript**: Tailwind CSS, Zustand, Monaco Editor, Xterm.js

**ワークスペース構造**:
```
D-code/
├── src/                  # Rust実装
│   ├── main.rs
│   ├── bridge.rs
│   ├── security.rs
│   └── terminal.rs       # ← フェーズ1でここを実装
├── engine/               # Python実装
│   ├── main_agent.py
│   ├── orchestrator.py
│   ├── planner.py
│   ├── worker.py
│   ├── chat.py
│   └── system_logic.py
├── ui/                   # React実装
│   └── src/
│       └── components/
└── Cargo.toml
```

---

## 🎯 実装フェーズ概要

| フェーズ | 優先度 | 目標 | 実装期間 |
|---------|--------|------|---------|
| **Phase 1** | 🔴 高 | PowerShell埋め込み + コマンドツリー + PID管理 | 3-4日 |
| **Phase 2** | 🟡 中 | AI思考ストリーミング + ステータスダッシュボード | 2-3日 |
| **Phase 3** | 🟡 中 | カスタムタイトルバー + ウィンドウ制御 | 1-2日 |
| **Phase 4** | 🟢 低 | 会話履歴保存 + 起動メッセージ制御 | 1日 |
| **Phase 5** | 🟢 低 | 差分修正（Partial Update）機能 | 2日 |

---

# ========================================
# PHASE 1: ターミナルシステムの刷新
# ========================================

## 実装目標
PowerShellをプロセスとして埋め込み、AIとユーザーがリアルタイムで監視・制御できる仕組みを構築。

---

## Task 1-1: PowerShellプロセスの埋め込みとリアルタイム監視

### 要件
- PowerShellを子プロセスとして起動
- stdin/stdout/stderr を非同期パイプで接続
- リアルタイム出力をUIに送信
- バッファなしの即時表示

### 気を付けること
1. ✅ **ブロッキングなし**: すべてのI/O操作を `tokio::spawn` で非同期化
2. ✅ **エラーハンドリング**: プロセス起動失敗時は `Result<T, Box<dyn Error>>` で返す
3. ✅ **メモリリーク防止**: チャネルの閉鎖を明示的に処理
4. ✅ **Windows互換性**: PowerShell.exe のパスは環境に応じて動的取得
5. ✅ **マルチプルターミナル**: 複数ターミナルを同時管理可能に

### 実装ファイル
- `src/terminal.rs` ← **新規作成** | Terminal構造体 + リーダー/ライター
- `src/main.rs` ← **編集** | Terminal の初期化をmain()に追加
- `engine/terminal_handler.py` ← **新規作成** | AIの出力監視
- `ui/src/components/Terminal.tsx` ← **新規作成** | Xterm.js統合

### 実装手順
1. Rust側で `Terminal` 構造体を実装
   - spawn()でPowerShell起動
   - stdout/stderr読み取り用 tokio task を生成
   - stdin書き込み用 tokio task を生成
   - 各々 mpsc チャネルで非同期通信

2. Python側で出力イベント購読
   - WebSocket経由でRust側からの出力を受信
   - バッファに蓄積してAIが参照可能に
   - エラー検知で自動復旧トリガー

3. React側でXterm.jsを統合
   - ターミナルUIレンダリング
   - ユーザー入力をWebSocket経由でRust側に送信
   - リアルタイム出力を表示

---

## Task 1-2: コマンドツリー管理システム

### 要件
- 親子関係を持つコマンド構造を管理
- 親コマンドが実行されたターミナルでのみ子コマンドを実行
- 例: `cd backend` (親) → `npm install` (子)

### 気を付けること
1. ✅ **トポロジカルソート**: 子コマンドは親の完了を待つ
2. ✅ **UUID管理**: コマンド追跡用に unique ID を割り当て
3. ✅ **ステート管理**: Pending → Running → Completed/Failed を厳密に管理
4. ✅ **タイムアウト**: 子コマンドが親の終了後も実行中なら警告

### 実装ファイル
- `src/command_tree.rs` ← **新規作成** | CommandNode + CommandTree構造体
- `src/terminal.rs` ← **編集** | Terminal に command_tree_id フィールド追加

### 実装手順
1. CommandNode 構造体を定義
   - id, command, terminal_id, parent_id, children[], status

2. CommandTree 構造体で管理
   - add_command() で新規コマンドを追加
   - get_parent() で親コマンドを取得
   - execute_children() で子を順次実行

3. 実行フロー
   - AIが `add_command()` でコマンドを追加
   - Orchestrator が完了を監視
   - 親完了時に自動的に子を実行

---

## Task 1-3: PID管理とプロセス制御

### 要件
- 実行中の全プロセスをPIDで追跡
- AIが自然言語指示からプロセスを推測して終了
- グローバルなコマンドトラッカーで一元管理

### 気を付けること
1. ✅ **OSごとの実装**: Windows (taskkill) / Unix (kill signal)
2. ✅ **子プロセス管理**: 親プロセス終了時に子も終了
3. ✅ **LLM連携**: キーワード抽出で目的プロセスを特定
4. ✅ **確認機構**: 複数候補時はユーザーに選択させる
5. ✅ **ログ記録**: 全プロセス終了を監査ログに記録

### 実装ファイル
- `src/process_manager.rs` ← **新規作成** | ProcessManager + ProcessInfo
- `engine/process_controller.py` ← **新規作成** | LLMベースのプロセス制御

### 実装手順
1. ProcessManager を実装
   - register() でプロセス登録
   - kill() で目的プロセスを終了
   - find_by_keyword() で候補検索

2. ProcessController (Python) を実装
   - ユーザー入力をLLMで解析
   - キーワード抽出
   - ProcessManager に問い合わせ

3. WebSocket インターフェース
   - `find_processes` リクエスト
   - `kill_process` リクエスト
   - `confirm_kill` 確認メッセージ

---

## Phase 1 完了条件

- [ ] PowerShell プロセスが起動し、コマンド実行が可能
- [ ] stdout/stderr がリアルタイムでUI に表示される
- [ ] ユーザーがターミナルに直接入力可能
- [ ] コマンドツリーで親子関係を管理可能
- [ ] PID管理で複数プロセスを同時追跡可能
- [ ] `npm run dev` を終了できる (例: "サーバーを止めて")

---

# ========================================
# PHASE 2: AI思考の可視化
# ========================================

## 実装目標
AIの応答をストリーミング表示し、エージェント群の状態をダッシュボードで可視化。

---

## Task 2-1: リアルタイム思考ストリーミング

### 要件
- AIの応答を1文字ずつストリーミング表示
- Gemini/ChatGPT のような流暢な表示
- WebSocket経由でフロントエンドに逐次送信

### 気を付けること
1. ✅ **遅延最小化**: チャンク送信間隔は 100ms 以内
2. ✅ **バッファ管理**: 受信側でバッファオーバーフロー対策
3. ✅ **エンコーディング**: UTF-8の多バイト文字を正確に処理
4. ✅ **LLMストリーミング**: Gemini/OpenAI の stream API を利用

### 実装ファイル
- `engine/worker.py` ← **編集** | stream_response() メソッド追加
- `engine/orchestrator.py` ← **編集** | LLMストリーミング呼び出し
- `ui/src/components/ChatPanel.tsx` ← **新規/編集** | ストリーミング表示

### 実装手順
1. Worker.stream_response() を実装
   ```
   async for chunk in llm.stream(prompt):
       await ws_send({"type": "ai_thinking", "chunk": chunk})
   ```

2. Orchestrator で stream_response() を呼び出し
   - prompt 構築 (コンテキスト含める)
   - ストリーミング開始
   - バッファに全文蓄積

3. React で受信
   - WebSocket message リスナー登録
   - `ai_thinking` メッセージを累積
   - 完了時に `ai_complete` イベント発火

---

## Task 2-2: AI群ステータスダッシュボード

### 要件
- 下部ユニットに「AI Status」タブを追加
- Orchestrator, Planner, Worker の状態をリアルタイム表示

### 気を付けること
1. ✅ **ステート定義**: 状態は Enum で管理 (Thinking | Idle | Error | Completed)
2. ✅ **ハートビート**: 各エージェントが定期的に自身のステータスを報告
3. ✅ **エラー表示**: Error 状態ではエラーメッセージを表示
4. ✅ **プログレス表示**: Thinking 中はプログレスバーを表示

### 実装ファイル
- `engine/main_agent.py` ← **編集** | ステータス報告ロジック
- `ui/src/components/AIStatusPanel.tsx` ← **新規作成** | ダッシュボード

### 実装手順
1. エージェント側で状態管理
   ```python
   class Agent:
       async def report_status(self, state, task=None, progress=None):
           await ws_send({
               "type": "agent_status",
               "data": {"agent": self.name, "state": state, ...}
           })
   ```

2. React でダッシュボード実装
   - 3列グリッド (Orchestrator, Planner, Worker)
   - ステータスアイコン表示
   - プログレスバー
   - 現在タスク表示

---

## Phase 2 完了条件

- [ ] AIの応答がリアルタイムでストリーミング表示される
- [ ] AI Status タブが表示される
- [ ] 各エージェントの状態が正確に反映される
- [ ] エラー発生時にダッシュボードに表示される

---

# ========================================
# PHASE 3: UI改善
# ========================================

## 実装目標
カスタムタイトルバーを実装し、ウィンドウ制御を整備。

---

## Task 3-1 & 3-2: カスタムタイトルバー + ウィンドウ制御

### 要件
- Rust の `tao` でネイティブタイトルバーを非表示化
- React でカスタムタイトルバーを実装
- 最小化/最大化/閉じるボタンを機能させる

### 気を付けること
1. ✅ **draggable 領域**: タイトルバーをドラッグ可能に設定
2. ✅ **Windows テーマ対応**: ダークモード/ライトモード自動切り替え
3. ✅ **クリック領域**: ボタン部分は draggable 除外
4. ✅ **IPC通信**: Rust ↔ React 間で確実に通信

### 実装ファイル
- `src/main.rs` ← **編集** | `with_decorations(false)` 設定
- `ui/src/components/TitleBar.tsx` ← **新規作成** | タイトルバーUI

### 実装手順
1. Rust 側
   ```rust
   WindowBuilder::new().with_decorations(false)
   ```

2. React 側でタイトルバーコンポーネント
   - 高さ 32px
   - Draggable 領域
   - ボタングループ (最小化/最大化/閉じる)

3. IPC Listener 設定
   ```rust
   ipc_handler.on("window:minimize", |_| { ... })
   ipc_handler.on("window:maximize", |_| { ... })
   ```

---

## Phase 3 完了条件

- [ ] ネイティブタイトルバーが非表示
- [ ] カスタムタイトルバーが正常に表示
- [ ] 最小化/最大化/閉じるボタンが動作
- [ ] タイトルバーをドラッグしてウィンドウ移動可能

---

# ========================================
# PHASE 4: データ永続化
# ========================================

## 実装目標
会話履歴を保存・復元し、起動メッセージを制御。

---

## Task 4-1: チャットルーム形式の履歴保存

### 要件
- `.dcode/conversations/` に JSONL 形式で保存
- タイムスタンプ付き
- セッション再開可能

### 気を付けること
1. ✅ **JSONL フォーマット**: 1行 = 1メッセージ (JSON)
2. ✅ **エンコーディング**: UTF-8 で統一
3. ✅ **ディレクトリ作成**: 存在しなければ自動作成
4. ✅ **ファイルロック**: 並行アクセス対応

### 実装ファイル
- `engine/conversation_manager.py` ← **新規作成** | 履歴管理

---

## Task 4-2: 起動時メッセージの制御

### 要件
- 開発モード以外では初期化メッセージを非表示
- `DCODE_DEBUG=true` でのみ表示

### 実装ファイル
- `engine/logger.py` ← **編集** | DCODE_DEBUG 確認

---

## Phase 4 完了条件

- [ ] `.dcode/conversations/` にセッションが保存される
- [ ] DCODE_DEBUG=false でメッセージが非表示
- [ ] DCODE_DEBUG=true でメッセージが表示

---

# ========================================
# PHASE 5: コード編集最適化
# ========================================

## 実装目標
ファイル全体ではなく、変更箇所のみを更新するパッチ機能を実装。

---

## Task 5-1: 差分修正（Partial Update）機能

### 要件
- unified diff フォーマットで変更指定
- 大規模ファイルも効率的に編集
- Monaco Editor と連携して diff 表示

### 気を付けること
1. ✅ **difflib 活用**: Python の difflib.unified_diff を使用
2. ✅ **キャッシュ**: ファイル変更前のハッシュ値を記録
3. ✅ **テスト**: パッチ適用後に構文チェック実行
4. ✅ **ロールバック**: エラー時は元のファイルに復元

### 実装ファイル
- `engine/code_editor.py` ← **新規作成** | CodeEditor クラス

---

## Phase 5 完了条件

- [ ] `apply_patch()` でファイルの一部のみ更新可能
- [ ] ファイル全体が再作成されない
- [ ] 構文エラー時は元に復元

---

# ========================================
# 実装開始時の確認事項
# ========================================

## 環境確認
- [ ] Rust 1.70+ インストール
- [ ] Python 3.13+ インストール
- [ ] Node.js 18+ インストール
- [ ] PowerShell 7+ インストール (Windows)

## 依存関係確認
```bash
# Rust
cargo check

# Python
pip install -r requirements.txt

# Node.js
cd ui && npm install
```

## テスト方法

### Phase 1 テスト
```bash
# Rust コンパイル確認
cargo build

# PowerShell 起動確認
# → UI で "dir" コマンド実行可能か確認
```

### Phase 2 テスト
```bash
# AI ストリーミング表示確認
# → UIで質問入力 → 応答が1文字ずつ表示されるか
```

### Phase 3 テスト
```bash
# ウィンドウ制御確認
# → タイトルバーボタンで最小化/最大化/閉じられるか
```

### Phase 4 テスト
```bash
# 履歴保存確認
ls -la .dcode/conversations/
```

### Phase 5 テスト
```bash
# 差分修正確認
# → ファイル編集後に .dcode ディレクトリで変更記録確認
```

---

# ========================================
# コード品質ガイドライン
# ========================================

### Rust
- [ ] `cargo fmt` で整形
- [ ] `cargo clippy` でリント実行
- [ ] 全て `Result<T, E>` でエラー処理
- [ ] `unwrap()` は使用禁止（テスト時を除く）

### Python
- [ ] `black` で整形
- [ ] `ruff` でリント実行
- [ ] `mypy` で型チェック
- [ ] `pydantic` で入出力バリデーション

### TypeScript/React
- [ ] `prettier` で整形
- [ ] `eslint` でリント実行
- [ ] 厳格な型定義（noImplicitAny = true）
- [ ] 全てのイベントハンドラに型付け

---

# ========================================
# 実装サポート
# ========================================

実装中に以下の質問があれば、遠慮なく聞いてください：

1. **コンパイルエラー**: ファイル名・行数を指定して共有
2. **ロジック不明**: 処理フロー図を描いて確認
3. **型定義**: 入出力の仕様を明確化
4. **テスト方法**: 再現手順を説明

---

**準備完了！Phase 1 から実装を開始できます。** 🚀
