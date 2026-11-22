# 008: The model stage

- **Status:** Built. PR open, checked by qa-peer (see Handoff), waiting on Lauren's merge.
- **Who:** agent (a cheaper model is fine)
- **Goal:** run a dataset's `.sql` rule files in order against the clean tables, and report what each rule did.
- **Inputs:**
  - `docs/adr/0001-package-design.md` and the code from chunks 006 and 007.
  - "Rules for all build chunks" in `chunks/006-skeleton-and-load.md`. They apply here.
  - Public HCRIS FY2023, same file as chunk 006.
- **Output:**
  - `data_prepper/model.py`, wired into `run` after clean, and into `selftest`.
  - `datasets/hcris/rules/` with the two check rules named below, and the `model` section in `datasets/hcris/dataset.json`.
  - Tests in `tests/`.
  - A short "Writing rules" section in `README.md`.

## What to build

**Rule files.** The config's `model` section maps a table to a list of rule files, as in the ADR example. Rules for a table run in the order listed.

A rule file is header comments, then exactly one `select` statement (it may start with `with`):

```sql
-- kind: check
-- severity: error
-- Rows returned are the rows that break the rule.
select visit_id, paid_amount from visits where paid_amount < 0;
```

- `kind` is `check` or `transform`. Required.
- `severity` is `error` or `warn`. Required for a check, not allowed on a transform.
- A file with a missing or unknown header value, more than one statement, or a statement that is not a `select` is a config error: one line naming the file, exit code 2, before any rule runs.

**How rules see tables.** At the start of the stage, every table gets `model_<table>` as a copy of `clean_<table>`, and a temp view with the plain table name (`visits`) that selects from `model_<table>`. Rules use the plain names, and can read any table in the dataset.

- **Check:** run the query. The rows returned are the failures. Nothing changes.
- **Transform:** the query's result becomes the new `model_<table>` for the table the rule is listed under. Build it as a new table, drop the old one, rename, and recreate the view. `_file` and `_row` survive only if the query selects them.

**Stopping.** All rules for all tables run and the report is written. Then, if any check with severity error failed, exit with code 1. One exception: after a failed error check on a table, later transforms on that same table are skipped and reported as skipped.

**Report `03-model.json`**, one entry per rule in run order: `table`, `file`, `kind`, `severity`, `status` (`pass`, `fail`, `applied`, `skipped`), `rows_failing` and a sample of up to 20 failing rows for a check, `rows_before` and `rows_after` for a transform, and seconds taken. Per table: `rows_in` and `rows_out`.

**HCRIS rules for this chunk.** Two checks only. Both are structural, not methodology:

1. `010_nmrc_has_report.sql` (error): NMRC rows whose report record number is not in RPT.
2. `020_fy_dates_in_order.sql` (error): RPT rows where the fiscal year end date is not after the begin date.

No HCRIS transform in this chunk. Which reports to keep and how providers match across releases are Lauren's rules and belong to the `provider-changes` repo, not this one. Transforms are tested on made-up data only.

- **Done when:**
  - [ ] On made-up data: a passing check, a failing warn check (run goes on, exit 0), and a failing error check (report written with the failing rows, exit 1) each behave as described.
  - [ ] On made-up data: a transform that drops rows and one that adds a column each change `model_<table>` as expected, and a later rule sees the result.
  - [ ] Rules run in the listed order (a test where the order changes the answer).
  - [ ] A transform listed after a failed error check on the same table is reported as skipped.
  - [ ] Each kind of bad rule file gives a one-line error and exit code 2 before any rule runs.
  - [ ] Running the same input twice gives the same `model_` tables (compare all rows, sorted) and the same report apart from times and run id.
  - [ ] HCRIS FY2023 runs through load, clean, and model from one command. The results of the two HCRIS checks are in the Handoff with their counts. If either fails, report it; don't change the rule or the data to make it pass.
  - [ ] `python -m unittest discover tests` and `python -m data_prepper selftest` both pass, with model added to selftest.
- **Out of scope:** HCRIS business rules beyond the two checks. Provider matching (the `provider-changes` repo). Merge and summarize. Rules written in Python.

## Handoff

Built on branch `feat/008-model-stage`. Laptop only: Python 3.14.6, SQLite 3.50.4. Python 3.13 and SQLite 3.45.3 are untested. Nothing in the chunk was loosened. SQL uses only plain `select`, `with`, joins, `create table as`, and `alter table rename`, all far older than 3.45.

**Evidence, one per box**

1. Check kinds on made-up data: `tests/test_model.py::Checks`. A passing check (`test_passing_check`), a failing warn check that goes on with exit 0 (`test_failing_warn_check_goes_on`), and a failing error check that writes the report with the failing rows, runs the rule listed after it, then exits 1 (`test_failing_error_check_writes_report_then_exit_1`). Also: a check changes nothing, the sample is cut at 20, a rule can read another table, a trailing comment and a `with` statement both work.
2. Transforms on made-up data: `Transforms::test_transform_drops_rows` (5 rows to 3, `clean_` untouched, report `rows_before` 5 and `rows_after` 3, per table `rows_in` 5 and `rows_out` 3), `test_transform_adds_column`, and `test_later_rule_sees_the_result` (drop rows, add a column, then a check that reads the new column).
3. Order: `test_order_changes_the_answer`. The same two files, check then transform gives `fail`, `applied`. Transform then check gives `applied`, `pass`.
4. Skipped: `test_transform_after_failed_error_check_is_skipped`. After a failed error check on `visits`, its two later transforms are `skipped` (before and after null), a later check on `visits` still runs, a transform on `clinics` still applies, `model_visits` is unchanged, and the run exits 1. A failed warn check does not skip (`test_transform_after_failed_warn_check_still_runs`).
5. Bad rule files: `BadRuleFiles`. Each of these gives exit 2, one stderr line naming the file, nothing on stdout, and no run folder: missing kind, unknown kind, empty kind, check with no severity, unknown severity, transform with a severity, a repeated header, two statements, no statement, `delete` and `drop` (not a select), an unclosed quote, an unclosed `/* */`, a file that is not UTF-8, a missing file, a `model` table not in `tables`, a wrong-shaped `model` value, and a good file followed by a bad one. All rule files are read when the config is read, so this happens before load starts, which is earlier than "before any rule runs".
6. Same input twice: `test_same_input_twice_gives_the_same_result` runs a dataset with a check and three transforms twice (two separate run folders), compares every row of every `model_` table sorted, and compares the whole report minus `started`, `finished`, `run_id`, and per-rule `seconds`.
7. HCRIS FY2023 through load, clean, and model from one command (`python -m data_prepper run datasets/hcris --data-root <fy2023 folder>`), exit 0, about 3 min 33 s in all (load 34 s, clean 2 min 46 s, model 13 s). **Both checks pass:**

   | Rule | Table | Severity | Rows failing | Seconds |
   |---|---|---|---|---|
   | `010_nmrc_has_report.sql` | nmrc | error | **0** | 3.3 |
   | `020_fy_dates_in_order.sql` | rpt | error | **0** | 0.0 |

   Table counts: rpt 6,109 in and out, nmrc 19,574,053 in and out, alpha 3,778,351 in and out (no HCRIS transform, so nothing changes). Second path, plain SQL on the run's `work.db` with a different query shape: NMRC rows whose record number is not in `clean_rpt` (`NOT IN`): 0. NMRC has 6,109 distinct record numbers and RPT has 6,109 rows. RPT rows with `julianday(end) <= julianday(begin)`: 0, and the smallest gap between begin and end is 18 days. `clean_nmrc EXCEPT model_nmrc` has 0 rows. No FY date is empty in RPT (0 null begin, 0 null end), so the choice about empty dates in rule 020 changed nothing for this file.
8. `python -m unittest discover tests`: 124 tests OK (43 new). `python -m data_prepper selftest`: `PASS load`, `PASS clean`, `PASS model`, exit 0. The model selftest runs two made-up datasets: one where an error check fails (the transform after it is skipped, exit 1) and one where the transform comes first (applied, then the check passes, exit 0).

**Judgment calls (change any you disagree with)**

- Rule files are parsed in `config.py` (`read_rule`), when the config is read, not in `model.py`. This gives exit 2 before load starts instead of after a 3 minute load and clean. `model.py` only runs them.
- "Header": only `-- kind:` and `-- severity:` lines (any case) that come before the statement are read. Any other comment is ignored. A repeated header line is an error. `;` and `--` inside a string or comment do not count, so they cannot fake a second statement.
- "Statement must be a select" is checked on the first word (`select` or `with`). A `with ... delete` passes that test, but a check runs inside `select * from (...)` and a transform inside `create table as`, and both are errors for anything that is not a select, so it cannot change the tables. That error exits 2 as a SQL error (next point).
- A SQL error found while a rule runs (misspelled column) exits 2 with one line naming the file, and no `03-model.json` is written. The chunk did not say. I chose to stop, not to record it as a failed rule, because a rule that cannot run is a bug in the rule. A failed transform leaves `model_<table>` as it was (tested). Say if you would rather have a partial report.
- Order across tables is the order of the keys in the `model` section (not the table order in `tables`). Within a table it is the listed order, as the chunk says. The ADR's "file-name order" is not used.
- The check sample is `select * from (rule) limit 20` with no ordering added, so rule authors who want a fixed sample put an `order by` in the rule. The same data gave the same sample in the two-run test.
- `failed_errors` in `run.py` now also reads `rules` in a model report (check, severity error, status fail), so the existing "write report, then stop with exit 1" path works. The model report has no separate `checks` list.
- `model_<table>` is `create table ... as select * from clean_<table>`, which keeps the declared column types (INTEGER, REAL, TEXT) of the clean table. A column a transform computes has no declared type (tested only for copied columns). The temporary table a transform builds is `_new_model_<table>`, which cannot clash with a config table name (those start with a letter).
- Rule 020 (`FY_END_DT <= FY_BGN_DT`) does not flag a row where either date is empty, because an empty date is a null, not a wrong order. HCRIS FY2023 has none, so it does not matter here. It is written in the rule file's comments.
- Rule 010 uses a left join on `RPT_REC_NUM` (both columns are integer) instead of `NOT EXISTS`, because the ADR benchmark measured the left join at 3 s on this table, and 3.3 s here agrees.
- Disk: every table now has a `model_` copy, as the chunk asks, so the HCRIS `work.db` is 5.8 GB after a full run (it was 2.6 GB right after load). The ADR warned about this. Not changed.

**Not checked**

- Python 3.13 and SQLite 3.45.3 (the remote desktop). Lauren's remote desktop run of `selftest` should be repeated after this merges.
- Rules on tables with hundreds of columns or tens of millions of rows beyond HCRIS.
- A table named like another table's raw or clean table (for example tables `x` and `raw_x`): the temp view named `raw_x` would hide the real `raw_x` table from rules only. Nothing in HCRIS does this.

**Where to pick up**

Lauren reviews and merges the PR. Chunk 009 (merge stage) follows the merge.
