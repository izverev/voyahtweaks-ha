"""Voyah Free integration for Home Assistant (via Voyahtweaks)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Tokens, VoyahApi
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_TOKEN,
    CONF_REFRESH_TOKEN,
)
from .coordinator import VoyahCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    # command platforms; they add nothing unless commands are enabled in options
    Platform.LOCK,
    Platform.COVER,
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.CLIMATE,
]

type VoyahConfigEntry = ConfigEntry[VoyahCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: VoyahConfigEntry) -> bool:
    """Set up the integration from a config entry."""

    @callback
    def _store_tokens(tokens: Tokens) -> None:
        """Persist renewed tokens in the config entry (secrets stay there)."""
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_ACCESS_TOKEN: tokens.access_token,
                CONF_REFRESH_TOKEN: tokens.refresh_token,
                CONF_DEVICE_TOKEN: tokens.device_token,
            },
        )

    api = VoyahApi(
        async_get_clientsession(hass),
        tokens=Tokens(
            entry.data.get(CONF_ACCESS_TOKEN),
            entry.data.get(CONF_REFRESH_TOKEN),
            entry.data.get(CONF_DEVICE_TOKEN),
        ),
        token_callback=_store_tokens,
    )

    coordinator = VoyahCoordinator(hass, entry, api)
    # Restore the last known state so entities have values right after a restart.
    await coordinator.async_load_cache()
    # May raise ConfigEntryAuthFailed (-> reauth flow).
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.data.telemetry and not coordinator.data.api_ok:
        raise ConfigEntryNotReady(
            f"Voyahtweaks API unavailable: {coordinator.data.last_error}"
        )

    entry.runtime_data = coordinator

    await coordinator.async_refresh_profile()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(hass: HomeAssistant, entry: VoyahConfigEntry) -> None:
    """Reload only when options changed (token/name updates must not reload)."""
    if dict(entry.options) != entry.runtime_data.options_snapshot:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VoyahConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
