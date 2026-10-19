"""Sales-rep roster for the prepared-by line.

The roster is data/preparers.json in the repo. An empty result means the
form should ask for name, title, and email by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "preparers.json"

ADD_PREPARER = "__add_preparer__"
ADD_PREPARER_LABEL = "+ Add a new person"


def preparer_id(rep: dict) -> str:
    return "|".join((rep.get("name") or "", rep.get("email") or ""))


def preparer_label(rep: dict, roster: list[dict]) -> str:
    if sum(1 for item in roster if item["name"] == rep["name"]) > 1 and rep.get("email"):
        return f"{rep['name']} ({rep['email']})"
    return rep["name"]


def preparer_options(roster: list[dict]) -> list[tuple[str, str]]:
    """Dropdown values and labels. The add-a-person choice is always last."""
    options = [("", "Select your name")]
    options.extend((preparer_id(rep), preparer_label(rep, roster)) for rep in roster)
    options.append((ADD_PREPARER, ADD_PREPARER_LABEL))
    return options


def apply_preparer_choice(choice: str, roster: list[dict], custom: dict | None = None) -> dict:
    """Name, title, and email for a dropdown choice. Does not change the roster."""
    if choice == ADD_PREPARER:
        entered = custom or {}
        return {
            "name": _field(entered, "name"),
            "title": _field(entered, "title"),
            "email": _field(entered, "email"),
        }
    match = next((rep for rep in roster if preparer_id(rep) == choice), None)
    if match is None:
        return {"name": "", "title": "", "email": ""}
    return {"name": match["name"], "title": match["title"], "email": match["email"]}


def load_preparers(json_path: Path | str | None = None) -> list[dict]:
    """Return the roster sorted by name. Missing or invalid files return []."""
    path = DEFAULT_PATH if json_path is None else Path(json_path)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    return _normalize(payload)


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
