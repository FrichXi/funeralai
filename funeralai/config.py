"""API key / provider / lang persistence to ~/.config/funeralai/config.json.

Also detects credentials from external tools (Codex CLI)."""

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "funeralai" / "config.json"

# Provider name -> env var. Order matches analyzer.py PROVIDERS.
PROVIDERS_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "kimi": "MOONSHOT_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "zhipu": "ZHIPU_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
}


def load_config() -> dict:
    """Read config file. Return {} if missing or corrupted."""
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(config: dict) -> None:
    """Write config to disk, creating parent directories as needed."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_api_key(provider: str) -> str | None:
    """Get API key for provider. Priority: env var > config.json keys."""
    env_var = PROVIDERS_ENV.get(provider)
    if env_var:
        env_val = os.environ.get(env_var, "").strip()
        if env_val:
            return env_val
    key = load_config().get("keys", {}).get(provider, "").strip()
    return key or None


def save_api_key(provider: str, key: str) -> None:
    """Save key and set provider as default."""
    config = load_config()
    config.setdefault("keys", {})[provider] = key
    config["default_provider"] = provider
    env_var = PROVIDERS_ENV.get(provider)
    if env_var:
        # Keep the current process consistent even when an old env var was wrong.
        os.environ[env_var] = key
    save_config(config)


def get_default_provider() -> tuple[str, str] | None:
    """Return (provider_name, api_key) from config's default_provider.

    Returns None if no default is configured or the key is missing.
    Called by analyzer.py as a fallback when no env vars are set.
    """
    config = load_config()
    provider = config.get("default_provider", "").strip()
    if not provider:
        return None
    key = config.get("keys", {}).get(provider, "").strip()
    if not key:
        return None
    return (provider, key)


def detect_provider_from_key(key: str) -> str | None:
    """Infer provider from API key prefix."""
    key = key.strip()
    if key.startswith("sk-ant-"):
        return "anthropic"
    if key.startswith("sk-"):
        return "openai"
    if key.startswith("AIzaSy"):
        return "gemini"
    # Chinese providers typically use longer opaque tokens; no reliable prefix.
    return None


def scan_env_keys() -> tuple[str, str] | None:
    """Scan all provider env vars, return first (provider, key) found."""
    for provider, env_var in PROVIDERS_ENV.items():
        key = os.environ.get(env_var, "").strip()
        if key:
            return (provider, key)
    return None


def try_codex_auth() -> tuple[str, str] | None:
    """Read OpenAI credentials from Codex CLI (~/.codex/auth.json).

    Checks for an explicit OPENAI_API_KEY first, then falls back to the
    OAuth access_token (ChatGPT Plus subscription).
    """
    auth_path = Path.home() / ".codex" / "auth.json"
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    api_key = (data.get("OPENAI_API_KEY") or "").strip()
    if api_key:
        return ("openai", api_key)

    tokens = data.get("tokens", {})
    access_token = (tokens.get("access_token") or "").strip()
    if access_token:
        return ("openai", access_token)

    return None
