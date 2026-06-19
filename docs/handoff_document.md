# Handoff Document: Sarathy Coding Assistant

Welcome to the handoff document for **Sarathy**, a command-line agentic AI assistant designed to help developers directly in their terminal.

---

## 1. Project Overview
**Sarathy** is an interactive, developer-focused CLI assistant. It provides a Claude Code-like terminal experience, allowing users to ask coding questions, write files, edit code block-by-block, and run commands. 

### Key Features
- **BYOK (Bring Your Own Key)**: Prompts for and stores the API key locally in `~/.config/sarathy/config.json` if not found in environment variables.
- **Sarvam AI Defaulting**: Tailored for the `sarvam-105b` model and OpenAI-compatible endpoints by default.
- **Claude Code-like TUI**: Polished layout using `rich` for styled console output and live spinners, and `prompt_toolkit` for interactive CLI features (history, auto-suggestions, custom prompt layout).
- **Agentic Loop with Tool Execution**: Natively supports file tools (`view_file`, `write_file`, `replace_content`, `list_dir`, `grep_search`) and execution tools (`run_command`).
- **Confirmation Safety Prompts**: Prompts the user before executing destructive or modifying actions (`write_file`, `replace_content`, `run_command`).

---

## 2. Directory Structure and Components

The codebase is organized in a modular structure:

```
sarathy/
├── pyproject.toml         # Package configurations and dependencies
├── .env.example           # Example local env variables
├── main.py                # Wrapper script pointing to the main CLI entrypoint
├── sarathy/
│   ├── __init__.py        # Version and packaging marker
│   ├── config.py          # Configuration parser, loader, and BYOK file writer
│   ├── llm.py             # Stream completions parser & tool-call aggregator
│   ├── tools.py           # Tool implementations & OpenAI function schemas
│   ├── prompts.py         # System prompt and safety instructions
│   ├── agent.py           # Multi-step conversational tool execution loop
│   └── cli.py             # Main interactive TUI loop and terminal layout
└── tests/
    └── test_sarathy.py    # Unit tests for tools and configuration
```

### Module Descriptions
- **[config.py](file:///Users/pushkar/Documents/sarathy/sarathy/config.py)**: Loads variables from `.env` and `~/.config/sarathy/config.json`. Performs API key presence validation.
- **[llm.py](file:///Users/pushkar/Documents/sarathy/sarathy/llm.py)**: Implements streaming completion logic, correctly handling and assembling fragmented tool-call chunks returned from the OpenAI-compatible endpoint.
- **[tools.py](file:///Users/pushkar/Documents/sarathy/sarathy/tools.py)**: Defines python functions for the developer tools and outputs their standard JSON function schemas. Replaces files safely with `replace_content` to prevent massive token writes.
- **[agent.py](file:///Users/pushkar/Documents/sarathy/sarathy/agent.py)**: Holds conversation state history and handles multi-turn agent execution where it feeds tool outputs back into the LLM.
- **[cli.py](file:///Users/pushkar/Documents/sarathy/sarathy/cli.py)**: Configures the terminal environment, welcomes the user, handles slash command syntax, executes shell commands inline when inputs start with `!`, and displays the status spinners and confirmation prompts.

---

## 3. Technology Stack & Dependencies

The project uses the modern Python packaging tool `uv` for speed and consistency:
- **Python**: `>=3.9`
- **openai**: Client library for interacting with OpenAI-compatible APIs.
- **rich**: Modern terminal color formatting, markdown printing, tables, and spinners.
- **prompt-toolkit**: Advanced terminal command-line prompt handling.
- **python-dotenv**: Local environment variables management.
- **pytest**: Test runner.

---

## 4. Run and Setup Instructions

### Environment Activation
To setup and install the virtual environment locally:
```bash
uv pip install -e .
```

### Running the App
To start the interactive shell:
```bash
uv run sarathy
```
Or to run with auto-approve enabled (skipping tool confirmation prompts):
```bash
uv run sarathy --yes
```

---

## 5. Verification Status

### Unit Tests
The core functionalities have been verified with unit tests. You can run them using:
```bash
PYTHONPATH=. uv run pytest
```
*Status: All tests passed.*

### Manual Checks
1. **Config Prompting**: Verified that deleting the configuration file triggers the setup prompt on next startup.
2. **Slash Commands**: Verified `/help`, `/status`, `/reset`, and `/exit` commands function correctly.
3. **Execution shortcuts**: Verified `!pwd` runs in the foreground shell directly.
4. **Agent flow**: Verified that asking the agent to modify code issues a permission check first, edits the file upon approval, and feeds the result back to the model.

---

## 6. Next Steps & Extension Ideas
- **Autocompletion**: Build custom completion classes in `prompt_toolkit` to autocomplete files in the current folder when typing paths.
- **Token Tracking**: Track model token usage (input/output) to show approximate cost/consumption statistics in `/status`.
- **System context**: Add file caching so the agent can reference files in its memory without calling `view_file` repeatedly.
