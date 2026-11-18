# 010: The summarize stage

- **Status:** Ready, after 009 is merged
- **Who:** agent (a cheaper model is fine)
- **Goal:** write the grouped summaries each dataset asks for, plus a profile of every column, with counts and sums that are proven to add up.
- **Inputs:**
  - `docs/adr/0001-package-design.md` and the code from chunks 006 to 009.
  - "Rules for all build chunks" in `chunks/006-skeleton-and-load.md`. They apply here.
  - Public HCRIS FY2023, same file as chunk 006.
- **Output:**
  - `data_prepper/summarize.py`, wired into `run` after merge, and into `selftest`.
  - The `summarize` section in `datasets/hcris/dataset.json`, and `datasets/hcris/summaries/` for the custom one.
  - Tests in `tests/`.
  - `README.md`: the one command that runs all five stages, and where the outputs land.

## What to build

**Which table is read.** For a table name in the config, read `merged_<table>` if it exists, otherwise `model_<table>`.

**Config.** `summarize` is a list. Each entry:

```json
{"table": "visits", "group_by": ["county"], "totals": ["paid_amount"], "name": "visits_by_county"}
```

- `group_by`: one or more columns. `totals`: zero or more columns, each of type `integer` or `number`. This is the default kind: a row count and a sum per column.
- `name`: optional. Default: the table name, `_by_`, and the group columns joined with `_`.

There are two ways to get something other than counts and sums.

**Other built-in aggregations.** Add `aggregates` to an entry:

```json
{"table": "visits", "group_by": ["county"], "totals": ["paid_amount"],
 "aggregates": [{"column": "paid_amount", "fn": "avg"}, {"column": "visit_date", "fn": "max"}]}
```

- `fn` is one of `avg`, `min`, `max`, `count` (non-null values), `count_distinct`. These are the ones SQLite 3.45.3 has built in. `avg` needs a numeric column.
- Each adds a column named `<fn>_<column>`, after the `sum_` columns, in the order listed.

**Anything else: a summary written as SQL.** For medians, percentiles, ratios, or a summary across several tables:

```json
{"name": "paid_quartiles_by_county", "sql": "summaries/paid_quartiles_by_county.sql"}
```

- The file holds exactly one `select` (it may start with `with`), checked the same way as a rule file in chunk 008. Its result is written to `out/<name>.csv` as it comes, in the order the query gives.
- It can read any table by its plain name. The plain name points to `merged_<table>` when that exists, otherwise `model_<table>`.
- `name` is required. An entry has either `sql`, or `table` and `group_by`, never both.
- SQLite 3.45.3 has no median or percentile function. Window functions (`ntile`, `row_number`, `percent_rank`) are there and are the way to get them.

Config errors (exit code 2, before anything runs): an unknown table or column, a `totals` or `avg` column that is not numeric, an unknown `fn`, an entry that mixes the two kinds, a SQL file that is missing or is not one `select`, or two entries with the same name.

**Summary files.** One CSV per entry at `out/<name>.csv`:

- A header row. Columns: the group columns, then `rows`, then `sum_<column>` for each total, then the `aggregates` columns.
- Sorted by the group columns. UTF-8. A null group value is written as an empty field.
- Written with `csv.writer`, streamed from the query. Don't hold the result in memory.

**Profile.** For every table summarized, one entry per column: `count` (non-null), `nulls`, `distinct`, `min`, `max`. Skip `_file` and `_row`. Write the seconds taken per table, since `distinct` on a wide table is the slow part.

**Checks per summary.** These are a second route to the same numbers. They cover `rows` and the `sum_` columns only. Other aggregations and SQL summaries can't be checked this way (averages don't add up across groups), so the report marks them `"checked": false`. Checking those is on whoever wrote them.

1. The `rows` column adds up to the table's row count (error).
2. Each `sum_<column>` adds up to the same total as a plain `sum()` over the table with no grouping (error). For `number` columns allow a relative difference of 1e-9, since adding decimals in a different order changes the last digits. For `integer` columns the totals must be equal.

**Report `05-summarize.json`:** the profiles, and per summary the file name, table read, number of groups, grand total per column, the checks, and seconds taken. If any error check failed, write the report and exit with code 1.

**HCRIS.** Two summaries. The default kind: NMRC grouped by worksheet, line, and column, with the item value as the total. A SQL one, to prove the route works on real data: the number of reports per provider number from RPT, a structural count and not a methodology choice. Use the column names already in `datasets/hcris/dataset.json`.

- **Done when:**
  - [ ] On made-up data with totals worked out by hand, the CSV has exactly the expected rows, order, header, and numbers, including a group whose value is null.
  - [ ] On made-up data, the profile's `count`, `nulls`, `distinct`, `min`, and `max` are right for a text, an integer, a number, and a date column.
  - [ ] On made-up data, each `fn` gives the hand-worked answer, and nulls are left out of `avg`, `min`, `max`, `count`, and `count_distinct`.
  - [ ] On made-up data, a SQL summary that works out a median with window functions writes the hand-worked answer, and the report marks it unchecked.
  - [ ] A summary reads `merged_<table>` when it exists and `model_<table>` when it doesn't (a test for each).
  - [ ] Each kind of config error gives a one-line message and exit code 2.
  - [ ] `python -m data_prepper run datasets/hcris --data-root <the fy2023 folder>` runs all five stages and writes five reports. This is the first "Done when" in `PROBLEM.md`.
  - [ ] The default HCRIS summary has 254,458 groups, the number from the ADR's benchmark, and both checks pass. If the count differs, stop and say so.
  - [ ] Seconds taken for the full five-stage HCRIS run, and the size of `work.db`, are in the Handoff. This is the first real measure of the ADR's "3 to 4 times" disk estimate.
  - [ ] `python -m unittest discover tests` and `python -m data_prepper selftest` both pass, with summarize added to selftest.
- **Out of scope:** median or percentile as a built-in `fn` (they go through a SQL summary). Aggregations written in Python. Charts. Excel output. CCRs, per diems, or any other calculation that is a methodology choice.

## Handoff

(not started)
