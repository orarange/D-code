

# D-code システム実装仕様書 (Draft v1.0)

## 1. プロジェクト概要

**D-code** は、人間と複数のAIエージェントがリアルタイムに協調してソフトウェアを開発するための、マルチエージェント・オーケストレーション・プラットフォームである。

### 核心コンセプト

* **ピラミッド型AI運用:** 高機能な指揮官と、安価で高速な多数の実作業員を組み合わせ、低コストで開発を行う。LM Studio等のローカルLLMサーバーにも対応。
* **ライブ・ストリーミング:** AI同士の思考・議論プロセスをDiscord風UIで実況し、人間が「走りながら」指示を出せる。
* **堅牢な配布形態:** Rustで外装を構築し、Pythonロジックをバイナリ埋め込みすることで、デコンパイル対策を施した単一実行ファイル (.exe) として提供する。

---

## 2. 技術スタック (Technical Stack)

### 2.1. コア・アーキテクチャ

* **Main Wrapper (Rust):**
  * 役割: 実行ファイル本体、Pythonインタープリタの埋め込み、UI（WebView）のホスト。
  * ライブラリ:
    - `pyo3` v0.23 - Rust/Python連携
    - `tao` v0.33 - クロスプラットフォームウィンドウ管理
    - `wry` v0.49 - WebView (devtools対応)
    - `serde` / `serde_json` - シリアライゼーション
    - `tokio` - 非同期ランタイム
    - `rust-embed` / `mime_guess` - 静的ファイル埋め込み
    - `dotenvy` - .envファイル読み込み
    - `aes-gcm` / `rand` / `base64` - セキュリティ（暗号化）
    - `dirs` - プラットフォームディレクトリ
    - `regex` - AI応答のパース

* **AI Engine (Python 3.13+):**
  * 役割: AIエージェントの思考、API通信、ファイル操作。
  * ライブラリ:
    - `google-genai` >= 1.0.0 - Gemini API
    - `openai` >= 1.0.0 - OpenAI互換API (LM Studio等)
    - `langgraph` >= 0.2.0 - 状態管理
    - `langchain` >= 0.3.0 - LLMフレームワーク
    - `pydantic` >= 2.0.0 - データバリデーション
    - `fastapi` / `uvicorn` / `websockets` - WebSocket通信
    - `watchdog` - ファイル監視

* **Frontend (React 18 + TypeScript):**
  * 役割: Discord風3カラムUI。
  * ライブラリ:
    - `React` v18.3.1 - UIフレームワーク
    - `Tailwind CSS` v3.4.16 - スタイリング
    - `Zustand` v5.0.0 - 状態管理
    - `Lucide React` v0.468.0 - アイコン
    - `Monaco Editor` v4.6.0 - コードエディタ
    - `Vite` v6.0.3 - ビルドツール
    - `clsx` - クラス名ユーティリティ

### 2.2. AI モデル構成

現在は以下の構成でローカルLLMに対応：

1. **Chat Agent (設定可能):** LM Studio等のOpenAI互換APIを使用。モデルは`.env`で設定可能。
2. **Orchestrator:** 全体の監督。人間の「割り込み」を解釈し、タスクの中断や変更を判断。
3. **Planner:** 要件定義書から `tasks.json` を生成。
4. **Worker:** 実際のコード記述、テスト作成、デバッグ。
5. **Streamer:** ログを人間が読みやすい実況テキストに変換し、UIへ送信。

### 2.3. 環境設定 (.env)

```env
# API設定
DCODE_API_BASE_URL=http://127.0.0.1:1234    # LM Studioの場合
DCODE_API_BACKEND=openai                     # openai または gemini
DCODE_CHAT_MODEL=google/gemma-3-12b         # 使用するモデル
GEMINI_API_KEY=your-api-key                 # Gemini API使用時のみ必要
```

---

## 3. UI 構成 (UI Layout Specification)

画面を3つの垂直カラムで構成する。

1. **左カラム: Project Explorer & Task List**
   * 生成されたファイルのツリー表示。
   * `tasks.json` に基づくタスク進捗状況（プログレスバー表示）。

2. **中央カラム: Live Code Editor**
   * Monaco Editorによるコード表示。
   * 現在AIが編集しているファイルをリアルタイム表示。
   * 差分（Diff）表示モードを搭載予定。

3. **右カラム: AI Discussion Stream (Discord-like)**
   * 各エージェントのアイコン付きチャットログ。
   * AI同士の相談、エラー報告、進捗報告が流れる。
   * **Chat Input:** 下部に配置。走行中のAIチームへ直接指示を出す。

4. **下部ユニット: Terminal**
   * AIが実行したコマンドの出力を表示。
   * `bash::run` 形式でAIがコマンドを出力すると自動実行される。



---

## 4. 主要ワークフロー (Key Workflows)

### 4.1. ライブ指示と割り込み

* **通常時:** AIは `tasks.json` に基づき自動で作業を進める。
* **指示介入:** 人間がチャットで指示を送ると、Orchestratorが現在のタスクに割り込ませるか、次タスクにするかを即座に判断し反映する。
* **緊急停止:** [Break] ボタン押下で `LangGraph` のステートを中断し、AIを待機状態にする。

### 4.2. 自律エラー復旧 (Self-Healing)

1. コマンド実行でエラーが発生した場合、Engineerエージェントがログを解析し、修正案を作成・実行する。
2. **ループ検知:** 同一エラーが3回連続で発生した場合、自動修正を停止。
3. **エスカレーション:** 右カラムに警告（赤色表示）を出し、人間に「原因の推測」と「解決のヒント」を求めて待機する。

---

## 5. セキュリティ & デコンパイル対策 (Security)

1. **ソース埋め込み:** Pythonコード（`.py`）は、ビルド時に `build.rs` でバイナリデータとして埋め込む。
2. **インメモリ実行:** 実行時、ディスクにファイルを書き出さず、RustからPyO3経由でPythonインタープリタへ直接コードを渡す。
3. **暗号化対応:** `aes-gcm` による暗号化機能を実装済み（オプション）。

---

## 6. 現在の実装状況

### 実装済み機能
- ✅ Rust + PyO3によるPython埋め込み
- ✅ wry WebViewによるUI表示
- ✅ Discord風3カラムUI（React + Tailwind）
- ✅ LM Studio (OpenAI互換API) サポート
- ✅ Gemini API サポート
- ✅ ファイル作成機能（`言語::パス` 形式）
- ✅ ターミナルコマンド実行（`bash::run` 形式）
- ✅ ファイルエクスプローラー
- ✅ Monaco Editorによるコード表示
- ✅ .env による環境設定

### 未実装・開発中
- 🔄 マルチエージェント並列実行
- 🔄 LangGraphによる状態管理
- 🔄 Break（一時停止）機能
- 🔄 タスク進捗表示
- 🔄 差分（Diff）表示

---

## 7. Copilot への実装指示

* **Rust層:** `src/main.rs`, `src/bridge.rs` ではPythonのライフサイクル管理とIPC通信に集中せよ。
* **Python層:** `engine/` 配下では各エージェントを独立したモジュールとして定義せよ。
* **UI層:** `ui/` では、`dcode://` プロトコルを通じてRustから送られてくるイベントをリアクティブに表示せよ。
* **禁止事項:** 開発対象の具体的なアプリ名をハードコードしてはならない。D-codeはあくまで汎用的な開発ツールとして構築せよ。

