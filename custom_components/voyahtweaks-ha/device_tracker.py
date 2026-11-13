"""GPS device tracker."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VoyahConfigEntry
from .entity import VoyahEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VoyahConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([VoyahTracker(entry.runtime_data)])


class VoyahTracker(VoyahEntity, TrackerEntity):
    """Position = last VALID fix (power.location.gps_valid == true).

    An invalid fix never overwrites the stored position and no fake
    coordinates are produced.
    """

    _attr_translation_key = "location"
    _attr_icon = "mdi:car-connected"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "location")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        pos = self.vdata.last_position
        return pos[0] if pos else None

    @property
    def longitude(self) -> float | None:
        pos = self.vdata.last_position
        return pos[1] if pos else None

    @property
    def location_accuracy(self) -> float:
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        loc = (self.vdata.telemetry.get("power") or {}).get("location")
        valid = loc.get("gps_valid") if isinstance(loc, dict) else None
        return {"gps_valid_in_last_update": valid}
