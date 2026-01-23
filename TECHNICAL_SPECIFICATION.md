# D-code 技術仕様書 (完全版)

**プロジェクト名**: D-code  
**説明**: AI駆動マルチエージェント開発プラットフォーム  
**バージョン**: 0.1.0  
**作成日**: 2026年1月23日  
**ステータス**: 開発中

---

## 📋 目次

1. [プロジェクト概要](#プロジェクト概要)
2. [技術スタック](#技術スタック)
3. [プロジェクト構造](#プロジェクト構造)
4. [アーキテクチャ](#アーキテクチャ)
5. [実装状況](#実装状況)
6. [API仕様](#api仕様)
7. [セキュリティ設計](#セキュリティ設計)
8. [コスト最適化](#コスト最適化)
9. [開発ガイドライン](#開発ガイドライン)

---

## プロジェクト概要

### ビジョン
複数のAIエージェントを組み合わせて、複雑なコーディングタスクを自動化・効率化するプラットフォーム。ユーザーが自然言語で指示すると、システムが自動的にタスク計画、実装、検証を行う。

### 主な特徴

| 特徴 | 説明 |
|------|------|
| **マルチエージェント** | Orchestrator, Planner, Engineers, Streamer が協調動作 |
| **セキュリティ第一** | Python コード埋め込み + メモリ内実行 + XOR 難読化 |
| **コスト最適化** | Gemini 2.5 Flash (推論) + 2.0 Flash (実行) の使い分け |
| **リアルタイムUI** | WebSocket でストリーミング表示、Monaco Editor 統合 |
| **並列処理** | 最大10個の Worker による同時実行 |
| **ターミナル統合** | PowerShell 埋め込み、リアルタイム監視 |

---

## 技術スタック

### Rust (バックエンド & デスクトップアプリケーション)

**バージョン**: 1.75+  
**エディション**: 2021

**コア依存関係**:

| ライブラリ | バージョン | 用途 |
|-----------|-----------|------|
| **pyo3** | 0.23 | Python インタプリタ埋め込み |
| **tokio** | 1.x | 非同期ランタイム |
| **tao** | 0.33 | ネイティブウィンドウ |
| **wry** | 0.49 | WebView レンダリング |
| **serde/serde_json** | 1.0 | JSON シリアライズ |
| **rust-embed** | 8 | 静的ファイル埋め込み |
| **uuid** | 1.x | 一意識別子生成 |
| **regex** | 1.x | テキスト解析 |
| **aes-gcm** | 0.10 | 暗号化 (予定) |
| **chrono** | 0.4 | タイムスタンプ管理 |
| **dirs** | 5 | OS パス取得 |
| **log/fern** | - | ログ出力 |

**ビルドプロファイル**:
```toml
[profile.release]
strip = true      # シンボル削除（セキュリティ）
lto = true        # Link-Time Optimization
codegen-units = 1 # 最適化レベル最大
opt-level = "z"   # 最小化
```

### Python (AI エンジン)

**バージョン**: 3.13+

**コア依存関係**:

| ライブラリ | バージョン | 用途 |
|-----------|-----------|------|
| **google-genai** | ≥1.0.0 | Gemini API |
| **openai** | ≥1.0.0 | OpenAI API (LM Studio 互換) |
| **langgraph** | ≥0.2.0 | エージェント状態管理 |
| **langchain** | ≥0.3.0 | LLM フレームワーク |
| **fastapi** | ≥0.115.0 | WebSocket サーバー |
| **uvicorn** | ≥0.32.0 | ASGI アプリケーション |
| **websockets** | ≥14.0 | リアルタイム通信 |
| **pydantic** | ≥2.0.0 | データバリデーション |
| **aiofiles** | ≥24.0.0 | 非同期ファイルI/O |
| **watchdog** | ≥5.0.0 | ファイルシステム監視 |
| **pytest** | ≥8.0.0 | テスティング |

### React (UI フロントエンド)

**バージョン**: 18.3+  
**言語**: TypeScript 5.6+

**コア依存関係**:

| ライブラリ | バージョン | 用途 |
|-----------|-----------|------|
| **react** | ^18.3.1 | UI フレームワーク |
| **react-dom** | ^18.3.1 | DOM 操作 |
| **@monaco-editor/react** | ^4.6.0 | コードエディタ |
| **zustand** | ^5.0.0 | 状態管理 |
| **tailwindcss** | ^3.4.16 | スタイリング |
| **lucide-react** | ^0.468.0 | アイコン |
| **@tauri-apps/api** | ^2.0.0 | デスクトップAPI |

**ビルドツール**:
- **Vite** 6.0+ (バンドラー)
- **TypeScript** 5.6+ (型安全性)
- **PostCSS/Autoprefixer** (CSS プリプロセッサ)

---

## プロジェクト構造

```
D-code/
├── 📄 Cargo.toml                    # Rust メタデータ
├── 📄 build.rs                      # Python 埋め込みスクリプト
├── 📄 main.py                       # Python エントリーポイント (PyWebView モード)
├── 📄 requirements.txt              # Python 依存関係
├── 📄 .env                          # 環境変数 (Git 除外)
├── 📄 README.md                     # プロジェクト説明
├── 📄 COPILOT_BEASTMODE_PROMPT.md  # Copilot チャットプロンプト
├── 📄 TECHNICAL_SPECIFICATION.md   # この文書
│
├── 📁 src/                          # Rust ソースコード
│   ├── main.rs                      # アプリケーション エントリーポイント (300+ 行)
│   ├── bridge.rs                    # WebSocket ブリッジ (2066 行)
│   ├── security.rs                  # セキュリティ & 難読化 (323 行)
│   └── terminal.rs                  # PowerShell 埋め込み (750 行)
│
├── 📁 engine/                       # Python AI エンジン
│   ├── __init__.py                  # モジュール エクスポート
│   ├── main_agent.py                # Orchestrator & メインエンジン
│   ├── orchestrator.py              # マルチエージェント調整 (683 行)
│   ├── planner.py                   # タスク計画エージェント (177 行)
│   ├── worker.py                    # Engineer ワーカープール (279 行)
│   ├── streamer.py                  # UI ストリーミング (299 行)
│   ├── chat.py                      # チャット インターフェース
│   ├── config.py                    # 設定管理 (233 行)
│   ├── code_editor.py               # コード編集ユーティリティ
│   ├── logger.py                    # ログシステム
│   ├── response_parser.py           # AI 応答解析
│   └── system_logic.py              # システムロジック
│
├── 📁 ui/                           # React フロントエンド
│   ├── package.json                 # Node 依存関係
│   ├── vite.config.ts               # Vite 設定
│   ├── tsconfig.json                # TypeScript 設定
│   ├── tailwind.config.js           # Tailwind 設定
│   ├── postcss.config.js            # PostCSS 設定
│   │
│   └── src/
│       ├── App.tsx                  # メインアプリケーション
│       ├── main.tsx                 # React エントリーポイント
│       ├── index.css                # グローバルスタイル
│       ├── store.ts                 # Zustand ストア (状態管理)
│       │
│       ├── 📁 components/           # React コンポーネント
│       │   ├── ChatPanel.tsx        # チャットUI
│       │   ├── Terminal.tsx         # ターミナル UI
│       │   ├── MonacoEditor.tsx     # コードエディタ
│       │   ├── FileExplorer.tsx     # ファイルツリー
│       │   ├── TitleBar.tsx         # カスタムタイトルバー
│       │   └── ...
│       │
│       ├── 📁 hooks/                # React カスタムフック
│       │   ├── useWebSocket.ts      # WebSocket 接続
│       │   └── ...
│       │
│       └── 📁 utils/                # ユーティリティ関数
│           ├── api.ts               # API 呼び出し
│           └── ...
│
├── 📁 docs/                         # ドキュメント
│   ├── DEVELOPMENT.md               # 開発ガイド
│   └── technical.md                 # 技術ノート
│
├── 📁 workspace/                    # ユーザー作業ディレクトリ
│   ├── build/                       # 生成ファイル
│   └── logs/                        # ログファイル
│
├── 📁 target/                       # Rust ビルド出力 (Git 除外)
│   ├── debug/
│   └── release/
│
└── 📁 .github/                      # GitHub 設定
    └── workflows/                   # CI/CD パイプライン
```

---

## アーキテクチャ

### システム全体図

```
┌─────────────────────────────────────────────────────────────────────┐
│                          D-code UI (React)                          │
├─────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌──────────────────┐  ┌────────────────┐   │
│  │ ファイルエクスプローラー │  │ Monaco Code Editor  │  │ Chat Panel    │   │
│  │ (FileExplorer)    │  │ (コード表示/編集)   │  │ (チャット入力)   │   │
│  └───────────────────┘  └──────────────────┘  └────────────────┘   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Terminal Panel (Xterm.js) | Task Progress | AI Status Panel    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Chat Input Bar | Emergency Stop | Settings                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ WebSocket (双方向)
┌─────────────────────────────┴──────────────────────────────────────┐
│                    Rust Wrapper (Tauri-like)                       │
├──────────────────────────────────────────────────────────────────────┤
│ ┌──────────────┐  ┌────────────┐  ┌─────────────────────────────┐  │
│ │ bridge.rs    │  │ security   │  │ terminal.rs                 │  │
│ │ (IPC/WS)     │  │ (暗号化)    │  │ (PowerShell 埋め込み)       │  │
│ └──────────────┘  └────────────┘  └─────────────────────────────┘  │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ PyO3 FFI
┌─────────────────────────────┴──────────────────────────────────────┐
│                     Python AI Engine (async)                        │
├──────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    LangGraph StateGraph                        │  │
│  │  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  │
│  │  │ Orchestrator │→│ Planner  │→│ Workers  │→│ Streamer │  │  │
│  │  │ (2.5 Flash)  │ │(2.5 Fl.) │ │(2.0 Fl.)│ │(2.5 Fl.)│  │  │
│  │  └──────────────┘ └──────────┘ └──────────┘ └──────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │ 外部API: Gemini 2.5 Flash, Gemini 2.0 Flash (Google GenAI)    │ │
│  └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### エージェントロール定義

#### 1. Orchestrator (指揮官)
- **モデル**: Gemini 2.5 Flash Preview
- **責務**:
  - ユーザー入力を受け取り、全体的な流れを制御
  - Planner にタスク計画を依頼
  - Workers の進捗を監視
  - ユーザー割り込み (緊急停止) を処理
  - エラー復旧戦略を決定
- **入力**: ユーザーメッセージ、エラーレポート
- **出力**: タスク計画、実行指示、スト リーミングメッセージ

#### 2. Planner (計画者)
- **モデル**: Gemini 2.5 Flash Preview
- **責務**:
  - 要件を詳細なタスクリストに分解
  - タスク間の依存関係を定義
  - 並列実行可能なタスクをグループ化
  - 優先度とリソース配分を決定
  - 見積り時間を計算
- **入力**: 要件、既存ファイルリスト
- **出力**: TaskPlan (タスク、依存関係、優先度)

#### 3. Engineer (エンジニア / Worker)
- **モデル**: Gemini 2.0 Flash (コスト効率)
- **責務** (PDCA サイクル):
  - **Plan**: タスク要件を分析
  - **Do**: コードを実装・生成
  - **Check**: 動作検証 (構文チェック、テスト)
  - **Act**: 修正・改善
- **並列性**: 最大10個の Worker が同時実行可能
- **入力**: Task オブジェクト
- **出力**: ExecutionResult (変更ファイル、エラーレポート)

#### 4. Streamer (中継者)
- **モデル**: Gemini 2.5 Flash Preview
- **責務**:
  - AI の思考プロセスを人間向けに翻訳
  - 冗長なログを要約
  - 適切なアイコン・色で視覚化
  - WebSocket でリアルタイム配信
- **入力**: エージェントからのログ・メッセージ
- **出力**: StreamMessage (UI 表示用フォーマット)

---

## 実装状況

### 現在のステータス (2026年1月23日)

| モジュール | ステータス | 進捗率 | 説明 |
|-----------|----------|--------|------|
| **Rust バックエンド** | 🟢 実装中 | 60% | main.rs, bridge.rs, security.rs 完成、terminal.rs は基本実装済 |
| **Python エンジン** | 🟢 実装中 | 50% | orchestrator.py, planner.py, worker.py の骨組み完成 |
| **React UI** | 🟡 計画中 | 30% | Vite 設定完了、コンポーネント構造設計中 |
| **PowerShell ターミナル** | 🟡 進行中 | 40% | terminal.rs に StreamingTerminal 実装、UIレイアウト待ち |
| **WebSocket 通信** | 🟢 実装中 | 50% | bridge.rs に基本実装、メッセージ型定義中 |
| **AI ストリーミング** | 🟡 計画中 | 10% | Gemini API ストリーミング API 確認中 |
| **コマンドツリー管理** | ⚫ 未開始 | 0% | Phase 1-2 実装予定 |
| **プロセス管理** | ⚫ 未開始 | 0% | Phase 1-3 実装予定 |
| **カスタムタイトルバー** | ⚫ 未開始 | 0% | Phase 3 実装予定 |
| **会話履歴保存** | ⚫ 未開始 | 0% | Phase 4 実装予定 |
| **差分修正機能** | ⚫ 未開始 | 0% | Phase 5 実装予定 |

### 完了モジュール

✅ **Cargo.toml** - 全依存関係定義完了  
✅ **build.rs** - Python コード埋め込みスクリプト完了  
✅ **src/main.rs** - アプリケーション初期化完了  
✅ **src/security.rs** - セキュリティ関数実装完了  
✅ **src/terminal.rs** - StreamingTerminal クラス実装完了  
✅ **engine/config.py** - 設定管理システム完成  
✅ **engine/orchestrator.py** - エージェント定義完成  
✅ **engine/planner.py** - Task/TaskPlan 構造完成  
✅ **engine/worker.py** - Engineer クラス構造完成  
✅ **engine/streamer.py** - StreamMessage 定義完成  

---

## API仕様

### WebSocket メッセージプロトコル

すべてのメッセージは JSON 形式です。

#### クライアント → サーバー (UI → Engine)

##### 1. チャットメッセージ送信

```json
{
  "type": "send_message",
  "data": {
    "message_id": "msg_123",
    "content": "ユーザーの指示",
    "context": {
      "workspace": "/path/to/workspace",
      "files": ["/file1.rs", "/file2.py"]
    }
  }
}
```

##### 2. ターミナルコマンド実行

```json
{
  "type": "terminal_command",
  "data": {
    "terminal_id": "term_1",
    "command": "npm install",
    "working_dir": "./project"
  }
}
```

##### 3. プロセス終了

```json
{
  "type": "kill_process",
  "data": {
    "pid": 12345
  }
}
```

##### 4. 緊急停止

```json
{
  "type": "emergency_stop",
  "data": {}
}
```

#### サーバー → クライアント (Engine → UI)

##### 1. メッセージストリーミング

```json
{
  "type": "message_chunk",
  "data": {
    "message_id": "msg_123",
    "agent": "orchestrator",
    "agent_icon": "🎯",
    "chunk": "これはAIの応答の一部です",
    "timestamp": "2026-01-23T12:00:00Z"
  }
}
```

##### 2. メッセージ完了

```json
{
  "type": "message_complete",
  "data": {
    "message_id": "msg_123",
    "full_content": "完全な応答テキスト",
    "metadata": {
      "execution_time_ms": 1500,
      "tokens_used": 245
    }
  }
}
```

##### 3. ターミナル出力

```json
{
  "type": "terminal_output",
  "data": {
    "terminal_id": "term_1",
    "line": "コマンドの出力行",
    "is_stderr": false,
    "timestamp": "2026-01-23T12:00:00Z"
  }
}
```

##### 4. エージェントステータス更新

```json
{
  "type": "agent_status",
  "data": {
    "agent_id": "orchestrator",
    "state": "thinking",
    "current_task": "タスク計画を作成中...",
    "progress": 45
  }
}
```

##### 5. エラー通知

```json
{
  "type": "error",
  "data": {
    "error_type": "execution_error",
    "message": "エラーメッセージ",
    "context": {}
  }
}
```

---

## セキュリティ設計

### Python コード埋め込み戦略

```
ビルド時 (build.rs)
  ↓
Python ファイル収集 → XOR 難読化 → Rust コード生成
  ↓
Cargo がバイナリにコンパイル → .exe に埋め込み
  ↓
実行時 (main.rs)
  ↓
埋め込みコード復号 → メモリ上で実行 → ディスク に書き込まない
```

### XOR 難読化

**鍵**: 32バイトの固定シーケンス (build.rs で定義)

```rust
pub const OBFUSCATION_KEY: [u8; 32] = [
    0x44, 0x2D, 0x43, 0x4F, 0x44, 0x45, 0x2D, 0x53, 
    0x45, 0x43, 0x52, 0x45, 0x54, 0x2D, 0x4B, 0x45,
    0x59, 0x2D, 0x32, 0x30, 0x32, 0x35, 0x2D, 0x56,
    0x31, 0x2E, 0x30, 0x2E, 0x30, 0x21, 0x21, 0x21,
];

fn obfuscate(data: &[u8], key: &[u8]) -> Vec<u8> {
    data.iter()
        .enumerate()
        .map(|(i, byte)| byte ^ key[i % key.len()])
        .collect()
}
```

### メモリ保護

- **in-memory 実行**: Python コードはメモリ上でのみ保持
- **明示的なクリア**: `security::clear_memory()` で機密データを上書き
- **デバッガ検出**: 開発ビルドでのみ有効 (リリースビルドで無効化可能)

### リリースビルド最適化

```toml
[profile.release]
strip = true          # デバッグシンボル削除
lto = true            # リンク時最適化
codegen-units = 1     # 最適化レベル最大
opt-level = "z"       # サイズ最小化
```

---

## コスト最適化

### モデル選択戦略

| エージェント | モデル | 用途 | 予想コスト |
|------------|--------|------|----------|
| **Orchestrator** | Gemini 2.5 Flash | 複雑な推論、会話管理 | $0.075 / M in, $0.30 / M out |
| **Planner** | Gemini 2.5 Flash | タスク分解、計画生成 | $0.075 / M in, $0.30 / M out |
| **Engineers (×10)** | Gemini 2.0 Flash | コード実装、実行 | $0.075 / M in, $0.30 / M out |
| **Streamer** | Gemini 2.5 Flash | ログ要約、UI 更新 | $0.075 / M in, $0.30 / M out |

### 使用料削減テクニック

1. **Prompt Caching** (予定)
   - システムプロンプトのキャッシュ化
   - コンテキストの再利用

2. **バッチ処理**
   - 複数ワーカーの結果を1つのリクエストで送信

3. **トークン数制限**
   - 応答の最大トークン数を制限
   - 必要なパート のみ生成

4. **キャッシング戦略**
   - 計画済みタスクの結果をキャッシュ
   - 同一要件の再実行を回避

---

## 開発ガイドライン

### コーディング規約

#### Rust
- **フォーマッタ**: `cargo fmt` 推奨 (LLVM スタイル)
- **リント**: `cargo clippy` でワーニング排除
- **エラー処理**: `Result<T, E>` 必須 (`unwrap()` 禁止、テスト時除く)
- **ドキュメント**: `///` で関数・構造体にドキュメンテーション記述

```rust
/// PowerShell プロセスを起動
/// 
/// # Arguments
/// * `id` - ターミナル ID
/// 
/// # Returns
/// `Ok(Terminal)` またはエラーメッセージ
pub fn new(id: String) -> Result<Self, String> {
    // ...
}
```

#### Python
- **フォーマッタ**: `black` (88文字折返し)
- **リント**: `ruff` でコード品質確認
- **型チェック**: `mypy` で型チェック実行
- **バリデーション**: `pydantic` で入出力検証

```python
from pydantic import BaseModel

class TaskPlan(BaseModel):
    """タスク計画"""
    project_name: str
    tasks: List[Task]
```

#### TypeScript/React
- **フォーマッタ**: `prettier` (使用)
- **リント**: `eslint` + React plugin
- **型**: `noImplicitAny = true` 厳密モード
- **スタイル**: Tailwind CSS で統一

```typescript
interface Message {
  id: string;
  timestamp: string;
  content: string;
  agent: AgentRole;
}
```

### テスト戦略

#### ユニットテスト
```bash
# Rust
cargo test

# Python
pytest

# React (予定)
npm run test
```

#### 統合テスト

1. **エージェント通信テスト**
   - Orchestrator → Planner への通信
   - Workers の並列実行

2. **WebSocket テスト**
   - UI ↔ Engine 間のメッセージ送受信
   - ストリーミングフロー

3. **ターミナルテスト**
   - PowerShell 起動・コマンド実行
   - 出力キャプチャ

#### 本番テスト

- ビルド: `cargo build --release`
- 実行: `./target/release/d_code.exe`
- ログ確認: `./logs/dcode_*.log`

### デバッグ方法

#### Rust

```bash
# デバッグビルド
cargo build

# ログ出力有効化
RUST_LOG=debug cargo run

# Backtrack 出力
RUST_BACKTRACE=1 cargo run
```

#### Python

```python
# 標準ロギング
import logging
logging.basicConfig(level=logging.DEBUG)

# Pytest デバッグ
pytest -vv --pdb -s
```

#### 環境変数

```bash
# デバッグモード有効
set DCODE_DEBUG=true

# ログレベル変更
set DCODE_LOG_LEVEL=debug

# API ベースURL 変更 (LM Studio など)
set DCODE_API_BASE_URL=http://localhost:8000/v1

# API バックエンド切り替え
set DCODE_API_BACKEND=openai
```

### リリースプロセス

1. **バージョン更新**
   ```toml
   [package]
   version = "0.2.0"
   ```

2. **ビルド**
   ```bash
   cargo build --release
   ```

3. **署名** (Windows)
   ```bash
   signtool sign /f cert.pfx /p password /t http://timestamp.server /v target/release/d_code.exe
   ```

4. **配布**
   - GitHub Releases にアップロード
   - インストーラー生成 (NSIS)

---

## 依存関係管理

### Rust 依存関係の更新

```bash
# 最新バージョン確認
cargo outdated

# 安全に更新
cargo update --aggressive
```

### Python 依存関係の更新

```bash
# 必要なパッケージ確認
pip list --outdated

# 全依存関係更新
pip install --upgrade -r requirements.txt

# requirements.txt 再生成
pip freeze > requirements.txt
```

---

## トラブルシューティング

### よくある問題

| 問題 | 原因 | 解決方法 |
|------|------|--------|
| PyO3 コンパイルエラー | Python パスが見つからない | `python --version` で確認、`PYO3_PYTHON` 環境変数設定 |
| WebView が起動しない | Webview2 Runtime 未インストール | [Edge WebView2](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) からインストール |
| API キー エラー | `GEMINI_API_KEY` 未設定 | `.env` ファイルに API キー記入 |
| ターミナル出力がない | PowerShell パス不正 | `which powershell` で確認 |
| TypeScript エラー | Node バージョン不正 | `node --version` で 18+ 確認 |

---

## 参考資料

### 公式ドキュメント
- [Rust Book](https://doc.rust-lang.org/book/)
- [PyO3 Docs](https://pyo3.rs/)
- [React Docs](https://react.dev/)
- [Google Generative AI Docs](https://ai.google.dev/)

### プロジェクトドキュメント
- [DEVELOPMENT.md](docs/DEVELOPMENT.md) - 開発ガイド
- [README.md](README.md) - プロジェクト概要
- [.env.example](.env.example) - 環境変数テンプレート

---

**最終更新**: 2026年1月23日  
**作成者**: Development Team  
**ステータス**: 開発中 (Phase 1-2 実装予定)
