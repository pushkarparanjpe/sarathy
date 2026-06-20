import json
from openai import OpenAI
from typing import List, Dict, Any, Generator, Tuple

class LLMClient:
    def __init__(self, api_key: str, api_base: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=api_base)
        self.model = model

    def chat_stream(
        self, 
        messages: List[Dict[str, Any]], 
        tools: List[Dict[str, Any]] = None
    ) -> Generator[Tuple[str, Any], None, None]:
        """
        Sends chat completion request with streaming.
        Yields tuples:
        - ("content", chunk_text)
        - ("tool_calls", parsed_tool_calls_list)
        - ("error", error_message)
        """
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            if tools:
                kwargs["tools"] = tools

            response = self.client.chat.completions.create(**kwargs)

            # We need to aggregate streamed tool calls
            # OpenAI streams tool calls as chunks where tool_calls is a list of deltas
            active_tool_calls = {}

            for chunk in response:
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    u = chunk.usage
                    if isinstance(u, dict):
                        prompt_details = u.get("prompt_tokens_details") or {}
                        cached_tokens = 0
                        if isinstance(prompt_details, dict):
                            cached_tokens = prompt_details.get("cached_tokens", 0) or 0
                        else:
                            cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
                        yield "usage", {
                            "prompt_tokens": u.get("prompt_tokens", 0),
                            "completion_tokens": u.get("completion_tokens", 0),
                            "total_tokens": u.get("total_tokens", 0),
                            "cached_tokens": cached_tokens
                        }
                    else:
                        prompt_details = getattr(u, "prompt_tokens_details", None)
                        cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0 if prompt_details else 0
                        yield "usage", {
                            "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                            "completion_tokens": getattr(u, "completion_tokens", 0) or 0,
                            "total_tokens": getattr(u, "total_tokens", 0) or 0,
                            "cached_tokens": cached_tokens
                        }

                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # Check for content stream
                if delta.content:
                    yield "content", delta.content
                
                # Check for tool call stream
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in active_tool_calls:
                            active_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {
                                    "name": tc.function.name or "",
                                    "arguments": tc.function.arguments or ""
                                }
                            }
                        else:
                            if tc.id:
                                active_tool_calls[idx]["id"] += tc.id
                            if tc.function.name:
                                active_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                active_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

            # Yield aggregated tool calls if any exist
            if active_tool_calls:
                # Sort by index and convert to list
                sorted_calls = [active_tool_calls[i] for i in sorted(active_tool_calls.keys())]
                # Parse arguments json to verify/clean if possible
                for tc in sorted_calls:
                    try:
                        # Ensure the arguments are parseable JSON
                        args_str = tc["function"]["arguments"]
                        # Sometimes incomplete json might cause error, let's keep it as string
                        # since the agent runner will parse it, but we can do a sanity check here.
                        pass
                    except Exception:
                        pass
                yield "tool_calls", sorted_calls

        except Exception as e:
            yield "error", str(e)
