"""Diagnostics download (secrets and location redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import VoyahConfigEntry

TO_REDACT = {
    "password",
    "username",
    "access_token",
    "refresh_token",
    "device_token",
    "vin",
    "email",
    "lat",
    "lon",
    "latitude",
    "longitude",
    "gps",
    "last_position",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VoyahConfigEntry
) -> dict[str, Any]:
    """Return diagnostics, including the full raw telemetry JSON.

    The raw JSON is what is needed to verify field paths and enum values.
    """
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "state": {
            "api_ok": data.api_ok,
            "last_error": data.last_error,
            "consecutive_failures": data.consecutive_failures,
            "last_success": data.last_success.isoformat() if data.last_success else None,
            "last_seen_raw": data.last_seen_raw,
            "last_seen": data.last_seen.isoformat() if data.last_seen else None,
            "last_seen_changed": data.last_seen_changed,
            "age_seconds": data.age_seconds,
            "fresh": data.fresh,
            "poll_interval_s": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
        },
        "telemetry": async_redact_data(data.telemetry, TO_REDACT),
    }
