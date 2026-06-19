import os
import subprocess
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional

# Define which tools require explicit user confirmation
DANGEROUS_TOOLS = {"run_command", "write_file", "replace_content"}

def run_command(command: str) -> str:
    """Executes a shell command. Runs in the current working directory."""
    try:
        # Run command with devnull stdin to prevent hanging on interactive inputs
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=120
        )
        output = []
        if result.stdout:
            output.append(result.stdout)
        if result.stderr:
            output.append(f"ERROR/STDERR:\n{result.stderr}")
        
        if not output:
            return f"Command executed successfully with no output (exit code {result.returncode})."
        
        return "\n".join(output)
    except subprocess.TimeoutExpired:
        return "Error: Command execution timed out after 120 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"

def view_file(path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
    """Reads content of a file."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: File '{path}' does not exist."
        if p.is_dir():
            return f"Error: '{path}' is a directory. Use list_dir instead."
        
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        start = max(1, start_line)
        end = min(total_lines, end_line) if end_line else total_lines
        
        if start > total_lines:
            return f"Error: Start line {start} is greater than total lines ({total_lines})."
        
        output = []
        for idx in range(start - 1, end):
            output.append(f"{idx + 1}: {lines[idx]}")
            
        header = f"File: {path} (Lines {start}-{end} of {total_lines})\n"
        return header + "".join(output)
    except Exception as e:
        return f"Error reading file '{path}': {str(e)}"

def write_file(path: str, content: str) -> str:
    """Creates or overwrites a file with the specified content."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote file '{path}' ({len(content)} bytes)."
    except Exception as e:
        return f"Error writing file '{path}': {str(e)}"

def replace_content(path: str, target: str, replacement: str) -> str:
    """Replaces a precise string block in a file with new content."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: File '{path}' does not exist."
            
        content = p.read_text(encoding="utf-8", errors="replace")
        
        occurrences = content.count(target)
        if occurrences == 0:
            return f"Error: The target content to replace was not found in '{path}'. Make sure spacing and line endings match exactly."
        elif occurrences > 1:
            return f"Error: The target content was found {occurrences} times in '{path}'. Please specify a more unique block of code to avoid ambiguity."
        
        new_content = content.replace(target, replacement)
        p.write_text(new_content, encoding="utf-8")
        return f"Successfully updated '{path}'."
    except Exception as e:
        return f"Error editing file '{path}': {str(e)}"

def list_dir(path: str = ".") -> str:
    """Lists the contents of a directory."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: Directory '{path}' does not exist."
        if not p.is_dir():
            return f"Error: '{path}' is a file. Use view_file instead."
            
        items = sorted(p.iterdir())
        output = []
        for item in items:
            # Skip common noise dirs/files
            if item.name in {".git", ".venv", "__pycache__", ".DS_Store"}:
                continue
            rel = item.relative_to(p.parent if p.parent else p)
            type_str = "DIR " if item.is_dir() else "FILE"
            size = f" ({item.stat().st_size} bytes)" if item.is_file() else ""
            output.append(f"{type_str} {item.name}{size}")
            
        if not output:
            return f"Directory '{path}' is empty or only contains ignored items (.git, .venv, etc.)."
            
        return f"Contents of '{path}':\n" + "\n".join(output)
    except Exception as e:
        return f"Error listing directory '{path}': {str(e)}"

def grep_search(query: str, path: str = ".") -> str:
    """Searches recursively for a query pattern in files (skipping ignored dirs)."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: Search path '{path}' does not exist."
            
        results = []
        ignored_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".config"}
        
        # Simple recursive text search
        for root, dirs, files in os.walk(p):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            for file in files:
                file_path = Path(root) / file
                # Skip binary files or common config
                if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".pyc", ".db", ".zip", ".tar", ".gz"}:
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if query in line:
                                results.append(f"{file_path}:{line_num}: {line.strip()}")
                                if len(results) >= 50:
                                    break
                except Exception:
                    pass
                if len(results) >= 50:
                    break
            if len(results) >= 50:
                break
                
        if not results:
            return f"No matches found for query '{query}'."
            
        output = f"Found {len(results)} matches for '{query}':\n" + "\n".join(results)
        if len(results) >= 50:
            output += "\n(Results capped at 50 matches)"
        return output
    except Exception as e:
        return f"Error searching directory '{path}': {str(e)}"

# OpenAI Tool Schemas mapping
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell/terminal command. Only use when necessary (e.g. running tests, building, checking versions). ALWAYS explain what command you want to run.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact shell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "view_file",
            "description": "View/read content of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative or absolute path of the file to view."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "The starting line number to view (1-indexed). Defaults to 1.",
                        "default": 1
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional ending line number to view (inclusive)."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or create a file in the workspace with complete content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative or absolute path of the file to write."
                    },
                    "content": {
                        "type": "string",
                        "description": "The full text content to write into the file."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_content",
            "description": "Modify an existing file by replacing a specific unique target block of text with new content. Prefer this over write_file for editing parts of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The relative or absolute path of the file to edit."
                    },
                    "target": {
                        "type": "string",
                        "description": "The exact block of code/text in the file to be replaced. Must match exactly including indentation."
                    },
                    "replacement": {
                        "type": "string",
                        "description": "The new block of code/text to replace the target block with."
                    }
                },
                "required": ["path", "target", "replacement"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List all files and folders in a workspace directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list. Defaults to '.'.",
                        "default": "."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search recursively for a specific text pattern or keyword inside files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The text pattern or keyword to search for."
                    },
                    "path": {
                        "type": "string",
                        "description": "The root path to start search. Defaults to '.'.",
                        "default": "."
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def execute_tool(name: str, arguments: Dict[str, Any]) -> str:
    """Dispatcher to execute tools by name with provided arguments."""
    try:
        if name == "run_command":
            return run_command(arguments["command"])
        elif name == "view_file":
            return view_file(
                arguments["path"],
                arguments.get("start_line", 1),
                arguments.get("end_line")
            )
        elif name == "write_file":
            return write_file(arguments["path"], arguments["content"])
        elif name == "replace_content":
            return replace_content(arguments["path"], arguments["target"], arguments["replacement"])
        elif name == "list_dir":
            return list_dir(arguments.get("path", "."))
        elif name == "grep_search":
            return grep_search(arguments["query"], arguments.get("path", "."))
        else:
            return f"Error: Tool '{name}' is not supported."
    except KeyError as e:
        return f"Error: Missing required argument {str(e)} for tool '{name}'."
    except Exception as e:
        return f"Error executing tool '{name}': {str(e)}"
