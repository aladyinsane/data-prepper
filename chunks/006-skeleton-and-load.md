# 006: Package skeleton and the load stage

- **Status:** Ready
- **Who:** agent (a cheaper model is fine; the design is already decided)
- **Goal:** one command loads a dataset's source files into a working SQLite database and writes a load report.
- **Inputs:**
  - `PROBLEM.md` and `docs/adr/0001-package-design.md`. The ADR is the design. Don't redesign it; if something in it can't work, stop and say so in the Handoff.
  - Public HCRIS FY2023, read-only: `C:\dev\daita\data\bronze\cms-hcris-hospital-2552-10\files\20260928T081652Z_fy2023\HOSP10FY2023.ZIP`. Column names and order come from the CMS documentation zip in the `..._documentation` folder beside it. Confirm them there; don't guess.
- **Output:**
  - `data_prepper/` (the package): `__main__.py`, `cli.py`, `config.py`, `run.py`, `load.py`, `selftest.py`.
  - `datasets/hcris/dataset.json` with the `tables` section for RPT, NMRC, and ALPHA. Other sections come in later chunks.
  - `tests/` using `unittest`, plus `tests/large_file_check.py`.
  - `runs/` added to `.gitignore`.
  - `README.md`: usage steps for what exists, only steps that were run.

## Rules for all build chunks

- Standard library only. No pandas, numpy, pytest, or anything installed with pip.
- Code must run on Python 3.13. The laptop has 3.14, so don't use anything added in 3.14.
- SQL must run on SQLite 3.45.3. The laptop has 3.50, so don't use anything added after 3.45.
- Never read a whole source file into memory. Stream it.
- No work or client data. Public or made-up data only.
- Don't change anything under `C:\dev\daita`.

## What to build

**Command line**

- `python -m data_prepper run <dataset folder> [--data-root <folder>] [--runs <folder>]`
- `python -m data_prepper selftest`
- `--data-root` is the folder that relative `source.path` values are resolved against. Default: the dataset folder. `--runs` defaults to `runs/` in the current folder.
- Exit codes: 0 success, 1 a check with severity error failed, 2 bad config or bad arguments.

**Config (`config.py`)**

- Reads `dataset.json` in the dataset folder. Shape as in the ADR example.
- `source` keys: `path` (may contain `*`; several matching files load into the same table), `member` (optional; a name pattern inside a zip when `path` is a .zip), `delimiter`, `header` (true or false), `encoding`.
- `columns` is in file order. With `header: false`, names come from the config. With `header: true`, the header row must match the config's column names in the same order, or the run stops with an error that shows both lists.
- A `"note"` key is allowed anywhere and ignored.
- A bad config (missing key, unknown key, wrong type, bad JSON) prints one line naming the file and the key, then exits with code 2. No traceback.

**Run folder (`run.py`)**

- `<runs>/<dataset>/<run id>/` holding `work.db`, `reports/`, `out/`. Run id is the UTC start time as `YYYYMMDDTHHMMSSZ`.
- `work.db` is opened with `journal_mode=OFF` and `synchronous=OFF`.
- One function writes a stage report as JSON to `reports/<two-digit number>-<stage>.json`. Every stage will use it.

**Load (`load.py`)**

- Creates `raw_<table>`: a `_row` integer column (the line number in its file, counting from 1) and a `_file` text column, then every config column as TEXT. Values go in exactly as read. No trimming, no type changes.
- Reads with `csv.reader`. For a zip, stream the member with `zipfile` and `io.TextIOWrapper`. Insert with `executemany` in batches of 50,000.
- A row with the wrong number of fields is not loaded. It goes to `badrows_<table>` (`_file`, `_row`, field count, the row joined back as text).
- Hash each source file as it sits on disk (the zip itself, when zipped) with SHA-256, read in 1 MB blocks.
- Report `01-load.json`:

```json
{
  "stage": "load", "dataset": "hcris", "run_id": "20261115T010203Z",
  "started": "...", "finished": "...",
  "tables": {
    "nmrc": {
      "files": [{"file": "HOSP10FY2023.ZIP", "member": "HOSP10_2023_nmrc.csv", "bytes": 0, "sha256": "..."}],
      "rows_read": 0, "rows_loaded": 0, "rows_bad": 0
    }
  },
  "checks": [{"name": "nmrc: no rows with the wrong number of fields", "severity": "error", "status": "pass", "count": 0}]
}
```

- If any check with severity error fails, write the report, then exit with code 1.

**Selftest (`selftest.py`)**

- Prints the Python and SQLite versions.
- Writes a small made-up dataset to a temp folder (two tables, a few hundred rows, one of them inside a zip, a few rows with the wrong field count), runs every stage that exists, and compares the report's counts to the known answers.
- Prints PASS or FAIL per stage and exits 0 or 1. Later chunks add their stage to it.

**Large-file check (`tests/large_file_check.py`)**

- Not part of the normal test run. It generates a made-up delimited file of about 200 MB and one of about 1 GB in a temp folder, loads each in a fresh process, and prints peak memory for each. Peak memory on Windows comes from `GetProcessMemoryInfo` through `ctypes`.
- Passes when the 1 GB peak is within 50 MB of the 200 MB peak. Deletes its files afterwards.

- **Done when:**
  - [ ] `python -m data_prepper run datasets/hcris --data-root <the fy2023 folder>` finishes with exit code 0 and writes `reports/01-load.json`.
  - [ ] In that report, `rows_loaded` for NMRC is 19,574,053 and for RPT is 6,109, and each equals a line count of the file made a different way (not through `load.py`).
  - [ ] The reported SHA-256 of the zip equals the one from `certutil -hashfile <zip> SHA256`.
  - [ ] `python -m unittest discover tests` passes. Tests cover: a good config, each kind of bad config (exit code 2, one-line message), header mismatch, a file inside a zip, several files matching one pattern, rows with the wrong field count, and rows read = rows loaded + rows bad.
  - [ ] `python tests/large_file_check.py` passes, and both peak numbers are written in the Handoff.
  - [ ] `python -m data_prepper selftest` prints PASS for load and exits 0.
  - [ ] No import in `data_prepper/` from outside the standard library (show the grep).
- **Out of scope:** the clean, model, merge, and summarize stages. Reading Excel, SAS datasets, or SQL Server. Any speed tuning past what is written here. Changing the ADR.

## Handoff

(not started)

After this chunk is checked, two things follow, both listed in `STATUS.md`: Lauren runs `selftest` on the remote desktop, and the first formal `qa-peer` trial runs on this chunk.
