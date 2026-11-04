# urim

A typed client for system-1 decision APIs: define a decision once, call it across providers,
and get every answer back with its confidence, the tier that served it and a stable envelope.
The Python package matches the `urim` npm package byte for byte on canonical JSON, contract hashes and envelopes.

**Status:** alpha (0.0.1a1). The API may change, and it has not been tested against live providers yet. Python 3.11 or later, no runtime dependencies.

```sh
pip install --pre urim      # core (alpha: needs --pre)
pip install "urim[httpx]"   # network adapters
pip install "urim[pydantic]" # Pydantic v2 input schemas
```

## Quickstart (offline)

This runs without a network or API key: `fake_provider` from `urim.testing` scripts the provider's reply.

```python
import asyncio

from urim import create_client, define_decision, json_schema_adapter, noul, tier
from urim.testing import fake_provider

# OpenAI publishes no model version, so "0.0.0" is a placeholder.
openai = tier(provider="openai", model="gpt-6-luna", version="0.0.0", camp="decisions", question_types=["noul"])

triage = define_decision(
    contract="incident-triage@1.0.0",
    tiers=[openai],
    # json_schema_adapter(schema, validate); `pydantic_schema` adapts a Pydantic model (extra: urim[pydantic]).
    input=json_schema_adapter({"type": "object"}, lambda value: []),
    questions={"page": noul("Should someone be paged right now?", yes="Active customer impact", no="No impact")},
    failover_on=["timeout", "provider_unavailable"],
)

# Offline: a scripted provider stands in for the network. For real calls use `openai_decisions()` from urim.adapters.
provider = fake_provider(
    {
        openai.id: [
            {"body": {"model": "gpt-6-luna", "answers": [{"type": "predicate", "name": "page", "probability": 0.95}]}}
        ]
    }
)


async def main() -> None:
    result = await create_client(adapters=[provider]).decide(triage, {"report": "checkout API returns 500s"})
    print(result.value["page"] if result.ok else result.error.type)


asyncio.run(main())
```

It prints the answer: `value='yes'`, `confidence=0.9` and where the confidence came from.

## What's included
- define, emit, canonical JSON and sha256 contract hashes
- the async client: `create_client(...)`, `await client.decide(...)`, `explain`, `flush`
- `urim.testing` (`fake_provider`)
- lock parse/serialize (`parse_lock`, `serialize_lock`), fit math and `run_fit`
- httpx adapters in `urim.adapters`, one per request format (`systemone` and `decisions`, e.g. `openai_decisions`)
- the `urim emit|fit|providers` CLI, also `python -m urim`, with the same exit codes and bytes as the npm package

Casing: the Python API is snake_case. All JSON is camelCase. The mapping lives only in `urim/boundary.py`.
Credentials are read from the `env` you pass (no default), at send time, and never logged.

Hooks: `on_settled` and `on_hook_error` run as asyncio tasks after `decide()` returns. `await client.flush()`
waits for them. Tasks still pending when the event loop ends are lost, so call `flush()` before shutdown.

## Development

Parity: `../shared-fixtures/*.vectors.json` are generated from the TypeScript package and both test suites
assert against them. `bash ../check.sh` runs pytest, `ruff check`, `ruff format --check` and `mypy --strict`,
plus the TypeScript tests and `tsc`.

    python -m pytest            # pydantic tests skip if it is not installed
