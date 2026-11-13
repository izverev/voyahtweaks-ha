"""API client tests using a stub aiohttp (the real one is not installed here)."""

import asyncio
import sys
import types

import pytest

from conftest import COMP


# ---- minimal aiohttp stub ------------------------------------------------
class _ClientError(Exception):
    pass


class _ClientTimeout:
    def __init__(self, total=None):
        self.total = total


stub = types.ModuleType("aiohttp")
stub.ClientError = _ClientError
stub.ClientTimeout = _ClientTimeout
stub.ClientSession = object
sys.modules["aiohttp"] = stub


def _load_pkg():
    """Load const + api as a tiny package so relative imports work."""
    import importlib.util

    pkg = types.ModuleType("vcpkg")
    pkg.__path__ = [str(COMP)]
    sys.modules["vcpkg"] = pkg
    for name in ("const", "api"):
        spec = importlib.util.spec_from_file_location(
            f"vcpkg.{name}", COMP / f"{name}.py"
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"vcpkg.{name}"] = mod
        spec.loader.exec_module(mod)
    return sys.modules["vcpkg.api"]


api = _load_pkg()


class FakeResp:
    def __init__(self, status, body=None, headers=None):
        self.status = status
        self._body = body
        self.headers = headers or {}

    async def json(self, content_type=None):
        if self._body is None:
            raise ValueError("no body")
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Scripted responses; records calls."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def request(self, method, url, headers=None, json=None, data=None, timeout=None):
        self.calls.append((method, url, dict(headers or {}), json, data))
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def run(coro):
    return asyncio.run(coro)


TOK = {"access_token": "A2", "refresh_token": "R2", "device_token": "D1"}


def make(script, **kw):
    s = FakeSession(script)
    saved = []
    a = api.VoyahApi(s, token_callback=saved.append, **kw)
    return a, s, saved


def test_telemetry_ok():
    a, s, _ = make(
        [FakeResp(200, {"online": True})],
        tokens=api.Tokens("A1", "R1", "D1"),
    )
    assert run(a.get_telemetry("VIN1")) == {"online": True}
    assert s.calls[0][1].endswith("/api/v2/vehicles/VIN1/telemetry")
    assert s.calls[0][2]["Authorization"] == "Bearer A1"


def test_401_refresh_then_retry_once():
    a, s, saved = make(
        [FakeResp(401), FakeResp(200, TOK), FakeResp(200, {"ok": 1})],
        tokens=api.Tokens("A1", "R1", "D1"),
    )
    assert run(a.get_telemetry("V")) == {"ok": 1}
    assert [c[1].rsplit("/api/v2", 1)[1] for c in s.calls] == [
        "/vehicles/V/telemetry",
        "/auth/refresh",
        "/vehicles/V/telemetry",
    ]
    assert s.calls[1][3] == {"refresh_token": "R1"}
    assert s.calls[2][2]["Authorization"] == "Bearer A2"
    assert saved and saved[-1].access_token == "A2"


def test_second_401_is_final_no_loop():
    a, s, _ = make(
        [FakeResp(401), FakeResp(200, TOK), FakeResp(401)],
        tokens=api.Tokens("A1", "R1", "D1"),
    )
    with pytest.raises(api.VoyahAuthError):
        run(a.get_telemetry("V"))
    assert len(s.calls) == 3  # exactly one refresh and one retry


def test_refresh_rejected_is_auth_error_no_password_fallback():
    """A rejected refresh token must end in reauth, never a silent password login."""
    a, s, _ = make(
        [FakeResp(401), FakeResp(401)], tokens=api.Tokens("A1", "R1", "D1")
    )
    with pytest.raises(api.VoyahAuthError):
        run(a.get_telemetry("V"))
    # exactly the original request + the failed refresh, nothing else
    assert [c[1].rsplit("/api/v2", 1)[1] for c in s.calls] == [
        "/vehicles/V/telemetry",
        "/auth/refresh",
    ]


def test_refresh_rejected_without_refresh_token_is_auth_error():
    a, _s, _ = make(
        [FakeResp(401), FakeResp(401)], tokens=api.Tokens("A1", None, None)
    )
    with pytest.raises(api.VoyahAuthError):
        run(a.get_telemetry("V"))


def test_password_is_not_stored_on_the_client():
    a, _s, _ = make([], tokens=api.Tokens("A1", "R1", "D1"))
    for attr in vars(a):
        assert "passw" not in attr.lower(), f"client keeps a password in {attr}"


def test_login_challenge_and_verify():
    a, s, saved = make(
        [
            FakeResp(202, {"challenge_id": "C", "email": "i***@x", "resend_after": 60}),
            FakeResp(200, TOK),
        ],
    )
    with pytest.raises(api.VoyahVerificationRequired) as ei:
        run(a.login("u", "p"))
    ch = ei.value.challenge
    assert (ch.challenge_id, ch.resend_after) == ("C", 60)
    tokens = run(a.verify("C", "123456"))
    assert tokens.device_token == "D1"
    assert s.calls[1][3] == {"challenge_id": "C", "code": "123456"}
    assert saved[-1].device_token == "D1"


def test_invalid_credentials_and_code():
    a, _s, _ = make([FakeResp(401)])
    with pytest.raises(api.VoyahAuthError):
        run(a.login("u", "bad"))
    a, _s, _ = make([FakeResp(400)])
    with pytest.raises(api.VoyahInvalidCode):
        run(a.verify("C", "0"))


def test_errors_mapped():
    tk = api.Tokens("A1", "R1", None)
    a, _s, _ = make([FakeResp(503)], tokens=tk)
    with pytest.raises(api.VoyahApiError) as ei:
        run(a.get_telemetry("V"))
    assert ei.value.status == 503 and not isinstance(ei.value, api.VoyahAuthError)

    a, _s, _ = make([FakeResp(429, headers={"Retry-After": "120"})], tokens=tk)
    with pytest.raises(api.VoyahRateLimited) as ei:
        run(a.get_telemetry("V"))
    assert ei.value.retry_after == 120

    a, _s, _ = make([_ClientError("boom")], tokens=tk)
    with pytest.raises(api.VoyahConnectionError):
        run(a.get_telemetry("V"))

    a, _s, _ = make([asyncio.TimeoutError()], tokens=tk)
    with pytest.raises(api.VoyahConnectionError):
        run(a.get_telemetry("V"))

    a, _s, _ = make([FakeResp(200, ["not", "a", "dict"])], tokens=tk)
    with pytest.raises(api.VoyahApiError):
        run(a.get_telemetry("V"))


def test_error_texts_have_no_secrets():
    a, _s, _ = make([FakeResp(401)])
    with pytest.raises(api.VoyahAuthError) as ei:
        run(a.login("u", "SECRETPASS"))
    assert "SECRETPASS" not in str(ei.value)


def test_enabled_vehicles():
    profile = {
        "vehicles": [
            {"vin": "A", "disabled": True},
            {"vin": "B", "name": "x", "disabled": False},
            {"name": "novin"},
            "junk",
            {"vin": "C"},
        ]
    }
    assert [v["vin"] for v in api.enabled_vehicles(profile)] == ["B", "C"]
    assert api.enabled_vehicles({}) == []


TK = api.Tokens("A1", "R1", "D1")


def test_send_command_body_shape():
    a, s, _ = make([FakeResp(200, {"ok": True})], tokens=TK)
    cid = run(a.send_command("V", "climate", {"mode": "temp", "temp": 22.5}))
    method, url, headers, body, _form = s.calls[0]
    assert method == "POST" and url.endswith("/api/v2/vehicles/V/command")
    assert body["cmd"] == "climate" and body["command_id"] == cid
    assert body["mode"] == "temp" and body["temp"] == 22.5
    assert len(cid) == 36
    # nothing from the UI descriptor leaks into the body
    assert not {"control_id", "control_value", "group", "label", "danger"} & set(body)


def test_payload_cannot_override_cmd_or_id():
    a, s, _ = make([FakeResp(200, {})], tokens=TK)
    run(a.send_command("V", "door_lock", {"cmd": "door_unlock", "command_id": "x"}))
    body = s.calls[0][3]
    assert body["cmd"] == "door_lock" and body["command_id"] != "x"


def test_run_command_polls_until_completed():
    a, s, _ = make(
        [
            FakeResp(200, {}),  # POST
            FakeResp(404),  # not visible yet
            FakeResp(200, {"status": "pending"}),
            FakeResp(200, {"status": "sent"}),
            FakeResp(200, {"status": "completed", "result": {"code": 17}}),
        ],
        tokens=TK,
    )
    res = run(a.run_command("V", "door_lock", poll_interval=0))
    assert res.status == "completed" and res.code == 17
    cid = s.calls[0][3]["command_id"]
    assert s.calls[-1][1].endswith(f"/vehicles/V/commands/{cid}")


@pytest.mark.parametrize("status", ["failed", "no_response", "expired"])
def test_run_command_terminal_states(status):
    a, _s, _ = make(
        [FakeResp(200, {}), FakeResp(200, {"status": status, "result": {"reason": "boom"}})],
        tokens=TK,
    )
    res = run(a.run_command("V", "door_lock", poll_interval=0))
    assert res.status == status and res.reason == "boom"


def test_run_command_timeout():
    a, _s, _ = make([FakeResp(200, {})] + [FakeResp(200, {"status": "sent"})] * 50, tokens=TK)
    with pytest.raises(api.VoyahCommandTimeout) as ei:
        run(a.run_command("V", "door_lock", timeout=0.01, poll_interval=0.005))
    assert ei.value.last_status == "sent"


def test_command_http_errors_carry_detail():
    a, _s, _ = make([FakeResp(403, {"detail": "vehicle blocked"})], tokens=TK)
    with pytest.raises(api.VoyahApiError) as ei:
        run(a.send_command("V", "door_lock"))
    assert ei.value.status == 403 and ei.value.detail == "vehicle blocked"

    a, _s, _ = make([FakeResp(429, {"detail": "slow down"}, {"Retry-After": "5"})], tokens=TK)
    with pytest.raises(api.VoyahRateLimited) as ei:
        run(a.send_command("V", "door_lock"))
    assert ei.value.detail == "slow down"


def test_command_401_refreshes_and_resends_once():
    a, s, _ = make(
        [FakeResp(401), FakeResp(200, TOK), FakeResp(200, {})], tokens=TK
    )
    run(a.send_command("V", "door_lock"))
    assert [c[1].rsplit("/api/v2", 1)[1] for c in s.calls] == [
        "/vehicles/V/command", "/auth/refresh", "/vehicles/V/command",
    ]
