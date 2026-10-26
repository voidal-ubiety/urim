# 0003. Contributions are signed off under the DCO 1.1 (D-32)

- **Status:** Accepted, 2026-10-26.
- **Decided by:** David (t52u). Spec decision D-32 (`drafts/DECISIONS.md`).

## Decision

Every commit carries a `Signed-off-by: Name <email>` trailer that matches its author. The trailer certifies the [Developer Certificate of Origin 1.1](../legal/DCO-1.1.txt). Contributions are licensed under Apache-2.0 §5 (inbound = outbound). There is no CLA.

Only a person signs off. A commit written by an agent is reviewed by a human, who adds the sign-off (`git commit -s --amend`, or `git rebase --signoff <base>` for a series). An agent never adds `Signed-off-by` for anyone.

## How the repo enforces it

- `CONTRIBUTING.md`, "Sign-off": the DCO text verbatim, `git commit -s`, and the agent rule.
- `scripts/check-dco [REV-RANGE]`: every non-merge commit needs a sign-off matching its author. It runs in `scripts/verify.sh --release` and in the `dco` job of `.github/workflows/ci.yml`. It is not in the default `verify.sh`.

## Consequences

- The commits from before D-32 have no sign-off and use the placeholder author email, so `check-dco` and the CI `dco` job fail until David's one-time history rewrite. That rewrite is described once, in release engineering's RELEASE-RUNBOOK §3a; this repo does not keep a second copy. `git filter-repo` has no `--signoff` option; §3a adds the trailer in the same pass, with a `--message-callback`.
- Agent-written commits (including the ones that added this ADR) fail `check-dco` until David reviews and signs them off.
- The DCO records the contributor's certification and moves responsibility to them. It doesn't stop employer-owned code from being submitted (spec repo `security/LEGAL-NOTES.md` §11).
