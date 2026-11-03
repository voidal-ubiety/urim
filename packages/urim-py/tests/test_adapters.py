"""httpx transport adapters, exercised ONLY through httpx.MockTransport. No live call is ever made from tests."""

import asyncio
import json

import pytest
from conftest import JEV, SEVERITY, SHARED, TRIAGE, load
from fake_systemone import FAKE_ENV, FAKE_SYSTEMONE

httpx = pytest.importorskip("httpx")

from urim import DESCRIPTORS, UrimError  # noqa: E402
from urim.adapters import http_adapter, openai_decisions, typesafe_jev  # noqa: E402
from urim.client import create_client  # noqa: E402

FAKE_KEY = "test-key-not-a-real-secret"


def fake_adapter():
    return http_adapter(FAKE_SYSTEMONE)


SCEN = {v["name"]: v for v in load(SHARED / "client.vectors.json")}
TRIAGE_OK = SCEN["primary ok"]["script"][JEV.id][0]["body"]
INPUT = {"report": "x"}


def mock(status, body, headers=None, raw=None):
    calls = []

    def handler(request):
        calls.append(request)
        content = raw if raw is not None else json.dumps(body).encode()
        return httpx.Response(status, content=content, headers={"Content-Type": "application/json", **(headers or {})})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), calls


def decide(adapters, http, env, d=TRIAGE):
    async def go():
        async with http:
            return await create_client(adapters=adapters, http=http, env=env).decide(d, INPUT)

    return asyncio.run(go())


def test_systemone_posts_body_with_bearer_auth_to_descriptor_url():
    http, calls = mock(200, TRIAGE_OK)
    r = decide([fake_adapter()], http, {FAKE_ENV: FAKE_KEY})
    assert r.ok
    req = calls[0]
    assert (req.method, str(req.url)) == ("POST", FAKE_SYSTEMONE.url)
    assert req.headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert req.headers["content-type"] == "application/json"
    assert json.loads(req.content)["model"] == "jev-1.14.0"


def test_body_bytes_are_js_json_stringify():
    from urim.jsonfmt import stringify

    http, calls = mock(200, TRIAGE_OK)
    decide([fake_adapter()], http, {FAKE_ENV: FAKE_KEY})
    assert calls[0].content.decode("utf-8") == stringify(json.loads(calls[0].content))


def test_openai_posts_decisions_body_and_records_request_id():
    from conftest import OPENAI

    http, calls = mock(200, SCEN["severity openai ok"]["script"][OPENAI.id][0]["body"], {"x-request-id": "req_42"})
    r = decide([openai_decisions(), fake_adapter()], http, {"OPENAI_API_KEY": FAKE_KEY}, d=SEVERITY)
    assert str(calls[0].url) == "https://api.openai.com/v1/decisions"
    assert calls[0].headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert r.ok and dict(r.envelope.request_ids) == {OPENAI.id: "req_42"}


def test_missing_credential_is_auth_without_network_naming_env_var_only():
    http, calls = mock(200, {})
    r = decide([fake_adapter()], http, {})
    assert not r.ok and r.error.type == "auth" and FAKE_ENV in r.error.message and calls == []


def test_credential_never_in_errors_attempts_reprs_or_logs(caplog):
    http, _ = mock(401, {"error": {"message": "bad key"}})
    adapter = fake_adapter()
    with caplog.at_level("DEBUG"):
        r = decide([adapter], http, {FAKE_ENV: FAKE_KEY})
    assert not r.ok and r.error.type == "auth"
    blob = repr((r.error, r.error.message, r.attempts, adapter, vars(adapter) if hasattr(adapter, "__dict__") else ""))
    assert FAKE_KEY not in blob and FAKE_KEY not in caplog.text


def test_transport_exception_is_internal_and_does_not_leak_the_key():
    def boom(request):
        raise httpx.ConnectError("connection refused", request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(boom))
    r = decide([fake_adapter()], http, {FAKE_ENV: FAKE_KEY})
    assert not r.ok and r.attempts[0].outcome == "internal" and FAKE_KEY not in str(r.error)


def test_529_is_provider_unavailable():
    http, _ = mock(529, {"error": "overloaded"})
    r = decide([fake_adapter()], http, {FAKE_ENV: FAKE_KEY})
    assert not r.ok and r.attempts[0].outcome == "provider_unavailable"


def test_non_json_body_is_nonconformant_and_headers_are_lowercased():
    http, _ = mock(200, None, {"X-Request-Id": "Abc"}, raw=b"<html>")
    r = decide([fake_adapter()], http, {FAKE_ENV: FAKE_KEY})
    assert not r.ok and r.attempts[0].outcome == "nonconformant_response"

    async def direct():
        from urim.testing import SendIO
        from urim.types import WireRequest

        http2, _ = mock(200, None, {"X-Request-Id": "Abc"}, raw=b"<html>")
        async with http2:
            return await fake_adapter().send(
                WireRequest(JEV.id, "systemone", "/v1/systemone", FAKE_SYSTEMONE.url, {}),
                SendIO(credential=FAKE_KEY, cancel=asyncio.Event(), http=http2),
            )

    reply = asyncio.run(direct())
    assert reply.body == "<html>" and reply.headers["x-request-id"] == "Abc"


def test_placeholder_url_descriptor_is_rejected():
    templated = [d for d in DESCRIPTORS.values() if "{" in d.url]
    for d in templated:
        with pytest.raises(UrimError) as e:
            http_adapter(d)
        assert e.value.type == "invalid_definition"


def test_adapters_are_opt_in_and_serve_their_provider():
    import urim

    assert not hasattr(urim, "typesafe_jev") and not hasattr(urim, "openai_decisions")
    assert fake_adapter().provider == JEV.provider and fake_adapter().credential_env == FAKE_ENV
    real, d = typesafe_jev(), DESCRIPTORS["typesafe"]  # shipped adapter = HTTP adapter of its descriptor
    assert (real.provider, real.credential_env) == (d.provider, d.auth[0].env)
    assert openai_decisions().credential_env == "OPENAI_API_KEY"
