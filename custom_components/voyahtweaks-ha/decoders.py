"""Telemetry decoding helpers (no Home Assistant dependencies).

All rules come from the project specification (section 5). Unknown or missing
values are never interpreted as "closed" / "off": decoders return ``None``.
"""

from __future__ import annotations

import math
import re
from typing import Any

_MISSING = object()


# --------------------------------------------------------------------------
# Generic accessors
# --------------------------------------------------------------------------
def _walk(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return _MISSING
    return cur


def S(name: str) -> tuple[str, str]:
    """Candidate paths for a field of the ``sensors`` object.

    The exact location of these fields is not yet confirmed against a real
    response, so ``sensors.<name>`` is tried first and the root ``<name>``
    second.
    """
    return (f"sensors.{name}", name)


class Telemetry:
    """Read-only helper around the raw telemetry JSON."""

    def __init__(self, data: dict[str, Any] | None) -> None:
        self.data: dict[str, Any] = data if isinstance(data, dict) else {}

    def has(self, *paths: str) -> bool:
        """True if at least one of the paths exists (even with a null value)."""
        return any(_walk(self.data, p) is not _MISSING for p in paths)

    def get(self, *paths: str) -> Any:
        """First non-null value among the paths, or None."""
        for path in paths:
            value = _walk(self.data, path)
            if value is not _MISSING and value is not None:
                return value
        return None

    def num(self, *paths: str) -> int | float | None:
        return to_number(self.get(*paths))

    def sensor(self, name: str) -> Any:
        return self.get(*S(name))

    def sensor_num(self, name: str) -> int | float | None:
        return to_number(self.sensor(name))

    def sensor_keys(self) -> list[str]:
        sensors = self.data.get("sensors")
        return list(sensors) if isinstance(sensors, dict) else []


def to_number(value: Any) -> int | float | None:
    """Convert to a finite number; bool / non-numeric / NaN give None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number: float = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


# --------------------------------------------------------------------------
# Body
# --------------------------------------------------------------------------
def door_open(value: Any) -> bool | None:
    """0 -> closed, any other value -> open."""
    n = to_number(value)
    return None if n is None else n != 0


def window_state(value: Any) -> str | None:
    """2 -> closed, 0 -> ajar, other -> open, unknown -> None."""
    n = to_number(value)
    if n is None:
        return None
    if n == 2:
        return "closed"
    if n == 0:
        return "ajar"
    return "open"


def tailgate_open(value: Any) -> bool | None:
    """1 -> closed, other -> open; null / missing -> unknown."""
    n = to_number(value)
    return None if n is None else n != 1


def lock_unlocked(value: Any) -> bool | None:
    """lock_fl: 0 -> locked, non-zero -> unlocked (True = unlocked)."""
    n = to_number(value)
    return None if n is None else n != 0


def sunroof_state(value: Any) -> str | None:
    """3 -> closed, 0 / 5 -> vent, 6 or any other non-zero -> open."""
    n = to_number(value)
    if n is None:
        return None
    if n == 3:
        return "closed"
    if n in (0, 5):
        return "vent"
    return "open"


SENTRY_STATES = {
    1: "off",
    2: "shock_only",
    3: "on",
    4: "low_battery",
    5: "arming",
    6: "unavailable",
    7: "error",
}


def sentry_state(value: Any) -> str | None:
    n = to_number(value)
    return SENTRY_STATES.get(n) if n is not None else None


def sentry_active(value: Any) -> bool | None:
    n = to_number(value)
    return None if n is None else n == 3


# --------------------------------------------------------------------------
# Charging
# --------------------------------------------------------------------------
_CHARGING_STATES = {"park_charge", "charging"}


def is_charging(chg_state: Any) -> bool | None:
    """Charging is decided by ``chg_state`` only, never by the cable alone."""
    if chg_state is None or isinstance(chg_state, bool):
        return None
    return str(chg_state).strip().lower() in _CHARGING_STATES


def charge_type(dc: Any, ac: Any) -> str | None:
    """Connected charger type: dc / ac / none / None (unknown)."""
    dc_n, ac_n = to_number(dc), to_number(ac)
    if dc_n == 1:
        return "dc"
    if ac_n == 1:
        return "ac"
    if dc_n is None and ac_n is None:
        return None
    return "none"


def charger_connected(dc: Any, ac: Any) -> bool | None:
    kind = charge_type(dc, ac)
    return None if kind is None else kind != "none"


def charge_remaining_minutes(value: Any) -> int | float | None:
    """bms_remainChargeTime is hours in the app; converted to minutes."""
    n = to_number(value)
    return None if n is None else round(n * 60)


# --------------------------------------------------------------------------
# Climate
# --------------------------------------------------------------------------
def climate_remote_active(t: Telemetry) -> bool | None:
    resp = t.sensor_num("AC_RemResp_Sts")
    cool = t.sensor_num("AC_RemCool_Sts")
    heat = t.sensor_num("AC_RemHeat_Sts")
    sys_on = t.sensor_num("ac_systemOnOffSts")
    mode = t.sensor_num("bcm_remoteMode")
    if all(v is None for v in (resp, cool, heat, sys_on, mode)):
        return None
    if 2 in (resp, cool, heat):
        return True
    return sys_on == 1 and mode == 2


def climate_flag(value: Any, active_value: int) -> bool | None:
    n = to_number(value)
    return None if n is None else n == active_value


# --------------------------------------------------------------------------
# GPS
# --------------------------------------------------------------------------
def valid_position(t: Telemetry) -> tuple[float, float] | None:
    """Coordinates from ``power.location`` only when ``gps_valid`` is true."""
    if t.get("power.location.gps_valid") is not True:
        return None
    lat = t.num("power.location.lat")
    lon = t.num("power.location.lon")
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    if lat == 0 and lon == 0:
        return None
    return float(lat), float(lon)


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------
_TIRE_RE = re.compile(r"(tire|tyre|tpms)", re.IGNORECASE)


def tire_keys(t: Telemetry) -> list[str]:
    """Discover tire related keys in ``sensors`` (names are unconfirmed)."""
    return sorted(k for k in t.sensor_keys() if _TIRE_RE.search(k))


def array_value(t: Telemetry, path: str, index: int) -> int | float | None:
    arr = t.get(path)
    if isinstance(arr, list) and 0 <= index < len(arr):
        return to_number(arr[index])
    return None


def cell_voltage_delta(t: Telemetry) -> int | float | None:
    vmax = t.num("power.extremes.cell_vmax_mv")
    vmin = t.num("power.extremes.cell_vmin_mv")
    if vmax is None or vmin is None:
        return None
    return round(vmax - vmin, 3)
