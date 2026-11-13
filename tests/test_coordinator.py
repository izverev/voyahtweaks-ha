"""Coordinator logic tests against minimal Home Assistant stubs.

These do NOT replace testing inside a real Home Assistant; they only verify the
sleep / error / rate-limit logic of coordinator.py.
"""

import asyncio
from datetime import UTC, datetime, timedelta
import importlib.util
import sys
import types

import pytest

from conftest import COMP

# ---------------- stubs for the aiohttp + homeassistant imports -------------
NOW = {"t": datetime(2026, 11, 11, 12, 0, tzinfo=UTC)}
MONO = {"t": 1000.0}


def _mod(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


class ConfigEntryAuthFailed(Exception):
    pass


class HomeAssistantError(Exception):
    def __init__(self, *a, translation_domain=None, translation_key=None,
                 translation_placeholders=None):
        super().__init__(translation_key)
        self.translation_key = translation_key
        self.placeholders = translation_placeholders or {}


CALLS = []  # async_call_later registrations


class DataUpdateCoordinator:
    def __init__(self, hass, logger, *, config_entry, name, update_interval):
        self.hass = hass
        self.config_entry = config_entry
        self.name = name
        self.update_interval = update_interval
        self.data = None
        self.refresh_requests = 0

    async def async_request_refresh(self):
        self.refresh_requests += 1

    async def async_shutdown(self):
        pass

    def __class_getitem__(cls, item):
        return cls


class Store:
    def __init__(self, hass, version, key):
        self.saved = None
        self.loaded = None

    def __class_getitem__(cls, item):
        return cls

    async def async_load(self):
        return self.loaded

    def async_delay_save(self, fn, delay):
        self.saved = fn()


class _Entries:
    def __init__(self):
        self.updated = []

    def async_update_entry(self, entry, data=None):
        self.updated.append(data)


class dt_util:  # noqa: N801
    @staticmethod
    def utcnow():
        return NOW["t"]

    @staticmethod
    def parse_datetime(s):
        try:
            return datetime.fromisoformat(s)
        except (ValueError, TypeError):
            return None


# aiohttp stub (api.py imports it)
if "aiohttp" not in sys.modules:
    _mod("aiohttp", ClientError=Exception, ClientTimeout=lambda total=None: None, ClientSession=object)

_mod("homeassistant")
_mod("homeassistant.core", HomeAssistant=object, callback=lambda f: f, CALLBACK_TYPE=object)
_mod("homeassistant.exceptions", ConfigEntryAuthFailed=ConfigEntryAuthFailed, HomeAssistantError=HomeAssistantError)
_mod("homeassistant.helpers")
_mod("homeassistant.helpers.device_registry", DeviceInfo=dict)
_mod("homeassistant.helpers.storage", Store=Store)


def _async_call_later(hass, delay, action):
    cancelled = {"v": False}
    CALLS.append((delay, action, cancelled))
    return lambda: cancelled.update(v=True)


_mod("homeassistant.helpers.event", async_call_later=_async_call_later)
_mod("homeassistant.helpers.update_coordinator", DataUpdateCoordinator=DataUpdateCoordinator)
_mod("homeassistant.util")
_mod("homeassistant.util.dt", utcnow=dt_util.utcnow, parse_datetime=dt_util.parse_datetime)
sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]



def _load():
    pkg = types.ModuleType("vcpkg2")
    pkg.__path__ = [str(COMP)]
    sys.modules["vcpkg2"] = pkg
    for name in ("const", "api", "freshness", "decoders", "coordinator"):
        spec = importlib.util.spec_from_file_location(f"vcpkg2.{name}", COMP / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"vcpkg2.{name}"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["vcpkg2.coordinator"], sys.modules["vcpkg2.api"]


coord_mod, api_mod = _load()
# Fake clock ONLY inside the coordinator module (patching time.monotonic
# globally would freeze the asyncio event loop clock).
coord_mod.time = types.SimpleNamespace(monotonic=lambda: MONO["t"])


class FakeApi:
    def __init__(self):
        self.queue = []
        self.calls = 0

    async def get_telemetry(self, vin):
        self.calls += 1
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def get_profile(self):
        return {"vehicles": [{"vin": "VIN", "name": "Renamed", "can_manage": self.can_manage}]}

    can_manage = True
    sent = []
    command_result = None  # CommandResult or Exception

    async def run_command(self, vin, cmd, payload=None):
        self.sent.append((vin, cmd, payload))
        if isinstance(self.command_result, Exception):
            raise self.command_result
        return self.command_result or api_mod.CommandResult("id1", "completed")


class Entry:
    entry_id = "e1"

    def __init__(self, options=None, data=None):
        self.data = {"vin": "VIN", "vehicle_name": "Voyah · 1", **(data or {})}
        self.options = options or {}
        self.reauth_started = False

    def async_start_reauth(self, hass):
        self.reauth_started = True


def make(options=None, data=None):
    hass = types.SimpleNamespace(config_entries=_Entries())
    api = FakeApi()
    api.sent = []
    c = coord_mod.VoyahCoordinator(hass, Entry(options, data), api)
    return c, api, hass


def run(coro):
    return asyncio.run(coro)


def tele(last_seen, soc=44, gps_valid=True, lat=55.75, lon=37.61):
    return {
        "online": True,
        "last_seen": last_seen,
        "soc_pct": soc,
        "power": {"location": {"lat": lat, "lon": lon, "gps_valid": gps_valid}},
    }


def iso(minutes_ago):
    return (NOW["t"] - timedelta(minutes=minutes_ago)).isoformat()


@pytest.fixture(autouse=True)
def reset_clock():
    NOW["t"] = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    MONO["t"] = 1000.0
    CALLS.clear()


def test_interval_defaults_and_minimum():
    c, _, _ = make()
    assert c.update_interval == timedelta(minutes=5)
    c, _, _ = make({"scan_interval_min": 1})
    assert c.update_interval == timedelta(seconds=60)
    c, _, _ = make({"scan_interval_min": 0})  # nonsense value cannot go below 60 s
    assert c.update_interval == timedelta(seconds=60)


def test_fresh_then_sleep_keeps_values():
    c, api, _ = make()
    api.queue.append(tele(iso(1)))
    d1 = run(c._async_update_data())
    c.data = d1
    assert d1.fresh is True and d1.api_ok and d1.last_seen_changed is None

    # next poll: API answers, but last_seen did not move (car asleep)
    NOW["t"] += timedelta(minutes=15)
    MONO["t"] += 900
    api.queue.append(tele(iso(16)))  # same last_seen as before
    d2 = run(c._async_update_data())
    assert d2.last_seen_changed is False
    assert d2.api_ok is True  # API fine, not an API error
    assert d2.fresh is False  # data is stale
    assert d2.age_seconds == pytest.approx(16 * 60)
    assert d2.telemetry["soc_pct"] == 44  # values untouched


def test_new_last_seen_detected():
    c, api, _ = make()
    api.queue.append(tele(iso(20)))
    c.data = run(c._async_update_data())
    MONO["t"] += 300
    api.queue.append(tele(iso(2)))
    d = run(c._async_update_data())
    assert d.last_seen_changed is True and d.fresh is True
    assert d.last_change_detected == NOW["t"]


def test_missing_or_bad_last_seen_is_unknown():
    c, api, _ = make()
    for bad in (None, "garbage"):
        api.queue.append(tele(bad))
        d = run(c._async_update_data())
        assert d.fresh is None and d.age_seconds is None
        assert d.last_seen_changed is None
        MONO["t"] += 100
        c.data = d
        c._last_request_monotonic = None


def test_api_error_keeps_last_state_and_backs_off():
    c, api, _ = make({"scan_interval_min": 5})
    api.queue.append(tele(iso(1)))
    c.data = run(c._async_update_data())

    MONO["t"] += 300
    api.queue.append(api_mod.VoyahApiError("server_error", 503))
    d = run(c._async_update_data())
    assert d.api_ok is False and "server_error" in d.last_error
    assert d.telemetry["soc_pct"] == 44  # last known state kept
    assert d.last_position == (55.75, 37.61)
    assert d.last_success == c.data.last_success  # not overwritten
    assert d.consecutive_failures == 1
    first_backoff = c.update_interval
    assert first_backoff > timedelta(minutes=5)

    c.data = d
    MONO["t"] += 700
    api.queue.append(api_mod.VoyahConnectionError("timeout"))
    d2 = run(c._async_update_data())
    assert d2.consecutive_failures == 2
    assert c.update_interval >= first_backoff
    assert c.update_interval <= timedelta(seconds=1800)  # bounded

    # recovery resets everything
    c.data = d2
    MONO["t"] += 2000
    api.queue.append(tele(iso(1)))
    d3 = run(c._async_update_data())
    assert d3.api_ok and d3.last_error is None and d3.consecutive_failures == 0
    assert c.update_interval == timedelta(minutes=5)


def test_rate_limit_uses_retry_after():
    c, api, _ = make({"scan_interval_min": 1})
    api.queue.append(tele(iso(1)))
    c.data = run(c._async_update_data())
    MONO["t"] += 100
    api.queue.append(api_mod.VoyahRateLimited(900))
    run(c._async_update_data())
    assert c.update_interval >= timedelta(seconds=900)


def test_never_more_than_once_per_minute():
    c, api, _ = make({"scan_interval_min": 1})
    api.queue.extend([tele(iso(1)), tele(iso(0))])
    c.data = run(c._async_update_data())
    assert api.calls == 1
    MONO["t"] += 30  # manual refresh 30 s later
    again = run(c._async_update_data())
    assert api.calls == 1 and again is c.data  # no HTTP request
    MONO["t"] += 31
    run(c._async_update_data())
    assert api.calls == 2


def test_auth_failure_raises_reauth():
    c, api, _ = make()
    api.queue.append(api_mod.VoyahAuthError("unauthorized", 401))
    with pytest.raises(ConfigEntryAuthFailed):
        run(c._async_update_data())


def test_gps_invalid_never_overwrites_position():
    c, api, _ = make()
    api.queue.append(tele(iso(1)))
    c.data = run(c._async_update_data())
    assert c.data.last_position == (55.75, 37.61)
    MONO["t"] += 100
    api.queue.append(tele(iso(0), gps_valid=False, lat=0, lon=0))
    d = run(c._async_update_data())
    assert d.last_position == (55.75, 37.61)


def test_cache_restore_and_save():
    c, api, _ = make()
    api.queue.append(tele(iso(3)))
    c.data = run(c._async_update_data())
    saved = c._store.saved
    assert saved["telemetry"]["soc_pct"] == 44
    assert saved["last_position"] == [55.75, 37.61]

    c2, _api2, _ = make()
    c2._store.loaded = saved
    run(c2.async_load_cache())
    assert c2._cache.telemetry["soc_pct"] == 44
    assert c2._cache.last_position == (55.75, 37.61)
    assert c2._cache.last_seen is not None
    # after restart a failing API still serves the cached values
    api2 = c2.api
    api2.queue.append(api_mod.VoyahApiError("server_error", 500))
    d = run(c2._async_update_data())
    assert d.telemetry["soc_pct"] == 44 and d.api_ok is False


def test_profile_refresh_updates_name_without_secrets_loss():
    c, _api, hass = make()
    run(c.async_refresh_profile())
    assert c.vehicle_name == "Renamed"
    assert hass.config_entries.updated[-1]["vin"] == "VIN"
    assert hass.config_entries.updated[-1]["vehicle_name"] == "Renamed"


# ----------------------------- commands ------------------------------------
ON = {"enable_commands": True}
ON_DANGER = {"enable_commands": True, "enable_dangerous_commands": True}


def test_commands_off_by_default():
    c, api, _ = make()
    assert c.commands_enabled is False and c.dangerous_enabled is False
    with pytest.raises(HomeAssistantError) as ei:
        run(c.async_send_command("door_unlock"))
    assert ei.value.translation_key == "commands_disabled"
    assert api.sent == []  # nothing reached the API


def test_dangerous_command_needs_its_own_switch():
    c, api, _ = make(ON)
    assert c.commands_enabled and not c.dangerous_enabled
    run(c.async_send_command("door_lock"))
    with pytest.raises(HomeAssistantError) as ei:
        run(c.async_send_command("keyless_start"))
    assert ei.value.translation_key == "dangerous_disabled"
    assert [x[1] for x in api.sent] == ["door_lock"]

    c, api, _ = make(ON_DANGER)
    run(c.async_send_command("keyless_start"))
    assert [x[1] for x in api.sent] == ["keyless_start"]


def test_dangerous_flag_alone_does_nothing():
    c, _api, _ = make({"enable_dangerous_commands": True})
    assert not c.commands_enabled and not c.dangerous_enabled


def test_can_manage_false_blocks_everything():
    c, api, _ = make(ON_DANGER, data={"can_manage": False})
    assert not c.commands_enabled and not c.dangerous_enabled
    with pytest.raises(HomeAssistantError):
        run(c.async_send_command("door_lock"))
    assert api.sent == []


def test_profile_updates_can_manage():
    c, api, hass = make(ON)
    api.can_manage = False
    run(c.async_refresh_profile())
    assert hass.config_entries.updated[-1]["can_manage"] is False


def test_payload_is_forwarded():
    c, api, _ = make(ON)
    run(c.async_send_command("climate", {"mode": "temp", "temp": 22.5}))
    assert api.sent[-1] == ("VIN", "climate", {"mode": "temp", "temp": 22.5})


@pytest.mark.parametrize(
    "status,key",
    [("failed", "command_failed"), ("no_response", "command_no_response"), ("expired", "command_expired")],
)
def test_non_completed_status_raises(status, key):
    c, api, _ = make(ON)
    api.command_result = api_mod.CommandResult("i", status, reason="why")
    with pytest.raises(HomeAssistantError) as ei:
        run(c.async_send_command("door_lock"))
    assert ei.value.translation_key == key


def test_api_errors_become_ha_errors():
    c, api, _ = make(ON)
    api.command_result = api_mod.VoyahApiError("forbidden", 403, "vehicle blocked")
    with pytest.raises(HomeAssistantError) as ei:
        run(c.async_send_command("door_lock"))
    assert ei.value.translation_key == "command_error"
    assert ei.value.placeholders["reason"] == "vehicle blocked"

    api.command_result = api_mod.VoyahCommandTimeout("sent")
    with pytest.raises(HomeAssistantError) as ei:
        run(c.async_send_command("door_lock"))
    assert ei.value.translation_key == "command_timeout"

    api.command_result = api_mod.VoyahAuthError("unauthorized", 401)
    with pytest.raises(HomeAssistantError):
        run(c.async_send_command("door_lock"))
    assert c.config_entry.reauth_started


def test_followup_refresh_respects_one_minute_limit():
    c, api, _ = make(ON)
    api.queue.append(tele(iso(1)))
    c.data = run(c._async_update_data())  # request at MONO=1000
    MONO["t"] += 10  # command finishes 10 s after the last poll
    run(c.async_send_command("door_lock"))
    assert len(CALLS) == 1
    delay, action, _ = CALLS[0]
    assert delay >= 51  # waits until 60 s after the last request
    # a second command before the first follow-up fired replaces (cancels) it
    run(c.async_send_command("door_unlock"))
    assert CALLS[0][2]["v"] is True and len(CALLS) == 2
    run(CALLS[1][1](None))
    assert c.refresh_requests == 1


def test_failed_command_still_schedules_refresh():
    c, api, _ = make(ON)
    api.command_result = api_mod.CommandResult("i", "failed", reason="x")
    with pytest.raises(HomeAssistantError):
        run(c.async_send_command("door_lock"))
    assert len(CALLS) == 1
