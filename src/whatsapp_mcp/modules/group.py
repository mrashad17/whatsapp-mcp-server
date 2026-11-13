"""Group module for WhatsApp MCP Server."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from whatsapp_mcp.models import Contact, Group, Participant
from whatsapp_mcp.modules.greenapi import call, check_group_id, get_api, to_chat_id

logger = logging.getLogger(__name__)


async def create_group(group_name: str, participants: List[str]) -> Group:
    """Create a new WhatsApp group with GreenAPI createGroup."""
    if not group_name or not group_name.strip():
        raise ValueError("Group name must not be empty")
    if len(participants) < 1:
        raise ValueError("Need at least one participant to create a group")

    api = get_api()
    chat_ids = [to_chat_id(p) for p in participants]
    logger.info("Creating group with %d participants", len(chat_ids))

    data = await call(api.groups.createGroup, group_name, chat_ids)
    if not isinstance(data, dict) or not data.get("created"):
        raise ValueError(f"GreenAPI did not create the group: {data}")

    group_id = data.get("chatId")
    if not group_id:
        raise ValueError("GreenAPI did not return the new group's chatId")

    participant_objects = [
        Participant(
            id=chat_id,
            is_admin=False,
            contact=Contact(id=chat_id, phone=chat_id.split("@")[0]),
        )
        for chat_id in chat_ids
    ]
    return Group(
        id=group_id,
        name=group_name,
        description=data.get("groupInviteLink", ""),
        owner="me",
        creation_time=datetime.now().isoformat(),
        participants=participant_objects,
    )


async def get_group_participants(group_id: str) -> List[Participant]:
    """Get the participants of a group with GreenAPI getGroupData."""
    group_id = check_group_id(group_id)
    api = get_api()

    data = await call(api.groups.getGroupData, group_id)
    if not isinstance(data, dict):
        raise ValueError("Unexpected getGroupData response from GreenAPI")

    participants = []
    for p in data.get("participants", []) or []:
        p_id = p.get("id", "")
        phone = (p.get("phoneNumber") or p_id).split("@")[0]
        participants.append(
            Participant(
                id=p_id,
                is_admin=bool(p.get("isAdmin") or p.get("isSuperAdmin")),
                contact=Contact(id=p_id, phone=phone),
            )
        )
    return participants


async def add_participant(group_id: str, participant_phone: str) -> Dict[str, Any]:
    """Add a participant with GreenAPI addGroupParticipant."""
    group_id = check_group_id(group_id)
    chat_id = to_chat_id(participant_phone)
    api = get_api()

    data = await call(api.groups.addGroupParticipant, group_id, chat_id)
    if not isinstance(data, dict) or not data.get("addParticipant"):
        raise ValueError(f"GreenAPI did not add the participant: {data}")
    return {
        "success": True,
        "group_id": group_id,
        "participant": chat_id,
        "timestamp": datetime.now().isoformat(),
    }


async def remove_participant(group_id: str, participant_id: str) -> Dict[str, Any]:
    """Remove a participant with GreenAPI removeGroupParticipant."""
    group_id = check_group_id(group_id)
    chat_id = to_chat_id(participant_id)
    api = get_api()

    data = await call(api.groups.removeGroupParticipant, group_id, chat_id)
    if not isinstance(data, dict) or not data.get("removeParticipant"):
        raise ValueError(f"GreenAPI did not remove the participant: {data}")
    return {
        "success": True,
        "group_id": group_id,
        "participant": chat_id,
        "timestamp": datetime.now().isoformat(),
    }


async def update_group_settings(
    group_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Rename a group with GreenAPI updateGroupName.

    GreenAPI's client library has no call for changing a group description,
    so asking for one raises instead of pretending to succeed.
    """
    group_id = check_group_id(group_id)
    if description is not None:
        raise ValueError("Changing a group description is not supported by GreenAPI")
    if not name:
        raise ValueError("Must provide a new group name")

    api = get_api()
    data = await call(api.groups.updateGroupName, group_id, name)
    if not isinstance(data, dict) or not data.get("updateGroupName"):
        raise ValueError(f"GreenAPI did not rename the group: {data}")
    return {
        "success": True,
        "group_id": group_id,
        "updated_fields": ["name"],
        "timestamp": datetime.now().isoformat(),
    }
