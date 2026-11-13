"""Tests that the modules call the real GreenAPI client methods correctly.

The GreenAPI client is replaced with a MagicMock using spec=GreenApi so a call
to a method that does not exist on the real client fails the test.
"""

from unittest.mock import MagicMock, patch

import pytest
from whatsapp_api_client_python.API import GreenApi

from whatsapp_mcp.modules import auth, group, message
from whatsapp_mcp.modules.greenapi import GreenApiError, to_chat_id


def _resp(data=None, code=200, error=None):
    r = MagicMock()
    r.code, r.data, r.error = code, data, error
    return r


@pytest.fixture
def api():
    real = GreenApi("1101000001", "token")
    fake = MagicMock()
    # spec_set mirrors the real sub-objects, so misspelled methods raise.
    for ns in ("account", "sending", "serviceMethods", "journals", "groups"):
        setattr(fake, ns, MagicMock(spec_set=getattr(real, ns)))
    session = MagicMock()
    session.client = fake
    with patch.object(auth.auth_manager, "session", session):
        yield fake


# --- phone number handling -------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("+20 100 123 4567", "201001234567@c.us"),
        ("201001234567", "201001234567@c.us"),
        ("201001234567@c.us", "201001234567@c.us"),
    ],
)
def test_to_chat_id_normalizes(raw, expected):
    assert to_chat_id(raw) == expected


@pytest.mark.parametrize("raw", ["", "John", "123", "1" * 16, "abc@g.us"])
def test_to_chat_id_rejects_bad_numbers(raw):
    with pytest.raises(ValueError):
        to_chat_id(raw)


# --- messages ----------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_message_calls_sendMessage(api):
    api.sending.sendMessage.return_value = _resp({"idMessage": "ABC"})
    result = await message.send_message("+20 100 123 4567", "hi")
    api.sending.sendMessage.assert_called_once_with("201001234567@c.us", "hi", None)
    assert result["message_id"] == "ABC"
    assert result["chat_id"] == "201001234567@c.us"


@pytest.mark.asyncio
async def test_send_message_raises_on_http_error(api):
    api.sending.sendMessage.return_value = _resp(code=401, error="Unauthorized")
    with pytest.raises(GreenApiError):
        await message.send_message("201001234567", "hi")


@pytest.mark.asyncio
async def test_send_message_rejects_empty_text(api):
    with pytest.raises(ValueError):
        await message.send_message("201001234567", "   ")
    api.sending.sendMessage.assert_not_called()


@pytest.mark.asyncio
async def test_get_chats_returns_real_contacts_not_placeholders(api):
    api.serviceMethods.getContacts.return_value = _resp(
        [
            {"id": "201001234567@c.us", "name": "A", "contactName": "Alice", "type": "user"},
            {"id": "1203630@g.us", "name": "Team", "type": "group"},
        ]
    )
    chats = await message.get_chats(limit=10)
    assert chats == [
        {"id": "201001234567@c.us", "name": "Alice", "is_group": False},
        {"id": "1203630@g.us", "name": "Team", "is_group": True},
    ]
    assert "John Doe" not in str(chats)


@pytest.mark.asyncio
async def test_get_chats_paginates(api):
    api.serviceMethods.getContacts.return_value = _resp(
        [{"id": f"2010000000{i}@c.us", "type": "user"} for i in range(5)]
    )
    chats = await message.get_chats(limit=2, offset=1)
    assert [c["id"] for c in chats] == ["20100000001@c.us", "20100000002@c.us"]


# --- groups ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_group_calls_createGroup(api):
    api.groups.createGroup.return_value = _resp(
        {"created": True, "chatId": "2010-1587570015@g.us", "groupInviteLink": "x"}
    )
    g = await group.create_group("Team", ["201001234567", "+20 111 222 3333"])
    api.groups.createGroup.assert_called_once_with(
        "Team", ["201001234567@c.us", "201112223333@c.us"]
    )
    assert g.id == "2010-1587570015@g.us"


@pytest.mark.asyncio
async def test_create_group_raises_when_not_created(api):
    api.groups.createGroup.return_value = _resp({"created": False})
    with pytest.raises(ValueError):
        await group.create_group("Team", ["201001234567"])


@pytest.mark.asyncio
async def test_get_group_participants_calls_getGroupData(api):
    api.groups.getGroupData.return_value = _resp(
        {
            "groupId": "1203630@g.us",
            "participants": [
                {"id": "201001234567@c.us", "phoneNumber": "201001234567@c.us", "isAdmin": True},
                {"id": "201112223333@c.us", "isAdmin": False, "isSuperAdmin": False},
            ],
        }
    )
    people = await group.get_group_participants("1203630@g.us")
    api.groups.getGroupData.assert_called_once_with("1203630@g.us")
    assert [(p.contact.phone, p.is_admin) for p in people] == [
        ("201001234567", True),
        ("201112223333", False),
    ]


@pytest.mark.asyncio
async def test_add_and_remove_participant(api):
    api.groups.addGroupParticipant.return_value = _resp({"addParticipant": True})
    api.groups.removeGroupParticipant.return_value = _resp({"removeParticipant": True})
    await group.add_participant("1203630@g.us", "201001234567")
    await group.remove_participant("1203630@g.us", "201001234567@c.us")
    api.groups.addGroupParticipant.assert_called_once_with("1203630@g.us", "201001234567@c.us")
    api.groups.removeGroupParticipant.assert_called_once_with(
        "1203630@g.us", "201001234567@c.us"
    )


@pytest.mark.asyncio
async def test_add_participant_false_flag_is_an_error(api):
    api.groups.addGroupParticipant.return_value = _resp({"addParticipant": False})
    with pytest.raises(ValueError):
        await group.add_participant("1203630@g.us", "201001234567")


@pytest.mark.asyncio
async def test_rename_group(api):
    api.groups.updateGroupName.return_value = _resp({"updateGroupName": True})
    out = await group.update_group_settings("1203630@g.us", name="New")
    api.groups.updateGroupName.assert_called_once_with("1203630@g.us", "New")
    assert out["updated_fields"] == ["name"]


# --- session -----------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resp, ok",
    [
        (_resp({"stateInstance": "authorized"}), True),
        (_resp({"stateInstance": "notAuthorized"}), False),
        (_resp(code=401, error="Unauthorized"), False),
    ],
)
async def test_open_session_checks_credentials(monkeypatch, resp, ok):
    monkeypatch.setenv("GREENAPI_ID_INSTANCE", "1101000001")
    monkeypatch.setenv("GREENAPI_API_TOKEN", "token")
    manager = auth.AuthManager()
    with patch.object(auth, "GreenApi") as green:
        green.return_value.account.getStateInstance.return_value = resp
        success, _ = await manager.open_session()
    assert success is ok
    assert manager.is_authenticated() is ok
