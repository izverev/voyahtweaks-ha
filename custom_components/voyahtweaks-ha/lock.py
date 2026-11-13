"""Door lock control (door_lock / door_unlock)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VoyahConfigEntry
from .decoders import S, Telemetry, lock_unlocked
from .entity import VoyahCommandEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: VoyahConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.commands_enabled:
        async_add_entities([VoyahLock(coordinator)])


class VoyahLock(VoyahCommandEntity, LockEntity):
    _attr_translation_key = "ctl_lock"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "ctl_lock")

    @property
    def is_locked(self) -> bool | None:
        if self._optimistic is not None:
            return self._optimistic
        unlocked = lock_unlocked(Telemetry(self.vdata.telemetry).get(*S("lock_fl")))
        return None if unlocked is None else not unlocked

    async def async_lock(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command("door_lock")
        self._set_optimistic(True)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_command("door_unlock")
        self._set_optimistic(False)
