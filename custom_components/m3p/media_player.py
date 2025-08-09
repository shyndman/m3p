"""Support for Mellow MQTT Media Players."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.components import media_player
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

from custom_components.m3p.const import (
    CONF_MEDIA_ALBUM_NAME_TOPIC,
    CONF_MEDIA_ARTIST_TOPIC,
    CONF_MEDIA_DURATION_TOPIC,
    CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE,
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


PLATFORM_SCHEMA_MODERN = MQTT_RO_SCHEMA.extend(
    {
        # Attributes
        vol.Optional(CONF_MEDIA_ALBUM_NAME_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_ARTIST_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_DURATION_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE): cv.boolean,
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

        _LOGGER.debug("MqttMediaPlayer initialized successfully")

    @staticmethod
    def config_schema() -> vol.Schema:
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        _LOGGER.debug(
            "MqttMediaPlayer _setup_from_config called with config: %s", config
        )
        features = MediaPlayerEntityFeature(0)
        if self._config.get(CONF_PLAY_TOPIC):
            features |= MediaPlayerEntityFeature.PLAY
        if self._config.get(CONF_PAUSE_TOPIC):
            features |= MediaPlayerEntityFeature.PAUSE
        if self._config.get(CONF_STOP_TOPIC):
            features |= MediaPlayerEntityFeature.STOP
        if self._config.get(CONF_PREVIOUS_TRACK_TOPIC):
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if self._config.get(CONF_NEXT_TRACK_TOPIC):
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if self._config.get(CONF_SEEK_TOPIC):
            features |= MediaPlayerEntityFeature.SEEK
        if self._config.get(CONF_VOLUME_SET_TOPIC):
            features |= MediaPlayerEntityFeature.VOLUME_SET
        if self._config.get(CONF_VOLUME_MUTE_TOPIC):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE

        self._attr_supported_features = features
        _LOGGER.debug("MqttMediaPlayer setup completed with features: %s", features)

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

    @callback
    def _prepare_subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

        @callback
        def state_message_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT state messages."""
            _LOGGER.debug("Received state message: %s", msg.payload)
            try:
                state_str = self._decode_payload(msg.payload)
                if state_str:
                    self._attr_state = MediaPlayerState(state_str)
                    self.async_write_ha_state()
            except ValueError as e:
                _LOGGER.warning("Invalid state received: %s, error: %s", msg.payload, e)

        self.add_subscription(CONF_STATE_TOPIC, state_message_received, {"_attr_state"})

        @callback
        def volume_level_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT volume level messages."""
            try:
                payload_str = self._decode_payload(msg.payload)
                if payload_str:
                    self._attr_volume_level = float(payload_str)
                    self.async_write_ha_state()
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid volume level received: %s, error: %s", msg.payload, e
                )

        self.add_subscription(
            CONF_VOLUME_LEVEL_TOPIC, volume_level_received, {"_attr_volume_level"}
        )

        @callback
        def media_title_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media title messages."""
            self._attr_media_title = self._decode_payload(msg.payload)
            self.async_write_ha_state()

        self.add_subscription(
            CONF_MEDIA_TITLE_TOPIC, media_title_received, {"_attr_media_title"}
        )

        @callback
        def media_artist_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media artist messages."""
            self._attr_media_artist = self._decode_payload(msg.payload)
            self.async_write_ha_state()

        self.add_subscription(
            CONF_MEDIA_ARTIST_TOPIC, media_artist_received, {"_attr_media_artist"}
        )

        @callback
        def media_album_name_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media album name messages."""
            self._attr_media_album_name = self._decode_payload(msg.payload)
            self.async_write_ha_state()

        self.add_subscription(
            CONF_MEDIA_ALBUM_NAME_TOPIC,
            media_album_name_received,
            {"_attr_media_album_name"},
        )

        @callback
        def media_duration_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media duration messages."""
            try:
                payload_str = self._decode_payload(msg.payload)
                if payload_str:
                    self._attr_media_duration = int(payload_str)
                    self.async_write_ha_state()
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid media duration received: %s, error: %s", msg.payload, e
                )

        self.add_subscription(
            CONF_MEDIA_DURATION_TOPIC, media_duration_received, {"_attr_media_duration"}
        )

        @callback
        def media_position_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media position messages."""
            try:
                payload_str = self._decode_payload(msg.payload)
                if payload_str:
                    self._attr_media_position = int(payload_str)
                    self.async_write_ha_state()
            except (ValueError, TypeError) as e:
                _LOGGER.warning(
                    "Invalid media position received: %s, error: %s", msg.payload, e
                )

        self.add_subscription(
            CONF_MEDIA_POSITION_TOPIC, media_position_received, {"_attr_media_position"}
        )

        @callback
        def media_image_url_received(msg: ReceiveMessage) -> None:
            """Handle new MQTT media image url messages."""
            self._attr_media_image_url = self._decode_payload(msg.payload)
            self.async_write_ha_state()

        self.add_subscription(
            CONF_MEDIA_IMAGE_URL_TOPIC,
            media_image_url_received,
            {"_attr_media_image_url"},
        )

    async def _subscribe_topics(self) -> None:
        """(Re)Subscribe to topics."""

    async def async_play(self) -> None:
        """Send a play command to the media player."""
        await self.async_publish(self._config[CONF_PLAY_TOPIC], "")

    async def async_pause(self) -> None:
        """Send a pause command to the media player."""
        await self.async_publish(self._config[CONF_PAUSE_TOPIC], "")

    async def async_stop(self) -> None:
        """Send a stop command to the media player."""
        await self.async_publish(self._config[CONF_STOP_TOPIC], "")

    async def async_next_track(self) -> None:
        """Send a next track command to the media player."""
        await self.async_publish(self._config[CONF_NEXT_TRACK_TOPIC], "")

    async def async_previous_track(self) -> None:
        """Send a previous track command to the media player."""
        await self.async_publish(self._config[CONF_PREVIOUS_TRACK_TOPIC], "")

    async def async_set_volume_level(self, volume: float) -> None:
        """Send a set volume level command to the media player."""
        await self.async_publish(self._config[CONF_VOLUME_SET_TOPIC], str(volume))

    async def async_mute_volume(self, mute: bool) -> None:
        """Send a mute volume command to the media player."""
        payload = "true" if mute else "false"
        await self.async_publish(self._config[CONF_VOLUME_MUTE_TOPIC], payload)

    async def async_seek(self, position: float) -> None:
        """Send a seek command to the media player."""
        await self.async_publish(self._config[CONF_SEEK_TOPIC], str(position))
