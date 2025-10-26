"""Support for Mellow MQTT Media Players."""

from __future__ import annotations

import logging
import re
import voluptuous as vol
from homeassistant.components import media_player, mqtt
from homeassistant.components.media_player import (
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.components.media_player.const import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC,
)
from homeassistant.components.mqtt.config import MQTT_RO_SCHEMA
from homeassistant.components.mqtt.entity import (
    MqttEntity,
    async_setup_entity_entry_helper,
)
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.mqtt.schemas import MQTT_ENTITY_COMMON_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from custom_components.m3p.const import (
    CONF_MEDIA_ALBUM_NAME_TOPIC,
    CONF_MEDIA_ARTIST_TOPIC,
    CONF_MEDIA_DURATION_TOPIC,
    CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC,
    CONF_MEDIA_IMAGE_URL_TOPIC,
    CONF_MEDIA_POSITION_TOPIC,
    CONF_MEDIA_TITLE_TOPIC,
    CONF_NEXT_TRACK_TOPIC,
    CONF_PAUSE_TOPIC,
    CONF_PLAY_TOPIC,
    CONF_PREVIOUS_TRACK_TOPIC,
    CONF_SEEK_TOPIC,
    CONF_STOP_TOPIC,
    CONF_VOLUME_LEVEL_TOPIC,
    CONF_VOLUME_MUTE_TOPIC,
    CONF_VOLUME_SET_TOPIC,
    CONF_VOLUME_STEP,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

# Pattern to detect image data URIs
DATA_URI_IMAGE_PATTERN = re.compile(r"^data:image/[^;]+;base64")


PLATFORM_SCHEMA_MODERN = MQTT_RO_SCHEMA.extend(
    {
        # Attributes
        vol.Optional(CONF_MEDIA_ALBUM_NAME_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_ARTIST_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_DURATION_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_IMAGE_URL_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_POSITION_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_TITLE_TOPIC): cv.string,
        vol.Optional(CONF_STATE_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_LEVEL_TOPIC): cv.string,
        # Commands
        vol.Optional(CONF_NEXT_TRACK_TOPIC): cv.string,
        vol.Optional(CONF_PAUSE_TOPIC): cv.string,
        vol.Optional(CONF_PLAY_TOPIC): cv.string,
        vol.Optional(CONF_PREVIOUS_TRACK_TOPIC): cv.string,
        vol.Optional(CONF_SEEK_TOPIC): cv.string,
        vol.Optional(CONF_STOP_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_MUTE_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_SET_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_STEP): vol.Coerce(float),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MQTT media player through YAML and through MQTT discovery."""
    _LOGGER.info(
        "[m3p] media_player.async_setup_entry called (entry_id=%s)",
        config_entry.entry_id,
    )
    mqtt_ready = await mqtt.async_wait_for_mqtt_client(hass)
    if not mqtt_ready:
        _LOGGER.warning(
            "[m3p] MQTT client not ready inside media_player platform (entry_id=%s)",
            config_entry.entry_id,
        )
        return
    _LOGGER.info(
        "[m3p] MQTT client ready for media_player platform (entry_id=%s)",
        config_entry.entry_id,
    )
    async_setup_entity_entry_helper(
        hass,
        entry=config_entry,
        entity_class=MqttMediaPlayer,
        domain=MEDIA_PLAYER_DOMAIN,
        async_add_entities=async_add_entities,
        discovery_schema=DISCOVERY_SCHEMA,
        platform_schema_modern=PLATFORM_SCHEMA_MODERN,
    )


class MqttMediaPlayer(MqttEntity, MediaPlayerEntity):
    """Representation of a MQTT media player."""

    _default_name = DEFAULT_NAME
    _entity_id_format = media_player.ENTITY_ID_FORMAT

    def __init__(
        self,
        hass: HomeAssistant,
        config: ConfigType,
        config_entry: ConfigEntry,
        discovery_data: DiscoveryInfoType | None,
    ) -> None:
        """Initialize the MQTT media player."""
        _LOGGER.debug("MqttMediaPlayer.__init__ called with config: %s", config)

        # Initialize the base MqttEntity with discovery data
        super().__init__(hass, config, config_entry, discovery_data)

        self._m3p_entry_id = config_entry.entry_id
        self._m3p_discovery_present = discovery_data is not None
        config_keys = sorted(config.keys()) if isinstance(config, dict) else []
        _LOGGER.info(
            "[m3p] MqttMediaPlayer init (entry_id=%s, entity_id=%s, discovery=%s, config_keys=%s)",
            self._m3p_entry_id,
            getattr(self, "entity_id", None),
            self._m3p_discovery_present,
            config_keys,
        )

        _LOGGER.debug("MqttMediaPlayer initialized successfully")

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _log_identity(self) -> str:
        """Return a stable identifier for log messages."""

        if getattr(self, "entity_id", None):
            return self.entity_id
        if getattr(self, "unique_id", None):
            return f"unique_id={self.unique_id}"
        return f"entry_id={self._m3p_entry_id}"

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        _LOGGER.debug(
            "MqttMediaPlayer _setup_from_config called with config: %s", config
        )

        # Store previous features if they exist (for change detection)
        previous_features = None
        if hasattr(self, "_attr_supported_features"):
            previous_features = self._attr_supported_features

        # Calculate new features
        features = MediaPlayerEntityFeature(0)
        feature_topics = []

        if self._config.get(CONF_PLAY_TOPIC):
            features |= MediaPlayerEntityFeature.PLAY
            feature_topics.append("PLAY")
        if self._config.get(CONF_PAUSE_TOPIC):
            features |= MediaPlayerEntityFeature.PAUSE
            feature_topics.append("PAUSE")
        if self._config.get(CONF_STOP_TOPIC):
            features |= MediaPlayerEntityFeature.STOP
            feature_topics.append("STOP")
        if self._config.get(CONF_PREVIOUS_TRACK_TOPIC):
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
            feature_topics.append("PREVIOUS_TRACK")
        if self._config.get(CONF_NEXT_TRACK_TOPIC):
            features |= MediaPlayerEntityFeature.NEXT_TRACK
            feature_topics.append("NEXT_TRACK")
        if self._config.get(CONF_SEEK_TOPIC):
            features |= MediaPlayerEntityFeature.SEEK
            feature_topics.append("SEEK")
        if self._config.get(CONF_VOLUME_SET_TOPIC):
            features |= MediaPlayerEntityFeature.VOLUME_SET
            feature_topics.append("VOLUME_SET")
            feature_topics.append("VOLUME_STEP")
        if self._config.get(CONF_VOLUME_MUTE_TOPIC):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
            feature_topics.append("VOLUME_MUTE")

        # Check if features have changed
        if previous_features is not None and previous_features != features:
            _LOGGER.info(
                "🔄 Features changed for %s: %s",
                self.entity_id if hasattr(self, "entity_id") else "entity",
                ", ".join(feature_topics) if feature_topics else "none",
            )

        self._attr_supported_features = features
        _LOGGER.debug(
            "MqttMediaPlayer setup completed with features: %s (%s)",
            features,
            ", ".join(feature_topics),
        )
        _LOGGER.info(
            "[m3p] %s supported_features=%s topics=%s",
            self._log_identity(),
            features,
            feature_topics or "<none>",
        )

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to hass."""
        _LOGGER.debug(
            "MqttMediaPlayer.async_added_to_hass called for entity: %s", self.entity_id
        )
        try:
            await super().async_added_to_hass()
            _LOGGER.debug(
                "MqttMediaPlayer.async_added_to_hass completed successfully for entity: %s",
                self.entity_id,
            )
        except Exception as e:
            _LOGGER.error(
                "Error in MqttMediaPlayer.async_added_to_hass for entity %s: %s",
                self.entity_id,
                e,
                exc_info=True,
            )
            raise

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
        _LOGGER.info(
            "[m3p] %s preparing MQTT subscriptions (configured_topics=%s)",
            self._log_identity(),
            configured_topics or "<none>",
        )

        @callback
        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            _LOGGER.debug(
                "🔥 STATE MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload
            )

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
                self._attr_state = STATE_UNKNOWN
                self.async_write_ha_state()
                _LOGGER.debug("✅ State marked as unknown from MQTT payload")
                return

            try:
                new_state = MediaPlayerState(state_str)
            except ValueError:
                _LOGGER.warning(
                    "Invalid media player state received: %s. Ignoring.", state_str
                )
                return

            self._attr_state = new_state
            self.async_write_ha_state()
            _LOGGER.debug("✅ State updated to: %s", self._attr_state)

        state_topic = self._config.get(CONF_STATE_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO STATE TOPIC: %s", state_topic)
        if state_topic:
            success = self.add_subscription(
                CONF_STATE_TOPIC, state_message_received, {"_attr_state"}
            )
            if not success:
                _LOGGER.error("Failed to subscribe to state topic: %s", state_topic)
                raise RuntimeError(f"Failed to subscribe to state topic: {state_topic}")
            _LOGGER.info(
                "[m3p] %s subscribed to state topic=%s",
                self._log_identity(),
                state_topic,
            )
        else:
            _LOGGER.debug("❌ No state topic configured, skipping state subscription")

        @callback
        def volume_level_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT volume level messages."""
            _LOGGER.debug(
                "🔊 VOLUME MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload
            )

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
                _LOGGER.warning(
                    "Volume level out of range: %s. Must be between 0.0 and 1.0", volume
                )
                return

            self._attr_volume_level = volume
            self.async_write_ha_state()
            _LOGGER.debug("✅ Volume updated to: %s", self._attr_volume_level)

        volume_topic = self._config.get(CONF_VOLUME_LEVEL_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO VOLUME TOPIC: %s", volume_topic)
        if volume_topic:
            success = self.add_subscription(
                CONF_VOLUME_LEVEL_TOPIC, volume_level_received, {"_attr_volume_level"}
            )
            if not success:
                _LOGGER.error("Failed to subscribe to volume topic: %s", volume_topic)
                raise RuntimeError(
                    f"Failed to subscribe to volume topic: {volume_topic}"
                )
            _LOGGER.info(
                "[m3p] %s subscribed to volume topic=%s",
                self._log_identity(),
                volume_topic,
            )
        else:
            _LOGGER.debug("❌ No volume topic configured, skipping volume subscription")

        @callback
        def media_title_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media title messages."""
            _LOGGER.debug(
                "🎵 TITLE MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload
            )
            self._attr_media_title = self._decode_payload(msg.payload)
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media title updated to: %s", self._attr_media_title)

        title_topic = self._config.get(CONF_MEDIA_TITLE_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO TITLE TOPIC: %s", title_topic)
        if title_topic:
            success = self.add_subscription(
                CONF_MEDIA_TITLE_TOPIC, media_title_received, {"_attr_media_title"}
            )
            if not success:
                _LOGGER.error("Failed to subscribe to title topic: %s", title_topic)
                raise RuntimeError(f"Failed to subscribe to title topic: {title_topic}")
            _LOGGER.info(
                "[m3p] %s subscribed to title topic=%s",
                self._log_identity(),
                title_topic,
            )
        else:
            _LOGGER.debug("❌ No title topic configured, skipping title subscription")

        @callback
        def media_artist_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media artist messages."""
            _LOGGER.debug(
                "🎤 ARTIST MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload
            )
            self._attr_media_artist = self._decode_payload(msg.payload)
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media artist updated to: %s", self._attr_media_artist)

        artist_topic = self._config.get(CONF_MEDIA_ARTIST_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO ARTIST TOPIC: %s", artist_topic)
        if artist_topic:
            success = self.add_subscription(
                CONF_MEDIA_ARTIST_TOPIC, media_artist_received, {"_attr_media_artist"}
            )
            if not success:
                _LOGGER.error("Failed to subscribe to artist topic: %s", artist_topic)
                raise RuntimeError(
                    f"Failed to subscribe to artist topic: {artist_topic}"
                )
            _LOGGER.info(
                "[m3p] %s subscribed to artist topic=%s",
                self._log_identity(),
                artist_topic,
            )
        else:
            _LOGGER.debug("❌ No artist topic configured, skipping artist subscription")

        @callback
        def media_album_name_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media album name messages."""
            _LOGGER.debug(
                "💿 ALBUM MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload
            )
            self._attr_media_album_name = self._decode_payload(msg.payload)
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media album updated to: %s", self._attr_media_album_name)

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
            _LOGGER.info(
                "[m3p] %s subscribed to album topic=%s",
                self._log_identity(),
                album_topic,
            )
        else:
            _LOGGER.debug("❌ No album topic configured, skipping album subscription")

        @callback
        def media_duration_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media duration messages."""
            _LOGGER.debug(
                "⏱️ DURATION MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload
            )

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

        duration_topic = self._config.get(CONF_MEDIA_DURATION_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO DURATION TOPIC: %s", duration_topic)
        if duration_topic:
            success = self.add_subscription(
                CONF_MEDIA_DURATION_TOPIC,
                media_duration_received,
                {"_attr_media_duration"},
            )
            if not success:
                _LOGGER.error(
                    "Failed to subscribe to duration topic: %s", duration_topic
                )
                raise RuntimeError(
                    f"Failed to subscribe to duration topic: {duration_topic}"
                )
            _LOGGER.info(
                "[m3p] %s subscribed to duration topic=%s",
                self._log_identity(),
                duration_topic,
            )
        else:
            _LOGGER.debug(
                "❌ No duration topic configured, skipping duration subscription"
            )

        @callback
        def media_position_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media position messages."""
            _LOGGER.debug(
                "⏲️ POSITION MESSAGE RECEIVED on topic %s: %s", msg.topic, msg.payload
            )

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
            self.async_write_ha_state()
            _LOGGER.debug("✅ Media position updated to: %s", self._attr_media_position)

        position_topic = self._config.get(CONF_MEDIA_POSITION_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO POSITION TOPIC: %s", position_topic)
        if position_topic:
            success = self.add_subscription(
                CONF_MEDIA_POSITION_TOPIC,
                media_position_received,
                {"_attr_media_position"},
            )
            if not success:
                _LOGGER.error(
                    "Failed to subscribe to position topic: %s", position_topic
                )
                raise RuntimeError(
                    f"Failed to subscribe to position topic: {position_topic}"
                )
            _LOGGER.info(
                "[m3p] %s subscribed to position topic=%s",
                self._log_identity(),
                position_topic,
            )
        else:
            _LOGGER.debug(
                "❌ No position topic configured, skipping position subscription"
            )

        @callback
        def media_image_url_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media image url messages."""
            payload_for_log = self._truncate_url_for_logging(
                self._decode_payload(msg.payload)
            )
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
                _LOGGER.debug(
                    "📊 Detected data URI image, setting remotely_accessible=True"
                )

            self.async_write_ha_state()
            url_for_log = self._truncate_url_for_logging(self._attr_media_image_url)
            _LOGGER.debug("✅ Media image URL updated to: %s", url_for_log)

        image_url_topic = self._config.get(CONF_MEDIA_IMAGE_URL_TOPIC)
        _LOGGER.debug("📡 SUBSCRIBING TO IMAGE URL TOPIC: %s", image_url_topic)
        if image_url_topic:
            success = self.add_subscription(
                CONF_MEDIA_IMAGE_URL_TOPIC,
                media_image_url_received,
                {"_attr_media_image_url"},
            )
            if not success:
                _LOGGER.error(
                    "Failed to subscribe to image URL topic: %s", image_url_topic
                )
                raise RuntimeError(
                    f"Failed to subscribe to image URL topic: {image_url_topic}"
                )
            _LOGGER.info(
                "[m3p] %s subscribed to image_url topic=%s",
                self._log_identity(),
                image_url_topic,
            )
        else:
            _LOGGER.debug(
                "❌ No image URL topic configured, skipping image URL subscription"
            )

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

        image_accessible_topic = self._config.get(
            CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC
        )
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
                raise RuntimeError(
                    f"Failed to subscribe to image accessible topic: {image_accessible_topic}"
                )
            _LOGGER.info(
                "[m3p] %s subscribed to image_accessible topic=%s",
                self._log_identity(),
                image_accessible_topic,
            )
        else:
            _LOGGER.debug(
                "❌ No image remotely accessible topic configured, skipping subscription"
            )

        # Final summary
        _LOGGER.debug("🎯 SUBSCRIPTION SETUP COMPLETED for entity: %s", self.entity_id)
        _LOGGER.debug(
            "📊 Total subscriptions object state: %s",
            len(getattr(self, "_subscriptions", {})),
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""
        from homeassistant.components.mqtt.subscription import (
            async_subscribe_topics_internal,
        )

        _LOGGER.debug(
            "🔌 Actually subscribing to MQTT topics for entity: %s", self.entity_id
        )
        async_subscribe_topics_internal(self.hass, self._sub_state)
        _LOGGER.debug("✅ MQTT subscription completed for entity: %s", self.entity_id)
        _LOGGER.info(
            "[m3p] %s MQTT topic subscription batch complete (subscriptions=%s)",
            self._log_identity(),
            list(getattr(self, "_subscriptions", {}).keys()),
        )

    async def async_media_play(self) -> None:
        """Send a play command to the media player."""
        topic = self._config.get(CONF_PLAY_TOPIC)
        if not topic:
            _LOGGER.warning("Play command called but no play topic configured")
            return
        _LOGGER.debug("🎵 Sending PLAY command to topic: %s", topic)
        try:
            await self.async_publish(topic, "")
        except Exception as e:
            _LOGGER.error("Failed to publish play command to topic %s: %s", topic, e)

    async def async_media_pause(self) -> None:
        """Send a pause command to the media player."""
        topic = self._config.get(CONF_PAUSE_TOPIC)
        if not topic:
            _LOGGER.warning("Pause command called but no pause topic configured")
            return
        _LOGGER.debug("⏸️ Sending PAUSE command to topic: %s", topic)
        try:
            await self.async_publish(topic, "")
        except Exception as e:
            _LOGGER.error("Failed to publish pause command to topic %s: %s", topic, e)

    async def async_media_stop(self) -> None:
        """Send a stop command to the media player."""
        topic = self._config.get(CONF_STOP_TOPIC)
        if not topic:
            _LOGGER.warning("Stop command called but no stop topic configured")
            return
        _LOGGER.debug("⏹️ Sending STOP command to topic: %s", topic)
        try:
            await self.async_publish(topic, "")
        except Exception as e:
            _LOGGER.error("Failed to publish stop command to topic %s: %s", topic, e)

    async def async_media_next_track(self) -> None:
        """Send a next track command to the media player."""
        topic = self._config.get(CONF_NEXT_TRACK_TOPIC)
        if not topic:
            _LOGGER.warning(
                "Next track command called but no next track topic configured"
            )
            return
        _LOGGER.debug("⏭️ Sending NEXT TRACK command to topic: %s", topic)
        try:
            await self.async_publish(topic, "")
        except Exception as e:
            _LOGGER.error(
                "Failed to publish next track command to topic %s: %s", topic, e
            )

    async def async_media_previous_track(self) -> None:
        """Send a previous track command to the media player."""
        topic = self._config.get(CONF_PREVIOUS_TRACK_TOPIC)
        if not topic:
            _LOGGER.warning(
                "Previous track command called but no previous track topic configured"
            )
            return
        _LOGGER.debug("⏮️ Sending PREVIOUS TRACK command to topic: %s", topic)
        try:
            await self.async_publish(topic, "")
        except Exception as e:
            _LOGGER.error(
                "Failed to publish previous track command to topic %s: %s", topic, e
            )

    async def async_set_volume_level(self, volume: float) -> None:
        """Send a set volume level command to the media player."""
        topic = self._config.get(CONF_VOLUME_SET_TOPIC)
        if not topic:
            _LOGGER.warning(
                "Set volume level command called but no volume set topic configured"
            )
            return
        payload = str(volume)
        _LOGGER.debug(
            "🔊 Sending SET VOLUME LEVEL command to topic: %s, payload: %s",
            topic,
            payload,
        )
        try:
            await self.async_publish(topic, payload)
        except Exception as e:
            _LOGGER.error(
                "Failed to publish volume level command to topic %s: %s", topic, e
            )

    async def async_mute_volume(self, mute: bool) -> None:
        """Send a mute volume command to the media player."""
        topic = self._config.get(CONF_VOLUME_MUTE_TOPIC)
        if not topic:
            _LOGGER.warning(
                "Mute volume command called but no volume mute topic configured"
            )
            return
        payload = "true" if mute else "false"
        _LOGGER.debug(
            "🔇 Sending MUTE VOLUME command to topic: %s, payload: %s", topic, payload
        )
        try:
            await self.async_publish(topic, payload)
        except Exception as e:
            _LOGGER.error(
                "Failed to publish mute volume command to topic %s: %s", topic, e
            )

    async def async_media_seek(self, position: float) -> None:
        """Send a seek command to the media player."""
        topic = self._config.get(CONF_SEEK_TOPIC)
        if not topic:
            _LOGGER.warning("Seek command called but no seek topic configured")
            return
        payload = str(position)
        _LOGGER.debug(
            "⏩ Sending SEEK command to topic: %s, payload: %s", topic, payload
        )
        try:
            await self.async_publish(topic, payload)
        except Exception as e:
            _LOGGER.error("Failed to publish seek command to topic %s: %s", topic, e)
