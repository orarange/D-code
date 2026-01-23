# D-code 🎭

**AI-Powered Multi-Agent Development Platform**

D-code is a sophisticated development platform that leverages multiple AI agents to assist with coding tasks. Built with security and efficiency in mind, it uses a unique architecture that embeds Python AI engines within a secure Rust wrapper.

![D-code Screenshot](docs/screenshot.png)

## Features

### 🤖 Multi-Agent AI System
- **Orchestrator**: Manages conversation flow and coordinates agents
- **Planner**: Breaks complex tasks into parallelizable subtasks
- **Engineers**: Execute coding tasks in parallel (up to 10 concurrent workers)
- **Streamer**: Formats output in Discord-style for the UI

### 🔒 Security-First Design
- Python code embedded in binary at compile time
- XOR obfuscation prevents reverse engineering
- In-memory execution without filesystem exposure
- Anti-debugging measures

### 💰 Cost-Optimized AI
- Uses Gemini 2.5 Flash for complex reasoning tasks
- Uses Gemini 2.0 Flash for bulk worker operations
- Parallel execution maximizes throughput

### 🎨 Modern UI
- Discord-inspired dark theme
- Real-time streaming updates
- Monaco Editor for code display
- Task progress visualization

## Quick Start

### Prerequisites

- Rust 1.75+
- Python 3.10+
- Node.js 20+
- Gemini API Key

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/d-code.git
cd d-code

# Setup environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Install Python dependencies
pip install -r requirements.txt

# Install UI dependencies
cd ui && npm install && cd ..

# Build and run
cargo run
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        D-code UI                            │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ File     │  │ Monaco       │  │ Discord-style Chat     │ │
│  │ Explorer │  │ Editor       │  │ Stream                 │ │
│  │          │  │              │  │                        │ │
│  │ Task     │  │              │  │                        │ │
│  │ List     │  │              │  │                        │ │
│  └──────────┘  └──────────────┘  └────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ Chat Input | Emergency Stop | Terminal                   ││
│  └──────────────────────────────────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────┘
                          │ WebSocket
┌─────────────────────────┴───────────────────────────────────┐
│                    Rust Wrapper (Tauri)                      │
│  ┌─────────┐  ┌──────────┐  ┌───────────────────────────────┐│
│  │ Bridge  │  │ Security │  │ Embedded Python Modules       ││
│  │ (WS)    │  │ (Memory) │  │ (XOR Obfuscated)              ││
│  └─────────┘  └──────────┘  └───────────────────────────────┘│
└─────────────────────────┬───────────────────────────────────┘
                          │ PyO3
┌─────────────────────────┴───────────────────────────────────┐
│                    Python AI Engine                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  LangGraph StateGraph                   │ │
│  │  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌─────────┐  │ │
│  │  │Orchestrat│→│ Planner │→│ Engineers│→│ Streamer│   │ │
│  │  │    or    │  │         │  │  (Pool) │  │         │   │ │
│  │  └──────────┘  └─────────┘  └──────────┘  └─────────┘  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

- [Development Guide](docs/DEVELOPMENT.md)
- [API Reference](docs/API.md)
- [Architecture Deep Dive](docs/ARCHITECTURE.md)

## Tech Stack

### Backend
- **Rust**: Core wrapper and security layer
- **PyO3**: Rust-Python bridge
- **Tauri**: WebView and system integration
- **Tokio**: Async runtime

### AI Engine
- **LangGraph**: Agent orchestration framework
- **Google Gemini**: AI model API
- **Pydantic**: Data validation

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type-safe JavaScript
- **Tailwind CSS**: Utility-first styling
- **Monaco Editor**: Code editing
- **Zustand**: State management

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

---

Built with ❤️ using AI-powered development
