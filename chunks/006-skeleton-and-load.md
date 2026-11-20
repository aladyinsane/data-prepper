# 006: Package skeleton and the load stage

- **Status:** Built, PR open, checked three times by qa-peer, the third review's findings fixed on the branch and rechecked, waiting on Lauren's review
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
  - [x] `python -m data_prepper run datasets/hcris --data-root <the fy2023 folder>` finishes with exit code 0 and writes `reports/01-load.json`.
  - [x] In that report, `rows_loaded` for NMRC is 19,574,053 and for RPT is 6,109, and each equals a line count of the file made a different way (not through `load.py`).
  - [x] The reported SHA-256 of the zip equals the one from `certutil -hashfile <zip> SHA256`.
  - [x] `python -m unittest discover tests` passes. Tests cover: a good config, each kind of bad config (exit code 2, one-line message), header mismatch, a file inside a zip, several files matching one pattern, rows with the wrong field count, and rows read = rows loaded + rows bad.
  - [x] `python tests/large_file_check.py` passes, and both peak numbers are written in the Handoff.
  - [x] `python -m data_prepper selftest` prints PASS for load and exits 0.
  - [x] No import in `data_prepper/` from outside the standard library (show the grep).
- **Out of scope:** the clean, model, merge, and summarize stages. Reading Excel, SAS datasets, or SQL Server. Any speed tuning past what is written here. Changing the ADR.

## Handoff

Built on branch `feat/006-skeleton-and-load`. All seven "Done when" boxes are met. Nothing was loosened. The ADR was not changed and nothing in it blocked the build. Since then checked by fresh qa-peer agents several times; see the sections below.

Run on the laptop: Python 3.14.6, SQLite 3.50.4. Python 3.13 and SQLite 3.45.3 were not available, so they are untested. Tests and selftest also pass on Python 3.12.15 (SQLite 3.53.1), so nothing newer than 3.12 is used.

**Evidence, one per box**

1. HCRIS run. Command: `python -m data_prepper run datasets/hcris --data-root C:\dev\daita\data\bronze\cms-hcris-hospital-2552-10\files\20260928T081652Z_fy2023`. Exit code 0, about 30 s, wrote `reports/01-load.json`. `work.db` was 2.0 GB.
2. Rows loaded, against a line count made without `load.py` or `csv`. I extracted the zip with .NET `ZipFile` and counted two ways: `cmd find /c /v ""` and `tr -cd '\n' | wc -c`. Every file ends in a newline, so lines = rows (the files have no header).

   | Table | `rows_loaded` | `find /c /v ""` | `tr`/`wc` newlines |
   |---|---|---|---|
   | NMRC | 19,574,053 | 19,574,053 | 19,574,053 |
   | RPT | 6,109 | 6,109 | 6,109 |
   | ALPHA | 3,778,351 | 3,778,351 | 3,778,351 |

   `rows_bad` was 0 for all three.
3. SHA-256 of the zip. Report and `certutil -hashfile <zip> SHA256` both give `adf2ed822f8da05d9c73ecc23bf6dcf88faee052028ee3a978e9f6628235b42b`.
4. `python -m unittest discover tests`: 31 tests at the first build, OK (56 now; see the latest section below). They cover a good config, each kind of bad config (missing key, unknown key, wrong type, bad JSON, plus a repeated key and a missing file; exit 2 and one line on stderr each), header mismatch, a file inside a zip, several files matching one pattern, rows with the wrong field count, and rows read = rows loaded + rows bad (across several batches). They also cover the pragmas, `_row` for a quoted field that spans lines, tab delimiter and non-UTF-8 encoding, and selftest.
5. `python tests/large_file_check.py`: PASS.

   | File | Rows (loaded = written) | Peak memory |
   |---|---|---|
   | about 200 MB (208 MB) | 2,500,000 | 53.4 MB |
   | about 1 GB (1004 MB) | 12,000,000 | 54.1 MB |

   Difference 0.6 MB, limit 50. Peak is `PeakWorkingSetSize` from `GetProcessMemoryInfo`, read inside a fresh process for each file.
6. `python -m data_prepper selftest` prints `PASS load` and exits 0.
7. Imports in `data_prepper/`, from `grep -rnE "^\s*(import|from)\s" data_prepper`: argparse, codecs, contextlib, csv, dataclasses, datetime, fnmatch, glob, hashlib, io, json, pathlib, re, sqlite3, sys, tempfile, time, zipfile, and relative imports inside the package. All standard library.

**Column names.** From `HCRIS_TABLE_DESCRIPTIONS _AND_SQL.txt` in `hospital2010-documentation.zip`, in that file's order, and checked against the first rows of each FY2023 file (RPT has 18 fields per row, NMRC and ALPHA 5). I kept CMS's upper-case names.

**Judgment calls (change any you disagree with)**

- Column `type` and `format` in `datasets/hcris/dataset.json` follow the CMS table definitions (dates `%m/%d/%Y`). Nothing reads them until the clean chunk. Only RPT has a `key` (`RPT_REC_NUM`, which CMS documents as its primary key). NMRC and ALPHA have none, since no key is documented for them.
- The config accepts `model`, `merge`, and `summarize` as top-level keys and does not check them yet, so the ADR's example config loads. Any other unknown key is an error.
- The config requires `path`, `delimiter`, `header`, and `encoding` on every source. Table and column names must be letters, digits, underscore, starting with a letter, so they cannot clash with `_row` and `_file`.
- Exit 2 (no traceback, one line) also covers: a header that does not match the config (both lists shown), no file matching `source.path`, no zip member matching `source.member`, a file that is not valid in the stated encoding, and a field over 16 MB (a stray quote).
- `_file` is the file name, or `<zip name>:<member>` for a zip member. The ZIP is therefore stored on every row, which costs disk. `_row` is the line where the record starts.
- Beyond the one check the chunk lists, the report has a second error check per table, "rows read = rows loaded + rows bad", so the reconciliation shows in the report.
- The HCRIS config uses `HOSP10FY*.ZIP` with `HOSP10_*_nmrc.csv` and so on, so it works for any year's folder. Pointing `--data-root` at a folder with several years would load them all into one table, with `_file` telling them apart.
- The zip is hashed once per table that reads from it (three times for HCRIS, 136 MB each; not timed). Not worth changing yet.
- Run id collisions: if a second run starts in the same second, it waits until the next one.
- Added `.gitignore` with `__pycache__/` as well as `runs/`, plus `data_prepper/__init__.py`.

**qa-peer check, 2026-11-16 (fresh agent, not the builder)**

Verdict: pass with fixes. All seven boxes passed on its own runs (Python 3.14.6, SQLite 3.50.4). Row counts matched a newline count of the zip members (19,574,053 / 6,109 / 3,778,351), the hash matched `certutil`, and all 23,358,513 loaded rows matched their source lines. HCRIS column names and order match the CMS documentation. Not checked: Python 3.13, SQLite 3.45.3, Python 3.12, other fiscal years.

Bugs found. None is fixed yet, and none affects the HCRIS numbers (the FY2023 files have no quote characters). The first, second, and fourth were reproduced a second time in the main session.

1. `load.py:76`: a stray quote swallows the rows after it and the run still exits 0 with both checks passing. `a,b / 1,x / 2,"y / 3,z / 4,w` gives rows_read 2, rows_loaded 2, rows_bad 0. Nothing compares records read to lines in the file.
2. `load.py:37`: `glob` runs over the data root too, so a data root with `[` or `]` in its name finds no files.
3. `load.py:61` and `:147`: `_file` and the report's `file` are the bare file name, so `y1/in.csv` and `y2/in.csv` cannot be told apart.
4. `cli.py:29` catches only `ConfigError`. `"encoding": "base64"` or a `.zip` that is not a zip gives a traceback and exit 1, the code reserved for a failed check.
5. `load.py:125`: the parse-error line number counts records across all of a table's files, not lines in the file at fault.

Smaller: a UTF-8 BOM is not handled or hinted at; an exit 2 after the run folder is made leaves a `work.db` with no report; "at byte N" in the bad-encoding message is an offset in the decoder block, not the file; the comment at `load.py:141` says once per file but hashing is once per table; an empty file with a header reports "file has None"; `csv.field_size_limit` is set at import for the whole process.

Follows the brief, but worth knowing: `csv.reader` removes quoting, so `"1"` is stored as `1` and a bad row's `row_text` is the fields joined back, not the original line. A blank line, including one at the end of a file, is a bad row and makes the run exit 1.

**Fixes, 2026-11-16 (after Lauren's answers)**

Her answers: fix on this branch before merge; for stray quotes, both a check and a config switch; blank lines at the end of a file are ignored; `_file` stays the bare name; keep the extra check.

- Bug 1: new error check per table, "lines in the files = rows read" (lines come from `csv.reader.line_num`, so no second pass). New optional source key `"quoting": false` stores quote characters as text. The stray-quote example now exits 1 with count 2. Side effect: a quoted field that really spans lines also fails the check. Such a file cannot pass load as it stands.
- Bug 2: only `*` in `source.path` is a pattern now. `[` and `?` in the path, and anything in the data root, are literal.
- Bug 3: not changed, by her answer. Noted in the README.
- Bug 4: an encoding that is not a text encoding, and a `.zip` that is not a zip, each give one line and exit 2.
- Bug 5: the parse-error message gives the line in the file at fault.
- Blank lines at the end of a file are ignored. A blank line followed by a row is still a bad row.
- The wrong comment at `load.py` about hashing is fixed. The other smaller items above are not changed.

Evidence: `python -m unittest discover tests` runs 40 tests, OK (9 new, one per fix; the spanning-field test now expects exit 1). `selftest` prints `PASS load`. HCRIS FY2023 rerun: exit 0, NMRC 19,574,053, RPT 6,109, ALPHA 3,778,351, 0 bad rows, all nine checks pass. `tests/large_file_check.py` was not rerun after the fixes.

The HCRIS config sets `"quoting": false` on all three tables (Lauren's answer, 2026-11-16). None of the 18 files for FY2020 to FY2025 in the daita copy has a quote character. FY2023 rerun with it: exit 0, same counts, all nine checks pass. With quoting off, a quoted value with a comma inside would land in `badrows` instead of loading.

**Second qa-peer check, 2026-11-16 (of the fix commit `cec606f`, fresh agent)**

Verdict: pass with fixes. Every fix above held on its own runs, the large-file check passed (53.3 and 53.2 MB), and HCRIS matched again. It found three problems the fixes had brought in, now fixed:

- A stray quote on the last line of a file passed every check, because it swallows only the final line break. Now the lines check also fails when the last record has a value ending in a line break.
- Bad rows from blank lines were not written in batches of 50,000, and the list of blank lines at the end of a file grew with their number. Both are now flat in memory.
- Also fixed from its smaller items: `"encoding": "undefined"` and a zip member with a bad CRC give one line and exit 2.

Evidence after these: 44 unit tests OK (4 new), `selftest` prints `PASS load`, HCRIS FY2023 exit 0 with the same counts and nine passing checks, large-file check PASS (53.2 MB and 54.2 MB, difference 0.9). A third qa-peer review (below) then checked these changes.

Known and not fixed at that point: a stray quote on the last line of a file with no final line break; the parse-error line far below the stray quote; blank lines in one-column tables. The first two are still open (see "Known gaps" below). The third is settled below.

**Third qa-peer review, 2026-11-16 (PR #10 comment, of commit `be58e02`, fresh agent)**

Verdict: pass with fixes. All seven boxes passed on its own runs (HCRIS 31 s, exit 0; hash matched `certutil`; 44 tests; large-file 54.6 MB and 53.2 MB; selftest; standard-library imports). Row counts re-derived from the zip matched, and each table's content matched its source by hash. It caught 17 of 17 bugs it injected into a copy.

Must fix: (1) STATUS conflicted with main; (2) the check "rows read = rows loaded + rows bad" could not fail, because all three numbers were counters from the same loop; with the insert removed the report still passed; (3) a Deflate64 zip member, a `--runs` path that is a file, and a table with 2,100 columns each gave a traceback and exit 1. Smaller: a UTF-8 BOM ends up in the first value; this Handoff said "not yet checked" and "31 tests"; `"encoding": "idna"` was accepted; a dataset name ending in a line break gave a traceback; no test of `_row` across several files with `header: false`.

**Lauren's answers, 2026-11-20**

Fix both must-fix bugs before merge and fold in the smaller items. Strip a UTF-8 BOM by default. In a one-column table a blank line at the end of a file is an empty value to keep. The known gaps can wait if they are written down for later. The remote desktop has 203 GB free. The repo is now public, so the remote desktop can clone it.

**Fixes, 2026-11-20**

- Must fix 1 was already resolved by the merge of main (`04aed35`).
- Must fix 2: `rows_loaded` and `rows_bad` are now `count(*)` of `raw_<table>` and `badrows_<table>` after loading. `rows_read` is still the loop's count of records. New test drops every insert into `raw_` and expects exit 1 with that check failing (count 2).
- Must fix 3: each now gives one line on stderr and exit 2, with a test each. A zip member zipfile cannot read (Deflate64) is caught where the member is opened. A `--runs` path that cannot be made into a folder is caught where the run folder is made. A `CREATE TABLE` that SQLite turns down (too many columns) names the table and the column count. As a backstop, the command line also turns any other `OSError` or `sqlite3.Error` (disk full, no permission) into one line and exit 2, so exit 1 only ever means a failed check.
- `"encoding"` turns down `idna`, `punycode`, `unicode-escape`, and `raw-unicode-escape`. They pass the text-encoding test but encode names or escape sequences, not file text.
- Dataset, table, and column names now have to match their pattern in full, so a trailing line break is a config error. Error messages escape line breaks, so stderr is always one line.
- New test: `_row` restarts at 1 in each file with `header: false` across several files.
- A UTF-8 byte order mark is dropped when `encoding` is UTF-8 (any spelling): the file is read as `utf-8-sig`. Tests for `header: true`, `header: false`, and a zip member. In the README.
- One-column tables: every blank line is an empty value and is loaded, at the end of a file or in the middle. Judgment call: a blank line in the middle is treated the same as one at the end, since in a one-column file it can only mean an empty value. Lauren confirmed, 2026-11-20. Tables with two or more columns are unchanged.

Evidence, same commands as above, Python 3.14.6, SQLite 3.50.4:

- `python -m unittest discover tests`: 56 tests, OK (12 new).
- `python -m data_prepper selftest`: `PASS load`, exit 0.
- HCRIS FY2023 load: exit 0, 37 s. `rows_loaded` NMRC 19,574,053, RPT 6,109, ALPHA 3,778,351, 0 bad rows, 9 of 9 checks pass. Zip SHA-256 unchanged (`adf2ed82...`).
- `python tests/large_file_check.py`: PASS. 208 MB file 53.2 MB peak, 1,004 MB file 53.8 MB peak, difference 0.6 MB.

**Known gaps, left for a later chunk (Lauren, 2026-11-20)**

Listed under Ready in `STATUS.md` too.

- A stray quote on the last line of a file that has no final line break still passes: the value is stored without its quote and nothing flags it.
- The parse-error line is where the 16 MB field limit was hit, which can be far below the stray quote that caused it.
- From the first check's smaller items: an exit 2 after the run folder is made leaves a `work.db` with no report; "at byte N" in the bad-encoding message is an offset in the decoder block, not the file; an empty file with a header reports "file has None"; `csv.field_size_limit` is set at import for the whole process.
- From the fourth check: a UTF-8 BOM in a file declared as another encoding (cp1252, say) is stored in the first value with no flag.

**Fourth qa-peer check, 2026-11-20 (of commit `0ba49ab`, fresh agent)**

Verdict: pass with fixes. All seven items on the fix list held and all seven "Done when" boxes passed on its own runs: 56 tests OK; selftest PASS; HCRIS exit 0 in 37 s with NMRC 19,574,053, RPT 6,109, ALPHA 3,778,351 matching a newline count streamed from the zip members, 9 of 9 checks; zip SHA-256 matched `certutil`; large-file PASS (54.4 MB and 54.0 MB); standard-library imports only. It ran the new row-count test against the old code and it failed there, as it should; it also removed each exit-2 fix, the BOM fix, and the one-column rule in turn and the matching test failed each time. `count(*)` on the 2.0 GB `work.db` took 1.2 s for NMRC. Not checked: Python 3.13, SQLite 3.45.3, a real disk-full error, a real Deflate64 zip from Windows (tests rewrite the method byte).

Findings, and what was done:

- Should fix, fixed: an encrypted zip member gave a traceback and exit 1. Now one line and exit 2, with a test.
- Should fix, fixed: the catch-all for `sqlite3.Error` also hid code bugs (a SQL syntax error gave exit 2 and one line, like a config problem). Now only SQLite errors from the disk or file (full, I/O, cannot open, read-only, no permission, busy, locked, corrupt, not a database) give exit 2; any other SQLite error keeps its traceback. Two tests: disk full gives exit 2; a syntax error is raised. Judgment call: a bug shows a traceback (Python's exit 1) rather than being dressed up as a config error. Lauren confirmed, 2026-11-20.
- Nit, fixed: only "too many columns" from `CREATE TABLE` is reported as a column-count problem; other errors there go through the rule above.
- Nit, fixed: the `cli.py` docstring now gives the wider meaning of exit 2.
- Nit, left: with a non-UTF-8 encoding such as cp1252, a UTF-8 BOM is stored as three characters in the first value. The README limits BOM dropping to UTF-8. Added to the known gaps.

After these: 59 tests OK (3 new), selftest PASS, HCRIS FY2023 rerun exit 0 with the same counts and 9 of 9 checks. The large-file check was not rerun (the loop that reads rows did not change). These last fixes are covered by their tests, not by another agent check.

**Where to pick up**

1. Lauren reviews and merges PR #10. Two one-line confirms are in STATUS under Waiting on Lauren.
2. Lauren clones the public repo on the remote desktop and runs `python -m data_prepper selftest`. That is the first test on Python 3.13 and SQLite 3.45.3.
3. Chunk 007 follows the merge.
