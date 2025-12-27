# Change: Add mock media playback CLI for M3P manual testing

## Why
Manual testing of the M3P integration currently requires a physical TV. A lightweight CLI media-player emulator will let us test discovery, state updates, and command roundtrips without hardware.

## What Changes
- Add a new, **standalone** CLI tool under `tools/mock-player/` that behaves like a full MQTT media player using `shyndman/ha-mqtt-discoverable` (GitHub `main`).
- The mock player publishes discovery + state/metadata and subscribes to command topics.
- The mock player auto-advances a playback clock while playing and starts a new fake track when one finishes.
- The mock player generates PNG album art in Python for each track and publishes it as a data URL.
- Provide an easy runner script at `scripts/mock-player`.
- Provide `tools/.env.sample` with all supported environment variables; `tools/.env` is uncommitted and used for local overrides.

## Impact
- Affected specs: `mock-media-playback` (new capability)
- Affected code: new tool in `tools/mock-player/`, new runner in `scripts/`, new `tools/.env.sample`
