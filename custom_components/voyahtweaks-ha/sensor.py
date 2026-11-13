"""Sensors."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VoyahConfigEntry
from .coordinator import VehicleData
from .decoders import (
    S,
    Telemetry,
    array_value,
    cell_voltage_delta,
    charge_remaining_minutes,
    charge_type,
    sentry_state,
    sunroof_state,
    to_number,
    window_state,
)
from .entity import VoyahEntity, add_dynamic

PARALLEL_UPDATES = 0

MEAS = SensorStateClass.MEASUREMENT

ValueFn = Callable[[Telemetry, VehicleData], Any]
AttrFn = Callable[[Telemetry, VehicleData], dict[str, Any]]


@dataclass(frozen=True, kw_only=True)
class VoyahSensorDescription(SensorEntityDescription):
    """Sensor description.

    ``paths`` are the candidate JSON paths (first non-null wins). A sensor is
    created only if one of the paths exists in the telemetry, unless
    ``always`` is set. ``detail`` marks the optional diagnostic group.
    """

    paths: tuple[str, ...] = ()
    value_fn: ValueFn | None = None
    attrs_fn: AttrFn | None = None
    always: bool = False
    detail: bool = False


def _raw_attr(*paths: str) -> AttrFn:
    return lambda t, d: {"raw_value": t.get(*paths)}


def _text(*paths: str) -> ValueFn:
    def fn(t: Telemetry, _d: VehicleData) -> Any:
        val = t.get(*paths)
        return None if val is None else str(val)

    return fn


def _window(sensor_name: str) -> dict[str, Any]:
    paths = S(sensor_name)
    return {
        "paths": paths,
        "value_fn": lambda t, d, p=paths: window_state(t.get(*p)),
        "attrs_fn": _raw_attr(*paths),
        "device_class": SensorDeviceClass.ENUM,
        "options": ["closed", "ajar", "open"],
        "icon": "mdi:car-door",
    }


_SUNROOF = S("sunroof")
_SENTRY = S("sentry_switch")
_DC = S("bms_dcChargeConnection")
_AC = S("bms_acChargeConnection")
_REMAIN = S("bms_remainChargeTime")

SENSORS: tuple[VoyahSensorDescription, ...] = (
    # ---- battery / powertrain ------------------------------------------
    VoyahSensorDescription(
        key="soc",
        paths=("soc_pct", "power.vehicle.soc_pct", *S("bms_SOC")),
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="soh",
        paths=S("bms_SOH"),
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEAS,
        icon="mdi:battery-heart-variant",
        suggested_display_precision=1,
    ),
    VoyahSensorDescription(
        key="soe",
        paths=S("bms_SOE"),
        native_unit_of_measurement=PERCENTAGE,  # unit not confirmed
        state_class=MEAS,
        icon="mdi:battery-charging-medium",
    ),
    VoyahSensorDescription(
        key="residual_energy",
        paths=S("bms_residualEnergy"),
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="range",
        paths=S("vcu_remainingMileage"),
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=MEAS,
        icon="mdi:map-marker-distance",
    ),
    VoyahSensorDescription(
        key="range_real",
        paths=S("vcu_remainingMileageReal"),
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=MEAS,
        icon="mdi:map-marker-distance",
    ),
    VoyahSensorDescription(
        key="range_cluster",
        paths=S("ic_RemainingMileage"),
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=MEAS,
        entity_registry_enabled_default=False,
    ),
    VoyahSensorDescription(
        key="mileage",
        paths=("mileage_km", "power.vehicle.mileage_km"),
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
    ),
    VoyahSensorDescription(
        key="speed",
        paths=("speed_kmh", "power.vehicle.speed_kmh"),
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="hv_voltage",
        paths=("volt_v", "power.vehicle.volt_v"),
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="hv_current",
        paths=("current_a", "power.vehicle.current_a", *S("bms_iPack")),
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="battery_power",
        paths=S("bms_pPack"),
        # unit and sign convention are not confirmed -> raw value, off by default
        state_class=MEAS,
        icon="mdi:flash",
        entity_registry_enabled_default=False,
    ),
    VoyahSensorDescription(
        key="pack_temp_avg",
        paths=S("bms_packTempAvg"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="pack_temp_min",
        paths=("power.extremes.temp_min_c",),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="pack_temp_max",
        paths=("power.extremes.temp_max_c",),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="v12_voltage",
        paths=S("v12_volt"),
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="v12_percent",
        paths=S("batt12v_pct"),
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEAS,
        icon="mdi:car-battery",
    ),
    VoyahSensorDescription(
        key="v12_soh",
        paths=S("batt12v_soh"),
        native_unit_of_measurement=PERCENTAGE,  # unit not confirmed
        state_class=MEAS,
        icon="mdi:car-battery",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VoyahSensorDescription(
        key="fuel",
        paths=S("fuel_pct"),
        native_unit_of_measurement=PERCENTAGE,
        state_class=MEAS,
        icon="mdi:gas-station",
    ),
    VoyahSensorDescription(
        key="charging_power",
        paths=S("IC_ChargingPower"),
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="charge_remaining",
        paths=_REMAIN,
        value_fn=lambda t, d: charge_remaining_minutes(t.get(*_REMAIN)),
        attrs_fn=_raw_attr(*_REMAIN),
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=MEAS,
    ),
    # ---- climate temperatures ------------------------------------------
    VoyahSensorDescription(
        key="cabin_temp",
        paths=S("ac_cabinTemp"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
    ),
    VoyahSensorDescription(
        key="ambient_temp",
        paths=S("ac_ambientTemp"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
    ),
    # ---- tyres (bcm_tyre{LF,RF,LR,RR}{Pressure,Temp}) ----------------------
    VoyahSensorDescription(
        key="tire_pressure_fl",
        paths=S("bcm_tyreLFPressure"),
        # unit is not confirmed (the app shows a bare number, 1 decimal)
        state_class=MEAS,
        icon="mdi:car-tire-alert",
        suggested_display_precision=1,
    ),
    VoyahSensorDescription(
        key="tire_temp_fl",
        paths=S("bcm_tyreLFTemp"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
        suggested_display_precision=0,
    ),
    VoyahSensorDescription(
        key="tire_pressure_fr",
        paths=S("bcm_tyreRFPressure"),
        # unit is not confirmed (the app shows a bare number, 1 decimal)
        state_class=MEAS,
        icon="mdi:car-tire-alert",
        suggested_display_precision=1,
    ),
    VoyahSensorDescription(
        key="tire_temp_fr",
        paths=S("bcm_tyreRFTemp"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
        suggested_display_precision=0,
    ),
    VoyahSensorDescription(
        key="tire_pressure_rl",
        paths=S("bcm_tyreLRPressure"),
        # unit is not confirmed (the app shows a bare number, 1 decimal)
        state_class=MEAS,
        icon="mdi:car-tire-alert",
        suggested_display_precision=1,
    ),
    VoyahSensorDescription(
        key="tire_temp_rl",
        paths=S("bcm_tyreLRTemp"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
        suggested_display_precision=0,
    ),
    VoyahSensorDescription(
        key="tire_pressure_rr",
        paths=S("bcm_tyreRRPressure"),
        # unit is not confirmed (the app shows a bare number, 1 decimal)
        state_class=MEAS,
        icon="mdi:car-tire-alert",
        suggested_display_precision=1,
    ),
    VoyahSensorDescription(
        key="tire_temp_rr",
        paths=S("bcm_tyreRRTemp"),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=MEAS,
        suggested_display_precision=0,
    ),
    # ---- states (raw values, meanings not confirmed) ---------------------
    VoyahSensorDescription(
        key="vehicle_state",
        paths=("veh_state", "power.vehicle.veh_state"),
        value_fn=_text("veh_state", "power.vehicle.veh_state"),
        icon="mdi:car-info",
    ),
    VoyahSensorDescription(
        key="charge_state",
        paths=("chg_state",),
        value_fn=_text("chg_state"),
        icon="mdi:ev-station",
    ),
    VoyahSensorDescription(
        key="charge_type",
        paths=(*_DC, *_AC),
        value_fn=lambda t, d: charge_type(t.get(*_DC), t.get(*_AC)),
        attrs_fn=lambda t, d: {"dc_raw": t.get(*_DC), "ac_raw": t.get(*_AC)},
        device_class=SensorDeviceClass.ENUM,
        options=["none", "ac", "dc"],
        icon="mdi:ev-plug-type2",
    ),
    # ---- body -------------------------------------------------------------
    VoyahSensorDescription(key="window_fl", **_window("win_lf")),
    VoyahSensorDescription(key="window_fr", **_window("win_rf")),
    VoyahSensorDescription(key="window_rl", **_window("win_lr")),
    VoyahSensorDescription(key="window_rr", **_window("win_rr")),
    VoyahSensorDescription(
        key="sunroof",
        paths=_SUNROOF,
        value_fn=lambda t, d: sunroof_state(t.get(*_SUNROOF)),
        attrs_fn=_raw_attr(*_SUNROOF),
        device_class=SensorDeviceClass.ENUM,
        options=["closed", "vent", "open"],
        icon="mdi:car-select",
    ),
    VoyahSensorDescription(
        key="sentry",
        paths=_SENTRY,
        value_fn=lambda t, d: sentry_state(t.get(*_SENTRY)),
        attrs_fn=_raw_attr(*_SENTRY),
        device_class=SensorDeviceClass.ENUM,
        options=[
            "off",
            "shock_only",
            "on",
            "low_battery",
            "arming",
            "unavailable",
            "error",
        ],
        icon="mdi:shield-car",
    ),
    # ---- detailed diagnostics --------------------------------------------
    VoyahSensorDescription(
        key="insulation",
        paths=("power.vehicle.insul_kohm",),
        native_unit_of_measurement="kΩ",
        state_class=MEAS,
        icon="mdi:omega",
        entity_category=EntityCategory.DIAGNOSTIC,
        detail=True,
    ),
    VoyahSensorDescription(
        key="cell_voltage_max",
        paths=("power.extremes.cell_vmax_mv",),
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=MEAS,
        entity_category=EntityCategory.DIAGNOSTIC,
        detail=True,
    ),
    VoyahSensorDescription(
        key="cell_voltage_min",
        paths=("power.extremes.cell_vmin_mv",),
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=MEAS,
        entity_category=EntityCategory.DIAGNOSTIC,
        detail=True,
    ),
    VoyahSensorDescription(
        key="cell_voltage_delta",
        paths=("power.extremes.cell_vmax_mv", "power.extremes.cell_vmin_mv"),
        value_fn=lambda t, d: cell_voltage_delta(t),
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=MEAS,
        entity_category=EntityCategory.DIAGNOSTIC,
        detail=True,
    ),
    # ---- API / freshness status (always created) ------------------------
    VoyahSensorDescription(
        key="last_seen",
        paths=("last_seen",),
        value_fn=lambda t, d: d.last_seen,
        attrs_fn=lambda t, d: {
            "raw_value": d.last_seen_raw,
            "changed_since_previous_poll": d.last_seen_changed,
            "change_detected_at": (
                d.last_change_detected.isoformat() if d.last_change_detected else None
            ),
        },
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        always=True,
    ),
    VoyahSensorDescription(
        key="last_success",
        value_fn=lambda t, d: d.last_success,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        always=True,
    ),
    VoyahSensorDescription(
        key="telemetry_age",
        value_fn=lambda t, d: None if d.age_seconds is None else round(d.age_seconds),
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=MEAS,
        entity_category=EntityCategory.DIAGNOSTIC,
        always=True,
    ),
)


class VoyahSensor(VoyahEntity, SensorEntity):
    """Generic description-driven sensor."""

    entity_description: VoyahSensorDescription

    def __init__(self, coordinator, description: VoyahSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    def _tele(self) -> Telemetry:
        return Telemetry(self.vdata.telemetry)

    @property
    def native_value(self) -> Any:
        desc = self.entity_description
        tele = self._tele()
        if desc.value_fn is not None:
            return desc.value_fn(tele, self.vdata)
        return to_number(tele.get(*desc.paths))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        desc = self.entity_description
        if desc.attrs_fn is None:
            return None
        return desc.attrs_fn(self._tele(), self.vdata)


class VoyahIndexedSensor(VoyahEntity, SensorEntity):
    """One cell temperature / cell voltage from the arrays (optional)."""

    _attr_state_class = MEAS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator, kind: str, index: int
    ) -> None:
        super().__init__(coordinator, f"{kind}_{index + 1}")
        self._index = index
        self._attr_translation_key = kind
        self._attr_translation_placeholders = {"index": str(index + 1)}
        if kind == "cell_temp":
            self._path = "power.cell_temps"
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        else:
            self._path = "power.cell_voltages"
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            # unit of the array is not confirmed; *_mv names suggest millivolts
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT

    @property
    def native_value(self) -> Any:
        return array_value(Telemetry(self.vdata.telemetry), self._path, self._index)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VoyahConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data

    def candidates() -> Iterable[tuple[str, Callable[[], Entity]]]:
        tele = Telemetry(coordinator.data.telemetry)

        for desc in SENSORS:
            if desc.detail and not coordinator.detailed:
                continue
            if desc.always or tele.has(*desc.paths):
                yield (
                    desc.key,
                    lambda desc=desc: VoyahSensor(coordinator, desc),
                )

        if coordinator.cell_sensors:
            temps = tele.get("power.cell_temps")
            if isinstance(temps, list):
                for i in range(len(temps)):
                    yield (
                        f"cell_temp_{i + 1}",
                        lambda i=i: VoyahIndexedSensor(coordinator, "cell_temp", i),
                    )
            volts = tele.get("power.cell_voltages")
            if isinstance(volts, list):
                for i in range(len(volts)):
                    yield (
                        f"cell_voltage_{i + 1}",
                        lambda i=i: VoyahIndexedSensor(coordinator, "cell_voltage", i),
                    )

    add_dynamic(entry, coordinator, async_add_entities, candidates)

