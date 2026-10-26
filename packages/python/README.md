# urim

**Urim is a contract language for decision models.** Write it once, compile it to any provider, and prove behavior holds before you switch.

<!-- generated:status (scripts/check-project --write) -->
> **Pre-alpha (v0.0.1).** The protocol is SPEC v0.2.0-draft. This release ships one working command, `urim check`. The compiler is not implemented yet.
<!-- /generated:status -->

## `urim check <file>`

Validates a Urim contract or a hoshen lockfile (`urim.lock`) against the closed 0.2 schemas.

```sh
urim check urim.lock
# urim.lock: ok (lockfile, hoshen 2, urim 0.2)
urim check old.lock
# old.lock: error: unsupported urim version 0.1 (supported: 0.2)
```

- Exit codes: 0 valid, 1 invalid (the message goes to stderr), 2 usage error.
- Lockfiles need `hoshen: 2`, `urim: "0.2"`, every required field of the hoshen 2 format, and an `integrity` that matches their content.
- Contracts need `urim: "0.2"`, plus `contract` (an id), `version` (SemVer), `state` and `questions`. Unknown keys are errors; vendor keys use `x-<provider>`.

The TypeScript, Python, and Rust implementations give identical output on a shared fixture suite.

<!-- generated:links (from config/project.json) -->
- Homepage: <https://urim.sh>
- Spec and source: <https://github.com/voidal-ubiety/urim>
- License: Apache-2.0. Copyright 2026 David Thomason and Urim contributors.
<!-- /generated:links -->
