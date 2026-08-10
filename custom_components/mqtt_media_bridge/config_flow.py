"""
Config flow for mqtt_media_bridge.

This module provides backwards compatibility for hassfest.
The actual implementation is in the config_flow_handler package.
"""

from __future__ import annotations

from .config_flow_handler import MqttMediaConfigFlowHandler

__all__ = ["MqttMediaConfigFlowHandler"]
