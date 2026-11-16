# 010: The summarize stage

- **Status:** Ready, after 009 is merged
- **Who:** agent (a cheaper model is fine)
- **Goal:** write the grouped totals each dataset asks for, plus a profile of every column, with totals that are proven to add up.
- **Inputs:**
  - `docs/adr/0001-package-design.md` and the code from chunks 006 to 009.
  - "Rules for all build chunks" in `chunks/006-skeleton-and-load.md`. They apply here.
  - Public HCRIS FY2023, same file as chunk 006.
- **Output:**
  - `data_prepper/summarize.py`, wired into `run` after merge, and into `selftest`.
  - The `summarize` section in `datasets/hcris/dataset.json`.
  - Tests in `tests/`.
  - `README.md`: the one command that runs all five stages, and where the outputs land.

## What to build

**Which table is read.** For a table name in the config, read `merged_<table>` if it exists, otherwise `model_<table>`.

**Config.** `summarize` is a list. Each entry:

```json
{"table": "visits", "group_by": ["county"], "totals": ["paid_amount"], "name": "visits_by_county"}
```

- `group_by`: one or more columns. `totals`: zero or more columns, each of type `integer` or `number`.
- `name`: optional. Default: the table name, `_by_`, and the group columns joined with `_`.
- Config errors (exit code 2, before anything runs): an unknown table or column, a `totals` column that is not numeric, or two entries with the same name.

**Summary files.** One CSV per entry at `out/<name>.csv`:

- A header row. Columns: the group columns, then `rows`, then `sum_<column>` for each total.
- Sorted by the group columns. UTF-8. A null group value is written as an empty field.
- Written with `csv.writer`, streamed from the query. Don't hold the result in memory.

**Profile.** For every table summarized, one entry per column: `count` (non-null), `nulls`, `distinct`, `min`, `max`. Skip `_file` and `_row`. Write the seconds taken per table, since `distinct` on a wide table is the slow part.

**Checks per summary.** These are a second route to the same numbers:

1. The `rows` column adds up to the table's row count (error).
2. Each `sum_<column>` adds up to the same total as a plain `sum()` over the table with no grouping (error). For `number` columns allow a relative difference of 1e-9, since adding decimals in a different order changes the last digits. For `integer` columns the totals must be equal.

**Report `05-summarize.json`:** the profiles, and per summary the file name, table read, number of groups, grand total per column, the checks, and seconds taken. If any error check failed, write the report and exit with code 1.

**HCRIS.** One summary: NMRC grouped by worksheet, line, and column, with the item value as the total. Use the column names already in `datasets/hcris/dataset.json`.

- **Done when:**
  - [ ] On made-up data with totals worked out by hand, the CSV has exactly the expected rows, order, header, and numbers, including a group whose value is null.
  - [ ] On made-up data, the profile's `count`, `nulls`, `distinct`, `min`, and `max` are right for a text, an integer, a number, and a date column.
  - [ ] A summary reads `merged_<table>` when it exists and `model_<table>` when it doesn't (a test for each).
  - [ ] Each kind of config error gives a one-line message and exit code 2.
  - [ ] `python -m data_prepper run datasets/hcris --data-root <the fy2023 folder>` runs all five stages and writes five reports. This is the first "Done when" in `PROBLEM.md`.
  - [ ] The HCRIS summary has 254,458 groups, the number from the ADR's benchmark, and both checks pass. If the count differs, stop and say so.
  - [ ] Seconds taken for the full five-stage HCRIS run, and the size of `work.db`, are in the Handoff. This is the first real measure of the ADR's "3 to 4 times" disk estimate.
  - [ ] `python -m unittest discover tests` and `python -m data_prepper selftest` both pass, with summarize added to selftest.
- **Out of scope:** averages, medians, percentiles, or any statistic besides count and sum. Charts. Excel output. CCRs, per diems, or any other calculation that is a methodology choice.

## Handoff

(not started)
