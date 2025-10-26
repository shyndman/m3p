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
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Mellow MQTT Media component."""
    config_domains = list(config.keys()) if isinstance(config, dict) else []
    _LOGGER.info(
        "[m3p] async_setup invoked (config_domains=%s)", config_domains
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mellow MQTT Media from a config entry."""
    _LOGGER.info(
        "[m3p] async_setup_entry start (entry_id=%s, title=%s, data_keys=%s)",
        entry.entry_id,
        entry.title,
        sorted(entry.data.keys()),
    )

    # Forward the entry setup to the media_player platform
    await hass.config_entries.async_forward_entry_setups(entry, ["media_player"])
    _LOGGER.info(
        "[m3p] Entry forwarded to media_player platform (entry_id=%s)",
        entry.entry_id,
    )

    # If we have a discovery payload, fire the discovery signal after platform is set up
    if "discovery_payload" in entry.data and "discovery_topic" in entry.data:
        _LOGGER.info(
            "[m3p] Replaying stored discovery payload (entry_id=%s, topic=%s)",
            entry.entry_id,
            entry.data["discovery_topic"],
        )

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
        _LOGGER.info(
            "[m3p] Discovery signal dispatched (entry_id=%s, hash=%s)",
            entry.entry_id,
            discovery_hash,
        )

    _LOGGER.info(
        "[m3p] async_setup_entry complete (entry_id=%s)", entry.entry_id
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info(
        "[m3p] async_unload_entry start (entry_id=%s)", entry.entry_id
    )

    # Note: We don't clean up mqtt_data.config here because:
    # 1. It's a shared MQTT structure
    # 2. The entity cleanup happens through the platform unload
    # 3. The MQTT integration manages its own config lifecycle

    unload_success = await hass.config_entries.async_unload_platforms(
        entry, ["media_player"]
    )
    _LOGGER.info(
        "[m3p] async_unload_entry complete (entry_id=%s, success=%s)",
        entry.entry_id,
        unload_success,
    )
    return unload_success
