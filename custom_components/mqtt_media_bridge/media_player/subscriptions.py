"""MQTT state subscriptions for media player entities."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
import re
from typing import cast

from custom_components.mqtt_media_bridge.const import (
    CONF_MEDIA_ALBUM_NAME_TOPIC,
    CONF_MEDIA_ARTIST_TOPIC,
    CONF_MEDIA_DURATION_TOPIC,
    CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC,
    CONF_MEDIA_IMAGE_URL_TOPIC,
    CONF_MEDIA_POSITION_TOPIC,
    CONF_MEDIA_TITLE_TOPIC,
    CONF_REPEAT_STATE_TOPIC,
    CONF_SHUFFLE_STATE_TOPIC,
    CONF_VOLUME_LEVEL_TOPIC,
    CONF_VOLUME_MUTE_STATE_TOPIC,
)
from homeassistant.components.media_player.const import MediaPlayerState, RepeatMode
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.mqtt.subscription import EntitySubscription, async_subscribe_topics_internal
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

DATA_URI_IMAGE_PATTERN = re.compile(r"^data:image/[^;]+;base64")


class MqttMediaPlayerSubscriptionsMixin:
    """Decode MQTT state messages and update a media player entity."""

    add_subscription: Callable[[str, Callable[[ReceiveMessage], None], set[str]], bool]
    async_write_ha_state: Callable[[], None]
    entity_id: str
    hass: HomeAssistant
    _config: ConfigType
    _log_identity: Callable[[], str]
    _sub_state: dict[str, EntitySubscription]
    _attr_available: bool
    _attr_is_volume_muted: bool | None
    _attr_media_album_name: str | None
    _attr_media_artist: str | None
    _attr_media_duration: int | None
    _attr_media_image_remotely_accessible: bool
    _attr_media_image_url: str | None
    _attr_media_position: int | None
    _attr_media_position_updated_at: datetime | None
    _attr_media_title: str | None
    _attr_repeat: RepeatMode | str | None
    _attr_shuffle: bool | None
    _attr_state: MediaPlayerState | None
    _attr_volume_level: float | None

    def _decode_payload(self, payload) -> str | None:
        """Decode MQTT payload to string."""
        if payload is None:
            return None
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        if isinstance(payload, bytearray):
            return payload.decode("utf-8")
        if isinstance(payload, memoryview):
            return payload.tobytes().decode("utf-8")
        return str(payload)

    def _decode_bool_payload(self, payload: str | None) -> bool | None:
        """Decode a string payload into a boolean state."""
        if payload is None:
            return None
        normalized = payload.strip().lower()
        if normalized == "":
            return None
        if normalized in ("true", "1", "yes", "on"):
            return True
        if normalized in ("false", "0", "no", "off"):
            return False
        _LOGGER.warning("Unexpected boolean payload received: %r. Ignoring.", payload)
        return None

    def _is_data_uri_image(self, url: str | None) -> bool:
        """Check if URL is an image data URI."""
        if not url:
            return False
        return DATA_URI_IMAGE_PATTERN.match(url) is not None

    def _truncate_url_for_logging(self, url: str | None, max_length: int = 100) -> str:
        """Truncate URL for safe logging, especially for data URIs."""
        if not url:
            return "None"
        if len(url) <= max_length:
            return url
        # For data URIs, show the prefix and indicate truncation
        if self._is_data_uri_image(url):
            prefix_match = DATA_URI_IMAGE_PATTERN.match(url)
            if prefix_match:
                prefix = prefix_match.group(0)  # e.g., "data:image/png;base64"
                return f"{prefix}...[truncated {len(url)} chars total]"
        # For regular URLs, just truncate
        return f"{url[:max_length]}...[truncated {len(url)} chars total]"

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        _LOGGER.debug(
            "MqttMediaPlayer._prepare_subscribe_topics called for entity: %s",
            self.entity_id,
        )
        _LOGGER.debug("Config keys available: %s", list(self._config.keys()))

        # Log all available topics from config
        all_topic_configs = [
            (CONF_STATE_TOPIC, "state"),
            (CONF_VOLUME_LEVEL_TOPIC, "volume_level"),
            (CONF_VOLUME_MUTE_STATE_TOPIC, "volume_mute_state"),
            (CONF_SHUFFLE_STATE_TOPIC, "shuffle_state"),
            (CONF_REPEAT_STATE_TOPIC, "repeat_state"),
            (CONF_MEDIA_TITLE_TOPIC, "media_title"),
            (CONF_MEDIA_ARTIST_TOPIC, "media_artist"),
            (CONF_MEDIA_ALBUM_NAME_TOPIC, "media_album"),
            (CONF_MEDIA_DURATION_TOPIC, "media_duration"),
            (CONF_MEDIA_POSITION_TOPIC, "media_position"),
            (CONF_MEDIA_IMAGE_URL_TOPIC, "media_image_url"),
            (
                CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC,
                "media_image_remotely_accessible",
            ),
        ]

        _LOGGER.debug("=== ALL TOPIC CONFIGURATIONS ===")
        for topic_key, topic_name in all_topic_configs:
            topic_value = self._config.get(topic_key)
            _LOGGER.debug("  %s (%s): %s", topic_name, topic_key, topic_value)
        _LOGGER.debug("=== END TOPIC CONFIGURATIONS ===")

        configured_topics = {
            topic_name: self._config.get(topic_key)
            for topic_key, topic_name in all_topic_configs
            if self._config.get(topic_key)
        }
        _LOGGER.debug(
            "[mmb] %s preparing MQTT subscriptions (configured_topics=%s)",
            self._log_identity(),
            configured_topics or "<none>",
        )
        self._prepare_playback_subscriptions()
        self._prepare_mode_subscriptions()
        self._prepare_media_info_subscriptions()
        self._prepare_timing_subscriptions()
        self._prepare_image_subscriptions()

        # Final summary
        _LOGGER.debug("🎯 SUBSCRIPTION SETUP COMPLETED for entity: %s", self.entity_id)
        _LOGGER.debug(
            "📊 Total subscriptions object state: %s",
            len(getattr(self, "_subscriptions", {})),
        )

    def _prepare_playback_subscriptions(self) -> None:
        """Prepare state, volume, and mute topic subscriptions."""

        @callback
        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            _LOGGER.debug("🔥 STATE MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)

            state_str = self._decode_payload(msg.payload)
            if not state_str:
                _LOGGER.debug("Empty state payload received, ignoring")
                return

            # Normalize to lowercase once
            state_str = state_str.lower()

            # Handle HA special cases first
            if state_str == STATE_UNAVAILABLE:
                self._attr_available = False
                self.async_write_ha_state()
                _LOGGER.debug("✅ Marked entity unavailable due to MQTT payload")
                return

            self._attr_available = True

            if state_str == STATE_UNKNOWN:
                self._attr_state = cast(MediaPlayerState, STATE_UNKNOWN)
                self.async_write_ha_state()
                _LOGGER.debug("✅ State marked as unknown from MQTT payload")
                return

            try:
                new_state = MediaPlayerState(state_str)
            except ValueError:
                _LOGGER.warning("Invalid media player state received: %s. Ignoring.", state_str)
                return

            self._attr_state = new_state
            self.async_write_ha_state()
            _LOGGER.debug("✅ State updated to: %s", self._attr_state)
            _LOGGER.debug(
                "[mmb] %s state update (topic=%s, payload=%s, state=%s)",
                self._log_identity(),
                msg.topic,
                state_str,
                self._attr_state,
            )

        state_topic = self._config.get(CONF_STATE_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO STATE TOPIC: %s", state_topic)
        if state_topic:
            success = self.add_subscription(CONF_STATE_TOPIC, state_message_received, {"_attr_state"})
            # Defensive: add_subscription is from HA's MqttEntity and currently can't
            # fail if topic is truthy, but we guard against future API changes.
            if not success:
                _LOGGER.error("Failed to subscribe to state topic: %s", state_topic)
                raise RuntimeError(f"Failed to subscribe to state topic: {state_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to state topic=%s",
                self._log_identity(),
                state_topic,
            )
        else:
            _LOGGER.debug("❌ No state topic configured, skipping state subscription")

        @callback
        def volume_level_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT volume level messages."""
            _LOGGER.debug("🔊 VOLUME MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)

            payload_str = self._decode_payload(msg.payload)
            if not payload_str:
                _LOGGER.debug("Empty volume payload received, ignoring")
                return

            try:
                volume = float(payload_str)
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid volume level format received: %s, error: %s",
                    msg.payload,
                    e,
                )
                return

            # Validate volume is in range 0.0 to 1.0
            if not 0.0 <= volume <= 1.0:
                _LOGGER.warning("Volume level out of range: %s. Must be between 0.0 and 1.0", volume)
                return

            self._attr_volume_level = volume
            self.async_write_ha_state()
            _LOGGER.debug("✅ Volume updated to: %s", self._attr_volume_level)
            _LOGGER.debug(
                "[mmb] %s volume update (topic=%s, payload=%s, volume=%.3f)",
                self._log_identity(),
                msg.topic,
                payload_str,
                self._attr_volume_level,
            )

        volume_topic = self._config.get(CONF_VOLUME_LEVEL_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO VOLUME TOPIC: %s", volume_topic)
        if volume_topic:
            success = self.add_subscription(CONF_VOLUME_LEVEL_TOPIC, volume_level_received, {"_attr_volume_level"})
            if not success:
                _LOGGER.error("Failed to subscribe to volume topic: %s", volume_topic)
                raise RuntimeError(f"Failed to subscribe to volume topic: {volume_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to volume topic=%s",
                self._log_identity(),
                volume_topic,
            )
        else:
            _LOGGER.debug("❌ No volume topic configured, skipping volume subscription")

        @callback
        def volume_mute_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT mute state messages."""
            _LOGGER.debug("🔇 MUTE MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)

            payload_str = self._decode_payload(msg.payload)
            muted = self._decode_bool_payload(payload_str)
            if muted is None:
                _LOGGER.debug("Empty mute payload received, ignoring")
                return

            self._attr_is_volume_muted = muted
            self.async_write_ha_state()
            _LOGGER.debug("✅ Muted updated to: %s", self._attr_is_volume_muted)
            _LOGGER.debug(
                "[mmb] %s mute update (topic=%s, payload=%s, muted=%s)",
                self._log_identity(),
                msg.topic,
                payload_str,
                self._attr_is_volume_muted,
            )

        mute_state_topic = self._config.get(CONF_VOLUME_MUTE_STATE_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO MUTE STATE TOPIC: %s", mute_state_topic)
        if mute_state_topic:
            success = self.add_subscription(
                CONF_VOLUME_MUTE_STATE_TOPIC,
                volume_mute_received,
                {"_attr_is_volume_muted"},
            )
            if not success:
                _LOGGER.error("Failed to subscribe to mute state topic: %s", mute_state_topic)
                raise RuntimeError(f"Failed to subscribe to mute state topic: {mute_state_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to mute_state topic=%s",
                self._log_identity(),
                mute_state_topic,
            )
        else:
            _LOGGER.debug("❌ No mute state topic configured, skipping mute subscription")

    def _prepare_mode_subscriptions(self) -> None:
        """Prepare shuffle and repeat topic subscriptions."""

        @callback
        def shuffle_state_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT shuffle state messages."""
            _LOGGER.debug("🔀 SHUFFLE MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)

            payload_str = self._decode_payload(msg.payload)
            shuffle = self._decode_bool_payload(payload_str)
            if shuffle is None:
                _LOGGER.debug("Empty shuffle payload received, ignoring")
                return

            self._attr_shuffle = shuffle
            self.async_write_ha_state()
            _LOGGER.debug("✅ Shuffle updated to: %s", self._attr_shuffle)
            _LOGGER.debug(
                "[mmb] %s shuffle update (topic=%s, payload=%s, shuffle=%s)",
                self._log_identity(),
                msg.topic,
                payload_str,
                self._attr_shuffle,
            )

        shuffle_state_topic = self._config.get(CONF_SHUFFLE_STATE_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO SHUFFLE STATE TOPIC: %s", shuffle_state_topic)
        if shuffle_state_topic:
            success = self.add_subscription(
                CONF_SHUFFLE_STATE_TOPIC,
                shuffle_state_received,
                {"_attr_shuffle"},
            )
            if not success:
                _LOGGER.error(
                    "Failed to subscribe to shuffle state topic: %s",
                    shuffle_state_topic,
                )
                raise RuntimeError(f"Failed to subscribe to shuffle state topic: {shuffle_state_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to shuffle_state topic=%s",
                self._log_identity(),
                shuffle_state_topic,
            )
        else:
            _LOGGER.debug("❌ No shuffle state topic configured, skipping shuffle subscription")

        @callback
        def repeat_state_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT repeat state messages."""
            _LOGGER.debug("🔁 REPEAT MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)

            payload_str = self._decode_payload(msg.payload)
            if payload_str is None:
                _LOGGER.debug("Empty repeat payload received, ignoring")
                return

            try:
                repeat = RepeatMode(payload_str.lower())
            except ValueError:
                _LOGGER.warning("Invalid repeat mode received: %s. Ignoring.", payload_str)
                return

            self._attr_repeat = repeat
            self.async_write_ha_state()
            _LOGGER.debug("✅ Repeat updated to: %s", self._attr_repeat)
            _LOGGER.debug(
                "[mmb] %s repeat update (topic=%s, payload=%s, repeat=%s)",
                self._log_identity(),
                msg.topic,
                payload_str,
                self._attr_repeat,
            )

        repeat_state_topic = self._config.get(CONF_REPEAT_STATE_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO REPEAT STATE TOPIC: %s", repeat_state_topic)
        if repeat_state_topic:
            success = self.add_subscription(
                CONF_REPEAT_STATE_TOPIC,
                repeat_state_received,
                {"_attr_repeat"},
            )
            if not success:
                _LOGGER.error("Failed to subscribe to repeat state topic: %s", repeat_state_topic)
                raise RuntimeError(f"Failed to subscribe to repeat state topic: {repeat_state_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to repeat_state topic=%s",
                self._log_identity(),
                repeat_state_topic,
            )
        else:
            _LOGGER.debug("❌ No repeat state topic configured, skipping repeat subscription")

    def _prepare_media_info_subscriptions(self) -> None:
        """Prepare media title, artist, and album topic subscriptions."""

        @callback
        def media_title_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media title messages."""
            _LOGGER.debug("🎵 TITLE MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)
            self._attr_media_title = self._decode_payload(msg.payload)
            self.async_write_ha_state()
            _LOGGER.debug(
                "[mmb] %s title update (topic=%s, title=%s)",
                self._log_identity(),
                msg.topic,
                self._attr_media_title,
            )

        title_topic = self._config.get(CONF_MEDIA_TITLE_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO TITLE TOPIC: %s", title_topic)
        if title_topic:
            success = self.add_subscription(CONF_MEDIA_TITLE_TOPIC, media_title_received, {"_attr_media_title"})
            if not success:
                _LOGGER.error("Failed to subscribe to title topic: %s", title_topic)
                raise RuntimeError(f"Failed to subscribe to title topic: {title_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to title topic=%s",
                self._log_identity(),
                title_topic,
            )
        else:
            _LOGGER.debug("❌ No title topic configured, skipping title subscription")

        @callback
        def media_artist_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media artist messages."""
            _LOGGER.debug("🎤 ARTIST MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)
            self._attr_media_artist = self._decode_payload(msg.payload)
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media artist updated to: %s", self._attr_media_artist)
            _LOGGER.debug(
                "[mmb] %s artist update (topic=%s, artist=%s)",
                self._log_identity(),
                msg.topic,
                self._attr_media_artist,
            )

        artist_topic = self._config.get(CONF_MEDIA_ARTIST_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO ARTIST TOPIC: %s", artist_topic)
        if artist_topic:
            success = self.add_subscription(CONF_MEDIA_ARTIST_TOPIC, media_artist_received, {"_attr_media_artist"})
            if not success:
                _LOGGER.error("Failed to subscribe to artist topic: %s", artist_topic)
                raise RuntimeError(f"Failed to subscribe to artist topic: {artist_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to artist topic=%s",
                self._log_identity(),
                artist_topic,
            )
        else:
            _LOGGER.debug("❌ No artist topic configured, skipping artist subscription")

        @callback
        def media_album_name_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media album name messages."""
            _LOGGER.debug("💿 ALBUM MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)
            self._attr_media_album_name = self._decode_payload(msg.payload)
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media album updated to: %s", self._attr_media_album_name)
            _LOGGER.debug(
                "[mmb] %s album update (topic=%s, album=%s)",
                self._log_identity(),
                msg.topic,
                self._attr_media_album_name,
            )

        album_topic = self._config.get(CONF_MEDIA_ALBUM_NAME_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO ALBUM TOPIC: %s", album_topic)
        if album_topic:
            success = self.add_subscription(
                CONF_MEDIA_ALBUM_NAME_TOPIC,
                media_album_name_received,
                {"_attr_media_album_name"},
            )
            if not success:
                _LOGGER.error("Failed to subscribe to album topic: %s", album_topic)
                raise RuntimeError(f"Failed to subscribe to album topic: {album_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to album topic=%s",
                self._log_identity(),
                album_topic,
            )
        else:
            _LOGGER.debug("❌ No album topic configured, skipping album subscription")

    def _prepare_timing_subscriptions(self) -> None:
        """Prepare media duration and position topic subscriptions."""

        @callback
        def media_duration_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media duration messages."""
            _LOGGER.debug("⏱️ DURATION MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)

            payload_str = self._decode_payload(msg.payload)
            if not payload_str:
                _LOGGER.debug("Empty duration payload received, ignoring")
                return

            try:
                duration = int(payload_str)
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid media duration format received: %s, error: %s",
                    msg.payload,
                    e,
                )
                return

            # Validate duration is non-negative
            if duration < 0:
                _LOGGER.warning("Media duration cannot be negative: %s", duration)
                return

            self._attr_media_duration = duration
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media duration updated to: %s", self._attr_media_duration)
            _LOGGER.debug(
                "[mmb] %s duration update (topic=%s, payload=%s, duration=%s)",
                self._log_identity(),
                msg.topic,
                payload_str,
                self._attr_media_duration,
            )

        duration_topic = self._config.get(CONF_MEDIA_DURATION_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO DURATION TOPIC: %s", duration_topic)
        if duration_topic:
            success = self.add_subscription(
                CONF_MEDIA_DURATION_TOPIC,
                media_duration_received,
                {"_attr_media_duration"},
            )
            if not success:
                _LOGGER.error("Failed to subscribe to duration topic: %s", duration_topic)
                raise RuntimeError(f"Failed to subscribe to duration topic: {duration_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to duration topic=%s",
                self._log_identity(),
                duration_topic,
            )
        else:
            _LOGGER.debug("❌ No duration topic configured, skipping duration subscription")

        @callback
        def media_position_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media position messages."""
            _LOGGER.debug("⏲️ POSITION MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload)

            payload_str = self._decode_payload(msg.payload)
            if not payload_str:
                _LOGGER.debug("Empty position payload received, ignoring")
                return

            try:
                position = int(payload_str)
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid media position format received: %s, error: %s",
                    msg.payload,
                    e,
                )
                return

            # Validate position is non-negative
            if position < 0:
                _LOGGER.warning("Media position cannot be negative: %s", position)
                return

            self._attr_media_position = position
            self._attr_media_position_updated_at = utcnow()
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media position updated to: %s", self._attr_media_position)
            _LOGGER.debug(
                "[mmb] %s position update (topic=%s, payload=%s, position=%s)",
                self._log_identity(),
                msg.topic,
                payload_str,
                self._attr_media_position,
            )

        position_topic = self._config.get(CONF_MEDIA_POSITION_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO POSITION TOPIC: %s", position_topic)
        if position_topic:
            success = self.add_subscription(
                CONF_MEDIA_POSITION_TOPIC,
                media_position_received,
                {"_attr_media_position"},
            )
            if not success:
                _LOGGER.error("Failed to subscribe to position topic: %s", position_topic)
                raise RuntimeError(f"Failed to subscribe to position topic: {position_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to position topic=%s",
                self._log_identity(),
                position_topic,
            )
        else:
            _LOGGER.debug("❌ No position topic configured, skipping position subscription")

    def _prepare_image_subscriptions(self) -> None:
        """Prepare media image topic subscriptions."""

        @callback
        def media_image_url_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media image url messages."""
            payload_for_log = self._truncate_url_for_logging(self._decode_payload(msg.payload))
            _LOGGER.debug(
                "🖼️ IMAGE URL MESSAGE RECEIVED on topic %s: %s",
                msg.topic,
                payload_for_log,
            )
            image_url = self._decode_payload(msg.payload)
            self._attr_media_image_url = image_url

            # Auto-detect data URIs and mark them as remotely accessible
            if self._is_data_uri_image(image_url):
                self._attr_media_image_remotely_accessible = True
                _LOGGER.debug("📊 Detected data URI image, setting remotely_accessible=True")

            self.async_write_ha_state()
            url_for_log = self._truncate_url_for_logging(self._attr_media_image_url)
            _LOGGER.debug("✅ Media image URL updated to: %s", url_for_log)
            _LOGGER.debug(
                "[mmb] %s image_url update (topic=%s, url=%s)",
                self._log_identity(),
                msg.topic,
                url_for_log,
            )

        image_url_topic = self._config.get(CONF_MEDIA_IMAGE_URL_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO IMAGE URL TOPIC: %s", image_url_topic)
        if image_url_topic:
            success = self.add_subscription(
                CONF_MEDIA_IMAGE_URL_TOPIC,
                media_image_url_received,
                {"_attr_media_image_url"},
            )
            if not success:
                _LOGGER.error("Failed to subscribe to image URL topic: %s", image_url_topic)
                raise RuntimeError(f"Failed to subscribe to image URL topic: {image_url_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to image_url topic=%s",
                self._log_identity(),
                image_url_topic,
            )
        else:
            _LOGGER.debug("❌ No image URL topic configured, skipping image URL subscription")

        @callback
        def media_image_remotely_accessible_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media image remotely accessible messages."""
            _LOGGER.debug(
                "🌐 IMAGE REMOTELY ACCESSIBLE MESSAGE RECEIVED on topic %s: %s",
                msg.topic,
                msg.payload,
            )
            payload_str = self._decode_payload(msg.payload)
            # Convert string payload to boolean
            if payload_str is not None:
                self._attr_media_image_remotely_accessible = payload_str.lower() in (
                    "true",
                    "1",
                    "yes",
                    "on",
                )
                self.async_write_ha_state()
                _LOGGER.debug(
                    "✅ Media image remotely accessible updated to: %s",
                    self._attr_media_image_remotely_accessible,
                )
                _LOGGER.debug(
                    "[mmb] %s image_accessible update (topic=%s, payload=%s, accessible=%s)",
                    self._log_identity(),
                    msg.topic,
                    payload_str,
                    self._attr_media_image_remotely_accessible,
                )

        image_accessible_topic = self._config.get(CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC)
        _LOGGER.debug(
            "📡 SUBSCRIBING TO IMAGE REMOTELY ACCESSIBLE TOPIC: %s",
            image_accessible_topic,
        )
        if image_accessible_topic:
            success = self.add_subscription(
                CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC,
                media_image_remotely_accessible_received,
                {"_attr_media_image_remotely_accessible"},
            )
            if not success:
                _LOGGER.error(
                    "Failed to subscribe to image accessible topic: %s",
                    image_accessible_topic,
                )
                raise RuntimeError(f"Failed to subscribe to image accessible topic: {image_accessible_topic}")
            _LOGGER.debug(
                "[mmb] %s subscribed to image_accessible topic=%s",
                self._log_identity(),
                image_accessible_topic,
            )
        else:
            _LOGGER.debug("❌ No image remotely accessible topic configured, skipping subscription")

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        _LOGGER.debug("🔌 Actually subscribing to MQTT topics for entity: %s", self.entity_id)
        async_subscribe_topics_internal(self.hass, self._sub_state)
        _LOGGER.debug("✅ MQTT subscription completed for entity: %s", self.entity_id)
        _LOGGER.debug(
            "[mmb] %s MQTT topic subscription batch complete (subscriptions=%s)",
            self._log_identity(),
            list(getattr(self, "_subscriptions", {}).keys()),
        )
