# urim

**Urim is a contract language for decision models.** Write it once, compile it to any provider, and prove behavior holds before you switch.

> **Pre-alpha (v0.0.1).** The protocol is a v0.1 spec draft. This release ships one working command, `urim check`. The compiler is not implemented yet.

## `urim check <file>`

Validates a hoshen lockfile (`urim.lock`) or the top-level shape of a Urim contract.

```sh
urim check urim.lock
# urim.lock: ok (lockfile, hoshen 2, urim 0.1)
urim check broken.lock
# broken.lock: error: unsupported hoshen version 2 (supported: 1)
```

- Exit codes: 0 valid, 1 invalid (the message goes to stderr), 2 usage error.
- Lockfiles need an integer `hoshen` in the supported set `{2}` and a string `urim`.
- Contracts need `urim` (a string), plus `contract`, `version`, `state`, and a non-empty `questions` mapping.

The TypeScript, Python, and Rust implementations give identical output on a shared fixture suite.

- Homepage: <https://urim.sh>
- Spec and source: <https://github.com/no-complect/urim>
- License: Apache-2.0. Copyright 2026 David Thomason.
