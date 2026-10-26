# 0002. One package, `urim`, on every registry (t51u)

- **Status:** Accepted, 2026-10-26.
- **Decided by:** David (t51u).

## Decision

Urim ships exactly one package, named `urim`, on every registry: npm, PyPI, crates.io and, if it is adopted, JSR. **Thummim** (the eval and conformance suite) and **hoshen** (the lockfile format) are internal names inside `urim`: a module and a file format. They are not packages. Nothing plans, reserves or claims a `thummim` or `hoshen` package name on any registry.

## Consequences

- Thummim lives behind a clean module boundary, so it could be split out later without breaking users. The planned layout is a `thummim` module per port: `src/thummim/` in JS, `urim.thummim` in Python, `urim::thummim` in Rust. Code outside the module uses only the module's public API, and the module does not import the CLI. When it is written, `scripts/check-architecture` should enforce this. It is not written yet, because Thummim has no code yet.
- Splitting Thummim out later would be a new decision, with its own name check at that time.
- Monitoring the registries for lookalike or typosquat packages named after `thummim` or `hoshen` is allowed. It is read-only, and it does not claim either name.
