## ADDED Requirements

### Requirement: Provide a standalone mock media player CLI
The system SHALL provide a CLI tool located at `tools/mock-player/` that acts as a media player device for manual testing of the M3P integration using `shyndman/ha-mqtt-discoverable` from GitHub `main`.

#### Scenario: Tool starts and is discoverable
- **WHEN** the CLI starts
- **THEN** it publishes a Home Assistant MQTT discovery payload for a media player entity
- **AND** Home Assistant creates the media player entity from that payload

### Requirement: Tool is fully disjoint from integration code
The system SHALL keep the mock player tool isolated from `custom_components/m3p/` with no shared modules or runtime coupling.

#### Scenario: Separation of concerns
- **WHEN** the tool runs
- **THEN** it operates without importing or relying on any integration code under `custom_components/m3p/`

### Requirement: Use WebSocket MQTT via environment configuration
The system SHALL load MQTT connection settings from `tools/.env` with defaults in `tools/.env.sample`, and use `paho.mqtt.Client(transport="websockets")` for the connection.

#### Scenario: WebSocket connection
- **WHEN** `MQTT_WS_URL` is set to `ws://ha-mosquitto-ws.don:80`
- **THEN** the tool connects via WebSocket transport
- **AND** publishes discovery and state updates successfully

### Requirement: Publish playback state and metadata
The system SHALL publish media player state and metadata updates to MQTT so Home Assistant displays current playback information.

#### Scenario: Initial state on startup
- **WHEN** the CLI starts
- **THEN** it publishes state `playing`
- **AND** it publishes track title, artist, album, duration, position, and artwork URL

### Requirement: Auto-advance playback position while playing
The system SHALL automatically advance playback position over time while in a `playing` state, using a 1-second tick loop.

#### Scenario: Playback clock progresses
- **WHEN** the CLI is in `playing` state for N seconds
- **THEN** it publishes updated playback position values that increase over time

### Requirement: Start a new fake track when the current one ends
The system SHALL generate and publish a new fake track when playback reaches the end of the current track.

#### Scenario: Track ends
- **WHEN** playback position reaches or exceeds track duration
- **THEN** the CLI publishes metadata for a new fake track
- **AND** it resets playback position to 0
- **AND** playback continues in `playing` state

### Requirement: React to Home Assistant commands
The system SHALL subscribe to command topics and update playback state accordingly.

#### Scenario: Pause and resume
- **WHEN** Home Assistant publishes a pause command
- **THEN** the CLI publishes state `paused` and stops advancing the clock
- **WHEN** Home Assistant publishes a play command
- **THEN** the CLI publishes state `playing` and resumes advancing the clock

#### Scenario: Seek
- **WHEN** Home Assistant publishes a seek command with a new position
- **THEN** the CLI publishes the updated playback position

#### Scenario: Next track
- **WHEN** Home Assistant publishes a next-track command
- **THEN** the CLI publishes metadata for a new fake track
- **AND** it resets playback position to 0

#### Scenario: Stop
- **WHEN** Home Assistant publishes a stop command
- **THEN** the CLI publishes state `idle`
- **AND** it resets playback position to 0

### Requirement: Generate PNG artwork in Python
The system SHALL generate PNG media artwork in Python and publish it as a data URL for each new track.

#### Scenario: Artwork per track
- **WHEN** a new fake track is generated
- **THEN** the CLI publishes a freshly generated PNG artwork data URL

### Requirement: Explicit CLI interface
The system SHALL provide a CLI entrypoint via `scripts/mock-player` with predictable defaults and overridable environment settings.

#### Scenario: Runner usage
- **WHEN** a developer runs `scripts/mock-player`
- **THEN** the tool loads `tools/.env` if present
- **AND** the tool starts the mock media player with the configured settings
