import os
import sys
import argparse
import shutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style

from sarathy.config import Config
from sarathy.agent import Agent
from sarathy.pricing import get_pricing_for_model

# Initialize Rich Console
console = Console()

# Styles for prompt_toolkit
prompt_style = Style.from_dict({
    "prompt": "bold cyan",
    "workspace": "green",
    "bottom-toolbar": "bg:#2c2c2c fg:#abb2bf",
    "bottom-toolbar.value": "bold fg:#61afef",
})

def print_welcome_banner(config: Config):
    """Displays a beautiful startup banner similar to Claude Code."""
    banner_text = (
        "[bold magenta]███████╗ █████╗ ██████╗  █████╗ ████████╗██╗  ██╗██╗   ██╗[/bold magenta]\n"
        "[bold magenta]██╔════╝██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██║  ██║╚██╗ ██╔╝[/bold magenta]\n"
        "[bold magenta]███████╗███████║██████╔╝███████║   ██║   ███████║ ╚████╔╝ [/bold magenta]\n"
        "[bold magenta]╚════██║██╔══██║██╔══██╗██╔══██║   ██║   ██╔══██║  ╚██╔╝  [/bold magenta]\n"
        "[bold magenta]███████║██║  ██║██║  ██║██║  ██║   ██║   ██║  ██║   ██║   [/bold magenta]\n"
        "[bold magenta]╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   [/bold magenta]\n\n"
        f"  [bold]Sarathy[/bold] - Agentic AI Coding Assistant for Developers\n"
        f"  Workspace: [green]{os.getcwd()}[/green]\n"
        f"  Model:     [yellow]{config.model}[/yellow]\n"
        f"  Endpoint:  [blue]{config.api_base}[/blue]\n"
        f"  Auto-Approve: {'[red]Enabled[/red]' if config.auto_approve else '[green]Disabled (Prompting for modifications)[/green]'}\n\n"
        "  Type [bold cyan]/help[/bold cyan] for commands, [bold cyan]!<cmd>[/bold cyan] for direct shell execution, or [bold]/exit[/bold] to quit."
    )
    console.print(Panel(banner_text, border_style="magenta", expand=False))

def print_help():
    """Prints the help menu with supported commands."""
    table = Table(title="Sarathy Commands", show_header=True, header_style="bold magenta")
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="white")
    
    table.add_row("/help", "Show this help menu")
    table.add_row("/clear", "Clear the terminal screen")
    table.add_row("/reset", "Reset the conversation history")
    table.add_row("/model <name>", "Switch the LLM model (e.g. /model sarvam-30b)")
    table.add_row("/status", "Display current configuration status")
    table.add_row("/exit, /quit", "Exit the assistant")
    table.add_row("!<command>", "Execute a shell command directly (e.g., !pytest)")
    
    console.print(table)

def prompt_for_api_key(config: Config):
    """Guides the user through setting up their API key if missing."""
    console.print(Panel(
        "[bold yellow]Sarvam AI API Key Required[/bold yellow]\n\n"
        "Sarathy needs an API key to communicate with Sarvam AI.\n"
        "You can generate an API key at [underline blue]https://dashboard.sarvam.ai/[/underline blue].\n\n"
        "Your key will be stored securely locally at `~/.config/sarathy/config.json`.",
        title="Setup Required",
        border_style="yellow"
    ))
    
    try:
        from prompt_toolkit import prompt
        api_key = prompt("Enter your Sarvam AI API Key: ", is_password=True)
        api_key = api_key.strip()
        if not api_key:
            console.print("[red]API Key cannot be empty. Exiting.[/red]")
            sys.exit(1)
        config.api_key = api_key
        if config.save():
            console.print("[green]API Key saved successfully to ~/.config/sarathy/config.json![/green]\n")
        else:
            console.print("[red]Warning: Could not save config file, key will only be active for this session.[/red]\n")
    except (KeyboardInterrupt, EOFError):
        console.print("\n[red]Setup cancelled. Exiting.[/red]")
        sys.exit(1)

def handle_tool_confirm(name: str, arguments: dict) -> bool:
    """Callback triggered before executing a dangerous tool."""
    # Print what the agent wants to do
    console.print()
    if name == "run_command":
        console.print(Panel(
            f"[bold yellow]Shell Command Execution Request[/bold yellow]\n"
            f"Command: [bold cyan]{arguments.get('command')}[/bold cyan]",
            border_style="yellow"
        ))
    elif name == "write_file":
        path = arguments.get("path")
        content = arguments.get("content", "")
        # Truncate content preview if long
        content_preview = content[:200] + "..." if len(content) > 200 else content
        console.print(Panel(
            f"[bold yellow]File Creation/Write Request[/bold yellow]\n"
            f"Path: [bold green]{path}[/bold green]\n\n"
            f"Content Preview:\n[dim]{content_preview}[/dim]",
            border_style="yellow"
        ))
    elif name == "replace_content":
        path = arguments.get("path")
        target = arguments.get("target", "")
        replacement = arguments.get("replacement", "")
        console.print(Panel(
            f"[bold yellow]File Modification Request[/bold yellow]\n"
            f"Path: [bold green]{path}[/bold green]\n\n"
            f"[bold red]- Target to Replace:[/bold red]\n{target}\n\n"
            f"[bold green]+ Replacement Content:[/bold green]\n{replacement}",
            border_style="yellow"
        ))
    
    # Confirm prompt
    try:
        ans = input("Approve this action? [y/N]: ").strip().lower()
        return ans in {"y", "yes"}
    except (KeyboardInterrupt, EOFError):
        console.print("\n[red]Action denied.[/red]")
        return False

def execute_direct_command(cmd: str):
    """Executes a command directly in the terminal from user input prefixed with !."""
    console.print(f"[bold dim]Executing: {cmd}[/bold dim]")
    try:
        subprocess_res = os.system(cmd)
        if subprocess_res != 0:
            console.print(f"[red]Command exited with non-zero code: {subprocess_res}[/red]")
    except Exception as e:
        console.print(f"[red]Error running command: {e}[/red]")

def main():
    parser = argparse.ArgumentParser(description="Sarathy - Agentic AI Coding Assistant")
    parser.add_argument("-y", "--yes", action="store_true", help="Auto-approve all actions without prompting")
    parser.add_argument("--model", type=str, help="Sarvam AI model to use")
    parser.add_argument("--api-key", type=str, help="API key override")
    parser.add_argument("--api-base", type=str, help="API base URL override")
    args = parser.parse_args()

    # Load Config
    config = Config(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
        auto_approve=args.yes
    )

    # Prompt for API key if missing
    if not config.is_valid():
        prompt_for_api_key(config)

    # Initialize Agent
    agent = Agent(config)

    # Session token usage tracking
    session_prompt_tokens = 0
    session_completion_tokens = 0
    session_total_tokens = 0
    session_cached_tokens = 0

    # Last turn token usage tracking
    last_turn_prompt_tokens = 0
    last_turn_completion_tokens = 0
    last_turn_total_tokens = 0
    last_turn_cached_tokens = 0

    # Welcome banner
    print_welcome_banner(config)

    # Set up prompt_toolkit session with persistent command history
    history_dir = Path.home() / ".config" / "sarathy"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "history"
    
    session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory()
    )

    def calculate_cost(prompt, completion, cached):
        input_rate, output_rate, cached_rate, symbol = get_pricing_for_model(config.model)
        non_cached_prompt = max(0, prompt - cached)
        cost = (non_cached_prompt * input_rate + completion * output_rate + cached * cached_rate) / 1000000.0
        return cost, symbol

    def get_toolbar():
        session_cost, session_sym = calculate_cost(session_prompt_tokens, session_completion_tokens, session_cached_tokens)
        last_cost, last_sym = calculate_cost(last_turn_prompt_tokens, last_turn_completion_tokens, last_turn_cached_tokens)
        return [
            ("class:bottom-toolbar", " Last Command: "),
            ("class:bottom-toolbar.value", f"{last_sym}{last_cost:.2f}"),
            ("class:bottom-toolbar", f" ({last_turn_total_tokens} t) | Session Total: "),
            ("class:bottom-toolbar.value", f"{session_sym}{session_cost:.2f}"),
            ("class:bottom-toolbar", f" ({session_total_tokens} t)"),
        ]

    # Main TUI Loop
    while True:
        try:
            # Format prompt string
            cwd_name = Path(os.getcwd()).name or "/"
            prompt_message = [
                ("class:prompt", "sarathy "),
                ("class:prompt", "("),
                ("class:workspace", cwd_name),
                ("class:prompt", ") > "),
            ]

            user_input = session.prompt(
                prompt_message,
                style=prompt_style,
                bottom_toolbar=get_toolbar
            )
            user_input = user_input.strip()

            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                parts = user_input.split()
                cmd = parts[0]
                if cmd in {"/exit", "/quit"}:
                    console.print("[bold magenta]Goodbye![/bold magenta]")
                    break
                elif cmd == "/clear":
                    console.print("\033[H\033[J", end="")
                    continue
                elif cmd == "/help":
                    print_help()
                    continue
                elif cmd == "/reset":
                    agent.reset_history()
                    console.print("[green]Conversation history has been reset.[/green]")
                    continue
                elif cmd == "/model":
                    if len(parts) < 2:
                        console.print(f"[yellow]Current model is {config.model}. Usage: /model <model_name>[/yellow]")
                    else:
                        config.model = parts[1]
                        config.save()
                        agent.update_config(config)
                        console.print(f"[green]Switched model to: {config.model}[/green]")
                    continue
                elif cmd == "/status":
                    last_cost, last_sym = calculate_cost(last_turn_prompt_tokens, last_turn_completion_tokens, last_turn_cached_tokens)
                    session_cost, session_sym = calculate_cost(session_prompt_tokens, session_completion_tokens, session_cached_tokens)
                    console.print(Panel(
                        f"Workspace: [green]{os.getcwd()}[/green]\n"
                        f"Active Model: [yellow]{config.model}[/yellow]\n"
                        f"Endpoint: [blue]{config.api_base}[/blue]\n"
                        f"API Key Set: {'[green]Yes[/green]' if config.api_key else '[red]No[/red]'} (ends in ...{config.api_key[-4:] if len(config.api_key) > 4 else ''})\n"
                        f"Auto-Approve: {'[red]Enabled[/red]' if config.auto_approve else '[green]Disabled[/green]'} (-y flag to enable)\n"
                        f"Last Command Usage: [cyan]{last_sym}{last_cost:.2f}[/cyan] ({last_turn_total_tokens} tokens)\n"
                        f"Session Usage: [cyan]{session_sym}{session_cost:.2f}[/cyan] ({session_total_tokens} tokens)",
                        title="Configuration Status",
                        border_style="magenta"
                    ))
                    continue
                else:
                    console.print(f"[red]Unknown command: {cmd}. Type /help for list of commands.[/red]")
                    continue

            # Handle direct shell execution
            if user_input.startswith("!"):
                cmd_to_run = user_input[1:].strip()
                if cmd_to_run:
                    execute_direct_command(cmd_to_run)
                continue

            # Run Agent Loop for regular prompts
            # Using rich live status spinner during reasoning / execution
            from rich.status import Status
            
            # Print a blank line before response
            console.print()
            
            # Turn token usage tracking
            turn_prompt_tokens = 0
            turn_completion_tokens = 0
            turn_total_tokens = 0
            turn_cached_tokens = 0
            
            with Status("[bold green]Thinking...", console=console, spinner="dots") as status:
                generator = agent.run_turn(user_input, handle_tool_confirm)
                
                # Stream the assistant outputs
                for event, data in generator:
                    if event == "thinking_start":
                        status.update("[bold green]Thinking...")
                        status.start()
                    elif event == "thinking_end":
                        status.stop()
                    elif event == "text_chunk":
                        # Print assistant token stream directly to console
                        console.print(data, end="")
                    elif event == "usage":
                        p_toks = data.get("prompt_tokens", 0)
                        c_toks = data.get("completion_tokens", 0)
                        t_toks = data.get("total_tokens", 0)
                        ca_toks = data.get("cached_tokens", 0)
                        
                        turn_prompt_tokens += p_toks
                        turn_completion_tokens += c_toks
                        turn_total_tokens += t_toks
                        turn_cached_tokens += ca_toks
                        
                        session_prompt_tokens += p_toks
                        session_completion_tokens += c_toks
                        session_total_tokens += t_toks
                        session_cached_tokens += ca_toks
                    elif event == "tool_request":
                        status.stop()
                        name, args = data
                        # We print status message before showing tool confirmation
                        if name == "run_command":
                            console.print(f"\n[bold yellow]↳ Agent requested command: {args.get('command')}[/bold yellow]")
                        else:
                            console.print(f"\n[bold yellow]↳ Agent requested tool: {name}[/bold yellow]")
                    elif event == "tool_executing":
                        status.update(f"[bold yellow]Executing {data}...")
                        status.start()
                    elif event == "tool_result":
                        status.stop()
                        name, result = data
                        # Print truncated tool result for cleaner CLI UI
                        res_preview = result[:300] + "\n..." if len(result) > 300 else result
                        console.print(f"[bold green]✓ Tool {name} finished.[/bold green]\n[dim]Output:\n{res_preview}[/dim]\n")
                    elif event == "error":
                        status.stop()
                        console.print(f"\n[bold red]Error: {data}[/bold red]\n")
            
            # Print an ending line
            console.print("\n")

            # Update last command usage tracking
            if turn_total_tokens > 0:
                last_turn_prompt_tokens = turn_prompt_tokens
                last_turn_completion_tokens = turn_completion_tokens
                last_turn_total_tokens = turn_total_tokens
                last_turn_cached_tokens = turn_cached_tokens

        except KeyboardInterrupt:
            # Control-C resets the line or exits clean if empty
            console.print("\n[yellow]KeyboardInterrupt. Use /exit or Ctrl-D to exit.[/yellow]")
        except EOFError:
            # Control-D exits the application
            console.print("\n[bold magenta]Goodbye![/bold magenta]")
            break
        except Exception as e:
            console.print(f"\n[bold red]System Error: {e}[/bold red]\n")

if __name__ == "__main__":
    main()
