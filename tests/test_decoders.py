from datetime import UTC, datetime, timedelta

import pytest

from conftest import load

dec = load("decoders")
fr = load("freshness")


@pytest.mark.parametrize(
    "value,expected",
    [(0, False), (1, True), (2, True), ("0", False), (None, None), ("x", None), (True, None)],
)
def test_door(value, expected):
    assert dec.door_open(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [(2, "closed"), (0, "ajar"), (1, "open"), (3, "open"), (None, None), ("abc", None)],
)
def test_window(value, expected):
    assert dec.window_state(value) == expected


@pytest.mark.parametrize(
    "value,expected", [(1, False), (0, True), (2, True), (None, None)]
)
def test_tailgate(value, expected):
    assert dec.tailgate_open(value) is expected


@pytest.mark.parametrize("value,expected", [(0, False), (1, True), (None, None)])
def test_lock_unlocked(value, expected):
    assert dec.lock_unlocked(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [(3, "closed"), (0, "vent"), (5, "vent"), (6, "open"), (1, "open"), (None, None)],
)
def test_sunroof(value, expected):
    assert dec.sunroof_state(value) == expected


def test_sentry():
    assert dec.sentry_state(1) == "off"
    assert dec.sentry_state(3) == "on"
    assert dec.sentry_state(7) == "error"
    assert dec.sentry_state(9) is None  # unknown -> not guessed
    assert dec.sentry_state(None) is None
    assert dec.sentry_active(3) is True
    assert dec.sentry_active(2) is False
    assert dec.sentry_active(None) is None


def test_charging_not_derived_from_cable():
    assert dec.is_charging("charging") is True
    assert dec.is_charging("park_charge") is True
    assert dec.is_charging("CHARGING") is True
    assert dec.is_charging("idle") is False
    assert dec.is_charging(None) is None
    # cable plugged but state says not charging -> not charging
    assert dec.is_charging("idle") is False
    assert dec.charger_connected(0, 1) is True


def test_charge_type():
    assert dec.charge_type(1, 0) == "dc"
    assert dec.charge_type(0, 1) == "ac"
    assert dec.charge_type(0, 0) == "none"
    assert dec.charge_type(None, None) is None
    assert dec.charge_type(None, 0) == "none"


def test_remaining_minutes():
    assert dec.charge_remaining_minutes(1.5) == 90
    assert dec.charge_remaining_minutes(0) == 0
    assert dec.charge_remaining_minutes(None) is None


def test_climate():
    t = dec.Telemetry({"sensors": {"AC_RemHeat_Sts": 2}})
    assert dec.climate_remote_active(t) is True
    t = dec.Telemetry({"sensors": {"ac_systemOnOffSts": 1, "bcm_remoteMode": 2}})
    assert dec.climate_remote_active(t) is True
    t = dec.Telemetry({"sensors": {"ac_systemOnOffSts": 1, "bcm_remoteMode": 0}})
    assert dec.climate_remote_active(t) is False
    assert dec.climate_remote_active(dec.Telemetry({})) is None


def test_position_requires_valid_flag():
    base = {"power": {"location": {"lat": 55.7, "lon": 37.6, "gps_valid": True}}}
    assert dec.valid_position(dec.Telemetry(base)) == (55.7, 37.6)
    base["power"]["location"]["gps_valid"] = False
    assert dec.valid_position(dec.Telemetry(base)) is None
    base["power"]["location"].update(gps_valid=True, lat=0, lon=0)
    assert dec.valid_position(dec.Telemetry(base)) is None
    base["power"]["location"].update(lat=95, lon=10)
    assert dec.valid_position(dec.Telemetry(base)) is None
    # root gps must not substitute power.location
    only_root = {"gps": {"lat": 55.7, "lon": 37.6}}
    assert dec.valid_position(dec.Telemetry(only_root)) is None


def test_telemetry_dedupe_prefers_root():
    t = dec.Telemetry(
        {"soc_pct": 44, "power": {"vehicle": {"soc_pct": 40}}, "sensors": {"bms_SOC": 43}}
    )
    paths = ("soc_pct", "power.vehicle.soc_pct", *dec.S("bms_SOC"))
    assert t.num(*paths) == 44
    t2 = dec.Telemetry({"soc_pct": None, "power": {"vehicle": {"soc_pct": 40}}})
    assert t2.num(*paths) == 40


def test_numbers():
    assert dec.to_number("14.3") == 14.3
    assert dec.to_number(44.0) == 44 and isinstance(dec.to_number(44.0), int)
    assert dec.to_number(float("nan")) is None
    assert dec.to_number(True) is None
    assert dec.to_number([1]) is None


def test_helpers():
    t = dec.Telemetry(
        {
            "sensors": {"tire_pressure_fl": 2.4, "tpms_temp_fr": 20, "bms_SOC": 5},
            "power": {
                "extremes": {"cell_vmax_mv": 3350, "cell_vmin_mv": 3330},
                "cell_temps": [10, 11],
            },
        }
    )
    assert dec.tire_keys(t) == ["tire_pressure_fl", "tpms_temp_fr"]
    assert dec.cell_voltage_delta(t) == 20
    assert dec.array_value(t, "power.cell_temps", 1) == 11
    assert dec.array_value(t, "power.cell_temps", 5) is None
    assert t.has("sensors.bms_SOC") and not t.has("sensors.nope")


NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)


def test_parse_last_seen():
    iso = fr.parse_last_seen("2026-11-11T11:50:00+00:00")
    assert iso == NOW - timedelta(minutes=10)
    assert fr.parse_last_seen("2026-11-11T11:50:00Z") == iso
    assert fr.parse_last_seen("2026-11-11T11:50:00") == iso  # naive -> UTC
    sec = int(iso.timestamp())
    assert fr.parse_last_seen(sec) == iso
    assert fr.parse_last_seen(sec * 1000) == iso
    assert fr.parse_last_seen(str(sec)) == iso
    for bad in (None, "", "garbage", True, 0, -5, [], {}):
        assert fr.parse_last_seen(bad) is None


def test_age_and_fresh():
    seen = NOW - timedelta(minutes=18)
    age = fr.compute_age_seconds(seen, NOW)
    assert age == 18 * 60
    assert fr.is_fresh(age, 600) is False
    assert fr.is_fresh(age, 1200) is True
    assert fr.is_fresh(None, 600) is None
    assert fr.compute_age_seconds(NOW + timedelta(minutes=3), NOW) == 0.0
    assert fr.compute_age_seconds(None, NOW) is None


def test_tyre_paths_resolve():
    t = dec.Telemetry({"sensors": {"bcm_tyreRRPressure": 2.4, "bcm_tyreRRTemp": 17, "bcm_tyreLFTemp": None}})
    assert t.sensor_num("bcm_tyreRRPressure") == 2.4
    assert t.sensor_num("bcm_tyreRRTemp") == 17
    assert t.sensor_num("bcm_tyreLFTemp") is None
    assert t.has(*dec.S("bcm_tyreLFTemp"))  # present with null -> entity exists
