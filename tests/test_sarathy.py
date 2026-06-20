import os
import pytest
from pathlib import Path
from sarathy.config import Config
from sarathy.tools import (
    write_file,
    view_file,
    replace_content,
    list_dir,
    grep_search,
    execute_tool
)

@pytest.fixture(autouse=True)
def mock_config_path(monkeypatch, tmp_path):
    mock_file = tmp_path / "mock_config.json"
    monkeypatch.setattr("sarathy.config.DEFAULT_CONFIG_FILE", mock_file)
    monkeypatch.setattr("sarathy.config.DEFAULT_CONFIG_DIR", tmp_path)

def test_config_defaults():
    # Test config defaults when no environment variables are present
    os.environ.pop("SARVAM_API_KEY", None)
    os.environ.pop("SARVAM_API_BASE", None)
    os.environ.pop("SARVAM_MODEL", None)
    
    cfg = Config()
    assert cfg.api_base == "https://api.sarvam.ai/v1"
    assert cfg.model == "sarvam-105b"
    assert not cfg.is_valid()

def test_config_env_overrides():
    # Test environment variable overrides
    os.environ["SARVAM_API_KEY"] = "test-key-123"
    os.environ["SARVAM_API_BASE"] = "https://custom.api/v2"
    os.environ["SARVAM_MODEL"] = "custom-model"
    
    cfg = Config()
    assert cfg.api_key == "test-key-123"
    assert cfg.api_base == "https://custom.api/v2"
    assert cfg.model == "custom-model"
    assert cfg.is_valid()
    
    # Clean up env
    os.environ.pop("SARVAM_API_KEY", None)
    os.environ.pop("SARVAM_API_BASE", None)
    os.environ.pop("SARVAM_MODEL", None)

def test_file_tools(tmp_path):
    # Test write_file
    test_file = tmp_path / "hello.txt"
    res_write = write_file(str(test_file), "hello world\nline two\nline three")
    assert "Successfully wrote" in res_write
    assert test_file.read_text() == "hello world\nline two\nline three"

    # Test view_file
    res_view = view_file(str(test_file), start_line=1, end_line=2)
    assert "File:" in res_view
    assert "1: hello world" in res_view
    assert "2: line two" in res_view
    assert "3: line three" not in res_view

    # Test replace_content
    res_replace = replace_content(str(test_file), "line two", "line replacement")
    assert "Successfully updated" in res_replace
    assert "line replacement" in test_file.read_text()
    assert "line two" not in test_file.read_text()

    # Test list_dir
    res_list = list_dir(str(tmp_path))
    assert "hello.txt" in res_list

    # Test grep_search
    res_grep = grep_search("replacement", str(tmp_path))
    assert "hello.txt:2: line replacement" in res_grep

def test_execute_tool_dispatch(tmp_path):
    test_file = tmp_path / "dispatch.txt"
    res = execute_tool("write_file", {"path": str(test_file), "content": "dispatched content"})
    assert "Successfully wrote" in res
    assert test_file.read_text() == "dispatched content"

    res_view = execute_tool("view_file", {"path": str(test_file)})
    assert "dispatched content" in res_view


def test_llm_client_yields_usage():
    from unittest.mock import MagicMock, patch
    
    mock_openai = MagicMock()
    
    class MockDelta:
        content = "Hello"
        tool_calls = None
        
    class MockChoice:
        delta = MockDelta()
        finish_reason = None
        index = 0
        
    class MockChunk:
        def __init__(self, choices, usage=None):
            self.choices = choices
            self.usage = usage
            
    mock_chunk_1 = MockChunk(choices=[MockChoice()])
    
    class MockPromptTokensDetails:
        cached_tokens = 3
    
    class MockUsage:
        prompt_tokens = 10
        completion_tokens = 5
        total_tokens = 15
        prompt_tokens_details = MockPromptTokensDetails()
        
    mock_chunk_2 = MockChunk(choices=[], usage=MockUsage())
    
    mock_openai.chat.completions.create.return_value = [mock_chunk_1, mock_chunk_2]
    
    with patch("sarathy.llm.OpenAI", return_value=mock_openai):
        from sarathy.llm import LLMClient
        client = LLMClient(api_key="dummy", api_base="dummy", model="dummy")
        
        events = list(client.chat_stream(messages=[]))
        
        # Verify content was yielded
        assert ("content", "Hello") in events
        # Verify usage was yielded
        assert ("usage", {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "cached_tokens": 3
        }) in events


def test_agent_run_turn_propagates_usage():
    from unittest.mock import MagicMock, patch
    
    mock_openai = MagicMock()
    
    class MockDelta:
        content = "Hi"
        tool_calls = None
        
    class MockChoice:
        delta = MockDelta()
        
    class MockChunk:
        def __init__(self, choices, usage=None):
            self.choices = choices
            self.usage = usage
            
    class MockPromptTokensDetails:
        cached_tokens = 4
            
    class MockUsage:
        prompt_tokens = 20
        completion_tokens = 8
        total_tokens = 28
        prompt_tokens_details = MockPromptTokensDetails()
        
    mock_openai.chat.completions.create.return_value = [
        MockChunk(choices=[MockChoice()]),
        MockChunk(choices=[], usage=MockUsage())
    ]
    
    with patch("sarathy.llm.OpenAI", return_value=mock_openai):
        from sarathy.agent import Agent
        from sarathy.config import Config
        
        config = Config(api_key="dummy")
        agent = Agent(config)
        
        events = list(agent.run_turn("hello", confirm_callback=lambda x, y: False))
        
        assert ("usage", {
            "prompt_tokens": 20,
            "completion_tokens": 8,
            "total_tokens": 28,
            "cached_tokens": 4
        }) in events


def test_get_pricing_for_model():
    from sarathy.pricing import get_pricing_for_model
    
    # Test valid model
    input_rate, output_rate, cached_rate, symbol = get_pricing_for_model("sarvam-105b")
    assert input_rate == 4.0
    assert output_rate == 16.0
    assert cached_rate == 2.5
    assert symbol == "₹"
    
    # Test case insensitivity and padding
    input_rate, output_rate, cached_rate, symbol = get_pricing_for_model("  SARVAM-105b  ")
    assert input_rate == 4.0
    assert output_rate == 16.0
    assert cached_rate == 2.5
    assert symbol == "₹"
    
    # Test fallback to defaults
    input_rate, output_rate, cached_rate, symbol = get_pricing_for_model("unknown-model")
    assert input_rate == 4.0
    assert output_rate == 16.0
    assert cached_rate == 2.5
    assert symbol == "₹"
