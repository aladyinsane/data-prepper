# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- Review the PRs for chunks 003 and 002 (CCN change research). One question in chunk 003's handoff: do the Mt. Graham, Sevier County, and Mena examples look like the cases you hit at work?
- OK to download one public Provider of Services file (outside the repo) to test whether it links old and new CCNs? Yes or no. See the end of `docs/research/ccn-change-sources.md`.
- Review and merge the PR for ADR-0001 (Accepted in chat, 2026-11-15).
- Review and merge the PR that adds chunk files 006 to 008. They have not been checked by a fresh agent.
- Free disk on the remote desktop. From the folder you would work in, type `python -c "import shutil; print(round(shutil.disk_usage('.').free/1e9), 'GB free')"` and report the number only. Not blocking the first build chunks.

## In progress

(none)

## Ready

- [001](chunks/001-current-process.md): describe the current HCRIS refresh. Lauren's call at triage, 2026-11-14: this is the next chunk.
- [006](chunks/006-skeleton-and-load.md): package skeleton and the load stage. Next build chunk. A cheaper model is fine.
- After 006 is built: run the first formal qa-peer trial on it, see C:\dev\dev-team\STATUS.md. Then Lauren runs `python -m data_prepper selftest` on the remote desktop.
- [007](chunks/007-clean-stage.md): the clean stage. After 006 is merged.
- [008](chunks/008-model-stage.md): the model stage. After 007 is merged.
- Not written as chunks yet: merge, summarize, NPPES by config only, and a large-file trial on the remote desktop.
- If Lauren says yes: test Provider of Services against three known CCN pairs (steps at the end of `docs/research/ccn-change-sources.md`). Not written as a chunk file yet.

## Done

(cleared at triage)
