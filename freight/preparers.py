"""Sales-rep roster for the prepared-by line.

The real roster is not in git. Streamlit secrets win, then a local
preparers.json. An empty result means the form should ask for the details.
"""

from __future__ import annotations

import json
from pathlib import Path


def preparer_id(rep: dict) -> str:
    return "|".join((rep.get("name") or "", rep.get("email") or "", rep.get("phone") or ""))


def load_preparers(secret_rows: object = None, json_path: Path | str | None = None) -> tuple[list[dict], str]:
    """Return (roster, source). Source is "secrets", "file", or ""."""
    roster = _normalize(secret_rows)
    if roster:
        return roster, "secrets"
    if json_path is None:
        return [], ""
    path = Path(json_path)
    if not path.is_file():
        return [], ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [], ""
    roster = _normalize(payload)
    if roster:
        return roster, "file"
    return [], ""


def read_preparer_secrets():
    """The [[preparers]] tables from st.secrets, or None when they are absent."""
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
        if "preparers" not in secrets:
            return None
        return secrets["preparers"]
    except Exception:
        return None


def _normalize(rows: object) -> list[dict]:
    if rows is None or isinstance(rows, (str, bytes)):
        return []
    try:
        items = list(rows)
    except TypeError:
        return []
    cleaned = []
    for item in items:
        rep = _rep(item)
        if rep:
            cleaned.append(rep)
    cleaned.sort(key=lambda rep: (rep["name"].casefold(), rep["email"].casefold()))
    return cleaned


def _rep(item: object) -> dict | None:
    if item is None or isinstance(item, (str, bytes, int, float)):
        return None
    name = _field(item, "name")
    if not name:
        return None
    return {
        "name": name,
        "title": _field(item, "title"),
        "email": _field(item, "email"),
        "phone": _field(item, "phone"),
    }


def _field(item: object, key: str) -> str:
    value = ""
    try:
        if key in item:  # type: ignore[operator]
            value = item[key]  # type: ignore[index]
    except Exception:
        value = ""
    if value in ("", None):
        try:
            value = item.get(key, "")  # type: ignore[attr-defined]
        except Exception:
            value = ""
    if value is None:
        return ""
    return " ".join(str(value).split())
