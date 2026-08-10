"""Set up MQTT Media Bridge media player entities."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import mqtt
from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.mqtt.const import ATTR_DISCOVERY_HASH, ATTR_DISCOVERY_PAYLOAD, ATTR_DISCOVERY_TOPIC
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import DISCOVERY_SCHEMA, MqttMediaPlayer

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT media player from a config entry."""
    _LOGGER.debug(
        "[mmb] media_player.async_setup_entry called (entry_id=%s)",
        config_entry.entry_id,
    )
    mqtt_ready = await mqtt.async_wait_for_mqtt_client(hass)
    if not mqtt_ready:
        _LOGGER.warning(
            "[mmb] MQTT client not ready inside media_player platform (entry_id=%s)",
            config_entry.entry_id,
        )
        return
    _LOGGER.debug(
        "[mmb] MQTT client ready for media_player platform (entry_id=%s)",
        config_entry.entry_id,
    )

    discovery_payload = config_entry.data.get("discovery_payload", {})
    discovery_topic = config_entry.data.get("discovery_topic")

    if not discovery_payload:
        _LOGGER.error(
            "[mmb] No discovery payload in config entry (entry_id=%s)",
            config_entry.entry_id,
        )
        return

    try:
        config = DISCOVERY_SCHEMA(discovery_payload)
    except vol.Invalid as err:
        _LOGGER.error(
            "[mmb] Invalid discovery payload (entry_id=%s, error=%s)",
            config_entry.entry_id,
            err,
        )
        return

    topic_parts = discovery_topic.split("/") if discovery_topic else []
    node_id = topic_parts[2] if len(topic_parts) > 2 else ""
    object_id = topic_parts[3] if len(topic_parts) > 3 else "mqtt"
    discovery_id = f"{node_id} {object_id}" if node_id else object_id
    discovery_hash = (MEDIA_PLAYER_DOMAIN, discovery_id)

    discovery_data = {
        ATTR_DISCOVERY_HASH: discovery_hash,
        ATTR_DISCOVERY_PAYLOAD: discovery_payload,
        ATTR_DISCOVERY_TOPIC: discovery_topic,
    }

    _LOGGER.debug(
        "[mmb] Creating entity directly (entry_id=%s, discovery_hash=%s)",
        config_entry.entry_id,
        discovery_hash,
    )
    async_add_entities([MqttMediaPlayer(hass, config, config_entry, discovery_data)])
