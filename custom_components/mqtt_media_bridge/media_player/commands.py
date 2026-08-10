"""MQTT command handling for media player entities."""

from __future__ import annotations

from collections.abc import Callable
import json
import logging
from typing import Any

from custom_components.mqtt_media_bridge.const import (
    CONF_NEXT_TRACK_TOPIC,
    CONF_PAUSE_TOPIC,
    CONF_PLAY_MEDIA_TOPIC,
    CONF_PLAY_TOPIC,
    CONF_PREVIOUS_TRACK_TOPIC,
    CONF_REPEAT_SET_TOPIC,
    CONF_SEEK_TOPIC,
    CONF_SELECT_SOUND_MODE_TOPIC,
    CONF_SELECT_SOURCE_TOPIC,
    CONF_SHUFFLE_SET_TOPIC,
    CONF_STOP_TOPIC,
    CONF_TURN_OFF_TOPIC,
    CONF_TURN_ON_TOPIC,
    CONF_VOLUME_MUTE_COMMAND_TOPIC,
    CONF_VOLUME_SET_TOPIC,
)
from homeassistant.components import mqtt
from homeassistant.components.media_player.const import RepeatMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


class MqttMediaPlayerCommandsMixin:
    """Publish media player commands to their configured MQTT topics."""

    hass: HomeAssistant
    _config: ConfigType
    _mmb_entry_id: str
    _log_identity: Callable[[], str]

    async def async_media_play(self) -> None:
        """Send a play command to the media player."""
        topic = self._config.get(CONF_PLAY_TOPIC)
        if not topic:
            _LOGGER.warning("Play command called but no play topic configured")
            return
        _LOGGER.debug("🎵 Sending PLAY command to topic: %s", topic)
        _LOGGER.debug("[mmb] %s publish PLAY (topic=%s)", self._log_identity(), topic)
        try:
            await mqtt.async_publish(self.hass, topic, "")
        except Exception:
            _LOGGER.exception("Failed to publish play command to topic %s", topic)

    async def async_media_pause(self) -> None:
        """Send a pause command to the media player."""
        topic = self._config.get(CONF_PAUSE_TOPIC)
        if not topic:
            _LOGGER.warning("Pause command called but no pause topic configured")
            return
        _LOGGER.debug("⏸️ Sending PAUSE command to topic: %s", topic)
        _LOGGER.debug("[mmb] %s publish PAUSE (topic=%s)", self._log_identity(), topic)
        try:
            await mqtt.async_publish(self.hass, topic, "")
        except Exception:
            _LOGGER.exception("Failed to publish pause command to topic %s", topic)

    async def async_media_stop(self) -> None:
        """Send a stop command to the media player."""
        topic = self._config.get(CONF_STOP_TOPIC)
        if not topic:
            _LOGGER.warning("Stop command called but no stop topic configured")
            return
        _LOGGER.debug("⏹️ Sending STOP command to topic: %s", topic)
        _LOGGER.debug("[mmb] %s publish STOP (topic=%s)", self._log_identity(), topic)
        try:
            await mqtt.async_publish(self.hass, topic, "")
        except Exception:
            _LOGGER.exception("Failed to publish stop command to topic %s", topic)

    async def async_media_next_track(self) -> None:
        """Send a next track command to the media player."""
        topic = self._config.get(CONF_NEXT_TRACK_TOPIC)
        if not topic:
            _LOGGER.warning("Next track command called but no next track topic configured")
            return
        _LOGGER.debug("⏭️ Sending NEXT TRACK command to topic: %s", topic)
        _LOGGER.debug("[mmb] %s publish NEXT (topic=%s)", self._log_identity(), topic)
        try:
            await mqtt.async_publish(self.hass, topic, "")
        except Exception:
            _LOGGER.exception("Failed to publish next track command to topic %s", topic)

    async def async_media_previous_track(self) -> None:
        """Send a previous track command to the media player."""
        topic = self._config.get(CONF_PREVIOUS_TRACK_TOPIC)
        if not topic:
            _LOGGER.warning("Previous track command called but no previous track topic configured")
            return
        _LOGGER.debug("⏮️ Sending PREVIOUS TRACK command to topic: %s", topic)
        _LOGGER.debug("[mmb] %s publish PREVIOUS (topic=%s)", self._log_identity(), topic)
        try:
            await mqtt.async_publish(self.hass, topic, "")
        except Exception:
            _LOGGER.exception("Failed to publish previous track command to topic %s", topic)

    async def async_turn_on(self) -> None:
        """Send a turn on command to the media player."""
        topic = self._config.get(CONF_TURN_ON_TOPIC)
        if not topic:
            _LOGGER.warning("Turn on command called but no turn on topic configured")
            return
        _LOGGER.debug("🔌 Sending TURN ON command to topic: %s", topic)
        _LOGGER.debug("[mmb] %s publish TURN_ON (topic=%s)", self._log_identity(), topic)
        try:
            await mqtt.async_publish(self.hass, topic, "")
        except Exception:
            _LOGGER.exception("Failed to publish turn on command to topic %s", topic)

    async def async_turn_off(self) -> None:
        """Send a turn off command to the media player."""
        topic = self._config.get(CONF_TURN_OFF_TOPIC)
        if not topic:
            _LOGGER.warning("Turn off command called but no turn off topic configured")
            return
        _LOGGER.debug("🔌 Sending TURN OFF command to topic: %s", topic)
        _LOGGER.debug("[mmb] %s publish TURN_OFF (topic=%s)", self._log_identity(), topic)
        try:
            await mqtt.async_publish(self.hass, topic, "")
        except Exception:
            _LOGGER.exception("Failed to publish turn off command to topic %s", topic)

    async def async_set_volume_level(self, volume: float) -> None:
        """Send a set volume level command to the media player."""
        topic = self._config.get(CONF_VOLUME_SET_TOPIC)
        if not topic:
            _LOGGER.warning("Set volume level command called but no volume set topic configured")
            return
        payload = str(volume)
        _LOGGER.debug(
            "🔊 Sending SET VOLUME LEVEL command to topic: %s, payload: %s",
            topic,
            payload,
        )
        _LOGGER.debug(
            "[mmb] %s publish VOLUME_SET (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            payload,
        )
        try:
            await mqtt.async_publish(self.hass, topic, payload)
        except Exception:
            _LOGGER.exception("Failed to publish volume level command to topic %s", topic)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send a mute volume command to the media player."""
        topic = self._config.get(CONF_VOLUME_MUTE_COMMAND_TOPIC)
        if not topic:
            _LOGGER.warning("Mute volume command called but no volume mute command topic configured")
            return
        payload = "ON" if mute else "OFF"
        _LOGGER.debug("🔇 Sending MUTE VOLUME command to topic: %s, payload: %s", topic, payload)
        _LOGGER.debug(
            "[mmb] %s publish VOLUME_MUTE (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            payload,
        )
        try:
            await mqtt.async_publish(self.hass, topic, payload)
        except Exception:
            _LOGGER.exception("Failed to publish mute volume command to topic %s", topic)

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Send a play media command to the media player."""
        topic = self._config.get(CONF_PLAY_MEDIA_TOPIC)
        if not topic:
            _LOGGER.warning("Play media command called but no play media topic configured")
            return

        payload_data: dict[str, str | bool] = {
            "media_type": media_type,
            "media_id": media_id,
        }
        enqueue = kwargs.get("enqueue")
        if enqueue is not None:
            payload_data["enqueue"] = getattr(enqueue, "value", str(enqueue))
        announce = kwargs.get("announce")
        if announce is not None:
            payload_data["announce"] = bool(announce)
        payload = json.dumps(payload_data)

        _LOGGER.debug("🎬 Sending PLAY MEDIA command to topic: %s, payload: %s", topic, payload)
        _LOGGER.debug(
            "[mmb] %s publish PLAY_MEDIA (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            payload,
        )
        try:
            await mqtt.async_publish(self.hass, topic, payload)
        except Exception:
            _LOGGER.exception("Failed to publish play media command to topic %s", topic)

    async def async_select_source(self, source: str) -> None:
        """Send a select source command to the media player."""
        topic = self._config.get(CONF_SELECT_SOURCE_TOPIC)
        if not topic:
            _LOGGER.warning("Select source command called but no select source topic configured")
            return
        _LOGGER.debug(
            "📻 Sending SELECT SOURCE command to topic: %s, payload: %s",
            topic,
            source,
        )
        _LOGGER.debug(
            "[mmb] %s publish SELECT_SOURCE (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            source,
        )
        try:
            await mqtt.async_publish(self.hass, topic, source)
        except Exception:
            _LOGGER.exception("Failed to publish select source command to topic %s", topic)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Send a select sound mode command to the media player."""
        topic = self._config.get(CONF_SELECT_SOUND_MODE_TOPIC)
        if not topic:
            _LOGGER.warning("Select sound mode command called but no select sound mode topic configured")
            return
        _LOGGER.debug(
            "🎚️ Sending SELECT SOUND MODE command to topic: %s, payload: %s",
            topic,
            sound_mode,
        )
        _LOGGER.debug(
            "[mmb] %s publish SELECT_SOUND_MODE (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            sound_mode,
        )
        try:
            await mqtt.async_publish(self.hass, topic, sound_mode)
        except Exception:
            _LOGGER.exception(
                "Failed to publish select sound mode command to topic %s",
                topic,
            )

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Send a shuffle command to the media player."""
        topic = self._config.get(CONF_SHUFFLE_SET_TOPIC)
        if not topic:
            _LOGGER.warning("Shuffle command called but no shuffle set topic configured")
            return
        payload = "ON" if shuffle else "OFF"
        _LOGGER.debug("🔀 Sending SHUFFLE command to topic: %s, payload: %s", topic, payload)
        _LOGGER.debug(
            "[mmb] %s publish SHUFFLE_SET (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            payload,
        )
        try:
            await mqtt.async_publish(self.hass, topic, payload)
        except Exception:
            _LOGGER.exception("Failed to publish shuffle command to topic %s", topic)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Send a repeat command to the media player."""
        topic = self._config.get(CONF_REPEAT_SET_TOPIC)
        if not topic:
            _LOGGER.warning("Repeat command called but no repeat set topic configured")
            return
        payload = repeat.value
        _LOGGER.debug("🔁 Sending REPEAT command to topic: %s, payload: %s", topic, payload)
        _LOGGER.debug(
            "[mmb] %s publish REPEAT_SET (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            payload,
        )
        try:
            await mqtt.async_publish(self.hass, topic, payload)
        except Exception:
            _LOGGER.exception("Failed to publish repeat command to topic %s", topic)

    async def async_media_seek(self, position: float) -> None:
        """Send a seek command to the media player."""
        topic = self._config.get(CONF_SEEK_TOPIC)
        if not topic:
            _LOGGER.warning("Seek command called but no seek topic configured")
            return
        payload = str(position)
        _LOGGER.debug("⏩ Sending SEEK command to topic: %s, payload: %s", topic, payload)
        _LOGGER.debug(
            "[mmb] %s publish SEEK (topic=%s, payload=%s)",
            self._log_identity(),
            topic,
            payload,
        )
        try:
            await mqtt.async_publish(self.hass, topic, payload)
        except Exception:
            _LOGGER.exception("Failed to publish seek command to topic %s", topic)
