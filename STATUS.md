# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- [005](chunks/005-adr-package-design.md): sign off on `docs/adr/0001-package-design.md` (Proposed). Five one-line questions at its end: SQLite as the engine, JSON plus `.sql` rules, Excel saved as CSV for version 1, free disk on the remote desktop, and whether "snapshot" can mean hash plus raw table with no file copy.

## In progress

(none)

## Ready

- [001](chunks/001-current-process.md): describe the current HCRIS refresh. Lauren's call at triage, 2026-11-14: this is the next chunk.
- After the ADR is accepted: write chunk files for the first three build chunks it lists (skeleton and load, clean, model).
- After the first chunk is built, run the qa-peer trial, see C:\dev\dev-team\STATUS.md.
- Held until the Model stage needs HCRIS rules (HCRIS test case work, see `docs/test-cases/hcris-provider-identity.md`):
  - [002](chunks/002-ccn-change-sources.md): find public sources that link old and new CCNs.
  - [003](chunks/003-ccn-changes-in-hcris.md): find how CCN changes show up across HCRIS years.

## Done

(cleared at triage)
