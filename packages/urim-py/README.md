# urim (Python)

Port of the urim-ts v1 **pure core**. It produces byte-identical canonical JSON, contract hashes and urim/1 envelopes.
Python 3.11+. It has no runtime dependencies. Pydantic v2 is an optional extra and sits behind the `{parse, to_json_schema}` adapter.

What the port covers:
- define
- emit
- canonical/sha256
- descriptors
- classify
- both camp codecs (systemone, decisions)
- plan/explain, including the pre-call token estimate
- cuts
- build_envelope
- read_envelope

Parity: `../shared-fixtures/*.vectors.json` are generated from urim-ts (`node test/shared-fixtures.gen.ts`).
Both test suites assert against them. `tests/test_canonical.py::test_cross_port_live_node` also runs the TS
reference locally through node; it is skipped if node is absent.

    python -m pytest            # needs pytest; pydantic tests skip if it is not installed

Also ported (slice 6):
- the async client: `create_client(...)`, `await client.decide(...)`, `explain`, `flush`
- `urim.testing` (`fake_provider`)
- lock parse/serialize (`parse_lock`, `serialize_lock`)
- fit math and `run_fit`
- httpx adapters in `urim.adapters` (one per request format, `systemone` and `decisions` (`openai_decisions`); `pip install urim[httpx]`)

Casing: the Python API is snake_case. All JSON is camelCase. The mapping lives only in `urim/boundary.py`.
Credentials are read from the `env` you pass (no default), at send time.

Hooks: `on_settled` and `on_hook_error` run as asyncio tasks after `decide()` returns. `await client.flush()`
waits for them. Tasks still pending when the event loop ends are lost, so call `flush()` before shutdown.

CLI (slice 7): `urim emit|fit|providers`, also `python -m urim`, with the same exit codes and bytes as urim-ts.
`providers --out x.py` writes a Python module. Any other path writes the TypeScript file.

Checks: `bash ../check.sh` runs pytest, `ruff check`, `ruff format --check` and `mypy --strict` here, plus the
urim-ts tests and `tsc`.
