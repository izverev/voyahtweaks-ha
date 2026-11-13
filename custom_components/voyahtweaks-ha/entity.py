"""Shared entity base and dynamic entity creation."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VehicleData, VoyahCoordinator


class VoyahEntity(CoordinatorEntity[VoyahCoordinator]):
    """Base entity. Always available: last known values are kept on purpose."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: VoyahCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.vin}_{key}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        # A sleeping car or a failing API must not make entities "unavailable";
        # the API / freshness entities describe the real situation.
        return True

    @property
    def vdata(self) -> VehicleData:
        return self.coordinator.data


class VoyahCommandEntity(VoyahEntity):
    """Entity that can send commands and shows the expected result at once.

    The optimistic value is dropped as soon as a newer successful poll arrives,
    so the real telemetry (even if the car is asleep and still reports the old
    state) always wins in the end.
    """

    _optimistic: Any = None
    _opt_marker: Any = None

    def _set_optimistic(self, value: Any) -> None:
        self._optimistic = value
        self._opt_marker = self.vdata.last_success
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._optimistic is not None and self.vdata.last_success != self._opt_marker:
            self._optimistic = None
        super()._handle_coordinator_update()


def add_dynamic(
    entry: ConfigEntry,
    coordinator: VoyahCoordinator,
    async_add_entities: AddEntitiesCallback,
    candidates: Callable[[], Iterable[tuple[str, Callable[[], Entity]]]],
) -> None:
    """Add entities now and whenever new telemetry fields appear later.

    ``candidates`` yields ``(unique_key, factory)`` only for entities whose
    source data currently exists, so no wall of permanently-unknown entities.
    """
    known: set[str] = set()

    def _check() -> None:
        new: list[Entity] = []
        for key, factory in candidates():
            if key in known:
                continue
            known.add(key)
            new.append(factory())
        if new:
            async_add_entities(new)

    _check()
    entry.async_on_unload(coordinator.async_add_listener(_check))

