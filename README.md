# Urim

**Urim is a contract language for decision models.** Write it once, compile it to any provider, and prove behavior holds before you switch.

Decision models take application state plus typed questions (choice, score, yes/no) and return typed answers with probabilities. Vendors expose them through incompatible APIs and different confidence definitions. A Urim contract describes the decision once. The compiler targets each provider. A lockfile records the exact model, version, and per-model fitted thresholds, so a verdict can be reproduced.

> **Status: pre-alpha.** The protocol is a v0.1 spec draft ([`spec/SPEC.md`](spec/SPEC.md)). v0.0.1 of the packages ships one small, working command, `urim check`, which validates contracts and lockfiles. The compiler, `plan` and `apply` are not implemented yet.

## Names

| Name | What it is | Status |
|---|---|---|
| **Urim** | The contract language and compiler (`urim`) | pre-alpha; `urim check` works |
| **Thummim** | Eval and conformance suite | planned |
| **hoshen** | The lockfile format (`urim.lock`, top-level `hoshen: 1`) | specified in spec §6.2 |

## Install and use (v0.0.1)

```sh
npm install -g urim       # or: npx urim check <file>
pip install urim          # Python >= 3.10
cargo install urim
```

```sh
urim check spec/examples/urim.lock
# spec/examples/urim.lock: ok (lockfile, hoshen 1, urim 0.1)
urim check spec/examples/incident-triage.decision.yaml
# spec/examples/incident-triage.decision.yaml: ok (contract incident-triage@1.2.0, dctp 0.1)
```

`urim check` exits 0 when the file is valid, 1 with a message naming the file and the problem when it isn't, and 2 on a usage error. The three implementations (TypeScript, Python, Rust) produce identical output on the shared fixtures in [`fixtures/`](fixtures/README.md).

## Repository layout

```
spec/                 v0.1 spec draft, changelog, examples
fixtures/             shared conformance cases for `urim check`
packages/js           npm package `urim` (TypeScript, ESM)
packages/python       PyPI package `urim`
packages/rust         crates.io crate `urim`
scripts/              cross-language parity check (scripts/parity.sh)
PUBLISHING.md         exact publish/push commands (nothing published yet)
```

## A note on the name

The Urim and Thummim appear in Exodus 28:30, carried in the breastpiece (the *hoshen*) of the high priest. They carry religious significance in Jewish, Christian, and Latter-day Saint traditions. This project borrows only the idea of asking a question and receiving a verdict, and uses the names with respect. No religious claim or affiliation is intended.

## Prior art and credits

- **Decision Model Protocol (DMP) draft 0.1:** <https://decisionmodelprotocol.io/specification/0.1>. Urim's response rules follow it where they overlap.
- **jevcompat:** conformance testing for Jev-compatible servers.
- **sys1bench:** calibration benchmarks for decision models.
- **Buf `protoc-gen-jev`:** Protobuf code generation for Jev requests.
- **Jev Harness:** built by David Thomason on TypeSafe's Jev; the motivating reference application.

Jev is a product of TypeSafe. Other vendor and product names belong to their owners. Mentioning them implies no endorsement.

## Links

- Homepage: <https://urim.sh>
- Repository: <https://github.com/no-complect/urim>

## License

Apache-2.0. See [LICENSE](LICENSE). Copyright 2026 David Thomason.
