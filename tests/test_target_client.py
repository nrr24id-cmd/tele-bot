import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from sn_forwarder.target_client import TelethonTargetClient


def make_client(reply_text: str = "Sukses", raise_on_get_response=None):
    mock_response = MagicMock()
    mock_response.raw_text = reply_text

    mock_button_msg = MagicMock()
    mock_button_msg.click = AsyncMock()

    mock_conv = AsyncMock()
    mock_conv.send_message = AsyncMock()
    if raise_on_get_response:
        mock_conv.get_response = AsyncMock(side_effect=raise_on_get_response)
    else:
        mock_conv.get_response = AsyncMock(side_effect=[mock_button_msg, mock_response])
    mock_conv.__aenter__ = AsyncMock(return_value=mock_conv)
    mock_conv.__aexit__ = AsyncMock(return_value=False)

    mock_telethon = AsyncMock()
    mock_telethon.get_entity = AsyncMock(return_value=MagicMock())
    mock_telethon.conversation = MagicMock(return_value=mock_conv)

    return mock_telethon


@pytest.mark.asyncio
async def test_sends_three_steps():
    mock_response = MagicMock()
    mock_response.raw_text = "Aktivasi berhasil"

    mock_button_msg = MagicMock()
    mock_button_msg.click = AsyncMock()

    mock_conv = AsyncMock()
    mock_conv.send_message = AsyncMock()
    mock_conv.get_response = AsyncMock(side_effect=[mock_button_msg, mock_response])
    mock_conv.__aenter__ = AsyncMock(return_value=mock_conv)
    mock_conv.__aexit__ = AsyncMock(return_value=False)

    mock_telethon = AsyncMock()
    mock_telethon.get_entity = AsyncMock(return_value=MagicMock())
    mock_telethon.conversation = MagicMock(return_value=mock_conv)

    tc = TelethonTargetClient(mock_telethon, "@bot")

    result = await tc.send_and_wait("Amrr Activator Pro Tool A12+", "SN123", 30.0)

    assert result == "Aktivasi berhasil"
    assert mock_conv.send_message.call_count == 2
    mock_button_msg.click.assert_awaited_once_with(text="Amrr Activator Pro Tool A12+")


@pytest.mark.asyncio
async def test_timeout_raises():
    client = make_client(raise_on_get_response=asyncio.TimeoutError())
    tc = TelethonTargetClient(client, "@bot")

    with pytest.raises(asyncio.TimeoutError):
        await tc.send_and_wait("btn", "SN", 0.01)
