import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load local environment variables from .env if present
load_dotenv()

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "sarathy"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"

class Config:
    def __init__(self, api_key: str = None, api_base: str = None, model: str = None, auto_approve: bool = False):
        # 1. Start with defaults
        self.api_base = "https://api.sarvam.ai/v1"
        self.model = "sarvam-105b"
        self.auto_approve = auto_approve

        # 2. Load from configuration file if exists
        self._load_from_file()

        # 3. Override with environment variables
        self.api_key = os.environ.get("SARVAM_API_KEY", self.api_key or "")
        self.api_base = os.environ.get("SARVAM_API_BASE", self.api_base)
        self.model = os.environ.get("SARVAM_MODEL", self.model)

        # 4. Override with explicitly passed parameters (e.g. from CLI)
        if api_key:
            self.api_key = api_key
        if api_base:
            self.api_base = api_base
        if model:
            self.model = model

    def _load_from_file(self):
        self.api_key = ""
        if DEFAULT_CONFIG_FILE.exists():
            try:
                with open(DEFAULT_CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.api_key = data.get("api_key", "")
                    self.api_base = data.get("api_base", self.api_base)
                    self.model = data.get("model", self.model)
            except Exception:
                # Silently ignore config read errors
                pass

    def save(self):
        """Saves current configuration to ~/.config/sarathy/config.json"""
        try:
            DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(DEFAULT_CONFIG_FILE, "w") as f:
                json.dump({
                    "api_key": self.api_key,
                    "api_base": self.api_base,
                    "model": self.model
                }, f, indent=4)
            return True
        except Exception:
            return False

    def is_valid(self) -> bool:
        """Returns True if config has a non-empty API key."""
        return bool(self.api_key.strip())
