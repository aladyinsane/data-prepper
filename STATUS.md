# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- [004](chunks/004-remote-desktop-environment.md): report what the remote desktop can run: Python and SQLite versions, installed libraries (including openpyxl for Excel), whether a copied folder of .py files imports, memory. Dataset sizes and formats are already answered.
- [001](chunks/001-current-process.md): describe the current HCRIS refresh. Lower priority now; it feeds the HCRIS test case.

## In progress

(none)

## Ready

- [005](chunks/005-adr-package-design.md): ADR for the package design. Can start once 004 is answered.
- After the first chunk is built: run the `qa-peer` agent (`.claude/agents/qa-peer.md`) on it in a fresh session. First trial of that agent.

## Parked

HCRIS test case work, picked up when the Model stage needs HCRIS rules. See `docs/test-cases/hcris-provider-identity.md`.

- [002](chunks/002-ccn-change-sources.md): find public sources that link old and new CCNs.
- [003](chunks/003-ccn-changes-in-hcris.md): find how CCN changes show up across HCRIS years.

## Done

- `PROBLEM.md` approved by Lauren, 2026-11-13. NPPES is the second test case.
- daita parked as read-only reference, 2026-11-13. This repo is the one home for this work.
