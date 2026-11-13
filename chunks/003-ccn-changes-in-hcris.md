# 003: Find how CCN changes show up across HCRIS years

- **Status:** Ready
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

(not started)
