# 011: NPPES by config only

- **Status:** Ready, after 010 is merged and Lauren has downloaded the file
- **Who:** agent (a cheaper model is fine)
- **Goal:** prove a differently shaped dataset runs through all five stages by adding config and rule files only. This is the second "Done when" in `PROBLEM.md`. NPPES is also wide (about 330 columns, millions of rows), so this is the first real test of a large, wide file.
- **Inputs:**
  - `docs/adr/0001-package-design.md` and the finished package.
  - "Rules for all build chunks" in `chunks/006-skeleton-and-load.md`. They apply here.
  - The public NPPES monthly file from CMS, downloaded by Lauren to a folder outside this repo. She gives the path. The agent does not download it.
  - The file layout from the documentation inside the NPPES zip. Take column names and formats from there; don't guess.
- **Output:**
  - `datasets/nppes/dataset.json` and `datasets/nppes/rules/`.
  - A findings section in this file's Handoff.
  - No changes under `data_prepper/`.

## What to build

- A config for the main NPI file: every column named and typed, `npi` as the key.
- Two or three structural check rules, for example: an entity type code outside its allowed values; a deactivation date earlier than the enumeration date. No methodology rules.
- One merge that makes sense within NPPES's own public files (for example, a second file from the same zip joined on NPI). If no second file fits, say so and leave `merge` empty; don't invent a supplemental table.
- One summary, for example a count of providers by entity type and practice state.

## The rule that matters

If something in `data_prepper/` has to change for NPPES to run, **stop**. Don't change it. Write in the Handoff exactly what was needed and why. That is a finding about the design, and fixing it is a new chunk Lauren decides on.

- **Done when:**
  - [ ] `python -m data_prepper run datasets/nppes --data-root <NPPES folder>` runs all five stages and writes five reports.
  - [ ] `git diff --stat main -- data_prepper/` shows nothing.
  - [ ] Rows loaded equals a line count of the file made a different way, minus the header row.
  - [ ] In every stage report, rows in and rows out add up as that stage's checks require.
  - [ ] The Handoff has: source file size, rows, columns, seconds per stage, peak memory, and the final size of `work.db` next to the source size. These are the real numbers behind the ADR's estimates for wide files.
  - [ ] Any rejects, failed checks, or surprises are listed with counts. Nothing is loosened to make them go away.
- **Out of scope:** changing shared code. Analysis of NPPES. Joining NPPES to HCRIS.

## Handoff

(not started)
