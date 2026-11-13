"""Remote climate control (cmd "climate")."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import VoyahConfigEntry
from .const import CLIMATE_DEFAULT_TEMP, CLIMATE_MAX_TEMP, CLIMATE_MIN_TEMP
from .decoders import S, Telemetry, climate_remote_active
from .entity import VoyahCommandEntity

PARALLEL_UPDATES = 1

PRESET_COOL = "rapid_cool"
PRESET_HEAT = "rapid_heat"
SEAT = vol.All(vol.Coerce(int), vol.Range(min=-3, max=3))


async def async_setup_entry(
    hass: HomeAssistant, entry: VoyahConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if not coordinator.commands_enabled:
        return
    async_add_entities([VoyahClimate(coordinator)])

    async_get_current_platform().async_register_entity_service(
        "climate_start",
        {
            vol.Optional("mode", default="temp"): vol.In(["temp", PRESET_COOL, PRESET_HEAT]),
            vol.Optional("temperature"): vol.All(
                vol.Coerce(float), vol.Range(min=CLIMATE_MIN_TEMP, max=CLIMATE_MAX_TEMP)
            ),
            vol.Optional("seat_fl"): SEAT,
            vol.Optional("seat_fr"): SEAT,
            vol.Optional("glass_heat"): cv.boolean,
            vol.Optional("runtime"): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
        },
        "async_climate_start",
    )


class VoyahClimate(VoyahCommandEntity, ClimateEntity):
    _attr_translation_key = "ctl_climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_preset_modes = [PRESET_COOL, PRESET_HEAT]
    _attr_min_temp = CLIMATE_MIN_TEMP
    _attr_max_temp = CLIMATE_MAX_TEMP
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "ctl_climate")
        self._target = CLIMATE_DEFAULT_TEMP
        self._preset: str | None = None

    @property
    def current_temperature(self) -> float | None:
        return Telemetry(self.vdata.telemetry).sensor_num("ac_cabinTemp")

    @property
    def target_temperature(self) -> float:
        return self._target

    @property
    def hvac_mode(self) -> HVACMode | None:
        if self._optimistic is not None:
            return self._optimistic
        active = climate_remote_active(Telemetry(self.vdata.telemetry))
        if active is None:
            return None
        return HVACMode.HEAT_COOL if active else HVACMode.OFF

    @property
    def preset_mode(self) -> str | None:
        return self._preset if self.hvac_mode == HVACMode.HEAT_COOL else None

    # ---- commands ----------------------------------------------------------
    async def _start(self, mode: str, payload: dict[str, Any]) -> None:
        await self.coordinator.async_send_command("climate", {"mode": mode, **payload})
        self._preset = mode if mode != "temp" else None
        self._set_optimistic(HVACMode.HEAT_COOL)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_send_command("climate", {"mode": "off"})
            self._preset = None
            self._set_optimistic(HVACMode.OFF)
        else:
            await self._start("temp", {"temp": self._target})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._target = float(temp)
        if kwargs.get("hvac_mode") == HVACMode.OFF:
            await self.async_set_hvac_mode(HVACMode.OFF)
        elif kwargs.get("hvac_mode") == HVACMode.HEAT_COOL or self.hvac_mode == HVACMode.HEAT_COOL:
            await self._start("temp", {"temp": self._target})
        else:
            # Only remember the target; changing it must not start the climate.
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._start(preset_mode, {})

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT_COOL)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_climate_start(
        self,
        mode: str = "temp",
        temperature: float | None = None,
        seat_fl: int | None = None,
        seat_fr: int | None = None,
        glass_heat: bool | None = None,
        runtime: int | None = None,
    ) -> None:
        """Entity service: start climate with every option the app supports."""
        payload: dict[str, Any] = {}
        if mode == "temp":
            temp = temperature if temperature is not None else self._target
            payload["temp"] = float(temp)
            self._target = float(temp)
        for key, value in (
            ("seat_fl", seat_fl), ("seat_fr", seat_fr),
            ("glass_heat", glass_heat), ("runtime", runtime),
        ):
            if value is not None:
                payload[key] = value
        await self._start(mode, payload)
