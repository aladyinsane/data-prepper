# 003: Find how CCN changes show up across HCRIS years

- **Status:** Waiting on Lauren (review)
- **Who:** agent
- **Goal:** see what a CCN change looks like in HCRIS itself, using real public cases.
- **Inputs:** HCRIS FY2020 to FY2025 files in `C:\dev\daita\data\bronze\cms-hcris-hospital-2552-10` (read only). CAHs use their own CCN range, which is worth checking as a lead.
- **Output:** a small script in `scripts/` plus `docs/research/ccn-changes-in-hcris.md` with findings and a few concrete example providers.
- **Done when:**
  - [ ] The script lists providers that appear or disappear between years.
  - [ ] It suggests likely matches between disappearing and appearing providers using whatever identifying fields HCRIS has (name, address, and so on), with the evidence shown.
  - [ ] At least two real CCN changes are found and written up, ideally CAH conversions.
  - [ ] The note says which fields made matching easy and which cases were ambiguous.
- **Out of scope:** a polished tool, saving confirmed matches, any change to daita.

## Handoff

**2026-11-16 (agent):**

- Wrote `scripts/ccn_changes.py` (standard library, reads the daita zips read-only) and `docs/research/ccn-changes-in-hcris.md`. The 105 candidate pairs are in `docs/research/ccn-change-candidates.csv`.
- Main finding: a CCN change shows up as the old CCN's last fiscal year ending the day before the new CCN's first one begins, at the same street address. 96 of 105 pairs have that one-day gap. 47 are short-term to CAH.
- Found along the way: 39 pairs are very likely Rural Emergency Hospital conversions (new since 2023), and one hospital changed CCN twice. Both matter for how confirmed matches get saved.
- To run: `python scripts/ccn_changes.py C:\dev\daita\data\bronze\cms-hcris-hospital-2552-10\files --out <any folder outside the repo>`. About a minute.
- Not checked by a fresh agent. None of the pairs is confirmed against an outside source; chunk 002 found one CMS file that can confirm the REH ones.
- The script's first version missed conversions in the newest year and the second step of a chain. Fixed, and described in the note. Thresholds (31 days before, 400 after, name similarity 0.85) are my choices, not tuned.
- Question for Lauren: do the Mt. Graham, Sevier County, and Mena examples look like the kind of case you hit at work? One line is enough.
