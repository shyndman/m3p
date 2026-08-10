"""Behavior tests for the MQTT Media Bridge media player."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import json
import logging
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

from custom_components.mqtt_media_bridge import media_player
from custom_components.mqtt_media_bridge.const import (
    CONF_PLAY_MEDIA_TOPIC,
    CONF_PLAY_TOPIC,
    CONF_REPEAT_SET_TOPIC,
    CONF_REPEAT_STATE_TOPIC,
    CONF_SELECT_SOUND_MODE_TOPIC,
    CONF_SELECT_SOURCE_TOPIC,
    CONF_SHUFFLE_SET_TOPIC,
    CONF_SHUFFLE_STATE_TOPIC,
    CONF_SOUND_MODE_LIST,
    CONF_SOURCE_LIST,
    CONF_TURN_OFF_TOPIC,
    CONF_TURN_ON_TOPIC,
    CONF_VOLUME_LEVEL_TOPIC,
    CONF_VOLUME_MUTE_COMMAND_TOPIC,
    CONF_VOLUME_MUTE_STATE_TOPIC,
    CONF_VOLUME_SET_TOPIC,
    CONF_VOLUME_STEP,
    DOMAIN,
)
from custom_components.mqtt_media_bridge.media_player import MqttMediaPlayer
from homeassistant.components.media_player import DATA_COMPONENT
from homeassistant.components.media_player.const import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEntityFeature,
    RepeatMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    EVENT_STATE_CHANGED,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_UP,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback

ENTITY_ID = "media_player.test_player"
DISCOVERY_TOPIC = "homeassistant/media_player/test/player/config"


@pytest.fixture
def setup_player(
    hass: HomeAssistant,
    mqtt_media_bridge_setup: None,
) -> Callable[[dict[str, Any]], Awaitable[State]]:
    """Return a factory that sets up a bridge player."""

    async def _setup_player(config: dict[str, Any]) -> State:
        payload = {
            "name": "Test Player",
            "unique_id": "test-player",
            "default_entity_id": ENTITY_ID,
            **config,
        }
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Test Player",
            data={
                "discovery_payload": payload,
                "discovery_topic": DISCOVERY_TOPIC,
            },
            unique_id="test-player-entry",
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(ENTITY_ID)
        assert state is not None
        return state

    return _setup_player


async def call_media_player_service(
    hass: HomeAssistant,
    service: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Call a media-player service for the test entity."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **(data or {})},
        blocking=True,
    )


@pytest.mark.unit
def test_config_schema_preserves_discovered_name() -> None:
    """The discovery schema preserves the configured entity name."""
    config = MqttMediaPlayer.config_schema()({"name": "Desktop Media"})

    assert config["name"] == "Desktop Media"


@pytest.mark.unit
def test_config_schema_accepts_split_state_and_command_topics() -> None:
    """The discovery schema accepts every split state and command topic."""
    config = MqttMediaPlayer.config_schema()(
        {
            CONF_SOURCE_LIST: ["TV", "Bluetooth"],
            CONF_VOLUME_MUTE_STATE_TOPIC: "bridge/player/volume_mute_state",
            CONF_VOLUME_MUTE_COMMAND_TOPIC: "bridge/player/volume_mute",
            CONF_SHUFFLE_STATE_TOPIC: "bridge/player/shuffle_state",
            CONF_SHUFFLE_SET_TOPIC: "bridge/player/shuffle_set",
            CONF_REPEAT_STATE_TOPIC: "bridge/player/repeat_state",
            CONF_REPEAT_SET_TOPIC: "bridge/player/repeat_set",
            CONF_SOUND_MODE_LIST: ["Movie", "Music"],
            CONF_SELECT_SOURCE_TOPIC: "bridge/player/select_source",
            CONF_SELECT_SOUND_MODE_TOPIC: "bridge/player/select_sound_mode",
            CONF_TURN_ON_TOPIC: "bridge/player/turn_on",
            CONF_TURN_OFF_TOPIC: "bridge/player/turn_off",
            CONF_PLAY_MEDIA_TOPIC: "bridge/player/play_media",
        }
    )

    assert config[CONF_SOURCE_LIST] == ["TV", "Bluetooth"]
    assert config[CONF_VOLUME_MUTE_STATE_TOPIC].endswith("volume_mute_state")
    assert config[CONF_VOLUME_MUTE_COMMAND_TOPIC].endswith("volume_mute")
    assert config[CONF_SHUFFLE_STATE_TOPIC].endswith("shuffle_state")
    assert config[CONF_SHUFFLE_SET_TOPIC].endswith("shuffle_set")
    assert config[CONF_REPEAT_STATE_TOPIC].endswith("repeat_state")
    assert config[CONF_REPEAT_SET_TOPIC].endswith("repeat_set")
    assert config[CONF_SOUND_MODE_LIST] == ["Movie", "Music"]
    assert config[CONF_SELECT_SOURCE_TOPIC].endswith("select_source")
    assert config[CONF_SELECT_SOUND_MODE_TOPIC].endswith("select_sound_mode")
    assert config[CONF_TURN_ON_TOPIC].endswith("turn_on")
    assert config[CONF_TURN_OFF_TOPIC].endswith("turn_off")
    assert config[CONF_PLAY_MEDIA_TOPIC].endswith("play_media")


@pytest.mark.integration
async def test_entity_enables_split_features_and_exposes_lists(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
) -> None:
    """Split command topics enable their features and optional lists."""
    state = await setup_player(
        {
            CONF_SOURCE_LIST: ["TV", "Bluetooth"],
            CONF_VOLUME_MUTE_COMMAND_TOPIC: "bridge/player/volume_mute",
            CONF_SHUFFLE_SET_TOPIC: "bridge/player/shuffle_set",
            CONF_REPEAT_SET_TOPIC: "bridge/player/repeat_set",
            CONF_SOUND_MODE_LIST: ["Movie", "Music"],
            CONF_SELECT_SOURCE_TOPIC: "bridge/player/select_source",
            CONF_SELECT_SOUND_MODE_TOPIC: "bridge/player/select_sound_mode",
            CONF_TURN_ON_TOPIC: "bridge/player/turn_on",
            CONF_TURN_OFF_TOPIC: "bridge/player/turn_off",
            CONF_PLAY_MEDIA_TOPIC: "bridge/player/play_media",
        },
    )
    features = MediaPlayerEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])

    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["TV", "Bluetooth"]
    assert state.attributes[ATTR_SOUND_MODE_LIST] == ["Movie", "Music"]
    assert MediaPlayerEntityFeature.SELECT_SOURCE in features
    assert MediaPlayerEntityFeature.SELECT_SOUND_MODE in features
    assert MediaPlayerEntityFeature.TURN_ON in features
    assert MediaPlayerEntityFeature.TURN_OFF in features
    assert MediaPlayerEntityFeature.PLAY_MEDIA in features
    assert MediaPlayerEntityFeature.VOLUME_MUTE in features
    assert MediaPlayerEntityFeature.SHUFFLE_SET in features
    assert MediaPlayerEntityFeature.REPEAT_SET in features


@pytest.mark.integration
async def test_volume_step_is_enabled_and_used_only_when_configured(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
) -> None:
    """A configured step enables volume stepping and controls its increment."""
    state = await setup_player(
        {
            CONF_VOLUME_LEVEL_TOPIC: "bridge/player/volume_state",
            CONF_VOLUME_SET_TOPIC: "bridge/player/volume_set",
            CONF_VOLUME_STEP: 0.1,
        },
    )
    features = MediaPlayerEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])

    assert MediaPlayerEntityFeature.VOLUME_SET in features
    assert MediaPlayerEntityFeature.VOLUME_STEP in features

    async_fire_mqtt_message(hass, "bridge/player/volume_state", "0.5")
    await hass.async_block_till_done()
    with patch.object(
        media_player.mqtt,
        "async_publish",
        new_callable=AsyncMock,
    ) as async_publish:
        await call_media_player_service(hass, SERVICE_VOLUME_UP)

    async_publish.assert_awaited_once_with(hass, "bridge/player/volume_set", "0.6")


@pytest.mark.integration
async def test_volume_step_is_not_enabled_without_step_value(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
) -> None:
    """A volume command topic alone does not advertise volume stepping."""
    state = await setup_player(
        {CONF_VOLUME_SET_TOPIC: "bridge/player/volume_set"},
    )
    features = MediaPlayerEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])

    assert MediaPlayerEntityFeature.VOLUME_SET in features
    assert MediaPlayerEntityFeature.VOLUME_STEP not in features


@pytest.mark.integration
async def test_entity_without_optional_lists_sets_up_cleanly(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
) -> None:
    """Omitted source and sound-mode lists remain absent from public state."""
    state = await setup_player(
        {CONF_PLAY_TOPIC: "bridge/player/play"},
    )

    assert ATTR_INPUT_SOURCE_LIST not in state.attributes
    assert ATTR_SOUND_MODE_LIST not in state.attributes


@pytest.mark.integration
async def test_mode_state_topics_update_public_state_once_each(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
) -> None:
    """Mute, shuffle, and repeat subscriptions each write their tracked state."""
    await setup_player(
        {
            CONF_VOLUME_MUTE_STATE_TOPIC: "bridge/player/volume_mute_state",
            CONF_SHUFFLE_STATE_TOPIC: "bridge/player/shuffle_state",
            CONF_REPEAT_STATE_TOPIC: "bridge/player/repeat_state",
        },
    )
    changed_entities: list[str] = []

    @callback
    def record_state_change(event: Event[EventStateChangedData]) -> None:
        """Record writes for the bridge entity."""
        if event.data["entity_id"] == ENTITY_ID:
            changed_entities.append(event.data["entity_id"])

    remove_listener = hass.bus.async_listen(EVENT_STATE_CHANGED, record_state_change)

    async_fire_mqtt_message(hass, "bridge/player/volume_mute_state", b"true")
    async_fire_mqtt_message(hass, "bridge/player/shuffle_state", b"false")
    async_fire_mqtt_message(hass, "bridge/player/repeat_state", b"all")
    await hass.async_block_till_done()
    remove_listener()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is True
    assert state.attributes[ATTR_MEDIA_SHUFFLE] is False
    assert state.attributes[ATTR_MEDIA_REPEAT] == RepeatMode.ALL
    assert changed_entities == [ENTITY_ID, ENTITY_ID, ENTITY_ID]


@pytest.mark.integration
async def test_invalid_repeat_mode_is_ignored_without_state_write(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
) -> None:
    """An invalid repeat payload neither sets repeat nor writes entity state."""
    await setup_player(
        {CONF_REPEAT_STATE_TOPIC: "bridge/player/repeat_state"},
    )
    changed_entities: list[str] = []

    @callback
    def record_state_change(event: Event[EventStateChangedData]) -> None:
        """Record writes for the bridge entity."""
        if event.data["entity_id"] == ENTITY_ID:
            changed_entities.append(event.data["entity_id"])

    remove_listener = hass.bus.async_listen(EVENT_STATE_CHANGED, record_state_change)
    async_fire_mqtt_message(hass, "bridge/player/repeat_state", b"invalid")
    await hass.async_block_till_done()
    remove_listener()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert ATTR_MEDIA_REPEAT not in state.attributes
    assert changed_entities == []


@pytest.mark.integration
async def test_split_commands_publish_exact_topics_and_payloads(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
) -> None:
    await setup_player(
        {
            CONF_PLAY_MEDIA_TOPIC: "bridge/player/play_media",
            CONF_SELECT_SOURCE_TOPIC: "bridge/player/select_source",
            CONF_SELECT_SOUND_MODE_TOPIC: "bridge/player/select_sound_mode",
            CONF_TURN_ON_TOPIC: "bridge/player/turn_on",
            CONF_TURN_OFF_TOPIC: "bridge/player/turn_off",
            CONF_VOLUME_MUTE_COMMAND_TOPIC: "bridge/player/volume_mute",
            CONF_SHUFFLE_SET_TOPIC: "bridge/player/shuffle_set",
            CONF_REPEAT_SET_TOPIC: "bridge/player/repeat_set",
        },
    )
    with patch.object(
        media_player.mqtt,
        "async_publish",
        new_callable=AsyncMock,
    ) as async_publish:
        await call_media_player_service(hass, SERVICE_TURN_ON)
        await call_media_player_service(hass, SERVICE_TURN_OFF)
        await call_media_player_service(
            hass,
            SERVICE_VOLUME_MUTE,
            {ATTR_MEDIA_VOLUME_MUTED: True},
        )

        component = hass.data[DATA_COMPONENT]
        player = component.get_entity(ENTITY_ID)
        assert isinstance(player, MqttMediaPlayer)
        await player.async_play_media(
            "music",
            "track-123",
            enqueue="replace",
            announce=True,
        )

        await call_media_player_service(
            hass,
            SERVICE_SELECT_SOURCE,
            {ATTR_INPUT_SOURCE: "Bluetooth"},
        )
        await call_media_player_service(
            hass,
            SERVICE_SELECT_SOUND_MODE,
            {ATTR_SOUND_MODE: "Movie"},
        )
        await call_media_player_service(
            hass,
            SERVICE_SHUFFLE_SET,
            {ATTR_MEDIA_SHUFFLE: False},
        )
        await call_media_player_service(
            hass,
            SERVICE_REPEAT_SET,
            {ATTR_MEDIA_REPEAT: RepeatMode.ONE},
        )

    play_media_payload = json.dumps(
        {
            "media_type": "music",
            "media_id": "track-123",
            "enqueue": "replace",
            "announce": True,
        }
    )
    assert async_publish.await_args_list == [
        call(hass, "bridge/player/turn_on", ""),
        call(hass, "bridge/player/turn_off", ""),
        call(hass, "bridge/player/volume_mute", "ON"),
        call(hass, "bridge/player/play_media", play_media_payload),
        call(hass, "bridge/player/select_source", "Bluetooth"),
        call(hass, "bridge/player/select_sound_mode", "Movie"),
        call(hass, "bridge/player/shuffle_set", "OFF"),
        call(hass, "bridge/player/repeat_set", "one"),
    ]


@pytest.mark.integration
async def test_boolean_state_payloads_are_decoded_and_invalid_values_warn(
    hass: HomeAssistant,
    setup_player: Callable[[dict[str, Any]], Awaitable[State]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Boolean subscriptions accept supported spellings and ignore invalid input."""
    await setup_player(
        {CONF_VOLUME_MUTE_STATE_TOPIC: "bridge/player/volume_mute_state"},
    )

    for payload, expected in (
        ("true", True),
        ("0", False),
        ("yes", True),
        ("off", False),
        ("1", True),
        ("false", False),
        ("on", True),
        ("no", False),
    ):
        async_fire_mqtt_message(hass, "bridge/player/volume_mute_state", payload)
        await hass.async_block_till_done()
        state = hass.states.get(ENTITY_ID)
        assert state is not None
        assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is expected

    async_fire_mqtt_message(hass, "bridge/player/volume_mute_state", "")
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False

    with caplog.at_level(logging.WARNING):
        async_fire_mqtt_message(hass, "bridge/player/volume_mute_state", "bogus")
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert any("Unexpected boolean payload" in record.getMessage() for record in caplog.records)
