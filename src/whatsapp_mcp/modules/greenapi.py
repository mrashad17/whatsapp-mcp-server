"""Small helpers shared by the modules that call the GreenAPI client."""

import asyncio
import re
from typing import Any, Callable

from whatsapp_mcp.modules.auth import auth_manager

_DIGITS = re.compile(r"\D")


class GreenApiError(ValueError):
    """Raised when GreenAPI returns a non-200 response."""


def get_api() -> Any:
    """Return the GreenApi client for the open session, or raise."""
    session = auth_manager.get_client()
    if not session or not session.client:
        raise ValueError("No active session. Call open_session first.")
    return session.client


async def call(fn: Callable[..., Any], *args: Any) -> Any:
    """Run a blocking GreenAPI call in a thread and return its JSON data.

    The GreenAPI client returns a Response object with .code, .data and .error.
    Anything other than HTTP 200 is turned into an exception so callers never
    mistake a failed call for a successful one.
    """
    response = await asyncio.to_thread(fn, *args)
    code = getattr(response, "code", None)
    if code != 200:
        error = getattr(response, "error", None) or "no response body"
        raise GreenApiError(f"GreenAPI returned HTTP {code}: {str(error)[:200]}")
    return response.data


def to_chat_id(phone_number: str) -> str:
    """Turn a phone number or chat ID into a GreenAPI personal chat ID.

    Accepts "+20 100 123 4567", "201001234567" or "201001234567@c.us".
    Rejects anything that is not 7-15 digits, so a typo or a name can never
    be sent to as if it were a number.
    """
    value = phone_number.strip()
    if value.endswith("@c.us"):
        value = value[: -len("@c.us")]
    digits = _DIGITS.sub("", value)
    if not 7 <= len(digits) <= 15:
        raise ValueError(
            "Phone number must be 7-15 digits including country code, "
            f"got {phone_number!r}"
        )
    return f"{digits}@c.us"


def check_group_id(group_id: str) -> str:
    """Validate a group chat ID."""
    group_id = group_id.strip()
    if not group_id.endswith("@g.us") or len(group_id) <= len("@g.us"):
        raise ValueError("Invalid group ID format. Must end with @g.us")
    return group_id
