"""Constants for the VoyahTweaks integration."""

from __future__ import annotations

DOMAIN = "voyahtweaks-ha"

BASE_URL = "https://app.voyahtweaks.ru"
API_PREFIX = "/api/v2"

MANUFACTURER = "Voyah"
MODEL = "Free"
DEFAULT_VEHICLE_NAME = "Voyah Free"

# config entry data
# The password is deliberately absent: it is only used while the config flow
# runs and is never written to the config entry.
CONF_USERNAME = "username"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_DEVICE_TOKEN = "device_token"
CONF_VIN = "vin"
CONF_VEHICLE_NAME = "vehicle_name"

# options
CONF_SCAN_INTERVAL_MIN = "scan_interval_min"
CONF_STALE_AFTER_MIN = "stale_after_min"
CONF_DETAILED = "detailed_diagnostics"
CONF_CELL_SENSORS = "cell_sensors"

INTERVAL_CHOICES_MIN = [1, 2, 5, 10, 15, 30]
DEFAULT_SCAN_INTERVAL_MIN = 5
DEFAULT_STALE_AFTER_MIN = 10
DEFAULT_DETAILED = True
DEFAULT_CELL_SENSORS = False

# Hard limit: telemetry is never requested more often than this.
MIN_POLL_SECONDS = 60
# Upper bound of the error back-off.
MAX_BACKOFF_SECONDS = 30 * 60

STORAGE_VERSION = 1
STORAGE_SAVE_DELAY = 30

REQUEST_TIMEOUT_SECONDS = 30

# --- vehicle commands -------------------------------------------------------
CONF_CAN_MANAGE = "can_manage"
CONF_ENABLE_COMMANDS = "enable_commands"
CONF_ENABLE_DANGEROUS = "enable_dangerous_commands"
DEFAULT_ENABLE_COMMANDS = False  # explicit opt-in
DEFAULT_ENABLE_DANGEROUS = False  # explicit opt-in, on top of the above

COMMAND_TIMEOUT_SECONDS = 90
COMMAND_POLL_SECONDS = 1.5

# Commands that can start the vehicle; need their own switch in the options.
DANGEROUS_COMMANDS = frozenset({"keyless_start"})

DEFAULT_CHARGE_MAX_SOC = 80
CLIMATE_MIN_TEMP = 16.0  # NOT confirmed against the app; server validates
CLIMATE_MAX_TEMP = 32.0
CLIMATE_DEFAULT_TEMP = 22.0
