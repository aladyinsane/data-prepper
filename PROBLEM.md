# Problem

Approved by Lauren on 2026-11-13, including every line Claude had proposed. Changes need her OK.

## Problem

For every new dataset or refresh, I rebuild the same stages by hand. I want a generalized system for:

1. **Loading** data.
2. **Cleaning** it: "technical" checks and transformations.
3. **Modeling** it: "semantic" checks and transformations.
4. **Merging** on supplemental data.
5. **Generating summaries.**

## Form

A small Python package plus per-dataset config. Each project imports the package and supplies its own config and rules.

## What's shared and what each dataset supplies

| Stage | Shared code does | Each dataset supplies |
|---|---|---|
| Load | Snapshot, hash, row counts | Source location and file format |
| Clean (technical) | Types, nulls, duplicates, key checks | Column types and keys |
| Model (semantic) | Applies business rules and checks them | The rules and definitions |
| Merge | Joins, match rates, fan-out checks | Which supplemental data, join keys |
| Summarize | Standard profiles and totals | Which groupings matter |

## Done when

- [ ] HCRIS runs through all five stages from one command.
- [ ] NPPES, a differently shaped dataset, runs through by adding only config and rule files, with no changes to shared code.
- [ ] Every stage writes its row counts and check results.
- [ ] It runs on the locked-down remote desktop with only what is installed there.
- [ ] A file too big to fit in memory runs through without failing.

## Constraints

- **Two places it has to run.** My laptop, where I can run Python locally. And a remote desktop that is very locked down: it has SAS, and Python 3.13 and SQLite 3.45, with numpy, pandas, pyodbc and their dependencies (no openpyxl), otherwise standard library only. 64 GB RAM.
- **Some datasets are very large.** Usually hundreds of thousands to several million rows; sometimes tens of millions of rows with hundreds of columns.
- **Formats.** Usually CSV and other delimited text files. Excel files, usually for supplemental data. SAS datasets and SQL Server tables are possible later.
- I'm also comfortable with PowerShell, cmd, node, and git bash.
- Built at home on public data only. No work or client data, names, or results in this repo.

## What the constraints mean for the design

- The core uses the standard library only. pandas and numpy are optional extras, never required.
- It installs by copying a folder. No pip install on the remote desktop.
- Config is JSON or plain Python. YAML needs a library that isn't there.
- Large files are processed in pieces, never read whole into memory.
- The engine for big joins and summaries is the main design question for the ADR. Candidates: streaming Python, the standard library's sqlite3, or handing the heavy step to SAS.

## Out of scope

- Analyses and methodology choices.
- A data lake or catalog (that was daita). daita is parked as read-only reference (2026-11-13); this repo is the one home for this work.
- Any UI.
- Generating SAS code from the config, unless the ADR shows the Python route can't handle the large files.

## Open questions

(none)
