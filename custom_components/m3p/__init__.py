"""The Mellow MQTT Media Play (Mellow) integration."""

from __future__ import annotations

import logging

from homeassistant.components.mqtt.const import (
    ATTR_DISCOVERY_HASH,
    ATTR_DISCOVERY_PAYLOAD,
    ATTR_DISCOVERY_TOPIC,
)
from homeassistant.components.mqtt.discovery import (
    MQTT_DISCOVERY_NEW,
    MQTTDiscoveryPayload,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

DOMAIN = "Mellow"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mellow MQTT Media component."""
    _LOGGER.debug("Mellow MQTT integration async_setup called")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mellow MQTT Media from a config entry."""
    _LOGGER.debug(
        "Mellow MQTT Media async_setup_entry called with entry: %s", entry.entry_id
    )

    # Forward the entry setup to the media_player platform
    await hass.config_entries.async_forward_entry_setups(entry, ["media_player"])

    # If we have a discovery payload, fire the discovery signal after platform is set up
    if "discovery_payload" in entry.data and "discovery_topic" in entry.data:
        _LOGGER.debug("Firing MQTT discovery signal for entry: %s", entry.entry_id)

        # Create the discovery payload object that MQTT expects
        # MQTTDiscoveryPayload is a dict subclass, initialized with the JSON payload
        discovery_payload = MQTTDiscoveryPayload(entry.data["discovery_payload"])

        # Extract node_id and object_id from the discovery topic
        # Topic format: homeassistant/media_player/{node_id}/{object_id}/config
        topic_parts = entry.data["discovery_topic"].split("/")
        node_id = topic_parts[2] if len(topic_parts) > 2 else ""
        object_id = topic_parts[3] if len(topic_parts) > 3 else "mqtt"

        # Create discovery_id (same logic as in discovery.py line 496)
        discovery_id = f"{node_id} {object_id}" if node_id else object_id
        discovery_hash = ("media_player", discovery_id)

        # Set the discovery_data attribute (as done in discovery.py line 500-504)

        discovery_payload.discovery_data = {
            ATTR_DISCOVERY_HASH: discovery_hash,
            ATTR_DISCOVERY_PAYLOAD: discovery_payload,
            ATTR_DISCOVERY_TOPIC: entry.data["discovery_topic"],
        }

        # Fire the discovery signal that the media_player platform is listening for
        async_dispatcher_send(
            hass, MQTT_DISCOVERY_NEW.format("media_player", "mqtt"), discovery_payload
        )
        _LOGGER.debug("Discovery signal fired for: %s", entry.entry_id)

    _LOGGER.debug("Mellow MQTT Media setup completed for entry: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(
        "Mellow MQTT Media async_unload_entry called for entry: %s", entry.entry_id
    )

    # Note: We don't clean up mqtt_data.config here because:
    # 1. It's a shared MQTT structure
    # 2. The entity cleanup happens through the platform unload
    # 3. The MQTT integration manages its own config lifecycle

    return await hass.config_entries.async_unload_platforms(entry, ["media_player"])
