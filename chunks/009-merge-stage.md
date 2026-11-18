# 009: The merge stage

- **Status:** Ready, after 008 is merged
- **Who:** agent (a cheaper model is fine)
- **Goal:** join supplemental tables onto a main table without losing or multiplying rows, and report how well each join matched.
- **Inputs:**
  - `docs/adr/0001-package-design.md` and the code from chunks 006 to 008.
  - "Rules for all build chunks" in `chunks/006-skeleton-and-load.md`. They apply here.
  - Public HCRIS FY2023, same file as chunk 006.
- **Output:**
  - `data_prepper/merge.py`, wired into `run` after model, and into `selftest`.
  - The `merge` section in `datasets/hcris/dataset.json`.
  - Tests in `tests/`.

## What to build

**Config.** `merge` is a list. Each entry:

```json
{"left": "visits", "right": "clinics", "on": ["clinic_id"], "expect": "many_to_one",
 "columns": ["county"], "min_match_rate": 0.99}
```

- `left`, `right`: table names from `tables`. Any table can be a right side; there is no separate "supplemental" kind.
- `on`: the join columns. Either a list of names that are the same on both sides (`["clinic_id"]`), or, when the names differ, an object mapping each left column to its right column (`{"clinic_id": "site_id", "year": "fiscal_year"}`). The result keeps the left side's names; the right side's join columns are not brought over.
- `expect`: `many_to_one` or `one_to_one`. Nothing else in version 1. A many-to-many join is not supported.
- `columns`: optional. The right-side columns to bring over. Default: every right column except the `on` columns, `_file`, and `_row`.
- `min_match_rate`: optional, between 0 and 1.
- Config errors (exit code 2, before anything runs): an unknown table or column (on either side of `on`), an `expect` value that isn't one of the two, or a brought-over column whose name already exists on the left.

**How a join runs.** Entries run in the order listed. The first join on a left table reads `model_<left>` and writes `merged_<left>`; later joins on the same left table read and replace `merged_<left>`. The right side is always `model_<right>`.

- Every join is a left join. All left rows are kept. Left rows with no match get NULL in the brought-over columns.
- A NULL in any `on` column never matches.
- Before joining, create an index on the right side's `on` columns.
- A table that is never a left side gets no `merged_` table.

**Checks per join**, run in this order. The first three run before the join, and if one fails with severity error the join is not done.

1. Right side is unique on the `on` columns (error). This is the guard against rows multiplying.
2. For `one_to_one` only: left side is unique on the `on` columns (error).
3. Join columns have the same stored type on both sides (error). Compare the set of `typeof()` values of each `on` column on each side, ignoring null. SQLite treats the integer `1` and the text `'1'` as different, so a type mismatch gives zero matches without any error. This check is what catches it.
4. Rows after = rows before (error).
5. Match rate is at least `min_match_rate`, when set (error).

**Report `04-merge.json`**, one entry per join: `left`, `right`, `on`, `expect`, `rows_before`, `rows_after`, `left_rows_matched`, `left_rows_unmatched`, `left_rows_null_key`, `match_rate` (matched divided by rows before), `right_rows_unused` (right rows no left row matched), a sample of up to 20 unmatched key values with their row counts, the checks, and seconds taken.

After all joins, if any error check failed, write the report and exit with code 1.

**HCRIS.** One join: NMRC (left) to RPT (right) on the report record number, `many_to_one`, bringing over the provider number and the fiscal year begin and end dates, `min_match_rate` 1.0. Use the column names already in `datasets/hcris/dataset.json`.

- **Done when:**
  - [ ] On made-up data, each of these gives exactly the expected table and report: a clean many-to-one join; a join where the column names differ between the two sides; unmatched left rows; null keys on the left; unused right rows; two joins in a row on the same left table.
  - [ ] On made-up data, each of these stops with the right failed check and no `merged_` table written for that join: a duplicate key on the right; a `one_to_one` join with a duplicate on the left; an integer key on one side and a text key on the other; a match rate under the minimum.
  - [ ] Each kind of config error gives a one-line message and exit code 2.
  - [ ] HCRIS FY2023 runs load through merge from one command. `merged_nmrc` has 19,574,053 rows, the match rate is 1.0, and 0 rows are unmatched. These equal the numbers in the ADR's benchmark. If they don't, stop and say so.
  - [ ] Seconds taken for the HCRIS join is in the Handoff.
  - [ ] `python -m unittest discover tests` and `python -m data_prepper selftest` both pass, with merge added to selftest.
- **Out of scope:** inner, right, or full joins. Many-to-many joins. Fuzzy or approximate matching. Provider matching across releases (the `provider-changes` repo).

## Handoff

(not started)
