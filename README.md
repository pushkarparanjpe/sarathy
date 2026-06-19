# 🚀 Sarathy - Unofficial Sarvam AI Agentic Coding Assistant CLI

`Sarathy` is a command-line agentic AI assistant designed to help developers directly in their terminal. It provides a polished, interactive Claude Code-like experience, allowing users to ask coding questions, write files, edit code block-by-block, and run commands.

Developed with **Sarvam AI** in mind, Sarathy utilizes agentic tool-calling to research, modify, test, and repair your codebase autonomously, all under your control.

---

## ✨ Key Features

- **💻 Claude Code-like TUI**: Polished layout using `rich` for styled console output, markdown rendering, and live thinking spinners, with `prompt_toolkit` providing persistent history and auto-suggestions.
- **🔄 Agentic Loop with Tool Execution**: Natively supports file inspection, modification, and execution tools, feeding tool outputs back into the LLM dynamically.
- **🛡️ Safety-First Confirmation**: Prompts for user approval before executing destructive or modifying actions (`run_command`, `write_file`, `replace_content`).
- **⚙️ Auto-Approve Mode**: Speed up operations with the `--yes` or `-y` flag to bypass safety prompts in trusted environments.
- **🔑 Bring Your Own Key (BYOK)**: Interactively prompts for and saves your API key locally in `~/.config/sarathy/config.json` if it's not found in the environment.
- **⚡ Built-in Shell Execution**: Execute shell commands directly from the prompt by prefixing them with `!` (e.g., `!pytest`).

---

## 🛠️ Tech Stack & Prerequisites

Sarathy is written in Python and is highly optimized using modern packaging tools:
- **Python**: `>=3.9`
- **uv**: Modern, lightning-fast Python package manager (recommended).
- **openai**: OpenAI-compatible client library for interacting with the LLM API.
- **rich**: Modern terminal styling, markdown rendering, and dynamic spinners.
- **prompt-toolkit**: Advanced terminal command-line prompt handling with syntax suggestions.

---

## 🚀 Getting Started

### 1. Installation
Clone the repository and install it in editable mode using `uv`:

```bash
# Clone the repository (if not already local)
git clone https://github.com/your-username/sarathy.git
cd sarathy

# Install project dependencies
uv pip install -e .
```

### 2. Run the Assistant
Launch the interactive coding assistant:

```bash
uv run sarathy
```

To run Sarathy and automatically approve all tool executions (e.g., file writes and shell commands) without being prompted:

```bash
uv run sarathy --yes
```

---

## ⚙️ Configuration

Sarathy resolves configuration values in the following order of priority:

1. **CLI Flag Overrides** (e.g. `--model`, `--api-key`, `--api-base`)
2. **Environment Variables** (loaded from the environment or a `.env` file in the current directory)
3. **Local JSON Config File** (`~/.config/sarathy/config.json`)

### Configuration Options

| Option / Variable | Description | Default Value |
| :--- | :--- | :--- |
| `SARVAM_API_KEY` | Your Sarvam AI API Key (Required) | *Prompted on start if missing* |
| `SARVAM_API_BASE` | Base API endpoint URL | `https://api.sarvam.ai/v1` |
| `SARVAM_MODEL` | The LLM model used for agentic reasoning | `sarvam-105b` |

### Setting up `.env`

You can copy the example configuration file and fill in your details:

```bash
cp .env.example .env
```

Open `.env` and add your API key:
```env
SARVAM_API_KEY=your-sarvam-api-key-here
```

---

## 💬 Usage & Interaction

When you launch Sarathy, you will see a prompt like `sarathy (your-workspace) > `. You can:
1. **Talk to Sarathy**: Ask questions, describe changes, or request bug fixes.
2. **Execute Terminal Commands**: Prefix any input with `!` to run it in the shell directly (e.g., `!pytest`).
3. **Use Slash Commands**: Control the session state using the commands below.

### Command Guide

| Command | Description |
| :--- | :--- |
| `/help` | Display the commands and help menu |
| `/status` | View current workspace, active model, endpoint, API key status, and auto-approve mode |
| `/model <name>` | Switch the LLM model on-the-fly (e.g., `/model sarvam-2b`) |
| `/reset` | Reset the conversation history |
| `/clear` | Clear the terminal screen |
| `/exit` or `/quit` | Exit the application |

---

## 🧠 Under the Hood

### Agent Toolkit
Sarathy provides the LLM agent with a targeted suite of workspace tools defined in `sarathy/tools.py`:
- `list_dir(path)`: Lists directory contents, skipping common noise folders (like `.git`, `.venv`).
- `view_file(path, start_line, end_line)`: Reads line-numbered segments of a file.
- `grep_search(query, path)`: Recursively searches files for matches.
- `write_file(path, content)`: Creates or completely overwrites a file.
- `replace_content(path, target, replacement)`: Safely edits a specific code block inside a file to save tokens.
- `run_command(command)`: Executes shell commands (automatically isolated from hanging inputs).

### Project Structure
```
sarathy/
├── pyproject.toml         # Package and dependency configuration
├── .env.example           # Example environment configuration
├── main.py                # Direct execution entrypoint wrapper
├── sarathy/
│   ├── __init__.py        # Version and package metadata
│   ├── cli.py             # CLI loops, status bars, and TUI layouts
│   ├── agent.py           # Multi-turn execution & reasoning agent loop
│   ├── config.py          # Configuration manager and local file builder
│   ├── llm.py             # Streaming response and tool call builder
│   ├── prompts.py         # System prompt and safety instructions
│   └── tools.py           # Python tool definitions and JSON schemas
└── tests/
    └── test_sarathy.py    # Suite of unit tests for configurations and tools
```

---

## 🧪 Development & Testing

Run unit tests using `pytest` to make sure everything works:

```bash
PYTHONPATH=. uv run pytest
```
