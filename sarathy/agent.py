import json
from typing import List, Dict, Any, Generator, Tuple, Callable
from sarathy.config import Config
from sarathy.llm import LLMClient
from sarathy.tools import TOOL_SCHEMAS, DANGEROUS_TOOLS, execute_tool
from sarathy.prompts import SYSTEM_PROMPT

class Agent:
    def __init__(self, config: Config):
        self.config = config
        self.llm_client = LLMClient(
            api_key=config.api_key,
            api_base=config.api_base,
            model=config.model,
            reasoning_effort=config.reasoning_effort
        )
        self.history: List[Dict[str, Any]] = []
        self.reset_history()

    def reset_history(self):
        """Resets conversation history to only the system prompt."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def update_config(self, config: Config):
        """Update runner config (e.g. key, endpoint, model) dynamically."""
        self.config = config
        self.llm_client = LLMClient(
            api_key=config.api_key,
            api_base=config.api_base,
            model=config.model,
            reasoning_effort=config.reasoning_effort
        )

    def run_turn(
        self, 
        user_input: str,
        confirm_callback: Callable[[str, Dict[str, Any]], bool]
    ) -> Generator[Tuple[str, Any], None, None]:
        """
        Runs a single turn of conversation.
        Yields events to the UI:
        - ("text_chunk", str) - part of the assistant's text response
        - ("thinking_start", None) - agent is reasoning/thinking
        - ("thinking_end", None) - agent stopped reasoning
        - ("tool_request", (tool_name, args)) - tool call request before execution
        - ("tool_executing", tool_name) - tool execution started
        - ("tool_result", (tool_name, result)) - tool finished with result
        - ("error", str) - error message
        - ("usage", dict) - token usage dict
        """
        self.history.append({"role": "user", "content": user_input})
        
        while True:
            # We will start thinking/waiting for response
            yield "thinking_start", None
            
            content_chunks = []
            tool_calls = []
            error_occurred = None
            
            # Request response from LLM client
            stream = self.llm_client.chat_stream(self.history, TOOL_SCHEMAS)
            for event_type, data in stream:
                if event_type == "content":
                    if not content_chunks:
                        # Once we get actual content, we stop the thinking state
                        yield "thinking_end", None
                    yield "text_chunk", data
                    content_chunks.append(data)
                elif event_type == "tool_calls":
                    yield "thinking_end", None
                    tool_calls = data
                elif event_type == "error":
                    yield "thinking_end", None
                    error_occurred = data
                    yield "error", data
                elif event_type == "usage":
                    yield "usage", data

            if error_occurred:
                break

            # Combine content chunks into standard assistant reply content
            assistant_content = "".join(content_chunks) if content_chunks else None

            # 1. Update history with assistant's reply (containing text and/or tool calls)
            assistant_msg = {"role": "assistant"}
            if assistant_content:
                assistant_msg["content"] = assistant_content
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
                
            self.history.append(assistant_msg)

            # 2. If no tool calls were requested, this turn is complete
            if not tool_calls:
                break

            # 3. Process tool calls
            for tool_call in tool_calls:
                tc_id = tool_call.get("id")
                func = tool_call.get("function", {})
                name = func.get("name")
                args_str = func.get("arguments", "{}")
                
                try:
                    arguments = json.loads(args_str) if args_str else {}
                except Exception:
                    arguments = {"raw_arguments": args_str}

                yield "tool_request", (name, arguments)
                
                # Check for approval if dangerous
                approved = True
                if name in DANGEROUS_TOOLS and not self.config.auto_approve:
                    # Request confirmation from UI via the confirm_callback
                    approved = confirm_callback(name, arguments)

                if approved:
                    yield "tool_executing", name
                    result = execute_tool(name, arguments)
                else:
                    result = f"Error: Execution of tool '{name}' was denied by the user."
                
                yield "tool_result", (name, result)

                # Append tool result to history
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "name": name,
                    "content": result
                })
            
            # Since we performed tool calls, loop again to feed results back to the LLM
            continue
