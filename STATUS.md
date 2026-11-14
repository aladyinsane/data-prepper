# Status

Current state only. Git history records what happened.

## Waiting on Lauren

(none)

## In progress

(none)

## Ready

- [001](chunks/001-current-process.md): describe the current HCRIS refresh. Lauren's call at triage, 2026-11-14: this is the next chunk.
- [005](chunks/005-adr-package-design.md): ADR for the package design.
- After the first chunk is built: run the `qa-peer` agent (installed at `~/.claude/agents/qa-peer.md`) on it in a fresh session. First trial of that agent.
- README check: README.md has what it is and a pointer to PROBLEM.md. It is missing who it is for, what done means, constraints, and key decisions (these currently live in PROBLEM.md, and the daita-as-reference decision is only a one-line note). Add them, or point to PROBLEM.md for each. Its "Status: Framing" line is also state that belongs here.
- Held until the Model stage needs HCRIS rules (HCRIS test case work, see `docs/test-cases/hcris-provider-identity.md`):
  - [002](chunks/002-ccn-change-sources.md): find public sources that link old and new CCNs.
  - [003](chunks/003-ccn-changes-in-hcris.md): find how CCN changes show up across HCRIS years.

## Done

- [004](chunks/004-remote-desktop-environment.md): remote desktop answers recorded, 2026-11-13. Python 3.13.2, SQLite 3.45.3, numpy/pandas/pyodbc (no openpyxl), copied-folder imports work, 64 GB RAM.
- `PROBLEM.md` approved by Lauren, 2026-11-13. NPPES is the second test case.
- daita parked as read-only reference, 2026-11-13. This repo is the one home for this work.
