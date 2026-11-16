# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- Review and merge the PR for ADR-0001 (Accepted in chat, 2026-11-15).
- Free disk on the remote desktop. From the folder you would work in, type `python -c "import shutil; print(round(shutil.disk_usage('.').free/1e9), 'GB free')"` and report the number only. Not blocking the first build chunks.

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
