"""Message module for WhatsApp MCP Server."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from whatsapp_mcp.modules.greenapi import call, get_api, to_chat_id

logger = logging.getLogger(__name__)


def _get_chat_id(phone_number: str) -> str:
    """Get the chat ID for a phone number (kept for backwards compatibility)."""
    return to_chat_id(phone_number)


async def send_message(
    phone_number: str, content: str, reply_to: Optional[str] = None
) -> dict:
    """Send a message to a chat."""
    if not content or not content.strip():
        raise ValueError("Message content must not be empty")

    api = get_api()
    chat_id = to_chat_id(phone_number)
    # Message text is not logged, only who it went to.
    logger.info("Sending message to %s", chat_id)

    data = await call(api.sending.sendMessage, chat_id, content, reply_to)

    message_id = "Not provided"
    if isinstance(data, dict) and data.get("idMessage"):
        message_id = data["idMessage"]

    return {
        "message_id": message_id,
        "chat_id": chat_id,
        "status": "sent",
        "timestamp": datetime.now().isoformat(),
    }


async def get_chats(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Get the account's chats (contacts and groups) from GreenAPI.

    Uses GreenAPI getContacts. Names come from WhatsApp and the phone book and
    are third-party data.
    """
    if limit < 1 or offset < 0:
        raise ValueError("limit must be >= 1 and offset must be >= 0")

    api = get_api()
    data = await call(api.serviceMethods.getContacts)
    if not isinstance(data, list):
        raise ValueError("Unexpected getContacts response from GreenAPI")

    chats = []
    for item in data:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        chats.append(
            {
                "id": item["id"],
                "name": item.get("contactName") or item.get("name") or "",
                "is_group": item.get("type") == "group",
            }
        )
    return chats[offset : offset + limit]


async def get_messages(chat_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent messages from a chat using GreenAPI getChatHistory."""
    if limit < 1:
        raise ValueError("limit must be >= 1")

    api = get_api()
    if not chat_id.endswith("@g.us"):
        chat_id = to_chat_id(chat_id)
    data = await call(api.journals.getChatHistory, chat_id, limit)
    if not isinstance(data, list):
        raise ValueError("Unexpected getChatHistory response from GreenAPI")
    return data[:limit]
