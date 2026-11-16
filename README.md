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

## Usage

Everything below was run on the laptop (Python 3.14.6, SQLite 3.50.4). It has not been run on the remote desktop yet.

Only the load stage exists so far. Run these from the repo folder:

```
python -m data_prepper run <dataset folder> [--data-root <folder>] [--runs <folder>]
python -m data_prepper selftest
python -m unittest discover tests
python tests/large_file_check.py
```

- `<dataset folder>` holds a `dataset.json`. `datasets/hcris` is the HCRIS one.
- `--data-root` is the folder relative `source.path` values are resolved against. Default: the dataset folder.
- `--runs` is where run folders go. Default: `runs/` in the current folder. Each run makes `runs/<dataset>/<run id>/` with `work.db`, `reports/`, and `out/`.
- Exit codes: 0 success, 1 a check with severity error failed (the report is written first), 2 bad config or bad arguments.
- The load report is `reports/01-load.json`: files with size and SHA-256, rows read, rows loaded, rows with the wrong number of fields. Those rows go to `badrows_<table>` in `work.db`.
- `selftest` builds a small made-up dataset in a temp folder and checks the load stage against known answers. It needs no data files.
- `tests/large_file_check.py` is not part of the normal test run. It makes 200 MB and 1 GB made-up files, so it needs Windows, a few minutes, and about 1.5 GB of temp disk.

Example, HCRIS FY2023 from the read-only daita copy:

```
python -m data_prepper run datasets/hcris --data-root C:\dev\daita\data\bronze\cms-hcris-hospital-2552-10\files\20260928T081652Z_fy2023
```

That took about 30 seconds and made a 2.0 GB `work.db`.

Python 3.13 and SQLite 3.45.3 (the remote desktop) were not available here, so neither was tested. The unit tests and selftest also pass on Python 3.12.15, so nothing newer than 3.12 is in use.
