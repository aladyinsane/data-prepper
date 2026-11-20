# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- Review and merge PR #10 for chunk 006 (branch `feat/006-skeleton-and-load`). Not merged. The third qa-peer review's findings are fixed and rechecked; the Handoff has the details.
- After 006 is merged: clone the repo on the remote desktop (it is public now) and run `python -m data_prepper selftest`, then report the output. This is the first run on Python 3.13 and SQLite 3.45.3.
- Confirm one line: in a one-column table, a blank line in the middle of a file is also loaded as an empty value, the same as one at the end (my call, built that way).

## In progress

- [006](chunks/006-skeleton-and-load.md): built, PR #10 open. Three qa-peer reviews, all "Done when" boxes hold. The third review's two must-fix bugs and smaller items are fixed on the branch (2026-11-20), with Lauren's answers on BOMs and one-column tables built in. Pick up at: Lauren's review of the PR.

## Ready

- [007](chunks/007-clean-stage.md): the clean stage. After 006 is merged.
- [008](chunks/008-model-stage.md): the model stage. After 007 is merged.
- [009](chunks/009-merge-stage.md): the merge stage. After 008 is merged.
- [010](chunks/010-summarize-stage.md): the summarize stage. After 009 is merged. Finishes "HCRIS runs through all five stages from one command".
- [011](chunks/011-nppes-by-config.md): NPPES by config only. After 010 is merged. Needs Lauren to download the public NPPES file first.
- [012](chunks/012-remote-desktop-trial.md): trial on the remote desktop. Lauren's, after 010 is merged. The remote desktop has 203 GB free (Lauren, 2026-11-20); HCRIS FY2023 alone makes a 2.0 GB `work.db`. The repo is public, so it can be cloned there.
- Load gaps left from 006 (a later chunk; no chunk file yet). Lauren said on 2026-11-20 these can wait: a stray quote on the last line of a file with no final line break still passes; the parse-error line can be far below the quote that caused it; an exit 2 after the run folder is made leaves a `work.db` with no report; "at byte N" in the bad-encoding message is not a file offset; an empty file with a header reports "file has None"; `csv.field_size_limit` is set at import for the whole process. Details in the [006 Handoff](chunks/006-skeleton-and-load.md).

## Done

- [005](chunks/005-adr-package-design.md): ADR-0001 accepted and merged.
- Chunk files 006 to 012 written and merged.
- Provider identifier work (old chunks 001 to 003) moved to `C:\dev\provider-changes`.
