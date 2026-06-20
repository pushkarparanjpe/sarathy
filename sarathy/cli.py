import os
import sys
import argparse
import shutil
import threading
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Input, Static, Button
from textual import work

from sarathy.config import Config
from sarathy.agent import Agent
from sarathy.pricing import get_model_details, get_pricing_for_model

# Initialize Rich Console (used for pre-TUI prompts and messages)
console = Console()

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
        import getpass
        api_key = getpass.getpass("Enter your Sarvam AI API Key: ")
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


class TopToolbar(Static):
    """Top Toolbar widget displaying model, vendor, and token rates."""
    def update_info(self, vendor: str, model: str, in_rate: float, out_rate: float, ca_rate: float, sym: str):
        self.update(
            f"Vendor: [bold #c678dd]{vendor.upper()}[/bold #c678dd] │ "
            f"Model: [bold #e5c07b]{model}[/bold #e5c07b] │ "
            f"Pricing (per 1M): In: [bold #98c379]{sym}{in_rate:.1f}[/bold #98c379], Out: [bold #98c379]{sym}{out_rate:.1f}[/bold #98c379], Cached: [bold #98c379]{sym}{ca_rate:.1f}[/bold #98c379]"
        )


class BottomToolbar(Static):
    """Bottom Toolbar widget tracking token counts and command costs."""
    def update_info(self, last_cost: float, last_sym: str, last_tokens: int, session_cost: float, session_sym: str, session_tokens: int):
        self.update(
            f"Last Command: [bold #61afef]{last_sym}{last_cost:.2f}[/bold #61afef] ({last_tokens} t) │ "
            f"Session Total: [bold #61afef]{session_sym}{session_cost:.2f}[/bold #61afef] ({session_tokens} t)"
        )


class MessageWidget(Static):
    """Message widget showing chat dialogs for user/assistant/system roles."""
    def __init__(self, content: str = "", role: str = "system", **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.role = role
        self.add_class(f"{role}-message")
        self.add_class("message-box")
        
    def on_mount(self):
        self.update_content(self.content)
        
    def update_content(self, new_content: str):
        self.content = new_content
        if self.role == "assistant":
            self.update(Markdown(self.content))
        elif self.role == "user":
            self.update(f"[bold #61afef]You:[/bold #61afef]\n{self.content}")
        else:
            self.update(self.content)


class ToolConfirmWidget(Static):
    """Inline confirmation widget for dangerous tools with click action buttons."""
    def __init__(self, name: str, arguments: dict, app_ref, **kwargs):
        super().__init__(**kwargs)
        self.tool_name = name
        self.arguments = arguments
        self.app_ref = app_ref
        self.add_class("confirm-box")
        
    def compose(self) -> ComposeResult:
        if self.tool_name == "run_command":
            details = f"Command: [bold cyan]{self.arguments.get('command')}[/bold cyan]"
        elif self.tool_name == "write_file":
            path = self.arguments.get("path")
            content = self.arguments.get("content", "")
            content_preview = content[:200] + "..." if len(content) > 200 else content
            details = f"Path: [bold green]{path}[/bold green]\nContent Preview:\n[dim]{content_preview}[/dim]"
        elif self.tool_name == "replace_content":
            path = self.arguments.get("path")
            target = self.arguments.get("target", "")
            replacement = self.arguments.get("replacement", "")
            details = f"Path: [bold green]{path}[/bold green]\n[red]- Target to Replace:[/red]\n{target}\n[green]+ Replacement Content:[/green]\n{replacement}"
        else:
            details = str(self.arguments)
            
        yield Static(f"[bold yellow]↳ Tool Execution Request: {self.tool_name}[/bold yellow]\n{details}")
        
        with Horizontal(id="btn-container", classes="confirm-buttons"):
            yield Button("Approve (y)", id="btn-approve", variant="success")
            yield Button("Deny (n)", id="btn-deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        approved = event.button.id == "btn-approve"
        self.app_ref.confirm_result = approved
        self.app_ref.confirm_event.set()
        
        self.query_one("#btn-container").remove()
        status_str = "[bold green]✓ Approved[/bold green]" if approved else "[bold red]✗ Denied[/bold red]"
        self.mount(Static(status_str))


class SarathyApp(App):
    """Main Textual TUI Application for Sarathy Assistant."""
    
    CSS = """
    Screen {
        background: #1e1e24;
        color: #abb2bf;
    }
    
    TopToolbar {
        dock: top;
        height: 1;
        background: #2c2c2c;
        color: #abb2bf;
        content-align: center middle;
    }
    
    #chat-container {
        height: 1fr;
        padding: 1;
        scrollbar-size: 1 1;
        overflow-y: scroll;
    }
    
    .message-box {
        margin: 1 0;
        padding: 1;
        border: round #3e4452;
        background: #21252b;
    }
    
    .user-message {
        border: round #61afef;
        background: #282c34;
    }
    
    .assistant-message {
        border: round #c678dd;
        background: #21252b;
    }
    
    .system-message {
        border: round #e5c07b;
        background: #2c313c;
    }
    
    .error-message {
        border: round #e06c75;
        background: #2c313c;
        color: #e06c75;
    }
    
    .confirm-box {
        border: double #e06c75;
        background: #2c313c;
        padding: 1;
        margin: 1 0;
        height: auto;
    }
    
    .confirm-buttons {
        margin-top: 1;
        height: 3;
        align: left middle;
    }
    
    #input-container {
        dock: bottom;
        height: auto;
        background: #1e1e24;
    }
    
    Input {
        border: round #3e4452;
        background: #21252b;
        color: #abb2bf;
        margin: 0 1;
    }
    
    Input:focus {
        border: round #61afef;
    }
    
    BottomToolbar {
        dock: bottom;
        height: 1;
        background: #2c2c2c;
        color: #abb2bf;
        content-align: center middle;
    }
    """
    
    def __init__(self, config: Config, agent: Agent, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.agent = agent
        
        # Token usage tracking
        self.session_prompt_tokens = 0
        self.session_completion_tokens = 0
        self.session_total_tokens = 0
        self.session_cached_tokens = 0

        self.last_turn_prompt_tokens = 0
        self.last_turn_completion_tokens = 0
        self.last_turn_total_tokens = 0
        self.last_turn_cached_tokens = 0

        self.turn_prompt_tokens = 0
        self.turn_completion_tokens = 0
        self.turn_total_tokens = 0
        self.turn_cached_tokens = 0
        
        # Confirmation events
        self.confirm_event = threading.Event()
        self.confirm_result = False
        
        # Active assistant message widget reference
        self.active_assistant_widget = None
        self.active_assistant_content = ""
        
        # Thinking status widget
        self.thinking_widget = None

    def compose(self) -> ComposeResult:
        yield TopToolbar(id="top-toolbar")
        with VerticalScroll(id="chat-container"):
            yield Static(self.get_welcome_banner_text(), classes="message-box system-message")
        yield Input(placeholder="Type here, or /help for list of commands...")
        yield BottomToolbar(id="bottom-toolbar")

    def on_mount(self) -> None:
        self.update_top_toolbar()
        self.update_bottom_toolbar()
        self.query_one(Input).focus()

    def get_welcome_banner_text(self) -> str:
        """Returns startup banner text similar to print_welcome_banner."""
        return (
            "[bold magenta]"
            "███████╗ █████╗ ██████╗  █████╗ ████████╗██╗  ██╗██╗   ██╗\n"
            "██╔════╝██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██║  ██║╚██╗ ██╔╝\n"
            "███████╗███████║██████╔╝███████║   ██║   ███████║ ╚████╔╝ \n"
            "╚════██║██╔══██║██╔══██║██╔══██║   ██║   ██╔══██║  ╚██╔╝  \n"
            "███████║██║  ██║██║  ██║██║  ██║   ██║   ██║  ██║   ██║   \n"
            "╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   \n"
            "[/bold magenta]\n"
            f"  [bold]Sarathy[/bold] - Agentic AI Coding Assistant for Developers\n"
            f"  Workspace: [green]{os.getcwd()}[/green]\n"
            f"  Model:     [yellow]{self.config.model}[/yellow]\n"
            f"  Endpoint:  [blue]{self.config.api_base}[/blue]\n"
            f"  Auto-Approve: {'[red]Enabled[/red]' if self.config.auto_approve else '[green]Disabled (Prompting for modifications)[/green]'}\n\n"
            "  Type [bold cyan]/help[/bold cyan] for commands, [bold cyan]!<cmd>[/bold cyan] for direct shell execution, or [bold]/exit[/bold] to quit."
        )

    def update_top_toolbar(self) -> None:
        from sarathy.pricing import get_model_details
        vendor, in_rate, out_rate, ca_rate, sym = get_model_details(self.config.model)
        self.query_one(TopToolbar).update_info(vendor, self.config.model, in_rate, out_rate, ca_rate, sym)

    def calculate_cost(self, prompt: int, completion: int, cached: int):
        input_rate, output_rate, cached_rate, symbol = get_pricing_for_model(self.config.model)
        non_cached_prompt = max(0, prompt - cached)
        cost = (non_cached_prompt * input_rate + completion * output_rate + cached * cached_rate) / 1000000.0
        return cost, symbol

    def update_bottom_toolbar(self) -> None:
        last_cost, last_sym = self.calculate_cost(self.last_turn_prompt_tokens, self.last_turn_completion_tokens, self.last_turn_cached_tokens)
        session_cost, session_sym = self.calculate_cost(self.session_prompt_tokens, self.session_completion_tokens, self.session_cached_tokens)
        self.query_one(BottomToolbar).update_info(
            last_cost, last_sym, self.last_turn_total_tokens,
            session_cost, session_sym, self.session_total_tokens
        )

    @work(thread=True)
    def run_agent_turn(self, user_input: str) -> None:
        try:
            self.call_from_thread(self.update_thinking_state, True)
            
            # Start tracking this turn's tokens
            self.turn_prompt_tokens = 0
            self.turn_completion_tokens = 0
            self.turn_total_tokens = 0
            self.turn_cached_tokens = 0
            
            # Reset active assistant widget
            self.active_assistant_widget = None
            self.active_assistant_content = ""

            generator = self.agent.run_turn(user_input, self.confirm_tool_callback)
            
            for event, data in generator:
                if event == "thinking_start":
                    self.call_from_thread(self.update_thinking_state, True)
                elif event == "thinking_end":
                    self.call_from_thread(self.update_thinking_state, False)
                elif event == "text_chunk":
                    self.call_from_thread(self.append_text_chunk, data)
                elif event == "usage":
                    self.call_from_thread(self.update_usage, data)
                elif event == "tool_request":
                    self.call_from_thread(self.update_thinking_state, False)
                    name, args = data
                    self.call_from_thread(self.log_tool_request, name, args)
                elif event == "tool_executing":
                    self.call_from_thread(self.update_thinking_state, True, f"Executing {data}...")
                elif event == "tool_result":
                    self.call_from_thread(self.update_thinking_state, False)
                    name, result = data
                    self.call_from_thread(self.log_tool_result, name, result)
                elif event == "error":
                    self.call_from_thread(self.update_thinking_state, False)
                    self.call_from_thread(self.log_error, data)

            self.call_from_thread(self.update_thinking_state, False)
            
            # Save last command tokens
            if self.turn_total_tokens > 0:
                self.last_turn_prompt_tokens = self.turn_prompt_tokens
                self.last_turn_completion_tokens = self.turn_completion_tokens
                self.last_turn_total_tokens = self.turn_total_tokens
                self.last_turn_cached_tokens = self.turn_cached_tokens
                self.call_from_thread(self.update_bottom_toolbar)

        except Exception as e:
            self.call_from_thread(self.update_thinking_state, False)
            self.call_from_thread(self.log_error, f"Turn processing error: {e}")
        finally:
            self.call_from_thread(self.enable_input)

    def confirm_tool_callback(self, name: str, arguments: dict) -> bool:
        self.confirm_event.clear()
        self.confirm_result = False
        
        # Display the confirmation widget
        self.call_from_thread(self.display_confirm_widget, name, arguments)
        
        # Block worker thread
        self.confirm_event.wait()
        return self.confirm_result

    def update_thinking_state(self, show: bool, message: str = "Thinking...") -> None:
        container = self.query_one("#chat-container")
        if show:
            if not self.thinking_widget:
                self.thinking_widget = Static(f"[bold green]↳ {message}[/bold green]", classes="message-box system-message")
                container.mount(self.thinking_widget)
            else:
                self.thinking_widget.update(f"[bold green]↳ {message}[/bold green]")
            self.thinking_widget.scroll_visible()
        else:
            if self.thinking_widget:
                self.thinking_widget.remove()
                self.thinking_widget = None

    def append_text_chunk(self, chunk: str) -> None:
        container = self.query_one("#chat-container")
        if not self.active_assistant_widget:
            self.update_thinking_state(False)
            self.active_assistant_content = chunk
            self.active_assistant_widget = MessageWidget(self.active_assistant_content, role="assistant")
            container.mount(self.active_assistant_widget)
        else:
            self.active_assistant_content += chunk
            self.active_assistant_widget.update_content(self.active_assistant_content)
        
        self.active_assistant_widget.scroll_visible()

    def update_usage(self, usage: dict) -> None:
        p_toks = usage.get("prompt_tokens", 0)
        c_toks = usage.get("completion_tokens", 0)
        t_toks = usage.get("total_tokens", 0)
        ca_toks = usage.get("cached_tokens", 0)
        
        self.turn_prompt_tokens += p_toks
        self.turn_completion_tokens += c_toks
        self.turn_total_tokens += t_toks
        self.turn_cached_tokens += ca_toks
        
        self.session_prompt_tokens += p_toks
        self.session_completion_tokens += c_toks
        self.session_total_tokens += t_toks
        self.session_cached_tokens += ca_toks
        self.update_bottom_toolbar()

    def log_tool_request(self, name: str, args: dict) -> None:
        container = self.query_one("#chat-container")
        log_widget = Static(f"[bold yellow]↳ Requested Tool:[/bold yellow] {name}", classes="message-box system-message")
        container.mount(log_widget)
        log_widget.scroll_visible()

    def display_confirm_widget(self, name: str, arguments: dict) -> None:
        container = self.query_one("#chat-container")
        confirm_widget = ToolConfirmWidget(name, arguments, self)
        container.mount(confirm_widget)
        confirm_widget.scroll_visible()

    def log_tool_result(self, name: str, result: str) -> None:
        container = self.query_one("#chat-container")
        res_preview = result[:300] + "\n..." if len(result) > 300 else result
        log_widget = Static(f"[bold green]✓ Tool {name} finished.[/bold green]\n[dim]{res_preview}[/dim]", classes="message-box system-message")
        container.mount(log_widget)
        log_widget.scroll_visible()

    def log_error(self, message: str) -> None:
        container = self.query_one("#chat-container")
        err_widget = Static(f"[bold red]Error: {message}[/bold red]", classes="message-box error-message")
        container.mount(err_widget)
        err_widget.scroll_visible()

    def enable_input(self) -> None:
        inp = self.query_one(Input)
        inp.disabled = False
        inp.focus()

    def append_system_message(self, message: str) -> None:
        container = self.query_one("#chat-container")
        widget = Static(message, classes="message-box system-message")
        container.mount(widget)
        widget.scroll_visible()

    def append_error_message(self, message: str) -> None:
        container = self.query_one("#chat-container")
        widget = Static(message, classes="message-box error-message")
        container.mount(widget)
        widget.scroll_visible()

    def show_help(self) -> None:
        help_text = (
            "[bold magenta]Supported TUI Commands:[/bold magenta]\n\n"
            "  [bold cyan]/help[/bold cyan]          Show this help menu\n"
            "  [bold cyan]/clear[/bold cyan]         Clear the terminal screen history\n"
            "  [bold cyan]/reset[/bold cyan]         Reset the conversation history\n"
            "  [bold cyan]/model <name>[/bold cyan] Switch LLM model (e.g. /model sarvam-105b)\n"
            "  [bold cyan]/status[/bold cyan]        Display current configuration status\n"
            "  [bold cyan]/exit, /quit[/bold cyan]  Exit the assistant\n"
            "  [bold cyan]!<command>[/bold cyan]    Execute a shell command interactively (e.g., !pytest)"
        )
        self.append_system_message(help_text)

    def show_status(self) -> None:
        last_cost, last_sym = self.calculate_cost(self.last_turn_prompt_tokens, self.last_turn_completion_tokens, self.last_turn_cached_tokens)
        session_cost, session_sym = self.calculate_cost(self.session_prompt_tokens, self.session_completion_tokens, self.session_cached_tokens)
        
        status_text = (
            "[bold magenta]Configuration Status:[/bold magenta]\n\n"
            f"  Workspace: [green]{os.getcwd()}[/green]\n"
            f"  Active Model: [yellow]{self.config.model}[/yellow]\n"
            f"  Endpoint: [blue]{self.config.api_base}[/blue]\n"
            f"  API Key Set: {'[green]Yes[/green]' if self.config.api_key else '[red]No[/red]'} (ends in ...{self.config.api_key[-4:] if len(self.config.api_key) > 4 else ''})\n"
            f"  Auto-Approve: {'[red]Enabled[/red]' if self.config.auto_approve else '[green]Disabled[/green]'} (-y flag to enable)\n"
            f"  Last Command Usage: [cyan]{last_sym}{last_cost:.2f}[/cyan] ({self.last_turn_total_tokens} tokens)\n"
            f"  Session Usage: [cyan]{session_sym}{session_cost:.2f}[/cyan] ({self.session_total_tokens} tokens)"
        )
        self.append_system_message(status_text)

    def execute_shell_command(self, cmd: str) -> None:
        with self.suspend():
            print(f"\nExecuting direct shell command: {cmd}\n")
            try:
                exit_code = os.system(cmd)
                if exit_code != 0:
                    print(f"\n[red]Command exited with non-zero code: {exit_code}[/red]")
            except Exception as e:
                print(f"\n[red]Error running command: {e}[/red]")
            print("\nPress Enter to return to Sarathy...")
            input()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        if not user_input:
            return
        
        # Clear input field
        self.query_one(Input).value = ""
        
        # Handle slash commands
        if user_input.startswith("/"):
            parts = user_input.split()
            cmd = parts[0]
            if cmd in {"/exit", "/quit"}:
                self.exit()
                return
            elif cmd == "/clear":
                self.query_one("#chat-container").remove_children()
                self.query_one("#chat-container").mount(Static(self.get_welcome_banner_text(), classes="message-box system-message"))
                return
            elif cmd == "/help":
                self.show_help()
                return
            elif cmd == "/reset":
                self.agent.reset_history()
                self.append_system_message("Conversation history has been reset.")
                return
            elif cmd == "/model":
                if len(parts) < 2:
                    self.append_system_message(f"Current model is {self.config.model}. Usage: /model <model_name>")
                else:
                    self.config.model = parts[1]
                    self.config.save()
                    self.agent.update_config(self.config)
                    self.append_system_message(f"Switched model to: {self.config.model}")
                    self.update_top_toolbar()
                return
            elif cmd == "/status":
                self.show_status()
                return
            else:
                self.append_error_message(f"Unknown command: {cmd}. Type /help for list of commands.")
                return

        # Handle direct shell execution
        if user_input.startswith("!"):
            cmd_to_run = user_input[1:].strip()
            if cmd_to_run:
                self.execute_shell_command(cmd_to_run)
            return

        # Regular turn
        # 1. Append user message widget
        container = self.query_one("#chat-container")
        user_widget = MessageWidget(user_input, role="user")
        container.mount(user_widget)
        user_widget.scroll_visible()
        
        # 2. Disable input and run worker
        self.query_one(Input).disabled = True
        self.run_agent_turn(user_input)


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

    # Start Textual App TUI
    app = SarathyApp(config=config, agent=agent)
    app.run()


if __name__ == "__main__":
    main()
