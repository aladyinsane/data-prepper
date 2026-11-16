# 008: The model stage

- **Status:** Ready, after 007 is merged
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

(not started)
