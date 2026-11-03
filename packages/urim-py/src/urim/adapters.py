"""A: real HTTP adapters over httpx (opt-in: ``from urim.adapters import typesafe_jev, openai_decisions``).

Nothing here runs unless you import it AND pass it to ``create_client``. The credential arrives from the client,
which reads the env var named by ``credential_env`` at send time. It is put in one request header and never
logged, stored, or placed in any error message. Pass ``create_client(http=httpx.AsyncClient(...))`` to share a
connection pool (tests use ``httpx.MockTransport``); otherwise one client is opened per send.
Requires the optional extra: ``pip install urim[httpx]``. Mirrors urim-ts src/adapters/index.ts.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from .descriptors import DESCRIPTORS, AuthSpec, Descriptor
from .errors import UrimError
from .jsonfmt import stringify
from .testing import SendIO
from .types import WireReply, WireRequest


def _reject_constant(name: str) -> Any:
    raise ValueError(name)  # NaN/Infinity are not JSON (JSON.parse rejects them too)


def _read_body(text: str) -> Any:
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ValueError:
        return text  # non-JSON -> the decoder reports nonconformant_response


@dataclass(frozen=True)
class HttpAdapter:
    provider: str
    credential_env: str
    _url: str
    _auth: AuthSpec

    async def send(self, req: WireRequest, io: SendIO) -> WireReply:
        if io.credential == "":
            raise UrimError("auth", f"missing credential: set {self.credential_env}", tier=req.tier_id)
        value = io.credential if self._auth.scheme is None else f"{self._auth.scheme} {io.credential}"
        headers = {"content-type": "application/json", self._auth.header: value}
        content = stringify(req.body).encode("utf-8")
        started = time.monotonic()
        if io.http is not None:
            res = await io.http.post(req.url, content=content, headers=headers)
        else:
            import httpx  # optional extra, imported only when a real send happens

            async with httpx.AsyncClient() as http:
                res = await http.post(req.url, content=content, headers=headers)
        return WireReply(
            res.status_code,
            {k.lower(): v for k, v in res.headers.items()},
            _read_body(res.text),
            (time.monotonic() - started) * 1000,
        )


def http_adapter(d: Descriptor) -> HttpAdapter:
    """One adapter per descriptor whose URL needs no caller-supplied placeholders."""
    if not d.auth or "{" in d.url:
        raise UrimError(
            "invalid_definition", f"{d.provider}: descriptor needs URL/auth options this slice does not support"
        )
    return HttpAdapter(d.provider, d.auth[0].env, d.url, d.auth[0])


def typesafe_jev() -> HttpAdapter:
    """TypeSafe Jev, systemone camp. Bearer TYPESAFE_API_KEY -> the descriptor URL."""
    return http_adapter(DESCRIPTORS["typesafe"])


def openai_decisions() -> HttpAdapter:
    """OpenAI, decisions camp. Bearer OPENAI_API_KEY -> the descriptor URL."""
    return http_adapter(DESCRIPTORS["openai"])
