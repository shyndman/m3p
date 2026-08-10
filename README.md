# MQTT Media Bridge

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

Creates Home Assistant media players from MQTT discovery messages, with playback controls, volume, sources, sound modes, and media metadata.

## Discovery schema

Publish a retained JSON object to `homeassistant/media_player/<node_id>/<object_id>/config`. `unique_id` is required; standard Home Assistant MQTT entity fields are also accepted.

| Type             | Fields                                                                                                                                                                                                                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `string`         | `unique_id`                                                                                                                                                                                                                                                                                            |
| `string \| null` | `name`                                                                                                                                                                                                                                                                                                 |
| `string`         | `state_topic`, `media_album_name_topic`, `media_artist_topic`, `media_duration_topic`, `media_image_remotely_accessible_topic`, `media_image_url_topic`, `media_position_topic`, `media_title_topic`, `repeat_state_topic`, `shuffle_state_topic`, `volume_level_topic`, `volume_mute_state_topic`     |
| `string`         | `next_track_topic`, `pause_topic`, `play_topic`, `play_media_topic`, `previous_track_topic`, `repeat_set_topic`, `seek_topic`, `select_sound_mode_topic`, `select_source_topic`, `shuffle_set_topic`, `stop_topic`, `turn_off_topic`, `turn_on_topic`, `volume_mute_command_topic`, `volume_set_topic` |
| `string[]`       | `source_list`, `sound_mode_list`                                                                                                                                                                                                                                                                       |
| `number`         | `volume_step`                                                                                                                                                                                                                                                                                          |

[commits-shield]: https://img.shields.io/github/commit-activity/y/shyndman/ha-mqtt-media-bridge.svg?style=for-the-badge
[commits]: https://github.com/shyndman/ha-mqtt-media-bridge/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/shyndman/ha-mqtt-media-bridge.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40shyndman-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/shyndman/ha-mqtt-media-bridge.svg?style=for-the-badge
[releases]: https://github.com/shyndman/ha-mqtt-media-bridge/releases
