# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- Review and merge the PR for chunk 006 (branch `feat/006-skeleton-and-load`). Not merged. It has been checked twice by qa-peer; the Handoff lists what was fixed and three known gaps left alone.
- One-column tables: is an empty line at the end of a file a blank line to ignore (as now) or an empty value to keep? One line. No dataset on hand has one column.
- After 006 is merged: run `python -m data_prepper selftest` on the remote desktop and report the output. This is the first run on Python 3.13 and SQLite 3.45.3.
- Free disk on the remote desktop. From the folder you would work in, type `python -c "import shutil; print(round(shutil.disk_usage('.').free/1e9), 'GB free')"` and report the number only. Not blocking 006. HCRIS FY2023 alone made a 2.0 GB `work.db`.

## In progress

- [006](chunks/006-skeleton-and-load.md): built, PR open. Checked by qa-peer on 2026-11-16: all "Done when" boxes hold, five bugs found on other inputs. Four are fixed on the branch and the fifth (`_file` bare names) stays by Lauren's answer. A second qa-peer check passed the fixes and found three new problems, also fixed and covered by tests. HCRIS has quoting off. Pick up at: Lauren's review of the PR.

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
