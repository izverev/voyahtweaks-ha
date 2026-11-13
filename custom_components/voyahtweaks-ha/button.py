"""One-shot command buttons."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VoyahConfigEntry
from .const import DANGEROUS_COMMANDS
from .entity import VoyahEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True)
class ButtonDef:
    key: str
    cmd: str
    icon: str


BUTTONS = (
    # horn + hazard lights, "find my car"
    ButtonDef("btn_find_start", "search_start", "mdi:bullhorn"),
    ButtonDef("btn_find_stop", "search_stop", "mdi:bullhorn-outline"),
    ButtonDef("btn_hazard", "hazard_on", "mdi:car-light-alert"),
    ButtonDef("btn_windows_vent", "windows_vent", "mdi:window-open-variant"),
    ButtonDef("btn_sunroof_vent", "sunroof_vent", "mdi:car-select"),
    ButtonDef("btn_keyless_start", "keyless_start", "mdi:engine"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: VoyahConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if not coordinator.commands_enabled:
        return
    async_add_entities(
        VoyahButton(coordinator, d)
        for d in BUTTONS
        if d.cmd not in DANGEROUS_COMMANDS or coordinator.dangerous_enabled
    )


class VoyahButton(VoyahEntity, ButtonEntity):
    def __init__(self, coordinator, definition: ButtonDef) -> None:
        super().__init__(coordinator, definition.key)
        self._def = definition
        self._attr_translation_key = definition.key
        self._attr_icon = definition.icon

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(self._def.cmd)
