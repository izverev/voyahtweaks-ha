"""Windows, sunroof and tailgate control."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VoyahConfigEntry
from .decoders import S, Telemetry, sunroof_state, tailgate_open, window_state
from .entity import VoyahCommandEntity

PARALLEL_UPDATES = 1


def _windows_closed(t: Telemetry) -> bool | None:
    states = [window_state(t.get(*S(n))) for n in ("win_lf", "win_rf", "win_lr", "win_rr")]
    known = [s for s in states if s is not None]
    if not known:
        return None
    return all(s == "closed" for s in known)


def _sunroof_closed(t: Telemetry) -> bool | None:
    state = sunroof_state(t.get(*S("sunroof")))
    return None if state is None else state == "closed"


def _tailgate_closed(t: Telemetry) -> bool | None:
    opened = tailgate_open(t.get(*S("tailgate")))
    return None if opened is None else not opened


@dataclass(frozen=True)
class CoverDef:
    key: str
    device_class: CoverDeviceClass
    open_cmd: str
    close_cmd: str
    closed_fn: Callable[[Telemetry], bool | None]
    icon: str | None = None


COVERS = (
    # windows_open / windows_close act on all four windows at once
    CoverDef("ctl_windows", CoverDeviceClass.WINDOW, "windows_open", "windows_close",
             _windows_closed, "mdi:car-door"),
    CoverDef("ctl_sunroof", CoverDeviceClass.WINDOW, "sunroof_open", "sunroof_close",
             _sunroof_closed, "mdi:car-select"),
    CoverDef("ctl_tailgate", CoverDeviceClass.DOOR, "tailgate_open", "tailgate_close",
             _tailgate_closed, "mdi:car-back"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: VoyahConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.commands_enabled:
        async_add_entities([VoyahCover(coordinator, d) for d in COVERS])


class VoyahCover(VoyahCommandEntity, CoverEntity):
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, coordinator, definition: CoverDef) -> None:
        super().__init__(coordinator, definition.key)
        self._def = definition
        self._attr_translation_key = definition.key
        self._attr_device_class = definition.device_class
        if definition.icon:
            self._attr_icon = definition.icon

    @property
    def is_closed(self) -> bool | None:
        if self._optimistic is not None:
            return self._optimistic
        return self._def.closed_fn(Telemetry(self.vdata.telemetry))

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(self._def.open_cmd)
        self._set_optimistic(False)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command(self._def.close_cmd)
        self._set_optimistic(True)
