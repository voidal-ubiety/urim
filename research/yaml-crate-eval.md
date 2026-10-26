# YAML parsing in the Rust port: crate evaluation and the Urim YAML profile

Status: **adopted**. The Urim YAML profile (CONTRACT.md §3, C-080..C-090) is enforced in all three
ports, and the Rust port now parses with **saphyr-parser events only**. serde_norway and its
libyaml transpilation are gone. This file covers (a) to (d) as asked, then the swap criteria and
results.

All numbers were measured on 2026-10-26 on the box (Linux x86_64, rustc stable, release builds).
"old" is the tree before the swap (saphyr-parser events for the profile checks, then serde_norway
for values). "new" is the swap commit.

## (a) YAML features actually used

The scan parsed every file with PyYAML's event API and counted events. Comments, `?`, `%`, tabs,
CRLF and BOMs were counted from the text. Script: see "Reproducing" below.

| feature | spec examples + `urim.lock` + SPEC.md blocks (7 docs) | valid fixtures (32) |
|---|---|---|
| block mappings | 54 (all 7) | 35 (31) |
| block sequences | 4 (2) | 0 |
| flow mappings, e.g. `compiler: { ... }` | 38 (6) | 16 (9) |
| flow sequences | 10 (5) | 64 (2) |
| plain scalars | 525 | 175 |
| double-quoted | 41 (6) | 23 (19) |
| single-quoted | 0 | 2 (2) |
| folded `>` | 1 (`incident-triage.decision.yaml` `description:`) | 0 |
| literal `\|` | 0 | 0 |
| multi-line plain/quoted scalars | 0 | 0 |
| comments | 53 (7) | 13 (13) |
| explicit `?` keys | 0 | 2 (2) |
| `---` document start | 0 | 1 |
| `%YAML` directive | 0 | 1 (`yaml-1.1-directive-keeps-core-schema.lock`) |
| BOM | 0 | 1 |
| anchors / aliases / tags / merge keys `<<` / multi-doc / `...` / CRLF / tabs | **0** | **0** |

The historical examples in `decision-contract-spec/examples/` (pre-hoshen and v0.1.0 lockfiles and
providers) add nothing beyond this list.

So the real documents need block and flow collections, the three flow-scalar styles plus folded
`>`, and comments. Nothing legitimate uses anchors, aliases, tags, merge keys or multiple
documents. Those are exactly the constructs behind billion-laughs, deserialization gadgets and
"last key wins" smuggling.

## (b) The Urim YAML profile

The profile is a strict subset: the YAML 1.2 core schema, with no anchors or aliases, no tags, a
single document, and size and depth caps. Each port enforces it by *rejecting* disallowed
constructs before any value is built, with the same message and exit code everywhere.

- **Rules:** the C-080..C-090 entries in CONTRACT.md cover the size cap, depth cap, character set,
  stream-order well-formedness, anchors and aliases, tags, merge keys, duplicate keys, the
  key/id character rules and output sanitizing.
- **Pipeline:** size → BOM/characters → well-formed (stream order) → profile events → values →
  schema. The precedence is defined and tested.
- **Results:** this resolved D-001..D-007 and D-010. Parity is 195 invocations × 3 ports,
  byte-identical.

Recommendation, **high confidence**: keep the profile as the contract. It removes every YAML
feature the documents do not use, and with it most of the cross-library disagreement.

## (c) saphyr-parser's low-level event parser instead of a DOM/serde layer

Rust already used saphyr-parser's events to check the profile. Building values from those same
events (`src/value.rs`, about 210 lines including the core-schema resolver) let us remove
serde_norway entirely.

Dependency tree (`cargo tree -e normal`, excluding `urim`). Lines are `*.rs` under `src/`.
`unsafe` counts are `grep -ow unsafe` hits, comments included, so they are an upper bound.

| | crates | runtime crates | third-party Rust lines | `unsafe` (all / runtime crates) |
|---|---|---|---|---|
| old | 17 | 12 | ~166,900 | 1,032 / 926 |
| **new** | **8** | **3** (saphyr-parser, arraydeque, thiserror) | **~73,000** | **178 / 72** |

The nine crates removed are serde_norway 0.9.42 (60 `unsafe`), unsafe-libyaml-norway 0.2.15 (240;
libyaml transpiled from C), indexmap, equivalent, hashbrown (495), itoa, ryu, serde and serde_core.

- **What is left:**
  - saphyr-parser has no `unsafe`.
  - arraydeque has 72, and it is the only runtime `unsafe`.
  - thiserror-impl/syn/quote/proc-macro2/unicode-ident are compile-time only (the `thiserror`
    proc-macro).
- **Build scripts still in the tree:** thiserror, proc-macro2, quote. serde and serde_core also had
  them.
- **Our code:** Rust `src/` went from 700 to 911 lines. That is +214 for `value.rs`, −4 in
  `profile.rs`, and small edits in `check.rs`/`lib.rs`.
- **Cargo.lock:** −48 lines.

Recommendation, **high confidence**: use the event parser only, as adopted. A follow-up could look
at dropping thiserror (a hand-written `Display` is about 30 lines), which would remove the last
proc-macro and all three build scripts. It is not done here because it was out of scope.

## (d) A hand-rolled subset parser (estimate only; nothing implemented)

The subset from (a) would need block/flow maps and seqs, plain/single/double-quoted and folded
scalars with their escapes and line folding, comments, indentation rules and error positions.

| | hand-rolled subset parser | saphyr-parser events + profile (adopted) |
|---|---|---|
| size | ~1,500–2,500 lines per language for a correct scanner, parser and escapes; ×3 if every port gets one | 0 parser lines; ~210 (value building) in Rust |
| effort | weeks, plus a fuzzing campaign per port | done |
| `unsafe` / deps | none | 72 `unsafe` in arraydeque |
| **parity risk vs JS `yaml` and PyYAML** | **high** | low, and measured (below) |
| other risk | our parser disagreeing with the YAML tools users run (a reviewer's editor or linter reads a file one way and `urim check` another) | upstream changes, mitigated by exact pins and the differential corpus |

The deciding evidence is that three mature parsers disagreed on 6 distinct issues in a 592-case
differential corpus of plain scalars and document markers alone (B-4, B-5, B-6, D-008, D-009,
D-013). A new parser would start with more, not fewer.

Recommendation, **high confidence**: do not hand-roll. Revisit only if saphyr-parser becomes
unmaintained. Even then, prefer another event-level crate, since the profile and `value.rs`
carry over unchanged.

## Swap criteria and results

> **Flag for the parent and David:** the original six acceptance criteria for the swap could not
> be recovered verbatim. The criteria below are my reconstruction. Please confirm or correct them.

| # | criterion (reconstructed) | result |
|---|---|---|
| 1 | All fixtures and byte-identical parity pass unchanged; no unintended change on the differential corpus | **Pass, with listed intended changes.** Fixtures and parity pass (195 × 3). 25 of 592 corpus cases changed in Rust: 12 are bugs B-5/B-6 (Rust now agrees with JS and Python) and 13 are empty implicit keys (D-013, a side swap). Also D-009 (2 fixtures): Rust now accepts `%YAML 1.3` and unknown directives, as JS and Python do. On the corpus, new Rust is never the lone outlier. A new `...`-before-document regression was caught and fixed before the commit. D-008 is unchanged. |
| 2 | 100% coverage is kept | **Pass.** Lines, regions, functions and branches are all 100% (`cargo +nightly llvm-cov --branch`). |
| 3 | Dependency tree equal or smaller; cargo-deny and cargo-audit clean | **Pass.** 17 → 8 crates; deny: advisories, bans, licenses and sources ok; audit: no findings. deny.toml now bans serde_yaml, serde_norway, unsafe-libyaml(-norway) and yaml-rust (one YAML parser only). |
| 4 | MSRV 1.85 builds | **Pass.** `cargo +1.85 build --locked`. |
| 5 | No size or performance regression beyond a bound (my bound: ≤10% time, ≤25% peak RSS) | **Pass.** Stripped binary 705,472 → 526,960 B (−25%). Median of 15 runs: 1 MB block map with 60k keys, 111 → 73 ms; 1 MB of flow sequences, 165 → 81 ms; small fixture, 0.99 → 0.73 ms. Peak RSS: 41.5 → 45.7 MB (+10%) on the 60k-key file, 58.6 → 47.4 MB on the flow file. |
| 6 | Maintenance and supply-chain health (public crates.io data, read-only), plus less `unsafe` | **Pass.** saphyr-parser: MIT OR Apache-2.0, declares MSRV 1.85, 21 releases since 2024-04, about 8.5M downloads. serde_norway's last release was 2024-12-21. Runtime `unsafe` fell from 926 to 72. |

**Pin note:** saphyr-parser released 0.3.0, 0.3.1 and 0.3.2 on 2026-10-25/26 (crates.io UTC
dates), the day before and the day of this evaluation. The port stays exactly pinned at **0.2.2**.
Do not bump until the Dependabot cooldown has passed and the differential corpus has been rerun on
the new version, because 0.3 is a semver-breaking line.

## Behavior changes in the swap (all listed in CONTRACT.md)

- **B-5:** `+0x1`, `-0o7` and `0b1` were integers in Rust only; now they are strings, as in the
  core schema. New fixtures under C-027.
- **B-6:** `1e400` was a string in Rust only; now it is a float (infinity). New fixtures under
  C-028.
- **D-009:** Rust now accepts `%YAML 1.3` and unknown directives, so all three ports agree. The
  item stays **open for David**.
- **D-013 (new, open for David):** empty implicit keys (`: 2`, `{: 1}`). JS and Rust now accept
  them; Python rejects them. Before the swap it was JS against Python and Rust.
- **Kept on purpose:** `...` before the first document is still `invalid YAML` in Rust (D-008 and
  a new C-022 fixture). saphyr-parser alone would accept it.

## Reproducing

- **Inventory:** a short PyYAML event scan over `spec/examples/**`, `spec/SPEC.md` yaml blocks and
  `fixtures/valid/*`. It counts `MappingStart`/`SequenceStart` by `flow_style`, scalar `style`,
  anchors, aliases, tags and explicit document markers.
- **Dependencies:** `cargo tree -e normal --prefix none | sort -u`. Lines and `unsafe` were
  counted over `~/.cargo/registry/src/*/<crate>/src`.
- **Differential:** 592 generated plain-scalar and document-marker cases, run through the JS dist,
  the Python package and old/new Rust drivers, then compared. Its golden form is the planned
  supply-chain canary (SECURITY.md).
