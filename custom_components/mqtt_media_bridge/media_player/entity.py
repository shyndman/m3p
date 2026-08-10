"""MQTT Media Bridge media player entity."""

from __future__ import annotations

from contextlib import suppress
import logging

import voluptuous as vol

from custom_components.mqtt_media_bridge.const import (
    CONF_MEDIA_ALBUM_NAME_TOPIC,
    CONF_MEDIA_ARTIST_TOPIC,
    CONF_MEDIA_DURATION_TOPIC,
    CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC,
    CONF_MEDIA_IMAGE_URL_TOPIC,
    CONF_MEDIA_POSITION_TOPIC,
    CONF_MEDIA_TITLE_TOPIC,
    CONF_NEXT_TRACK_TOPIC,
    CONF_PAUSE_TOPIC,
    CONF_PLAY_MEDIA_TOPIC,
    CONF_PLAY_TOPIC,
    CONF_PREVIOUS_TRACK_TOPIC,
    CONF_REPEAT_SET_TOPIC,
    CONF_REPEAT_STATE_TOPIC,
    CONF_SEEK_TOPIC,
    CONF_SELECT_SOUND_MODE_TOPIC,
    CONF_SELECT_SOURCE_TOPIC,
    CONF_SHUFFLE_SET_TOPIC,
    CONF_SHUFFLE_STATE_TOPIC,
    CONF_SOUND_MODE_LIST,
    CONF_SOURCE_LIST,
    CONF_STOP_TOPIC,
    CONF_TURN_OFF_TOPIC,
    CONF_TURN_ON_TOPIC,
    CONF_VOLUME_LEVEL_TOPIC,
    CONF_VOLUME_MUTE_COMMAND_TOPIC,
    CONF_VOLUME_MUTE_STATE_TOPIC,
    CONF_VOLUME_SET_TOPIC,
    CONF_VOLUME_STEP,
    DEFAULT_NAME,
)
from homeassistant.components import media_player
from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.components.mqtt import CONF_STATE_TOPIC
from homeassistant.components.mqtt.config import MQTT_RO_SCHEMA
from homeassistant.components.mqtt.entity import MqttEntity
from homeassistant.components.mqtt.schemas import MQTT_ENTITY_COMMON_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .commands import MqttMediaPlayerCommandsMixin
from .subscriptions import MqttMediaPlayerSubscriptionsMixin

_LOGGER = logging.getLogger(__name__)


def _clear_attr(entity: MediaPlayerEntity, name: str) -> None:
    """Revert an HA `_attr_` cached property to its default.

    # DANGER! Relies on HA's CachedProperties deleter: it invalidates the
    # cache then deletes the private backing attr, raising AttributeError
    # when no value was ever set. We swallow that case. If HA changes this
    # internal behavior, revisit here.
    """
    with suppress(AttributeError):
        delattr(entity, name)


PLATFORM_SCHEMA_MODERN = MQTT_RO_SCHEMA.extend(
    {
        # Attributes
        vol.Optional(CONF_NAME): vol.Any(cv.string, None),
        vol.Optional(CONF_MEDIA_ALBUM_NAME_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_ARTIST_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_DURATION_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_IMAGE_REMOTELY_ACCESSIBLE_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_IMAGE_URL_TOPIC): cv.string,
        vol.Optional(CONF_MEDIA_POSITION_TOPIC): cv.string,
        vol.Optional(CONF_SOURCE_LIST): [cv.string],
        vol.Optional(CONF_MEDIA_TITLE_TOPIC): cv.string,
        vol.Optional(CONF_STATE_TOPIC): cv.string,
        vol.Optional(CONF_REPEAT_STATE_TOPIC): cv.string,
        vol.Optional(CONF_SHUFFLE_STATE_TOPIC): cv.string,
        vol.Optional(CONF_SOUND_MODE_LIST): [cv.string],
        vol.Optional(CONF_VOLUME_LEVEL_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_MUTE_STATE_TOPIC): cv.string,
        # Commands
        vol.Optional(CONF_NEXT_TRACK_TOPIC): cv.string,
        vol.Optional(CONF_PAUSE_TOPIC): cv.string,
        vol.Optional(CONF_PLAY_TOPIC): cv.string,
        vol.Optional(CONF_PLAY_MEDIA_TOPIC): cv.string,
        vol.Optional(CONF_PREVIOUS_TRACK_TOPIC): cv.string,
        vol.Optional(CONF_REPEAT_SET_TOPIC): cv.string,
        vol.Optional(CONF_SEEK_TOPIC): cv.string,
        vol.Optional(CONF_SELECT_SOUND_MODE_TOPIC): cv.string,
        vol.Optional(CONF_SELECT_SOURCE_TOPIC): cv.string,
        vol.Optional(CONF_SHUFFLE_SET_TOPIC): cv.string,
        vol.Optional(CONF_STOP_TOPIC): cv.string,
        vol.Optional(CONF_TURN_OFF_TOPIC): cv.string,
        vol.Optional(CONF_TURN_ON_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_MUTE_COMMAND_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_SET_TOPIC): cv.string,
        vol.Optional(CONF_VOLUME_STEP): vol.Coerce(float),
    }
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

DISCOVERY_SCHEMA = PLATFORM_SCHEMA_MODERN.extend({}, extra=vol.REMOVE_EXTRA)


class MqttMediaPlayer(
    MqttMediaPlayerCommandsMixin,
    MqttMediaPlayerSubscriptionsMixin,
    MqttEntity,
    MediaPlayerEntity,
):
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

        # Log the MRO to understand the class hierarchy
        _LOGGER.debug("[mmb MRO] %s", [c.__name__ for c in self.__class__.__mro__])

        # Initialize the base MqttEntity with discovery data
        super().__init__(hass, config, config_entry, discovery_data)

        self._mmb_entry_id = config_entry.entry_id
        self._mmb_discovery_present = discovery_data is not None
        config_keys = sorted(config.keys()) if isinstance(config, dict) else []
        _LOGGER.debug(
            "[mmb] MqttMediaPlayer init (entry_id=%s, entity_id=%s, discovery=%s, config_keys=%s)",
            self._mmb_entry_id,
            getattr(self, "entity_id", None),
            self._mmb_discovery_present,
            config_keys,
        )

        # Check the type of _attr_media_title after super().__init__
        attr_type = type(self.__class__.__dict__.get("_attr_media_title", "NOT_IN_DICT")).__name__
        _LOGGER.debug("[mmb INIT] _attr_media_title type in class: %s", attr_type)

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
        return f"entry_id={self._mmb_entry_id}"

    def _setup_from_config(self, config: ConfigType) -> None:
        """(Re)Setup the entity."""
        _LOGGER.debug("MqttMediaPlayer _setup_from_config called with config: %s", config)

        # Store previous features if they exist (for change detection)
        previous_features = None
        if hasattr(self, "_attr_supported_features"):
            previous_features = self._attr_supported_features

        # Calculate new features
        features = MediaPlayerEntityFeature(0)
        feature_topics = []

        source_list = self._config.get(CONF_SOURCE_LIST)
        if source_list is not None:
            self._attr_source_list = source_list
        else:
            _clear_attr(self, "_attr_source_list")

        sound_mode_list = self._config.get(CONF_SOUND_MODE_LIST)
        if sound_mode_list is not None:
            self._attr_sound_mode_list = sound_mode_list
        else:
            _clear_attr(self, "_attr_sound_mode_list")

        volume_step = self._config.get(CONF_VOLUME_STEP)
        if volume_step is not None:
            self._attr_volume_step = volume_step
        else:
            _clear_attr(self, "_attr_volume_step")

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
        if self._config.get(CONF_TURN_ON_TOPIC):
            features |= MediaPlayerEntityFeature.TURN_ON
            feature_topics.append("TURN_ON")
        if self._config.get(CONF_TURN_OFF_TOPIC):
            features |= MediaPlayerEntityFeature.TURN_OFF
            feature_topics.append("TURN_OFF")
        if self._config.get(CONF_PLAY_MEDIA_TOPIC):
            features |= MediaPlayerEntityFeature.PLAY_MEDIA
            feature_topics.append("PLAY_MEDIA")
        if self._config.get(CONF_SEEK_TOPIC):
            features |= MediaPlayerEntityFeature.SEEK
            feature_topics.append("SEEK")
        if self._config.get(CONF_SELECT_SOURCE_TOPIC):
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
            feature_topics.append("SELECT_SOURCE")
        if self._config.get(CONF_SELECT_SOUND_MODE_TOPIC):
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
            feature_topics.append("SELECT_SOUND_MODE")
        if self._config.get(CONF_VOLUME_SET_TOPIC):
            features |= MediaPlayerEntityFeature.VOLUME_SET
            feature_topics.append("VOLUME_SET")
            if volume_step is not None:
                features |= MediaPlayerEntityFeature.VOLUME_STEP
                feature_topics.append("VOLUME_STEP")
        if self._config.get(CONF_VOLUME_MUTE_COMMAND_TOPIC):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
            feature_topics.append("VOLUME_MUTE")
        if self._config.get(CONF_SHUFFLE_SET_TOPIC):
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
            feature_topics.append("SHUFFLE_SET")
        if self._config.get(CONF_REPEAT_SET_TOPIC):
            features |= MediaPlayerEntityFeature.REPEAT_SET
            feature_topics.append("REPEAT_SET")

        # Check if features have changed
        if previous_features is not None and previous_features != features:
            _LOGGER.debug(
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
        _LOGGER.debug(
            "[mmb] %s supported_features=%s topics=%s",
            self._log_identity(),
            features,
            feature_topics or "<none>",
        )

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to hass."""
        _LOGGER.debug("MqttMediaPlayer.async_added_to_hass called for entity: %s", self.entity_id)
        try:
            await super().async_added_to_hass()
            _LOGGER.debug(
                "MqttMediaPlayer.async_added_to_hass completed successfully for entity: %s",
                self.entity_id,
            )
        except Exception:
            _LOGGER.exception(
                "Error in MqttMediaPlayer.async_added_to_hass for entity %s",
                self.entity_id,
            )
            raise
