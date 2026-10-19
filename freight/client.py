"""HTTP client for Priority1. The API key never leaves this module's request."""

from __future__ import annotations

import requests

from freight.config import get_config


class Priority1Error(RuntimeError):
    def __init__(self, status: int, messages: list[str]):
        super().__init__(messages[0] if messages else f"Rating request failed ({status}).")
        self.status = status
        self.messages = messages


def _messages(body: object) -> list[str]:
    def one(entry: object) -> str | None:
        if not isinstance(entry, dict):
            return None
        text = entry.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return None

    if isinstance(body, list):
        return [text for text in (one(entry) for entry in body) if text]
    single = one(body)
    return [single] if single else []


def _scrub(text: str, secret: str) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")


def post_priority1(path: str, body: dict) -> dict:
    config = get_config()
    if not config.api_key:
        raise Priority1Error(401, ["No API key is configured."])
    try:
        response = requests.post(
            f"{config.base_url}{path}",
            headers={
                "X-API-KEY": config.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=body,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise Priority1Error(504, [f"The rating service did not respond ({_scrub(str(exc), config.api_key)})."]) from exc

    parsed: object = None
    if response.content:
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
    if not response.ok:
        messages = [_scrub(message, config.api_key) for message in _messages(parsed)]
        if not messages:
            if response.status_code == 401:
                messages = ["The API key was rejected."]
            elif response.status_code == 403:
                messages = ["This API key is not allowed to call that endpoint."]
            elif response.status_code == 429:
                messages = ["The rating service is rate limiting requests. Try again shortly."]
            else:
                messages = [f"The rating service returned {response.status_code}."]
        raise Priority1Error(response.status_code, messages)
    if not isinstance(parsed, dict):
        raise Priority1Error(502, ["The rating service returned an unreadable response."])
    return parsed


def truckload_unavailable_message(error: Priority1Error) -> str | None:
    if error.status in (401, 403):
        return (
            "Truckload quoting is not available on this API key. Priority1 may not have "
            "enabled full truckload for the EasyPost account. LTL quoting is unaffected."
        )
    return None
