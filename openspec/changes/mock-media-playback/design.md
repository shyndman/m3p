## Context
We need a CLI media-player emulator to test the M3P integration without a physical TV. The tool must behave like a real MQTT media player via Home Assistant discovery and state topics, and it must automatically progress playback and roll to a new fake track when the current one ends. The tool is **completely disjoint** from the integration code; no shared modules or runtime coupling.

## Goals / Non-Goals
- Goals:
  - Use `shyndman/ha-mqtt-discoverable` (GitHub `main`) to publish discovery and state/metadata.
  - Subscribe to command topics and update state accordingly.
  - Start playing immediately on launch.
  - Maintain a playback clock that advances while playing (1-second ticks).
  - On track end, create a new fake track and continue playback.
  - Generate PNG artwork in Python on the fly and publish it as a data URL.
  - Load MQTT connection settings from `tools/.env` (uncommitted) with defaults mirrored in `tools/.env.sample`.
- Non-Goals:
  - Advanced playback features (shuffle/repeat/source lists) unless requested later.
  - Shared libraries or code between this tool and the Home Assistant integration.

## Decisions
- Decision: Implement as an isolated `uv` application in `tools/mock-player/`.
  - Why: Tool is separate from integration; `uv` keeps dependencies isolated.
- Decision: Use `paho.mqtt.Client(transport="websockets")` and pass it to `Settings.mqtt.client`.
  - Why: Broker is exposed at `ws://ha-mosquitto-ws.don:80`; `ha-mqtt-discoverable` accepts a prebuilt client.
- Decision: Use a 1-second tick loop for playback progression.
  - Why: Minimal complexity, sufficient for manual testing, deterministic.
- Decision: Track metadata uses simple placeholders (`aaa`, `bbb`, `ccc`, ...) with deterministic cycling.
  - Why: Easy to recognize and verify during manual tests.
- Decision: Generate PNG art via Pillow and embed it as a `data:image/png;base64,...` URL.
  - Why: Close to real TV behavior without needing a file server.

## Alternatives considered
- Event-driven clock with higher precision: rejected as unnecessary complexity for manual testing.
- Using `mosquitto_pub/sub` wrappers instead of a full client: rejected because we need command callbacks and auto-updating state.

## Risks / Trade-offs
- 1-second tick loop may drift slightly; acceptable for manual testing.
- `ha-mqtt-discoverable` mute payload parsing expects `ON/OFF` while M3P publishes `true/false`; callbacks will parse raw payload from the MQTT message to avoid mismatch.

## Migration Plan
- None. This is a new tool and does not modify existing runtime behavior.

## Open Questions
- None.
