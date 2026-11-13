# 005: ADR for the package design

- **Status:** Ready once 004 is answered (`PROBLEM.md` approved 2026-11-13)
- **Who:** agent
- **Goal:** decide how the package is built so it runs in both places and handles large files.
- **Inputs:** `PROBLEM.md`, the answers in chunk 004, `C:\dev\_templates\ADR_TEMPLATE.md`. `C:\dev\daita` and `C:\dev\_templates\data-workflow.md` are read-only reference for ideas already tried.
- **Output:** `docs/adr/0001-package-design.md`, status Proposed.
- **Done when:**
  - [ ] It picks the engine for big joins and summaries (streaming Python, sqlite3, or SAS for the heavy step), with real pros and cons for each.
  - [ ] It picks the config format and shows one small example config for a made-up dataset.
  - [ ] It names what each of the five stages takes in and writes out.
  - [ ] Every dependency it uses is confirmed available in chunk 004's answers.
  - [ ] It lists the first three build chunks.
- **Out of scope:** writing package code. Stops for Lauren's sign-off.

## Handoff

(not started)
