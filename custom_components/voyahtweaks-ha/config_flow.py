"""Config flow and options flow."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    Challenge,
    Tokens,
    VoyahApi,
    VoyahApiError,
    VoyahAuthError,
    VoyahConnectionError,
    VoyahInvalidCode,
    VoyahVerificationRequired,
    enabled_vehicles,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CAN_MANAGE,
    CONF_CELL_SENSORS,
    CONF_DETAILED,
    CONF_DEVICE_TOKEN,
    CONF_ENABLE_COMMANDS,
    CONF_ENABLE_DANGEROUS,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL_MIN,
    CONF_STALE_AFTER_MIN,
    CONF_USERNAME,
    CONF_VEHICLE_NAME,
    CONF_VIN,
    DEFAULT_CELL_SENSORS,
    DEFAULT_DETAILED,
    DEFAULT_ENABLE_COMMANDS,
    DEFAULT_ENABLE_DANGEROUS,
    DEFAULT_SCAN_INTERVAL_MIN,
    DEFAULT_STALE_AFTER_MIN,
    DEFAULT_VEHICLE_NAME,
    DOMAIN,
    INTERVAL_CHOICES_MIN,
)

_LOGGER = logging.getLogger(__name__)

# Flow-local keys only: CONF_PASSWORD is a user input, never entry data.
CONF_PASSWORD = "password"
CONF_CODE = "code"
CONF_RESEND = "resend"

PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _interval_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[str(m) for m in INTERVAL_CHOICES_MIN],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="scan_interval",
        )
    )


class VehicleCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow: login -> (email code) -> vehicle -> done."""

    VERSION = 1

    def __init__(self) -> None:
        self._api: VoyahApi | None = None
        self._username: str = ""
        self._password: str = ""
        self._challenge: Challenge | None = None
        self._vehicles: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VehicleCloudOptionsFlow()

    # ---- credentials -----------------------------------------------------
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME].strip()
            self._password = user_input[CONF_PASSWORD]
            self._api = VoyahApi(async_get_clientsession(self.hass))
            result, errors = await self._async_login()
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, vol.UNDEFINED),
                    ): str,
                    vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
                }
            ),
            errors=errors,
        )

    async def _async_login(
        self,
    ) -> tuple[ConfigFlowResult | None, dict[str, str]]:
        assert self._api is not None
        try:
            await self._api.login(self._username, self._password)
        except VoyahVerificationRequired as err:
            self._challenge = err.challenge
            return await self.async_step_verify(), {}
        except VoyahAuthError:
            return None, {"base": "invalid_auth"}
        except VoyahConnectionError:
            return None, {"base": "cannot_connect"}
        except VoyahApiError:
            return None, {"base": "unknown"}
        return await self._async_after_login(), {}

    # ---- email verification ---------------------------------------------
    async def async_step_verify(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._api is not None and self._challenge is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_RESEND):
                try:
                    await self._api.resend_code(self._challenge.challenge_id)
                except VoyahConnectionError:
                    errors["base"] = "cannot_connect"
                except VoyahApiError:
                    errors["base"] = "resend_failed"
            else:
                code = (user_input.get(CONF_CODE) or "").strip()
                if not code:
                    errors[CONF_CODE] = "invalid_code"
                else:
                    try:
                        await self._api.verify(self._challenge.challenge_id, code)
                    except VoyahInvalidCode:
                        errors[CONF_CODE] = "invalid_code"
                    except VoyahConnectionError:
                        errors["base"] = "cannot_connect"
                    except VoyahApiError:
                        errors["base"] = "unknown"
                    else:
                        return await self._async_after_login()

        return self.async_show_form(
            step_id="verify",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CODE): str,
                    vol.Optional(CONF_RESEND, default=False): BooleanSelector(),
                }
            ),
            description_placeholders={"email": self._challenge.email or "—"},
            errors=errors,
        )

    # ---- after tokens are obtained --------------------------------------
    async def _async_after_login(self) -> ConfigFlowResult:
        assert self._api is not None
        if self.source == SOURCE_REAUTH:
            entry = self._get_reauth_entry()
            # Only the tokens are updated; the password is not stored.
            return self.async_update_reload_and_abort(
                entry,
                data_updates=self._token_data(),
            )

        try:
            profile = await self._api.get_profile()
        except VoyahAuthError:
            return self.async_abort(reason="invalid_auth")
        except VoyahApiError:
            return self.async_abort(reason="cannot_connect")

        self._vehicles = enabled_vehicles(profile)
        if not self._vehicles:
            return self.async_abort(reason="no_vehicles")
        if len(self._vehicles) == 1:
            return await self._async_create(self._vehicles[0])
        return await self.async_step_vehicle()

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Only shown when the profile has several enabled vehicles."""
        if user_input is not None:
            chosen = next(
                (v for v in self._vehicles if v["vin"] == user_input[CONF_VIN]), None
            )
            if chosen is not None:
                return await self._async_create(chosen)

        options = [
            SelectOptionDict(
                value=v["vin"], label=f"{v.get('name') or DEFAULT_VEHICLE_NAME} ({v['vin']})"
            )
            for v in self._vehicles
        ]
        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VIN): SelectSelector(
                        SelectSelectorConfig(
                            options=options, mode=SelectSelectorMode.LIST
                        )
                    )
                }
            ),
        )

    def _token_data(self) -> dict[str, Any]:
        assert self._api is not None
        tokens: Tokens = self._api.tokens
        return {
            CONF_ACCESS_TOKEN: tokens.access_token,
            CONF_REFRESH_TOKEN: tokens.refresh_token,
            CONF_DEVICE_TOKEN: tokens.device_token,
        }

    async def _async_create(self, vehicle: dict[str, Any]) -> ConfigFlowResult:
        vin = vehicle["vin"]
        await self.async_set_unique_id(vin)
        self._abort_if_unique_id_configured()
        name = vehicle.get("name") or DEFAULT_VEHICLE_NAME
        return self.async_create_entry(
            title=name,
            data={
                CONF_USERNAME: self._username,
                CONF_VIN: vin,
                CONF_VEHICLE_NAME: name,
                CONF_CAN_MANAGE: vehicle.get("can_manage") is not False,
                **self._token_data(),
            },
            options={
                CONF_SCAN_INTERVAL_MIN: DEFAULT_SCAN_INTERVAL_MIN,
                CONF_STALE_AFTER_MIN: DEFAULT_STALE_AFTER_MIN,
                CONF_DETAILED: DEFAULT_DETAILED,
                CONF_CELL_SENSORS: DEFAULT_CELL_SENSORS,
                CONF_ENABLE_COMMANDS: DEFAULT_ENABLE_COMMANDS,
                CONF_ENABLE_DANGEROUS: DEFAULT_ENABLE_DANGEROUS,
            },
        )

    # ---- re-authentication ----------------------------------------------
    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = entry.data[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]
            self._api = VoyahApi(
                async_get_clientsession(self.hass),
                tokens=Tokens(device_token=entry.data.get(CONF_DEVICE_TOKEN)),
            )
            result, errors = await self._async_login()
            if result is not None:
                return result

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )


class VehicleCloudOptionsFlow(OptionsFlow):
    """Options: poll interval, stale threshold, diagnostic sensors."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL_MIN: int(user_input[CONF_SCAN_INTERVAL_MIN]),
                    CONF_STALE_AFTER_MIN: int(user_input[CONF_STALE_AFTER_MIN]),
                    CONF_DETAILED: bool(user_input[CONF_DETAILED]),
                    CONF_CELL_SENSORS: bool(user_input[CONF_CELL_SENSORS]),
                    CONF_ENABLE_COMMANDS: bool(user_input[CONF_ENABLE_COMMANDS]),
                    # the dangerous switch only counts together with commands
                    CONF_ENABLE_DANGEROUS: bool(
                        user_input[CONF_ENABLE_COMMANDS]
                        and user_input[CONF_ENABLE_DANGEROUS]
                    ),
                }
            )

        opts = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL_MIN,
                        default=str(opts.get(CONF_SCAN_INTERVAL_MIN, DEFAULT_SCAN_INTERVAL_MIN)),
                    ): _interval_selector(),
                    vol.Required(
                        CONF_STALE_AFTER_MIN,
                        default=opts.get(CONF_STALE_AFTER_MIN, DEFAULT_STALE_AFTER_MIN),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=1440,
                            step=1,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_DETAILED,
                        default=opts.get(CONF_DETAILED, DEFAULT_DETAILED),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_CELL_SENSORS,
                        default=opts.get(CONF_CELL_SENSORS, DEFAULT_CELL_SENSORS),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_COMMANDS,
                        default=opts.get(CONF_ENABLE_COMMANDS, DEFAULT_ENABLE_COMMANDS),
                    ): BooleanSelector(),
                    vol.Required(
                        CONF_ENABLE_DANGEROUS,
                        default=opts.get(CONF_ENABLE_DANGEROUS, DEFAULT_ENABLE_DANGEROUS),
                    ): BooleanSelector(),
                }
            ),
        )
