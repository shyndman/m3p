"""Shared fixtures for MQTT Media Bridge tests."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant_custom_component.typing import MqttMockPahoClient

from custom_components.mqtt_media_bridge.const import DOMAIN
from homeassistant.components.mqtt.const import DOMAIN as MQTT_DOMAIN
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom integrations in every test."""


@pytest.fixture
async def mqtt_media_bridge_setup(
    hass: HomeAssistant,
    verify_cleanup: None,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: object,
) -> AsyncGenerator[None]:
    """Set up MQTT and unload bridge resources before cleanup verification."""
    mock_socket = MagicMock()
    mock_socket.fileno.return_value = -1

    def close_mock_socket() -> None:
        """Mirror Paho's socket-close callback when the mocked client disconnects."""
        mqtt_client_mock.on_socket_close(mqtt_client_mock, None, mock_socket)

    mqtt_client_mock.disconnect.side_effect = close_mock_socket
    yield

    for entry in hass.config_entries.async_entries(DOMAIN):
        assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    for entry in hass.config_entries.async_entries(MQTT_DOMAIN):
        assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
