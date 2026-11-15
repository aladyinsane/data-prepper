# 007: The clean stage

- **Status:** Ready, after 006 is merged
- **Who:** agent (a cheaper model is fine)
- **Goal:** turn each raw table into a typed table, set aside the rows that fail technical checks with the reason, and report the counts.
- **Inputs:**
  - `docs/adr/0001-package-design.md` and the code from chunk 006.
  - "Rules for all build chunks" in `chunks/006-skeleton-and-load.md`. They apply here.
  - Public HCRIS FY2023, same file as chunk 006. Date and number formats come from the CMS documentation zip; confirm them there.
- **Output:**
  - `data_prepper/clean.py`, wired into `run` after load, and into `selftest`.
  - `datasets/hcris/dataset.json`: `type`, `required`, `format`, and `key` filled in for RPT, NMRC, and ALPHA.
  - Tests in `tests/`.

## What to build

**Types.** A column's `type` is one of `text`, `integer`, `number`, `date`.

| Type | Passes when | Stored in `clean_<table>` as |
|---|---|---|
| `text` | always | TEXT, with leading and trailing spaces removed |
| `integer` | optional sign, then digits only | INTEGER |
| `number` | optional sign, digits, optional decimal point and digits, optional exponent. No commas, no currency signs, no `NaN` or `inf`. | REAL |
| `date` | `datetime.strptime(value, format)` succeeds | TEXT as `YYYY-MM-DD` |

- An empty value, or one that is only spaces, is null. Null is stored as NULL and is not a type failure.
- `required: true` means null is not allowed.
- The checks are small Python functions registered with `con.create_function(..., deterministic=True)` and called from SQL, as the ADR says. Each one has its own unit tests.

**Rejects.** A row is rejected when any value fails its type or any required column is null.

- Rejected rows go to `reject_<table>`: `_file`, `_row`, `reason`, then the raw text columns unchanged.
- `reason` lists every problem in the row, in column order, separated by `; `. Example: `paid_amount: not a number; visit_date: not a date (%Y-%m-%d)`.
- Rows that pass go to `clean_<table>` with `_file` and `_row` kept.

**Keys and duplicates.** These are reported, never fixed. Nothing is dropped.

- Duplicate keys: the number of key values that appear on more than one row in `clean_<table>`. Check with severity error.
- Exact duplicate rows (every config column equal): counted. Check with severity warn.
- A table with no `key` skips the key check.

**Report `02-clean.json`**, per table: `rows_in`, `rows_out`, `rows_rejected`, `rejected_by_reason` (count per single problem, such as `paid_amount: not a number`), `nulls` (count per column), `duplicate_keys`, `exact_duplicate_rows`, a sample of up to 20 duplicate key values, and seconds taken. Checks:

- `rows_in = rows_out + rows_rejected` (error).
- no duplicate keys (error).
- no exact duplicate rows (warn).
- rejected rows (warn; the run goes on, since the rejects are set aside and counted).

- **Done when:**
  - [ ] A made-up test file with known bad rows (a bad number, a bad date, a missing required value, a row with two problems, a duplicate key, an exact duplicate row, values with spaces around them) gives exactly the expected `clean_`, `reject_`, reasons, and report counts.
  - [ ] Each type function has tests for values that pass, values that fail, and null.
  - [ ] HCRIS FY2023 runs through load and clean from one command. For RPT, NMRC, and ALPHA, `rows_in = rows_out + rows_rejected`.
  - [ ] The NMRC key (report record number, worksheet, line, column) has 0 duplicate keys. This matches the ADR's benchmark. If it doesn't, stop and say so; don't change the key to make it pass.
  - [ ] Any HCRIS rejects are listed in the Handoff with their reasons. Don't loosen a type to make rejects go away; a wrong type in the config is fixed against the CMS documentation.
  - [ ] Seconds taken for the NMRC clean (19.6 million rows) is written in the Handoff. This is the speed cost the ADR left unmeasured.
  - [ ] `python -m unittest discover tests` and `python -m data_prepper selftest` both pass, with clean added to selftest.
- **Out of scope:** dropping or fixing rows. Business rules (that is the model stage). Changing how load works, beyond a bug fix that is described in the Handoff.

## Handoff

(not started)
