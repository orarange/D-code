# D-code Development Guide

## Prerequisites

- **Rust**: 1.75+ with `cargo`
- **Python**: 3.10+ with `pip`
- **Node.js**: 20+ with `npm`
- **Gemini API Key**: Get one from [Google AI Studio](https://aistudio.google.com/app/apikey)

## Project Structure

```
D-code/
├── Cargo.toml          # Rust dependencies
├── build.rs            # Python embedding build script
├── src/                # Rust source code
│   ├── main.rs         # Application entry point
│   ├── bridge.rs       # WebSocket bridge to UI
│   └── security.rs     # Memory protection utilities
├── engine/             # Python AI engine
│   ├── __init__.py     # Module exports
│   ├── main_agent.py   # Orchestrator and main engine
│   ├── planner.py      # Task planning agent
│   ├── worker.py       # Engineer worker pool
│   └── streamer.py     # UI communication agent
├── ui/                 # React frontend
│   ├── src/
│   │   ├── App.tsx     # Main application component
│   │   ├── store.ts    # Zustand state management
│   │   └── components/ # UI components
│   └── ...
├── workspace/          # User project workspace
└── docs/               # Documentation
```

## Setup Instructions

### 1. Clone and Configure

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your Gemini API key
```

### 2. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
cd ui && npm install && cd ..
```

### 3. Build and Run

```bash
# Development mode
cargo run

# Production build
cargo build --release
```

## Architecture Overview

### Security Model

D-code uses a unique security model where Python code is:
1. Embedded into the Rust binary at compile time
2. Obfuscated using XOR cipher
3. Executed in memory without touching the filesystem
4. Protected from debugger inspection

### Agent System

The AI engine uses a multi-agent architecture:

1. **Orchestrator**: Manages conversation flow and agent coordination
2. **Planner**: Breaks down tasks into parallelizable subtasks
3. **Engineers**: Execute coding tasks in parallel
4. **Streamer**: Formats and streams output to UI

### Cost Optimization

- **Orchestrator/Planner/Streamer**: Use Gemini 2.5 Flash for complex reasoning
- **Engineers**: Use Gemini 2.0 Flash for cost-effective bulk operations

### Communication Flow

```
User Input → WebSocket → Rust Bridge → Python Engine → LangGraph
                                                          ↓
UI ← WebSocket ← Rust Bridge ← Streamer ← Agent Outputs
```

## Development

### Running UI Separately

```bash
cd ui
npm run dev
```

### Running Tests

```bash
# Python tests
cd engine && pytest

# Rust tests
cargo test
```

### Code Style

- **Rust**: `rustfmt` and `clippy`
- **Python**: `black` and `ruff`
- **TypeScript**: Prettier and ESLint

## Troubleshooting

### WebSocket Connection Failed

Check that the Rust backend is running and the WebSocket port (default: 9001) is available.

### Gemini API Errors

1. Verify your API key in `.env`
2. Check your API quota at Google AI Studio
3. Ensure you're using the correct model names

### Build Errors

Make sure you have the required Python version and all dependencies installed:

```bash
python --version  # Should be 3.10+
pip list | grep -E "google-genai|langgraph|pydantic"
```
