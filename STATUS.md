# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- Chunk 006 questions from the qa-peer check (details in the chunk's Handoff). One line each:
  1. Fix the five bugs on the 006 branch before merge, or merge 006 as is and fix them in a new chunk?
  2. Stray quote: fail the load when lines in the file and records read differ, or turn quoting off per dataset in config, or both?
  3. Blank line at the end of a file: bad row (exit 1, as now) or ignored?
  4. `_file`: path relative to the data root, or keep the bare file name?
  5. Keep the extra "rows read = rows loaded + rows bad" check in the report, or only the one check the brief shows?
- Review and merge the PR for chunk 006 (branch `feat/006-skeleton-and-load`). Not merged.
- After 006 is merged: run `python -m data_prepper selftest` on the remote desktop and report the output. This is the first run on Python 3.13 and SQLite 3.45.3.
- Free disk on the remote desktop. From the folder you would work in, type `python -c "import shutil; print(round(shutil.disk_usage('.').free/1e9), 'GB free')"` and report the number only. Not blocking 006. HCRIS FY2023 alone made a 2.0 GB `work.db`.

## In progress

- [006](chunks/006-skeleton-and-load.md): built, PR open. All "Done when" boxes met, with evidence in its Handoff. Checked by qa-peer on 2026-11-16: pass with fixes. The HCRIS numbers hold. Five bugs found on other inputs, not fixed yet. Pick up at: Lauren's answers above, then the fixes.

## Ready

- [001](chunks/001-current-process.md): describe the current HCRIS refresh. Lauren's call at triage, 2026-11-14: this is the next chunk.
- [007](chunks/007-clean-stage.md): the clean stage. After 006 is merged.
- [008](chunks/008-model-stage.md): the model stage. After 007 is merged.
- Not written as chunks yet: merge, summarize, NPPES by config only, and a large-file trial on the remote desktop.
- Held until the Model stage needs HCRIS rules (HCRIS test case work, see `docs/test-cases/hcris-provider-identity.md`):
  - [002](chunks/002-ccn-change-sources.md): find public sources that link old and new CCNs.
  - [003](chunks/003-ccn-changes-in-hcris.md): find how CCN changes show up across HCRIS years.

## Done

- [005](chunks/005-adr-package-design.md): ADR-0001 accepted and merged.
- Chunk files 006 to 008 written and merged.
