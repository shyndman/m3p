## 1. Implementation
- [x] 1.1 Create `tools/mock-player/` as a standalone `uv` app (`uv init --application`).
- [x] 1.2 Add dependency on `shyndman/ha-mqtt-discoverable` from GitHub `main` and `Pillow` for PNG generation.
- [x] 1.3 Add `tools/.env.sample` with all supported settings and defaults; do not commit `tools/.env`.
- [x] 1.4 Implement `tools/mock-player/src/mock_player/main.py` with:
  - MQTT WS client via `paho.mqtt.Client(transport="websockets")` using `MQTT_WS_URL`.
  - `ha_mqtt_discoverable.MediaPlayer` wired with callbacks for play/pause/stop/next/previous/seek/volume_set/volume_mute.
  - Playback loop ticking every `TICK_SECONDS` (default 1) and advancing position while state is `playing`.
  - Track generator cycling titles `aaa`, `bbb`, `ccc`, ... and random duration in `[TRACK_DURATION_MIN_SECONDS, TRACK_DURATION_MAX_SECONDS]`.
  - PNG artwork generation per track and publish as `data:image/png;base64,...`.
  - On track end: generate next track, reset position to 0, remain `playing`.
  - On stop: set state `idle` and reset position to 0.
  - On pause: set state `paused` and stop clock.
  - On play: set state `playing` and resume clock.
  - On seek: set position to payload value and publish immediately.
- [x] 1.5 Add `scripts/mock-player` runner that executes the tool (loading `tools/.env`).
- [x] 1.6 Add a brief tool README in `tools/mock-player/README.md` with usage and env var reference.

## 2. Validation
- [x] 2.1 Run `openspec validate mock-media-playback --strict` and fix any issues.
- [ ] 2.2 Manually verify in Home Assistant that discovery, state updates, artwork, and command handling work end-to-end.
