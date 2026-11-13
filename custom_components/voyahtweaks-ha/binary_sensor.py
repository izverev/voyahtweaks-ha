"""Binary sensors."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VoyahConfigEntry
from .coordinator import VehicleData
from .decoders import (
    S,
    Telemetry,
    charger_connected,
    climate_flag,
    climate_remote_active,
    door_open,
    is_charging,
    lock_unlocked,
    sentry_active,
    tailgate_open,
)
from .entity import VoyahEntity, add_dynamic

PARALLEL_UPDATES = 0

ValueFn = Callable[[Telemetry, VehicleData], bool | None]
AttrFn = Callable[[Telemetry, VehicleData], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class VoyahBinaryDescription(BinarySensorEntityDescription):
    paths: tuple[str, ...] = ()
    value_fn: ValueFn
    attrs_fn: AttrFn | None = None
    always: bool = False


def _raw_attr(*paths: str) -> AttrFn:
    return lambda t, d: {"raw_value": t.get(*paths)}


def _door(key: str, field: str) -> VoyahBinaryDescription:
    paths = S(field)
    return VoyahBinaryDescription(
        key=key,
        paths=paths,
        value_fn=lambda t, d: door_open(t.get(*paths)),
        attrs_fn=_raw_attr(*paths),
        device_class=BinarySensorDeviceClass.DOOR,
    )


def _climate(key: str, field: str, active: int, icon: str) -> VoyahBinaryDescription:
    paths = S(field)
    return VoyahBinaryDescription(
        key=key,
        paths=paths,
        value_fn=lambda t, d: climate_flag(t.get(*paths), active),
        attrs_fn=_raw_attr(*paths),
        icon=icon,
    )


_TAILGATE = S("tailgate")
_LOCK = S("lock_fl")
_SENTRY = S("sentry_switch")
_DC = S("bms_dcChargeConnection")
_AC = S("bms_acChargeConnection")
_SYS = S("ac_systemOnOffSts")
_CLIMATE_SRC = (
    *S("AC_RemResp_Sts"),
    *S("AC_RemCool_Sts"),
    *S("AC_RemHeat_Sts"),
    *_SYS,
    *S("bcm_remoteMode"),
)

BINARY_SENSORS: tuple[VoyahBinaryDescription, ...] = (
    # ---- status (always created, independent from each other) -----------
    VoyahBinaryDescription(
        key="api",
        value_fn=lambda t, d: d.api_ok,
        attrs_fn=lambda t, d: {
            "last_error": d.last_error,
            "consecutive_failures": d.consecutive_failures,
        },
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        always=True,
    ),
    VoyahBinaryDescription(
        key="online",
        paths=("online",),
        value_fn=lambda t, d: t.get("online") if isinstance(t.get("online"), bool) else None,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        always=True,
    ),
    VoyahBinaryDescription(
        key="telemetry_fresh",
        value_fn=lambda t, d: d.fresh,
        attrs_fn=lambda t, d: {
            "age_seconds": None if d.age_seconds is None else round(d.age_seconds),
            "threshold_minutes": round(d.stale_threshold_seconds / 60),
            "last_seen_changed": d.last_seen_changed,
        },
        icon="mdi:clock-check-outline",
        always=True,
    ),
    # ---- charging -------------------------------------------------------
    VoyahBinaryDescription(
        key="charging",
        paths=("chg_state",),
        value_fn=lambda t, d: is_charging(t.get("chg_state")),
        attrs_fn=lambda t, d: {"chg_state": t.get("chg_state")},
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    VoyahBinaryDescription(
        key="charger_connected",
        paths=(*_DC, *_AC),
        value_fn=lambda t, d: charger_connected(t.get(*_DC), t.get(*_AC)),
        attrs_fn=lambda t, d: {"dc_raw": t.get(*_DC), "ac_raw": t.get(*_AC)},
        device_class=BinarySensorDeviceClass.PLUG,
    ),
    # ---- body -----------------------------------------------------------
    _door("door_fl", "door_fl"),
    _door("door_fr", "door_fr"),
    _door("door_rl", "door_rl"),
    _door("door_rr", "door_rr"),
    VoyahBinaryDescription(
        key="tailgate",
        paths=_TAILGATE,
        value_fn=lambda t, d: tailgate_open(t.get(*_TAILGATE)),
        attrs_fn=_raw_attr(*_TAILGATE),
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:car-back",
    ),
    VoyahBinaryDescription(
        key="lock",
        paths=_LOCK,
        # device class LOCK: on == unlocked
        value_fn=lambda t, d: lock_unlocked(t.get(*_LOCK)),
        attrs_fn=_raw_attr(*_LOCK),
        device_class=BinarySensorDeviceClass.LOCK,
    ),
    VoyahBinaryDescription(
        key="sentry_active",
        paths=_SENTRY,
        value_fn=lambda t, d: sentry_active(t.get(*_SENTRY)),
        attrs_fn=_raw_attr(*_SENTRY),
        icon="mdi:shield-car",
    ),
    # ---- climate --------------------------------------------------------
    VoyahBinaryDescription(
        key="climate_remote",
        paths=_CLIMATE_SRC,
        value_fn=lambda t, d: climate_remote_active(t),
        attrs_fn=lambda t, d: {
            "AC_RemResp_Sts": t.sensor("AC_RemResp_Sts"),
            "AC_RemCool_Sts": t.sensor("AC_RemCool_Sts"),
            "AC_RemHeat_Sts": t.sensor("AC_RemHeat_Sts"),
            "ac_systemOnOffSts": t.sensor("ac_systemOnOffSts"),
            "bcm_remoteMode": t.sensor("bcm_remoteMode"),
        },
        icon="mdi:air-conditioner",
    ),
    _climate("climate_cooling", "AC_RemCool_Sts", 2, "mdi:snowflake"),
    _climate("climate_heating", "AC_RemHeat_Sts", 2, "mdi:fire"),
    _climate("climate_system", "ac_systemOnOffSts", 1, "mdi:fan"),
)


class VoyahBinarySensor(VoyahEntity, BinarySensorEntity):
    entity_description: VoyahBinaryDescription

    def __init__(self, coordinator, description: VoyahBinaryDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(
            Telemetry(self.vdata.telemetry), self.vdata
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attrs_fn
        if fn is None:
            return None
        return fn(Telemetry(self.vdata.telemetry), self.vdata)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VoyahConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates() -> Iterable[tuple[str, Callable[[], Entity]]]:
        tele = Telemetry(coordinator.data.telemetry)
        for desc in BINARY_SENSORS:
            if desc.always or tele.has(*desc.paths):
                yield (desc.key, lambda desc=desc: VoyahBinarySensor(coordinator, desc))

    add_dynamic(entry, coordinator, async_add_entities, candidates)
