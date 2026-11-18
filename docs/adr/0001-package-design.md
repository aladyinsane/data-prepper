# ADR-0001: Package design

## Status

Accepted by Lauren on 2026-11-15.

## Context

`PROBLEM.md` asks for one small Python package that runs five stages (load, clean, model, merge, summarize) for any dataset, driven by per-dataset config and rule files.

What limits the design:

- It has to run in two places: Lauren's laptop, and a locked-down remote desktop.
- The remote desktop has Python 3.13.2, SQLite 3.45.3, numpy, pandas, pyodbc, and SAS. No openpyxl. Nothing else can be assumed (chunk 004).
- Copying a folder of .py files onto the remote desktop and importing it works (chunk 004). `pip install` was not tested.
- Data is usually hundreds of thousands to a few million rows. Sometimes it is tens of millions of rows with hundreds of columns.
- The remote desktop has 64 GB of RAM, but how much one session gets is not known.
- Formats are mostly delimited text. Excel shows up for supplemental data.

The main open question was the engine for big joins and summaries.

### What was measured

One benchmark, run on the laptop on 2026-11-15, standard library only (Python 3.14.6, SQLite 3.50.4; the remote desktop's versions are older and were not tested). Data: public HCRIS hospital FY2023 read straight from the CMS zip, plus a made-up wide table.

| Step | Rows | Time |
|---|---|---|
| Load HCRIS NMRC from the zip into SQLite (5 columns, 678 MB of text) | 19,574,053 | 20 s |
| Group by worksheet, line, column with a sum | 19.6 M in, 254,458 out | 11 s |
| Left join NMRC to RPT, count matches and unmatched | 19.6 M | 3 s |
| Copy NMRC with typed columns | 19.6 M | 4 s |
| Duplicate check on a 4-column key | 19.6 M | 7 s |
| Load a made-up wide table (300 columns) | 500,000 | 15 s |
| Group by on the wide table | 500,000 | under 1 s |

Peak memory for the whole run was 616 MB, of which 256 MB was the cache size the script asked for. The database file reached 4.6 GB.

What this shows: SQLite handles HCRIS-sized data in seconds with flat memory. Wide data loads at about 33,000 rows a second, so if load time grows in step with row count (assumed, not tested), 10 million rows by 300 columns would take about 5 minutes to load and 50 million about 25 minutes. That is slow but it should finish. Disk is the real cost: a table in SQLite takes about as much space as its raw text, and each stage that copies a table adds that much again.

What it does not show: speed on the remote desktop, or behaviour on a real file with tens of millions of wide rows. The first build chunk has to test both.

## Decision

### Engine

**SQLite, through the standard library's `sqlite3`, is the engine for clean, model, merge, and summarize.** Python reads the source files as a stream and inserts rows in batches. From there on, the work is SQL run by SQLite against a database file on disk.

- Each run has one working database file. It can be deleted and rebuilt from the source files at any time, so it is written with journaling and sync turned off for speed.
- pandas and numpy are never imported by the package. A project's own code can use them on the summary outputs.
- SAS is not used. It stays the fallback in `PROBLEM.md` if a real large file fails on the remote desktop.
- Type checks in the clean stage (is this a number, does this date match its format) are small Python functions registered with SQLite and called from SQL. SQLite cannot parse a date by an arbitrary format on its own, and it accepts bad numbers silently. The date `format` in the config uses Python's `strptime` codes. The speed cost of these functions is not measured yet; build chunk 2 measures it.
- SQL is limited to what SQLite 3.45.3 supports. The laptop has a newer SQLite, so this needs a test (see Consequences).

### Config format

**One JSON file per dataset, plus one `.sql` file per rule.** JSON holds what is declared (sources, columns, keys, joins, groupings). Rules are logic, so they are SQL files, which also keeps multi-line SQL out of JSON strings.

Example for a made-up dataset. Folder layout:

```
clinic_visits/
  dataset.json
  rules/
    010_drop_voided.sql
    020_paid_not_negative.sql
```

`dataset.json`:

```json
{
  "dataset": "clinic_visits",
  "tables": {
    "visits": {
      "source": {"path": "input/visits_*.csv", "delimiter": ",", "header": true, "encoding": "utf-8"},
      "columns": {
        "visit_id":    {"type": "text", "required": true},
        "clinic_id":   {"type": "text", "required": true},
        "visit_date":  {"type": "date", "format": "%Y-%m-%d"},
        "paid_amount": {"type": "number"},
        "status":      {"type": "text"}
      },
      "key": ["visit_id"]
    },
    "clinics": {
      "source": {"path": "input/clinics.csv", "delimiter": ",", "header": true, "encoding": "utf-8"},
      "columns": {
        "clinic_id": {"type": "text", "required": true},
        "county":    {"type": "text"}
      },
      "key": ["clinic_id"]
    }
  },
  "model": {"visits": ["rules/010_drop_voided.sql", "rules/020_paid_not_negative.sql"]},
  "merge": [
    {"left": "visits", "right": "clinics", "on": ["clinic_id"], "expect": "many_to_one", "min_match_rate": 0.99}
  ],
  "summarize": [
    {"table": "visits", "group_by": ["county"], "totals": ["paid_amount"]}
  ]
}
```

`rules/020_paid_not_negative.sql`:

```sql
-- kind: check
-- severity: error
-- Rows returned are the rows that break the rule.
select visit_id, paid_amount from visits where paid_amount < 0;
```

In the example, the summary groups `visits` by `county`. That works because summarize reads the merged table, where `county` has been joined on.

A rule is one of two kinds. A **check** is a query that returns the rows breaking the rule. A **transform** is a query whose result replaces the table. Rules run in file-name order. The exact header format is settled in the build chunk for the model stage.

### What each stage takes in and writes out

Everything for a run goes in one folder: `runs/<dataset>/<run id>/`, holding `work.db`, a `reports/` folder, and an `out/` folder.

| Stage | Takes in | Writes out |
|---|---|---|
| Load | Source files named in the config (plain or inside a zip). | `raw_<table>` in `work.db`, every column as text, nothing changed. Report: file name, size, SHA-256, rows read, rows loaded, rows with the wrong number of fields. |
| Clean | `raw_<table>`, plus column types, required columns, and keys from the config. | `clean_<table>` with typed columns. `reject_<table>` holding each rejected row and the reason. Report: rows in, rows out, rows rejected by reason, nulls per column, duplicate keys. |
| Model | `clean_<table>`, plus the rule files. | `model_<table>`. Report: one line per rule with its kind, severity, rows affected or rows failing, and a sample of failing rows. |
| Merge | `model_<table>` for the main table and each supplemental table (supplemental tables go through load, clean, and model the same way), plus the join list. | `merged_<table>`. Report per join: rows before, rows after, match rate, unmatched keys sample, and whether the row count grew when it should not have. |
| Summarize | `merged_<table>` (or `model_<table>` when there are no joins), plus the groupings. | CSV files in `out/`. Report: a profile per column (count, nulls, distinct, min, max) and the totals per grouping. |

Rules that apply to every stage:

- Each stage writes `reports/<number>-<stage>.json` with row counts in and out and every check result. This is the third "Done when" in `PROBLEM.md`.
- A failed check with severity `error` stops the run after that stage's report is written. Severity `warn` is recorded and the run goes on.
- "Snapshot" in the load stage means the hash and the untouched raw table, not a second copy of the source file. Copying a multi-GB file on every run costs disk for nothing the hash doesn't already prove.

### Running and installing

- Install: copy the `data_prepper/` folder next to the project. No pip.
- One command: `python -m data_prepper run <dataset folder>`. Single stages can be run by name for debugging.
- `python -m data_prepper selftest` builds a small made-up dataset and runs all stages on it. It needs no data files, so it is the check to run on the remote desktop.
- Tests use the standard library's `unittest`, so they run in both places with nothing installed.

### Dependencies

Every one is confirmed in chunk 004's answers:

| Used for | Dependency | In chunk 004 |
|---|---|---|
| Language | Python 3.13 or newer | 3.13.2 |
| Engine | `sqlite3` module, SQLite 3.45.3 or newer | 3.45.3, and it imports |
| Reading files | `csv`, `zipfile`, `io`, `pathlib` (standard library) | comes with Python |
| Config, reports, hashing, command line, tests | `json`, `hashlib`, `argparse`, `unittest` (standard library) | comes with Python |
| Install | Copy a folder and import from it | confirmed working |

Not used: pandas, numpy, pyodbc, SAS, openpyxl, YAML.

### First three build chunks

1. **Skeleton and load.** Package folder, command line, config reading with clear errors for a bad config, the run folder, and the load stage with its report. Runs on HCRIS FY2023 straight from the zip. Includes `selftest` for the stages that exist. Checked by: row counts match an independent line count of the files; a made-up file larger than a set memory cap loads while peak memory stays under the cap; Lauren runs `selftest` on the remote desktop.
2. **Clean.** Types, required columns, duplicates, and keys, with the reject table and report. Checked by: a made-up file with known bad rows produces exactly the expected rejects and reasons; HCRIS RPT and NMRC pass with counts that add up (rows in = rows out + rejects).
3. **Model.** The rule runner for check and transform rules, with its report, and two or three real HCRIS rules that don't depend on provider matching (moved to the `provider-changes` repo on 2026-11-16). Checked by: a rule known to fail stops the run with the failing rows in the report; rules run in order; the same input gives the same output twice.

Merge, summarize, NPPES, and the large-file trial on the remote desktop follow as later chunks. Build chunk 1 is the one the first `qa-peer` trial runs on (see `C:\dev\dev-team\STATUS.md`).

## Alternatives Considered

### Engine

- **Streaming Python only.**
  - For: nothing but the standard library. Memory stays flat for row-by-row work such as type checks.
  - Against: joins, group-bys, and duplicate checks on data larger than memory need sorting and merging on disk, which means writing and testing a small database by hand. Rules would be Python instead of SQL. Row-by-row Python is also expected to be slower than SQLite for the same aggregate (not measured here).
- **SQLite (chosen).**
  - For: in the standard library in both places. Works from disk, so memory stays flat (616 MB peak on 19.6 M rows). Joins, group-bys, window functions, and indexes are already built and tested. Rules are SQL, which Lauren already writes. The working database can be opened and inspected with any SQLite tool when a number looks wrong.
  - Against: it stores rows, not columns, so wide tables are slow to load (about 33,000 rows a second at 300 columns) and take a lot of disk. It runs on one core. Its typing is loose: a bad value in a number column is stored without complaint unless the clean stage checks it, so the clean stage has to do real type checking of its own. It has no date type, so dates are stored as ISO text.
- **SAS for the heavy step.**
  - For: built for files this size, and already on the remote desktop.
  - Against: it can't run or be tested at home, so half the package would be untested until it reached work. It means two languages and generated SAS code, which `PROBLEM.md` puts out of scope unless Python fails.
- **pandas.**
  - For: installed on the remote desktop, and familiar. (It is not installed on the laptop's Python 3.14 today.)
  - Against: it holds the table in memory. Tens of millions of rows by hundreds of columns will not fit reliably in a shared 64 GB session. `PROBLEM.md` already rules it out of the core.
- **DuckDB (what daita used).** Likely faster than SQLite for this work (not measured here), but it is not on the remote desktop. Ruled out by the constraints, not on merit.

### Config format

- **JSON plus `.sql` rule files (chosen).**
  - For: standard library. A config can't hide logic. Easy to diff and to check for mistakes with clear messages. SQL files get proper editor support.
  - Against: JSON has no comments, so notes go in the README next to it or in a `"note"` key the package ignores. It is wordy for tables with hundreds of columns.
- **Plain Python file holding a dict.**
  - For: comments, multi-line strings, and loops for repetitive column lists.
  - Against: loading a config means running code, so a config can do anything, and a mistake shows up as a Python traceback instead of a clear message. Configs drift into programs.
- **YAML.** Needs a library the remote desktop doesn't have.

## Consequences

Easier:

- One engine and one language for rules. Adding a dataset means writing a JSON file and SQL files, which is the second "Done when".
- Any intermediate table can be inspected after a run, because it is still in `work.db`.
- Nothing to install on the remote desktop.

Harder, and accepted:

- **Disk use.** `work.db` holds a raw, clean, model, and merged copy of each table. A rough estimate is 3 to 4 times the size of the source text; this was not measured stage by stage. The benchmark's 4.6 GB file held about 0.7 GB of HCRIS text loaded once, one typed copy of NMRC, and the made-up wide table, whose text size was not measured separately. For the largest files this may not fit, and the fix (dropping earlier stage tables as the run goes, or keeping only the columns named in the config) costs the ability to inspect them. Decide this when a real file forces it.
- **Speed on wide tables.** A file with tens of millions of rows and hundreds of columns will take tens of minutes to load. If that is too slow in practice, SAS for the heavy step comes back on the table.
- **Type checking is ours to write.** SQLite will not reject bad values, so the clean stage carries that weight and needs the most tests.
- **Two SQLite versions.** The laptop has 3.50, the remote desktop 3.45. SQL that works at home can fail at work. `selftest` on the remote desktop is the guard, and it should run after every chunk that adds SQL.
- **Excel is not read.** Without openpyxl, the package cannot open .xlsx on the remote desktop. Version 1 expects supplemental Excel sheets to be saved as CSV first. A small standard-library .xlsx reader is possible later if this turns out to hurt.
- **Not tested yet:** the remote desktop's actual speed, its free disk, whether it gives a writable temp folder for SQLite's sorting, and a real file at the top of the size range. Free disk and a writable folder are real dependencies that chunk 004 did not cover.

## Lauren's answers (2026-11-15)

1. SQLite as the engine, with SAS only as the fallback: yes.
2. JSON config plus `.sql` rule files: yes.
3. Supplemental Excel saved as CSV first for version 1: yes.
4. Free disk on the remote desktop: not known yet. Lauren will check (see `STATUS.md`).
5. "Snapshot" in `PROBLEM.md` means the file's hash plus the untouched raw table, with no second copy of the source file: yes.

## Related

- `PROBLEM.md` (the brief this answers)
- `chunks/004-remote-desktop-environment.md` (what the remote desktop has)
- `chunks/005-adr-package-design.md` (this chunk)
- `C:\dev\daita\docs\adr\0013-python-duckdb-and-parquet.md` (the earlier engine choice, for a machine without these limits)
