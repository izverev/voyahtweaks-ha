"""Sentry mode and charging switches (+ charging entity services)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import VoyahConfigEntry
from .const import DEFAULT_CHARGE_MAX_SOC
from .decoders import S, Telemetry, is_charging, sentry_active
from .entity import VoyahCommandEntity

PARALLEL_UPDATES = 1

TIME_RE = r"^([01]\d|2[0-3]):[0-5]\d$"
SOC = vol.All(vol.Coerce(int), vol.Range(min=50, max=100))


async def async_setup_entry(
    hass: HomeAssistant, entry: VoyahConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if not coordinator.commands_enabled:
        return
    async_add_entities([VoyahSentrySwitch(coordinator), VoyahChargeSwitch(coordinator)])

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "charge_start",
        {vol.Optional("max_soc", default=DEFAULT_CHARGE_MAX_SOC): SOC},
        "async_charge_start",
    )
    platform.async_register_entity_service(
        "charge_schedule",
        {
            vol.Required("start"): vol.All(cv.string, vol.Match(TIME_RE)),
            vol.Required("end"): vol.All(cv.string, vol.Match(TIME_RE)),
            vol.Optional("max_soc", default=DEFAULT_CHARGE_MAX_SOC): SOC,
            vol.Optional("cycle", default=False): cv.boolean,
        },
        "async_charge_schedule",
    )
    platform.async_register_entity_service(
        "charge_cancel_schedule", {}, "async_charge_cancel_schedule"
    )


class VoyahSentrySwitch(VoyahCommandEntity, SwitchEntity):
    _attr_translation_key = "ctl_sentry"
    _attr_icon = "mdi:shield-car"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "ctl_sentry")

    @property
    def is_on(self) -> bool | None:
        if self._optimistic is not None:
            return self._optimistic
        return sentry_active(Telemetry(self.vdata.telemetry).get(*S("sentry_switch")))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command("sentry_on")
        self._set_optimistic(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command("sentry_off")
        self._set_optimistic(False)


class VoyahChargeSwitch(VoyahCommandEntity, SwitchEntity):
    """On = charging now. Turning on starts charging up to the default SOC."""

    _attr_translation_key = "ctl_charge"
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "ctl_charge")

    @property
    def is_on(self) -> bool | None:
        if self._optimistic is not None:
            return self._optimistic
        return is_charging(Telemetry(self.vdata.telemetry).get("chg_state"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.async_charge_start(DEFAULT_CHARGE_MAX_SOC)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command("charge", {"op": "stop"})
        self._set_optimistic(False)

    async def async_charge_start(self, max_soc: int = DEFAULT_CHARGE_MAX_SOC) -> None:
        await self.coordinator.async_send_command(
            "charge", {"op": "start_now", "max_soc": int(max_soc)}
        )
        self._set_optimistic(True)

    async def async_charge_schedule(
        self, start: str, end: str, max_soc: int, cycle: bool
    ) -> None:
        await self.coordinator.async_send_command(
            "charge",
            {"op": "schedule", "start": start, "end": end,
             "max_soc": int(max_soc), "cycle": bool(cycle)},
        )

    async def async_charge_cancel_schedule(self) -> None:
        await self.coordinator.async_send_command("charge", {"op": "schedule_cancel"})
