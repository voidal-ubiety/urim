"""transport.vectors.json parity: urim-ts adapter + sendOnce transport-error rules, reproduced over httpx.MockTransport.

Every fault is simulated in process (no network): connect/dns/tls are httpx transport exceptions, a body read
failure is a stream that raises, a hang is a handler that sleeps past the deadline."""

import asyncio

import pytest
from conftest import JEV, SHARED, TRIAGE, load
from fake_systemone import FAKE_ENV, FAKE_SYSTEMONE

httpx = pytest.importorskip("httpx")

from urim import DESCRIPTORS, UrimError  # noqa: E402
from urim.adapters import http_adapter  # noqa: E402
from urim.camps import encode_request  # noqa: E402
from urim.client import create_client  # noqa: E402
from urim.testing import SendIO  # noqa: E402

V = load(SHARED / "transport.vectors.json")
RAISES = {"connect": httpx.ConnectError, "dns": httpx.ConnectError, "tls": httpx.ConnectError}


class _Broken(httpx.AsyncByteStream):
    async def __aiter__(self):
        raise httpx.ReadError("reset")
        yield b""  # pragma: no cover


def client_for(fault, calls):
    async def handler(request):
        calls.append(request)
        kind = fault["kind"]
        if kind == "throw":
            raise RAISES[fault["fault"]](fault["fault"])
        if kind == "hang":
            await asyncio.sleep(5)
        if kind == "body_read":
            return httpx.Response(200, stream=_Broken())
        return httpx.Response(fault["status"], content=fault["bodyText"].encode(), headers=fault["headers"])

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def err_json(e):
    return {"type": e.type, "message": e.message, "tier": e.tier} if isinstance(e, UrimError) else {"threw": True}


@pytest.mark.parametrize("row", V["constructible"], ids=[r["provider"] for r in V["constructible"]])
def test_constructible(row):
    if row["ok"]:
        assert http_adapter(DESCRIPTORS[row["provider"]]).provider == row["provider"]
    else:
        with pytest.raises(UrimError, match="^" + row["message"] + "$") as e:
            http_adapter(DESCRIPTORS[row["provider"]])
        assert e.value.type == "invalid_definition"


@pytest.mark.parametrize("case", V["cases"], ids=[c["name"] for c in V["cases"]])
def test_transport_case(case):
    exp, fault, cred = case["expected"], case["fault"], case["credential"]
    adapter = http_adapter(FAKE_SYSTEMONE)

    async def go():
        if exp["adapter"] is not None:
            calls = []
            async with client_for(fault, calls) as http:
                try:
                    r = await adapter.send(encode_request(TRIAGE, JEV, {"report": "x"}), SendIO(cred or "", None, http))
                    headers = {k: v for k, v in r.headers.items() if k != "content-length"}  # added by the stack
                    got = {"reply": {"status": r.status, "headers": headers, "body": r.body}}
                except Exception as e:  # the vector records "threw" for any non-UrimError
                    got = {"error": err_json(e)}
            assert got == exp["adapter"]
        calls = []
        env = {} if cred is None else {FAKE_ENV: cred}
        async with client_for(fault, calls) as http:
            c = create_client(adapters=[adapter], env=env, http=http, now=lambda: 1793221200000)
            r = await c.decide(TRIAGE, {"report": "x"}, deadline_ms=case["deadlineMs"])
        attempts = [a.outcome for a in (r.envelope.attempts if r.ok else r.attempts)]
        assert {"ok": r.ok, "error": None if r.ok else err_json(r.error), "attempts": attempts} == exp["decide"]
        assert len(calls) == exp["fetchCalls"]

    asyncio.run(go())
