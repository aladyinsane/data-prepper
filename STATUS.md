# Status

Current state only. Git history records what happened.

## Waiting on Lauren

- Review and merge the PR for ADR-0001 (Accepted in chat, 2026-11-15).
- Review and merge the PR that adds chunk files 006 to 008. They have not been checked by a fresh agent.
- Free disk on the remote desktop. From the folder you would work in, type `python -c "import shutil; print(round(shutil.disk_usage('.').free/1e9), 'GB free')"` and report the number only. Not blocking the first build chunks.

## In progress

(none)

## Ready

- [006](chunks/006-skeleton-and-load.md): package skeleton and the load stage. Next build chunk. A cheaper model is fine.
- After 006 is built: run the first formal qa-peer trial on it, see C:\dev\dev-team\STATUS.md. Then Lauren runs `python -m data_prepper selftest` on the remote desktop.
- [007](chunks/007-clean-stage.md): the clean stage. After 006 is merged.
- [008](chunks/008-model-stage.md): the model stage. After 007 is merged.
- [009](chunks/009-merge-stage.md): the merge stage. After 008 is merged.
- [010](chunks/010-summarize-stage.md): the summarize stage. After 009 is merged. Finishes "HCRIS runs through all five stages from one command".
- [011](chunks/011-nppes-by-config.md): NPPES by config only. After 010 is merged. Needs Lauren to download the public NPPES file first.
- [012](chunks/012-remote-desktop-trial.md): trial on the remote desktop. Lauren's, after 010 is merged.

## Done

(cleared at triage)
