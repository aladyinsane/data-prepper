# 007: The clean stage

- **Status:** Built. PR #16 open, checked by qa-peer (see Handoff), waiting on Lauren's merge.
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

Built on branch `feat/007-clean-stage`. Laptop only: Python 3.14.6, SQLite 3.50.4. Python 3.13 and SQLite 3.45.3 are untested. Nothing in the chunk was loosened. SQL uses only features older than SQLite 3.45 (the reason text is built with `substr` and `||`, not `concat_ws`).

**Evidence, one per box**

1. Known bad rows. `tests/test_clean.py::test_known_bad_rows` loads a 12-row file (good rows, spaces around values, a bad number, a bad date, a missing required value, a row with two problems, a duplicate key, an exact duplicate row, empty values) and asserts every `clean_` row, every `reject_` row with its reason, and every report count and check. `selftest` does a smaller version of the same.
2. Type functions. `Functions` in `tests/test_clean.py`: pass, fail, and null cases for `integer`, `number`, and `date`, plus the registered SQL functions.
3. HCRIS FY2023 through load and clean from one command (`python -m data_prepper run datasets/hcris --data-root <fy2023 folder>`), exit 0, 3 min 16 s in all.

   | Table | rows_in | rows_out | rows_rejected | check rows_in = out + rejected |
   |---|---|---|---|---|
   | RPT | 6,109 | 6,109 | 0 | pass |
   | NMRC | 19,574,053 | 19,574,053 | 0 | pass |
   | ALPHA | 3,778,351 | 3,778,351 | 0 | pass |

4. NMRC key (RPT_REC_NUM, WKSHT_CD, LINE_NUM, CLMN_NUM): 0 duplicate keys, 0 exact duplicate rows. This matches the ADR benchmark. RPT key (RPT_REC_NUM) and ALPHA key (same four columns as NMRC): 0 duplicate keys.
5. HCRIS rejects: none, for any table. All 12 checks pass (4 per table).
6. Seconds for the NMRC clean (19,574,053 rows): **138.5 s** (140.6 s on the recheck run) in the report (the whole table: both passes, counts, and both duplicate checks). RPT 0.4 s, ALPHA 21.9 s. From separate timings on that `work.db`: a plain scan of the column takes 1.7 s; running only the type checks over every row takes 27.8 s (so the checks cost about 26 s a pass); the duplicate-key group by takes 9.9 s; the exact-duplicate group by takes 11.6 s. The checks run twice (once to find rejects, once to choose the rows to keep) and the second pass also converts values and writes the table, which makes up most of the rest. This is the speed cost the ADR left unmeasured. For comparison the ADR measured 4 s to copy NMRC with typed columns and 7 s for a duplicate check.
7. `python -m unittest discover tests`: 81 tests OK (22 new, counting the five added after the qa-peer check). `python -m data_prepper selftest`: `PASS load` and `PASS clean`, exit 0.

**Judgment calls (change any you disagree with)**

- Types in `datasets/hcris/dataset.json`: CMS defines `RPT_REC_NUM` and `NPI` as `NUMBER`. I made both `integer` (whole-number identifiers), and `ITM_VAL_NUM` stays `number`. All 23.4 million rows pass, so this changes no counts. NPI is empty on every FY2023 row, so the `integer` choice for NPI is not exercised by this data. Dates are `MM/DD/YYYY` per `HCRIS_DataDictionary.csv`.
- Key for ALPHA: the same four columns as NMRC (the chunk said to fill a key for ALPHA but gave none). It has 0 duplicates.
- `number` follows the chunk literally: digits, optional `.` and digits, so `5.` and `.5` fail. A value that overflows a float (`1e999`) fails as "not a number". `integer` also fails outside SQLite's 64-bit range. No HCRIS value hit these.
- `config.py`: added `integer` as a column type, and a `date` column now needs a `format` (config error, exit 2, otherwise every value would fail).
- `exact_duplicate_rows` counts the extra copies, so three identical rows count as 2. Compared on the typed, trimmed values.
- `nulls` counts nulls in `clean_<table>` (kept rows). A null in a required column shows under `rejected_by_reason` instead.
- A null key value counts as a value when looking for duplicate keys (two rows with a null key are a duplicate).
- `rejected_by_reason` counts single problems, so a row with two problems counts once under each.
- A date format that never matches (a typo in the config) rejects every row with "not a date (<format>)". The run still finishes. It is not caught at config time.
- Selftest now makes a second made-up dataset for clean, because the first one stops after load on purpose.
- `reject_<table>` and `clean_<table>` start with `_file, _row`.

**qa-peer check, 2026-11-21 (fresh agent, of commit `39b6517`)**

Verdict: pass with fixes. All seven boxes held on its own runs. Re-derived without `data_prepper`, straight from the zip: NMRC 19,574,053 rows and 0 duplicate keys, RPT 6,109 rows with 6,109 distinct record numbers, ALPHA 3,778,351 rows with 0 duplicate keys, every NMRC value fits `-?digits(.digits)?`, every RPT date fits `%m/%d/%Y`, 2,716 empty NPR_DT. It measured 138.7 s for the NMRC clean (mine: 138.5 s). It ran 76 tests and selftest on Python 3.14.6 and on 3.12.15 (SQLite 3.53.1), and showed the row-count check is real by breaking the clean insert in a scratch copy. Nothing in HCRIS was wrong; the findings were about configs HCRIS does not use. Fixed on this branch:

- Should fix: a config column named `p` made `rejected_by_reason` wrong (the alias lost to the column). The alias is now `_problem`, which no column can have. Test added.
- Should fix: a column named `reason` crashed `CREATE TABLE reject_` (traceback, exit 1). It is now a config error, exit 2, one line. Judgment call: the reject table must keep its `reason` column (the chunk says so), so the name is reserved instead. Test added.
- Should fix: 1,000 or more columns that can fail gave "Expression tree is too large" (traceback, exit 1). The reason text is now joined in a balanced tree. Tested with 1,100 number columns, and by hand with 1,990 required integer columns (works). A table of 1,998 columns, the most load accepts, cannot get its reject table (SQLite's 2,000 column limit) and now gives one line and exit 2. Tests added.
- Should fix: no test showed the row-count check can fail. New test breaks the clean insert so it loses a row and expects that check to fail with count 1.
- Nits: README now says a year-less date format gives year 1900. NPI note added above. STATUS wording follows the recheck.

Questions it raised, answered here as judgment calls: reserve `reason` at config time (done), and keep the date rule as the chunk wrote it, "strptime succeeds" (done, documented).

Evidence after the fixes: 81 tests OK, `selftest` PASS load and PASS clean. The HCRIS full run was repeated by the recheck (below).

**qa-peer recheck, 2026-11-21 (same agent, of commit `5c8ed9b`)**

Verdict: pass. All findings fixed, nothing new to fix. Its repro cases now work: the column `p` count is right, `reason` in any case gives exit 2 with one line, and 980, 1,010, 1,500, 1,990 and 1,997 number columns finish with reasons in column order (also with 150 to 300 character column names). 1,998 columns give exit 2 with one line from the clean stage; 1,999 or more are turned down by load. So 1,997 is the real maximum for a table that goes through clean. It reverted each fix in a scratch copy and the matching new test failed every time (alias, reserved name, deep chain, create-table catch, and a row-count check made always 0). It also ran the full HCRIS run from the committed code: exit 0, 3 min 17 s, same row counts, 12 of 12 checks pass, 0 duplicate keys, NMRC clean 140.6 s (RPT 0.4 s, ALPHA 22.2 s). Tests: 81 OK on Python 3.14.6 and on 3.12.15 (SQLite 3.53.1); selftest PASS load and PASS clean. Not checked: Python 3.13, SQLite 3.45.3, temp disk use of the NMRC group-bys, other fiscal years. Small leftover: after the 1,998-column exit 2, `clean_<table>` stays in `work.db` with no clean report. Harmless; not changed.

**Where to pick up**

Lauren reviews and merges the PR. Chunk 008 (model stage) follows the merge.
