"""Async client for the Voyahtweaks API (https://app.voyahtweaks.ru/api/v2).

Secrets (password, tokens) are never logged and never put in exception texts.
The password is not stored by this client: it is passed to :meth:`VoyahApi.login`
by the config flow and discarded afterwards. Session renewal relies on the
refresh token only. Vehicle commands are intentionally NOT implemented here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any
import uuid

import aiohttp

from .const import (
    API_PREFIX,
    BASE_URL,
    COMMAND_POLL_SECONDS,
    COMMAND_TIMEOUT_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------
class VoyahApiError(Exception):
    """Base error. ``status`` is the HTTP status when known."""

    def __init__(
        self, reason: str, status: int | None = None, detail: str | None = None
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.detail = detail  # server-provided text, never contains our secrets


class VoyahConnectionError(VoyahApiError):
    """Network problem or timeout."""


class VoyahAuthError(VoyahApiError):
    """Credentials rejected or the session cannot be renewed."""


class VoyahInvalidCode(VoyahApiError):
    """Wrong or expired email verification code."""


class VoyahRateLimited(VoyahApiError):
    """HTTP 429."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__("rate_limited", 429)
        self.retry_after = retry_after


class VoyahCommandTimeout(VoyahApiError):
    """No terminal command status within the timeout."""

    def __init__(self, last_status: str) -> None:
        super().__init__("command_timeout")
        self.last_status = last_status


TERMINAL_COMMAND_STATUSES = frozenset({"completed", "failed", "no_response", "expired"})


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    status: str  # completed | failed | no_response | expired
    code: int | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Challenge:
    """Email confirmation challenge (HTTP 202 from /auth/token)."""

    challenge_id: str
    email: str | None = None
    resend_after: int | None = None


class VoyahVerificationRequired(Exception):
    """Login needs an email code."""

    def __init__(self, challenge: Challenge) -> None:
        super().__init__("verification_required")
        self.challenge = challenge


@dataclass(frozen=True)
class Tokens:
    access_token: str | None = None
    refresh_token: str | None = None
    device_token: str | None = None


# --------------------------------------------------------------------------
# Client
# --------------------------------------------------------------------------
class VoyahApi:
    """Voyahtweaks API client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        tokens: Tokens | None = None,
        token_callback: Callable[[Tokens], None] | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self._session = session
        self._tokens = tokens or Tokens()
        self._token_callback = token_callback
        self._base = base_url.rstrip("/") + API_PREFIX
        self._lock = asyncio.Lock()

    @property
    def tokens(self) -> Tokens:
        return self._tokens

    # ---- internals -------------------------------------------------------
    def _set_tokens(self, new: Tokens) -> None:
        # Keep older values if the server did not send a new one.
        merged = Tokens(
            access_token=new.access_token or self._tokens.access_token,
            refresh_token=new.refresh_token or self._tokens.refresh_token,
            device_token=new.device_token or self._tokens.device_token,
        )
        changed = merged != self._tokens
        self._tokens = merged
        if changed and self._token_callback is not None:
            self._token_callback(merged)

    @staticmethod
    def _parse_tokens(body: Any) -> Tokens:
        if not isinstance(body, dict) or not isinstance(body.get("access_token"), str):
            raise VoyahApiError("unexpected_response")

        def _s(key: str) -> str | None:
            val = body.get(key)
            return val if isinstance(val, str) and val else None

        return Tokens(_s("access_token"), _s("refresh_token"), _s("device_token"))

    async def _raw(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any = None,
        form: dict[str, str] | None = None,
    ) -> tuple[int, Any, float | None]:
        """Perform one HTTP request. Returns (status, json_or_None, retry_after)."""
        all_headers = {"Accept": "application/json"}
        if headers:
            all_headers.update(headers)
        url = f"{self._base}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=all_headers,
                json=json_body,
                data=form,
                timeout=_TIMEOUT,
            ) as resp:
                status = resp.status
                retry_after: float | None = None
                raw_retry = resp.headers.get("Retry-After")
                if raw_retry:
                    try:
                        retry_after = float(raw_retry)
                    except ValueError:
                        retry_after = None
                try:
                    body = await resp.json(content_type=None)
                except (ValueError, aiohttp.ClientError):
                    body = None
        except asyncio.TimeoutError as err:
            raise VoyahConnectionError("timeout") from err
        except aiohttp.ClientError as err:
            raise VoyahConnectionError(type(err).__name__) from err
        return status, body, retry_after

    @staticmethod
    def _detail(body: Any) -> str | None:
        if isinstance(body, dict):
            detail = body.get("detail") or body.get("message") or body.get("error")
            if isinstance(detail, str) and detail:
                return detail[:200]
        return None

    @classmethod
    def _raise_for_status(
        cls, status: int, retry_after: float | None, body: Any = None
    ) -> None:
        if 200 <= status < 300:
            return
        detail = cls._detail(body)
        if status == 401:
            raise VoyahAuthError("unauthorized", status, detail)
        if status == 429:
            err = VoyahRateLimited(retry_after)
            err.detail = detail
            raise err
        if status == 403:
            raise VoyahApiError("forbidden", status, detail)
        if status == 404:
            raise VoyahApiError("not_found", status, detail)
        if status >= 500:
            raise VoyahApiError("server_error", status, detail)
        raise VoyahApiError(f"http_{status}", status, detail)

    async def _authed(
        self, method: str, path: str, *, json_body: Any = None
    ) -> Any:
        """Authorised request with one refresh+retry on HTTP 401."""
        if not self._tokens.access_token:
            await self._reauthenticate(None)

        used = self._tokens.access_token
        status, body, retry_after = await self._raw(
            method,
            path,
            headers={"Authorization": f"Bearer {used}"},
            json_body=json_body,
        )
        if status == 401:
            await self._reauthenticate(used)
            used = self._tokens.access_token
            status, body, retry_after = await self._raw(
                method,
                path,
                headers={"Authorization": f"Bearer {used}"},
                json_body=json_body,
            )
            # Second 401 is final: no more attempts, no loop.
        self._raise_for_status(status, retry_after, body)
        return body

    async def _reauthenticate(self, failed_token: str | None) -> None:
        """Renew the access token using the refresh token.

        The password is never kept around, so there is no password fallback:
        a rejected refresh token means the user has to re-authenticate.
        """
        async with self._lock:
            current = self._tokens.access_token
            if current and current != failed_token:
                return  # somebody else already renewed it

            if not self._tokens.refresh_token:
                raise VoyahAuthError("no_credentials")
            # A rejected refresh token raises VoyahAuthError; connection and
            # server errors propagate to the caller unchanged.
            await self._refresh_locked()

    async def _refresh_locked(self) -> None:
        headers: dict[str, str] = {}
        if self._tokens.device_token:
            headers["x-device-token"] = self._tokens.device_token
        status, body, retry_after = await self._raw(
            "POST",
            "/auth/refresh",
            headers=headers,
            json_body={"refresh_token": self._tokens.refresh_token},
        )
        if status in (400, 401, 403, 422):
            raise VoyahAuthError("refresh_rejected", status)
        self._raise_for_status(status, retry_after)
        self._set_tokens(self._parse_tokens(body))

    async def _login_locked(self, username: str, password: str) -> Tokens:
        headers: dict[str, str] = {}
        if self._tokens.device_token:
            headers["x-device-token"] = self._tokens.device_token
        status, body, retry_after = await self._raw(
            "POST",
            "/auth/token",
            headers=headers,
            form={
                "grant_type": "password",
                "username": username,
                "password": password,
            },
        )
        if status == 202:
            cid = body.get("challenge_id") if isinstance(body, dict) else None
            if not isinstance(cid, str) or not cid:
                raise VoyahApiError("unexpected_response", 202)
            resend = body.get("resend_after")
            email = body.get("email")
            raise VoyahVerificationRequired(
                Challenge(
                    cid,
                    email if isinstance(email, str) else None,
                    resend if isinstance(resend, int) else None,
                )
            )
        if status in (400, 401, 403, 422):
            raise VoyahAuthError("invalid_credentials", status)
        self._raise_for_status(status, retry_after)
        self._set_tokens(self._parse_tokens(body))
        return self._tokens

    # ---- public: authentication -----------------------------------------
    async def login(self, username: str, password: str) -> Tokens:
        """Log in with the password.

        Called only from the config flow: the password is not stored, so a
        fresh login needs the user to type it again. May raise
        VoyahVerificationRequired.
        """
        async with self._lock:
            return await self._login_locked(username, password)

    async def verify(self, challenge_id: str, code: str) -> Tokens:
        """Confirm email with the code; stores access/refresh/device tokens."""
        status, body, retry_after = await self._raw(
            "POST",
            "/auth/token/verify",
            json_body={"challenge_id": challenge_id, "code": code},
        )
        if status in (400, 401, 403, 404, 422):
            raise VoyahInvalidCode("invalid_code", status)
        self._raise_for_status(status, retry_after)
        self._set_tokens(self._parse_tokens(body))
        return self._tokens

    async def resend_code(self, challenge_id: str) -> None:
        """Ask the server to resend the email code.

        NOTE: the request body of /auth/token/resend is not confirmed; only the
        route was seen in the app's JavaScript.
        """
        status, _body, retry_after = await self._raw(
            "POST",
            "/auth/token/resend",
            json_body={"challenge_id": challenge_id},
        )
        self._raise_for_status(status, retry_after)

    async def refresh(self) -> None:
        async with self._lock:
            await self._refresh_locked()

    # ---- public: data ----------------------------------------------------
    async def get_profile(self) -> dict[str, Any]:
        body = await self._authed("GET", "/me")
        if not isinstance(body, dict):
            raise VoyahApiError("unexpected_response")
        return body

    async def get_telemetry(self, vin: str) -> dict[str, Any]:
        body = await self._authed("GET", f"/vehicles/{vin}/telemetry")
        if not isinstance(body, dict):
            raise VoyahApiError("unexpected_response")
        return body

    # ---- public: commands ------------------------------------------------
    async def send_command(
        self, vin: str, cmd: str, payload: dict[str, Any] | None = None
    ) -> str:
        """POST /vehicles/{vin}/command. Returns the client generated command id.

        Body shape (confirmed from the app's JavaScript):
        ``{"command_id": <uuid4>, "cmd": <name>, **payload}``.
        The app ignores the response body and polls its own UUID, so we do too.
        """
        command_id = str(uuid.uuid4())
        body: dict[str, Any] = {**(payload or {}), "command_id": command_id, "cmd": cmd}
        await self._authed("POST", f"/vehicles/{vin}/command", json_body=body)
        return command_id

    async def get_command(self, vin: str, command_id: str) -> dict[str, Any]:
        body = await self._authed("GET", f"/vehicles/{vin}/commands/{command_id}")
        if not isinstance(body, dict):
            raise VoyahApiError("unexpected_response")
        return body

    async def run_command(
        self,
        vin: str,
        cmd: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float = COMMAND_TIMEOUT_SECONDS,
        poll_interval: float = COMMAND_POLL_SECONDS,
    ) -> CommandResult:
        """Send a command and wait until it reaches a terminal status.

        Raises VoyahCommandTimeout if no terminal status arrives in ``timeout``
        seconds (the command may still be executed by the car).
        """
        command_id = await self.send_command(vin, cmd, payload)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        not_found = 0
        last_status = "accepted"
        while True:
            await asyncio.sleep(poll_interval)
            try:
                body = await self.get_command(vin, command_id)
            except VoyahApiError as err:
                # right after POST the record may not be visible yet
                if err.status == 404 and not_found < 5:
                    not_found += 1
                    body = None
                else:
                    raise
            if body is not None:
                status = body.get("status")
                if isinstance(status, str):
                    last_status = status
                if last_status in TERMINAL_COMMAND_STATUSES:
                    result = body.get("result")
                    result = result if isinstance(result, dict) else {}
                    reason = result.get("reason")
                    code = result.get("code")
                    return CommandResult(
                        command_id=command_id,
                        status=last_status,
                        code=code if isinstance(code, int) else None,
                        reason=reason if isinstance(reason, str) else None,
                    )
            if loop.time() >= deadline:
                raise VoyahCommandTimeout(last_status)


def enabled_vehicles(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Vehicles from /me that are not disabled and have a VIN."""
    result: list[dict[str, Any]] = []
    for item in profile.get("vehicles") or []:
        if not isinstance(item, dict) or item.get("disabled") is True:
            continue
        vin = item.get("vin")
        if isinstance(vin, str) and vin:
            result.append(item)
    return result


__all__ = [
    "Challenge",
    "CommandResult",
    "TERMINAL_COMMAND_STATUSES",
    "Tokens",
    "VoyahApi",
    "VoyahApiError",
    "VoyahAuthError",
    "VoyahCommandTimeout",
    "VoyahConnectionError",
    "VoyahInvalidCode",
    "VoyahRateLimited",
    "VoyahVerificationRequired",
    "enabled_vehicles",
]
