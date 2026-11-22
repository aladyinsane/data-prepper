# data-prepper

A small Python package, plus per-dataset config, for the stages Lauren keeps rebuilding: load, clean, model, merge supplemental data, and summarize. Each project imports it and supplies its own config and rules.

Background and design decisions are in `OVERVIEW.md`. Where things stand is in `STATUS.md`.

## Usage

Everything below was run on the laptop (Python 3.14.6, SQLite 3.50.4). It has not been run on the remote desktop yet.

The load, clean, and model stages exist so far. Run these from the repo folder:

```
python -m data_prepper run <dataset folder> [--data-root <folder>] [--runs <folder>]
python -m data_prepper selftest
python -m unittest discover tests
python tests/large_file_check.py
```

- `<dataset folder>` holds a `dataset.json`. `datasets/hcris` is the HCRIS one.
- `--data-root` is the folder relative `source.path` values are resolved against. Default: the dataset folder.
- `--runs` is where run folders go. Default: `runs/` in the current folder. Each run makes `runs/<dataset>/<run id>/` with `work.db`, `reports/`, and `out/`.
- Exit codes: 0 success, 1 a check with severity error failed (the report is written first), 2 bad config, bad arguments, or a file or folder that cannot be read or written (for example a zip member packed with Deflate64 or encrypted, `--runs` pointing at a file, more columns than SQLite allows, or a full disk). Exit 2 prints one line on stderr. A bug in the code still shows a Python traceback.
- The load report is `reports/01-load.json`: files with size and SHA-256, rows read, rows loaded, rows with the wrong number of fields. Those rows go to `badrows_<table>` in `work.db`. Rows loaded and rows bad are counted from the two tables after loading, not from the loop that inserts them.
- The report has three checks per table, all severity error: no rows with the wrong number of fields, rows read = rows loaded + rows bad, and lines in the files = rows read. The last one fails when a quote swallows line breaks, so a file with a quoted field that really does span lines fails it too.
- `"quoting": false` in a table's `source` turns quote handling off, so quote characters are stored as text. Default is true.
- Blank lines at the end of a file are ignored. A blank line anywhere else is a bad row. In a one-column table a blank line is an empty value instead, at the end of a file or anywhere else, and is loaded.
- With `"encoding": "utf-8"`, a UTF-8 byte order mark at the start of a file is dropped, so it never ends up in the first value or the header.
- `_file` is the bare file name (`<zip name>:<member>` for a zip member), so two files with the same name in different folders look the same.
- The clean stage turns each `raw_<table>` into `clean_<table>` (typed) and `reject_<table>`, and writes `reports/02-clean.json`. A column `type` is `text`, `integer`, `number`, or `date`. A `date` column needs a `format` in Python `strptime` codes; it is stored as `YYYY-MM-DD`. Leading and trailing spaces are removed; an empty value is null, which is not a type failure. `required: true` means null is a reject. A rejected row goes to `reject_<table>` with `reason` listing every problem in column order, then its raw text unchanged. Nothing is fixed or dropped.
  - `integer`: optional sign, then digits, within SQLite's 64-bit range. `number`: optional sign, digits, optional `.` and digits (so `5.` and `.5` fail), optional exponent; no commas, currency signs, `NaN`, `inf`, or a value too big for a float. `date` passes when `datetime.strptime` accepts it, so a format with no year (such as `%m/%d`) gives year 1900 and rejects `02/29`. A column cannot be named `reason` (the reject table has one). These rules are in `data_prepper/clean.py`.
  - The report has, per table: rows in, rows out, rows rejected, rejects by single problem, nulls per column (in `clean_<table>`), duplicate keys, up to 20 duplicate key values, exact duplicate rows, and seconds. Duplicate keys are counted on `clean_<table>` as the number of key values on more than one row. Exact duplicate rows are the extra copies (three identical rows count as 2), compared on the typed, trimmed values. A table with no `key` skips the key check.
  - Checks: rows in = rows out + rows rejected (error), no duplicate keys (error), no exact duplicate rows (warn), no rejected rows (warn). Rejects alone do not stop the run.
  - If load fails an error check, the run stops there and clean does not run.
- `selftest` builds small made-up datasets in a temp folder and checks the load, clean, and model stages against known answers. It needs no data files.
- The model stage runs the rule files named in the config's `model` section and writes `reports/03-model.json`. See "Writing rules" below.
- `tests/large_file_check.py` is not part of the normal test run. It makes 200 MB and 1 GB made-up files, so it needs Windows, a few minutes, and about 1.5 GB of temp disk.

Example, HCRIS FY2023 from the read-only daita copy:

```
python -m data_prepper run datasets/hcris --data-root C:\dev\daita\data\bronze\cms-hcris-hospital-2552-10\files\20260928T081652Z_fy2023
```

That took about 30 seconds and made a 2.0 GB `work.db`.

Python 3.13 and SQLite 3.45.3 (the remote desktop) were not available here, so neither was tested. The unit tests and selftest also pass on Python 3.12.15, so nothing newer than 3.12 is in use.

## Writing rules

The model stage runs `.sql` rule files against the clean tables. The config's `model` section maps a table name to a list of rule files (paths relative to the dataset folder):

```
"model": {"nmrc": ["rules/010_nmrc_has_report.sql"], "rpt": ["rules/020_fy_dates_in_order.sql"]}
```

Tables run in the order they appear in `model`, and the rules for a table run in the order listed (not by file name). A table with no rules is still copied.

A rule file is header comments, then exactly one `select` statement (it may start with `with`), with or without a final `;`:

```sql
-- kind: check
-- severity: error
-- Rows returned are the rows that break the rule.
select visit_id, paid_amount from visits where paid_amount < 0;
```

- `-- kind:` is `check` or `transform`. Required. `-- severity:` is `error` or `warn`. Required on a check, not allowed on a transform. Other comment lines are ignored. Only the `--` lines before the statement count as header.
- A missing or unknown header value, a repeated header, more than one statement, no statement, a statement that is not a `select`, an unreadable file, or a table name in `model` that is not in `tables` is a config error: one line naming the file, exit code 2. All rule files are read when the config is read, so this happens before load starts.
- A SQL error found when a rule runs (a misspelled column, for example) also exits 2 with one line naming the file. No `03-model.json` is written in that case, and a transform that failed leaves `model_<table>` as it was.
- At the start of the stage every config table gets `model_<table>`, a copy of `clean_<table>`, and a temp view with the plain table name that selects from it. Rules use the plain names (`visits`) and can read any table in the dataset. `clean_<table>` is never changed.
- A **check** returns the rows that break the rule; nothing changes. Status is `pass` (no rows) or `fail`. The report has `rows_failing` and up to 20 of those rows.
- A **transform**'s result becomes the new `model_<table>` for the table it is listed under, so a later rule sees the new rows and columns. `_file` and `_row` survive only if the query selects them. Columns the query computes have no declared type in SQLite; columns copied straight from the table keep theirs.
- All rules run and the report is written. Then, if any check with severity `error` failed, the run exits 1. The one exception: after a failed error check on a table, later transforms listed for that same table are reported as `skipped`. Later checks on it still run, and other tables are not affected.
- `03-model.json` has one entry per rule in run order (`table`, `file`, `kind`, `severity`, `status`, `rows_failing` and `sample` for a check, `rows_before` and `rows_after` for a transform, `seconds`), and per table `rows_in` and `rows_out`. `rows_before` and `rows_after` are null for a skipped transform.
- SQL runs on SQLite 3.45.3 on the remote desktop. Don't use anything newer.
