"""Data coordinator: polling, sleep detection and last-known-state handling."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import (
    CommandResult,
    VoyahApi,
    VoyahApiError,
    VoyahAuthError,
    VoyahCommandTimeout,
    VoyahRateLimited,
    enabled_vehicles,
)
from .const import (
    CONF_CAN_MANAGE,
    CONF_CELL_SENSORS,
    CONF_DETAILED,
    CONF_ENABLE_COMMANDS,
    CONF_ENABLE_DANGEROUS,
    CONF_SCAN_INTERVAL_MIN,
    CONF_STALE_AFTER_MIN,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    DEFAULT_CELL_SENSORS,
    DANGEROUS_COMMANDS,
    DEFAULT_DETAILED,
    DEFAULT_ENABLE_COMMANDS,
    DEFAULT_ENABLE_DANGEROUS,
    DEFAULT_SCAN_INTERVAL_MIN,
    DEFAULT_STALE_AFTER_MIN,
    DEFAULT_VEHICLE_NAME,
    DOMAIN,
    MANUFACTURER,
    MAX_BACKOFF_SECONDS,
    MIN_POLL_SECONDS,
    MODEL,
    STORAGE_SAVE_DELAY,
    STORAGE_VERSION,
)
from .decoders import Telemetry, valid_position
from .freshness import compute_age_seconds, is_fresh, parse_last_seen

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class VehicleData:
    """Everything entities need. Telemetry is the last known good response."""

    telemetry: dict[str, Any] = field(default_factory=dict)
    # API / transport state (independent from the car state)
    api_ok: bool = True
    last_error: str | None = None
    consecutive_failures: int = 0
    # last successful HTTP answer (says nothing about car freshness)
    last_success: datetime | None = None
    # car-side freshness
    last_seen_raw: Any = None
    last_seen: datetime | None = None
    last_seen_changed: bool | None = None
    last_change_detected: datetime | None = None
    # last valid GPS position (never reset)
    last_position: tuple[float, float] | None = None
    # age / freshness computed at poll time
    age_seconds: float | None = None
    fresh: bool | None = None
    stale_threshold_seconds: float = DEFAULT_STALE_AFTER_MIN * 60


class VoyahCoordinator(DataUpdateCoordinator[VehicleData]):
    """Polls /vehicles/{vin}/telemetry."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, api: VoyahApi
    ) -> None:
        opts = entry.options
        self.options_snapshot = dict(opts)
        minutes = int(opts.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN))
        self.base_interval = max(MIN_POLL_SECONDS, minutes * 60)
        self.stale_after_seconds = (
            int(opts.get(CONF_STALE_AFTER_MIN, DEFAULT_STALE_AFTER_MIN)) * 60
        )
        self.detailed: bool = bool(opts.get(CONF_DETAILED, DEFAULT_DETAILED))
        self.cell_sensors: bool = bool(opts.get(CONF_CELL_SENSORS, DEFAULT_CELL_SENSORS))
        self._commands_opt: bool = bool(opts.get(CONF_ENABLE_COMMANDS, DEFAULT_ENABLE_COMMANDS))
        self._dangerous_opt: bool = bool(
            opts.get(CONF_ENABLE_DANGEROUS, DEFAULT_ENABLE_DANGEROUS)
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.data[CONF_VIN]}",
            update_interval=timedelta(seconds=self.base_interval),
        )
        self.api = api
        self.vin: str = entry.data[CONF_VIN]
        self.vehicle_name: str = entry.data.get(CONF_VEHICLE_NAME) or DEFAULT_VEHICLE_NAME
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._cache = VehicleData(stale_threshold_seconds=self.stale_after_seconds)
        self._last_request_monotonic: float | None = None
        self._command_lock = asyncio.Lock()
        self._unsub_followup: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------
    @property
    def can_manage(self) -> bool:
        """The profile says whether this account may control the vehicle."""
        return self.config_entry.data.get(CONF_CAN_MANAGE, True) is not False

    @property
    def commands_enabled(self) -> bool:
        return self._commands_opt and self.can_manage

    @property
    def dangerous_enabled(self) -> bool:
        return self.commands_enabled and self._dangerous_opt

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.vin)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.vehicle_name,
        )

    # ---- persistence (restore last known state after restart) ----------
    async def async_load_cache(self) -> None:
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return
        telemetry = stored.get("telemetry")
        if isinstance(telemetry, dict):
            self._cache.telemetry = telemetry
            self._cache.last_seen_raw = stored.get("last_seen_raw")
            self._cache.last_seen = parse_last_seen(self._cache.last_seen_raw)
            self._cache.last_success = dt_util.parse_datetime(
                stored.get("last_success") or ""
            )
            self._cache.last_change_detected = dt_util.parse_datetime(
                stored.get("last_change_detected") or ""
            )
        pos = stored.get("last_position")
        if (
            isinstance(pos, list)
            and len(pos) == 2
            and all(isinstance(v, (int, float)) for v in pos)
        ):
            self._cache.last_position = (float(pos[0]), float(pos[1]))

    def _schedule_save(self, data: VehicleData) -> None:
        def _payload() -> dict[str, Any]:
            return {
                "telemetry": data.telemetry,
                "last_seen_raw": data.last_seen_raw,
                "last_success": data.last_success.isoformat() if data.last_success else None,
                "last_change_detected": (
                    data.last_change_detected.isoformat()
                    if data.last_change_detected
                    else None
                ),
                "last_position": list(data.last_position) if data.last_position else None,
            }

        self._store.async_delay_save(_payload, STORAGE_SAVE_DELAY)

    # ---- profile refresh (vehicle list may change) -----------------------
    async def async_refresh_profile(self) -> None:
        """Best-effort refresh of the vehicle name; never raises."""
        try:
            profile = await self.api.get_profile()
        except VoyahApiError as err:
            _LOGGER.debug("Profile refresh skipped: %s", err.reason)
            return
        vehicles = enabled_vehicles(profile)
        mine = next((v for v in vehicles if v.get("vin") == self.vin), None)
        if mine is None:
            _LOGGER.warning(
                "Vehicle %s is no longer present/enabled in the Voyahtweaks profile",
                self.vin,
            )
            return
        name = mine.get("name")
        new_data = dict(self.config_entry.data)
        if isinstance(name, str) and name and name != self.vehicle_name:
            self.vehicle_name = name
            new_data[CONF_VEHICLE_NAME] = name
        can_manage = mine.get("can_manage")
        if isinstance(can_manage, bool):
            new_data[CONF_CAN_MANAGE] = can_manage
        if new_data != dict(self.config_entry.data):
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

    # ---- commands --------------------------------------------------------
    async def async_send_command(
        self, cmd: str, payload: dict[str, Any] | None = None
    ) -> CommandResult:
        """Run a vehicle command and wait for its final status.

        Raises HomeAssistantError unless the command completed. Commands are
        serialised: only one is in flight at a time.
        """
        if not self.commands_enabled:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="commands_disabled"
            )
        if cmd in DANGEROUS_COMMANDS and not self.dangerous_enabled:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="dangerous_disabled"
            )

        async with self._command_lock:
            _LOGGER.info("Sending vehicle command %s", cmd)  # payload not logged
            try:
                result = await self.api.run_command(self.vin, cmd, payload)
            except VoyahAuthError as err:
                self.config_entry.async_start_reauth(self.hass)
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="command_auth"
                ) from err
            except VoyahCommandTimeout as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_timeout",
                    translation_placeholders={"status": err.last_status},
                ) from err
            except VoyahApiError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_error",
                    translation_placeholders={
                        "reason": err.detail or err.reason,
                        "status": str(err.status or "-"),
                    },
                ) from err

        # The car state changes later; ask for fresh telemetry as soon as the
        # one-poll-per-minute limit allows (never sooner).
        self._schedule_followup_refresh()

        if result.status != "completed":
            key = {
                "failed": "command_failed",
                "no_response": "command_no_response",
                "expired": "command_expired",
            }.get(result.status, "command_failed")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders={"reason": result.reason or "-"},
            )
        return result

    def _schedule_followup_refresh(self) -> None:
        if self._unsub_followup is not None:
            self._unsub_followup()
        elapsed = (
            time.monotonic() - self._last_request_monotonic
            if self._last_request_monotonic is not None
            else MIN_POLL_SECONDS
        )
        delay = max(15.0, MIN_POLL_SECONDS - elapsed + 1.0)

        async def _run(_now: datetime) -> None:
            self._unsub_followup = None
            await self.async_request_refresh()

        self._unsub_followup = async_call_later(self.hass, delay, _run)

    async def async_shutdown(self) -> None:
        if self._unsub_followup is not None:
            self._unsub_followup()
            self._unsub_followup = None
        await super().async_shutdown()

    # ---- main update -----------------------------------------------------
    async def _async_update_data(self) -> VehicleData:
        previous = self.data or self._cache

        # Hard guard: never hit the API more than once per MIN_POLL_SECONDS,
        # even for manual refresh requests.
        now_mono = time.monotonic()
        if (
            self._last_request_monotonic is not None
            and now_mono - self._last_request_monotonic < MIN_POLL_SECONDS
            and self.data is not None
        ):
            return self.data
        self._last_request_monotonic = now_mono

        try:
            raw = await self.api.get_telemetry(self.vin)
        except VoyahAuthError as err:
            raise ConfigEntryAuthFailed(err.reason) from err
        except VoyahRateLimited as err:
            return self._failure(previous, "rate_limited", retry_after=err.retry_after)
        except VoyahApiError as err:
            reason = err.reason if err.status is None else f"{err.reason} ({err.status})"
            return self._failure(previous, reason)

        return self._success(previous, raw)

    def _success(self, previous: VehicleData, raw: dict[str, Any]) -> VehicleData:
        now = dt_util.utcnow()
        tele = Telemetry(raw)

        last_seen_raw = raw.get("last_seen")
        last_seen = parse_last_seen(last_seen_raw)

        if last_seen is None:
            changed: bool | None = None  # freshness unknown
        elif previous.last_seen is None:
            changed = None  # nothing to compare with yet
        else:
            changed = last_seen != previous.last_seen

        last_change = previous.last_change_detected
        if changed:
            last_change = now
        elif last_change is None and last_seen is not None:
            last_change = now

        age = compute_age_seconds(last_seen, now)
        position = valid_position(tele) or previous.last_position

        data = VehicleData(
            telemetry=raw,  # full raw JSON is kept
            api_ok=True,
            last_error=None,
            consecutive_failures=0,
            last_success=now,
            last_seen_raw=last_seen_raw,
            last_seen=last_seen,
            last_seen_changed=changed,
            last_change_detected=last_change,
            last_position=position,
            age_seconds=age,
            fresh=is_fresh(age, self.stale_after_seconds),
            stale_threshold_seconds=self.stale_after_seconds,
        )

        # back to the normal polling interval
        self.update_interval = timedelta(seconds=self.base_interval)
        self._schedule_save(data)
        return data

    def _failure(
        self,
        previous: VehicleData,
        reason: str,
        retry_after: float | None = None,
    ) -> VehicleData:
        """API error: keep every last known value, record the error, back off."""
        failures = previous.consecutive_failures + 1
        delay = min(self.base_interval * (2 ** min(failures, 6)), MAX_BACKOFF_SECONDS)
        delay = max(delay, MIN_POLL_SECONDS)
        if retry_after:
            delay = min(max(delay, retry_after), MAX_BACKOFF_SECONDS)
        self.update_interval = timedelta(seconds=delay)
        _LOGGER.warning(
            "Voyahtweaks telemetry update failed (%s); last known data kept, "
            "next attempt in %d s",
            reason,
            delay,
        )

        now = dt_util.utcnow()
        age = compute_age_seconds(previous.last_seen, now)
        return VehicleData(
            telemetry=previous.telemetry,
            api_ok=False,
            last_error=reason,
            consecutive_failures=failures,
            last_success=previous.last_success,
            last_seen_raw=previous.last_seen_raw,
            last_seen=previous.last_seen,
            last_seen_changed=previous.last_seen_changed,
            last_change_detected=previous.last_change_detected,
            last_position=previous.last_position,
            age_seconds=age,
            fresh=is_fresh(age, self.stale_after_seconds),
            stale_threshold_seconds=self.stale_after_seconds,
        )
