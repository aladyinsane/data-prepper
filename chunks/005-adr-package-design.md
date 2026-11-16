# 005: ADR for the package design

- **Status:** Done (2026-11-15)
- **Who:** agent
- **Goal:** decide how the package is built so it runs in both places and handles large files.
- **Inputs:** `PROBLEM.md`, the answers in chunk 004, `C:\dev\_templates\ADR_TEMPLATE.md`. `C:\dev\daita` and `C:\dev\_templates\data-workflow.md` are read-only reference for ideas already tried.
- **Output:** `docs/adr/0001-package-design.md`, status Proposed.
- **Done when:**
  - [x] It picks the engine for big joins and summaries (streaming Python, sqlite3, or SAS for the heavy step), with real pros and cons for each.
  - [x] It picks the config format and shows one small example config for a made-up dataset.
  - [x] It names what each of the five stages takes in and writes out.
  - [x] Every dependency it uses is confirmed available in chunk 004's answers.
  - [x] It lists the first three build chunks.
- **Out of scope:** writing package code. Stops for Lauren's sign-off.

## Handoff

**2026-11-15 (agent):**

- Wrote `docs/adr/0001-package-design.md`, status Proposed. It picks SQLite (standard library) as the engine and JSON plus `.sql` rule files for config, names each stage's inputs and outputs, lists dependencies against chunk 004, and lists the first three build chunks.
- Backed by one benchmark on public HCRIS FY2023 (19.6 M rows), run on the laptop only. Numbers are in the ADR. The benchmark script was a throwaway and is not in the repo.
- Checked by `qa-peer` in a fresh context on 2026-11-15: all five "Done when" items pass, row counts and arithmetic re-derived and matching, verdict pass with fixes. Its fixes are applied (untested claims labelled, pandas and pytest statements corrected, date checking described, snapshot question added). The fixes themselves have not been re-checked. Agent QA only; Lauren's review is still needed.
- Judgment calls made: "snapshot" means hash plus untouched raw table, not a file copy; tests use `unittest`; Excel is not read in version 1.
- Lauren signed off in chat on 2026-11-15: yes to SQLite, JSON plus `.sql` rules, Excel as CSV for version 1, and the snapshot reading. Free disk on the remote desktop is still unknown; that item is in `STATUS.md`.
- Pick up: chunk files 006 to 008.
