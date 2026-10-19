"""Settings from Streamlit secrets, then environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

SANDBOX = "https://dev-api.priority1.com"
PRODUCTION = "https://api.priority1.com"


def _from_secrets(name: str):
    try:
        import streamlit as st
        from streamlit.errors import StreamlitSecretNotFoundError
    except Exception:
        return None
    try:
        secrets = st.secrets
    except (StreamlitSecretNotFoundError, FileNotFoundError, RuntimeError):
        return None
    except Exception:
        return None
    try:
        if name in secrets:
            return secrets[name]
    except Exception:
        return None
    return None


def read_setting(name: str, default: str = "") -> str:
    """Prefer st.secrets. Fall back to the environment, then default."""
    secret = _from_secrets(name)
    if secret is not None:
        return str(secret).strip()
    if name in os.environ:
        return os.environ[name].strip()
    return default


@dataclass(frozen=True)
class Priority1Config:
    base_url: str
    api_key: str
    mock: bool
    environment: str

    @property
    def mode_label(self) -> str:
        if self.mock:
            return "Demo rates"
        if self.environment == "production":
            return "Production"
        if self.environment == "sandbox":
            return "Sandbox"
        return "Custom endpoint"


def get_config() -> Priority1Config:
    base_url = (read_setting("P1_BASE_URL", SANDBOX) or SANDBOX).rstrip("/")
    api_key = read_setting("P1_API_KEY", "")
    force_mock = read_setting("P1_MOCK", "").lower() in {"1", "true", "yes"}
    if base_url == SANDBOX:
        environment = "sandbox"
    elif base_url == PRODUCTION:
        environment = "production"
    else:
        environment = "custom"
    return Priority1Config(
        base_url=base_url,
        api_key=api_key,
        mock=force_mock or not api_key,
        environment=environment,
    )
