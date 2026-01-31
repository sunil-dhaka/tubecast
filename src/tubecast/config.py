"""Configuration management for TubeCast."""

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".tubecast"
CONFIG_FILE = CONFIG_DIR / "config.json"
CREDENTIALS_FILE = CONFIG_DIR / "client_secret.json"
TOKEN_FILE = CONFIG_DIR / "token.json"

DEFAULT_CONFIG = {
    "gemini_api_key": None,
    "gemini_model": "gemini-2.5-flash",
    "default_privacy": "unlisted",
    "default_category": "22",  # People & Blogs
    "ai_enabled": False,
    "made_for_kids": False,
    "contains_synthetic_media": True,
}

GEMINI_MODELS = [
    {"value": "gemini-3-pro-preview", "label": "Gemini 3 Pro Preview", "description": "Latest and most capable (Recommended)"},
    {"value": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "description": "Enhanced reasoning"},
    {"value": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "description": "Fast and efficient"},
]

PRIVACY_OPTIONS = [
    {"value": "public", "label": "Public", "description": "Anyone can watch"},
    {"value": "unlisted", "label": "Unlisted", "description": "Only people with link can watch"},
    {"value": "private", "label": "Private", "description": "Only you can watch"},
]

CATEGORY_OPTIONS = [
    {"value": "1", "label": "Film & Animation"},
    {"value": "2", "label": "Autos & Vehicles"},
    {"value": "10", "label": "Music"},
    {"value": "15", "label": "Pets & Animals"},
    {"value": "17", "label": "Sports"},
    {"value": "19", "label": "Travel & Events"},
    {"value": "20", "label": "Gaming"},
    {"value": "22", "label": "People & Blogs"},
    {"value": "23", "label": "Comedy"},
    {"value": "24", "label": "Entertainment"},
    {"value": "25", "label": "News & Politics"},
    {"value": "26", "label": "Howto & Style"},
    {"value": "27", "label": "Education"},
    {"value": "28", "label": "Science & Technology"},
    {"value": "29", "label": "Nonprofits & Activism"},
]


def ensure_config_dir() -> None:
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Load configuration from file."""
    ensure_config_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            stored = json.load(f)
            return {**DEFAULT_CONFIG, **stored}
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    """Save configuration to file."""
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_gemini_api_key() -> Optional[str]:
    """Get Gemini API key from config or environment."""
    config = load_config()
    return config.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY")


def credentials_exist() -> bool:
    """Check if OAuth credentials exist."""
    return CREDENTIALS_FILE.exists()


def token_exists() -> bool:
    """Check if OAuth token exists."""
    return TOKEN_FILE.exists()


def is_configured() -> bool:
    """Check if TubeCast is configured."""
    return credentials_exist()
