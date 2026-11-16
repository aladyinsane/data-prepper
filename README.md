# data-prepper

A small Python package, plus per-dataset config, for the stages Lauren keeps rebuilding: load, clean, model, merge supplemental data, and summarize.

`C:\dev\daita` is reference material for this project, not its starting point.

## Who it's for

Lauren, for her own projects. Each project imports the package and supplies its own config and rules. Built at home on public data only. See `PROBLEM.md`.

## What done means

From the "Done when" list in `PROBLEM.md`, which is the source of truth:

- HCRIS runs through all five stages from one command.
- NPPES, a differently shaped dataset, runs through by adding only config and rule files, with no changes to shared code.
- Every stage writes its row counts and check results.
- It runs on the locked-down remote desktop with only what is installed there.
- A file too big to fit in memory runs through without failing.

## Constraints

It has to run on Lauren's laptop and on a locked-down remote desktop, and it has to handle very large files. See "Constraints" in `PROBLEM.md` for the details.

## Key decisions

From `PROBLEM.md` ("What the constraints mean for the design" and "Out of scope"):

- The core uses the standard library only. pandas and numpy are optional extras.
- It installs by copying a folder. No pip install on the remote desktop.
- Config is JSON or plain Python, not YAML.
- Large files are processed in pieces, never read whole into memory.
- daita is parked as read-only reference. This repo is the one home for this work.
- SQLite, through the standard library, is the engine. Config is one JSON file per dataset plus `.sql` rule files. See `docs/adr/0001-package-design.md`.

Where things stand is in `STATUS.md`.
