# How CCN changes show up in HCRIS

Chunk 003, 2026-11-16. Public data only: HCRIS hospital (2552-10) file years FY2020 to FY2025, as downloaded by daita on 2026-09-28.

Script: `scripts/ccn_changes.py`. Full list of pairs it found: `docs/research/ccn-change-candidates.csv` (105 rows).

Not checked by anyone but the agent that wrote it.

## Short version

- A CCN change is easy to see in HCRIS. The old CCN files a short final cost report, and the new CCN's first cost report begins the next day, at the same street address, usually under the same name.
- The script found 105 likely changes across the six file years. In 96 of them the new CCN's first fiscal year begins exactly one day after the old CCN's last one ends.
- No old CCN matched more than one new CCN, and no new CCN matched more than one old one.
- HCRIS has no field that says "this CCN used to be that CCN". The link has to be worked out from dates and addresses.
- Checked against CMS's Provider of Services file on 2026-11-16: it agrees on 82 of the 105, is blank for 22, and disagrees on 1. Details in `docs/research/ccn-change-sources.md`.
- Known bug: the script only compares CCNs with the same first two digits, and some states have two prefixes (Texas uses 45 and 67). At least three Texas changes were missed for this reason.

## What HCRIS has to match on

Everything comes from two places.

| Field | Where | Use |
|---|---|---|
| CCN | RPT file, provider number | The thing that changes |
| Fiscal year begin and end | RPT file | The strongest signal: old ends, new begins the next day |
| Name | ALPHA file, worksheet S-2 Part I (`S200001`), line 3 column 1 | Usually identical. Cut off at 36 characters. |
| Street | same worksheet, line 1 column 1 | Usually identical, sometimes abbreviated differently |
| City, state, ZIP, county | same worksheet, line 2 columns 1 to 4 | ZIP is sometimes 5 digits, sometimes 9 |
| Date certified | same worksheet, line 3 column 5 | Mixed. See below. |

## What the script does

1. Reads RPT and the S-2 lines of ALPHA straight from each year's zip. Keeps one record per CCN per file year.
2. Lists CCNs that are in one file year and not the next, in both directions.
3. Treats a CCN as "new" if it is missing from the first file year (FY2020).
4. Pairs any CCN with a new CCN in the same state when the new one's first fiscal year begins between 31 days before and 400 days after the old one's last fiscal year ends, and the two share either the same street and ZIP, or the same ZIP (or city) and a near-identical name.
5. Flags a pair when the old CCN's last year end is within about 18 months of the newest data, because that hospital may simply not have filed its next report yet.

## Counts

CCNs per file year: 5,990 (FY2020), 5,984, 6,004, 6,046, 6,026, and 3,253 (FY2025). **FY2025 is about half complete.** Reports arrive late, so "missing from the latest year" means nothing on its own.

Missing from the next year, and new in the next year:

| From | To | Not in the next year | New |
|---|---|---|---|
| FY2020 | FY2021 | 72 | 66 |
| FY2021 | FY2022 | 49 | 69 |
| FY2022 | FY2023 | 76 | 118 |
| FY2023 | FY2024 | 122 | 102 |
| FY2024 | FY2025 | 2,836 | 63 |

The 105 pairs by type of CCN. The type comes from the last four digits of the CCN: 0001 to 0879 short-term, 1300 to 1399 critical access (CAH), 2000 to 2299 long-term, 3025 to 3099 rehabilitation, 4000 to 4499 psychiatric.

| Old type to new type | Pairs |
|---|---|
| Short-term to CAH | 47 |
| Short-term to short-term | 25 |
| CAH to short-term | 15 |
| Short-term to long-term | 8 |
| Short-term to psychiatric | 7 |
| Psychiatric to psychiatric | 2 |
| Rehabilitation to psychiatric | 1 |

Other counts:

- 100 pairs share the same street and ZIP. The other 5 share the ZIP and a near-identical name, with small differences in how the street was typed.
- 92 pairs have exactly the same name.
- 96 pairs have a one-day gap. 4 have a gap of 2 to 31 days. 5 have a longer gap (139 to 335 days).
- 21 pairs are flagged because the old CCN may still be filing.

## Real examples

**Short-term to CAH.** The case from the original problem statement.

| | Old | New |
|---|---|---|
| Mt. Graham Regional Medical Center, Safford AZ | 030068, last year ends 2021-09-27 | 031319, first year begins 2021-09-28 |
| Sevier County Medical Center, De Queen AR | 040162, ends 2023-08-06 | 041333, begins 2023-08-07 |
| Mena Medical Center, Mena AR | 040015, ends 2024-11-12 | 041334, begins 2024-11-13 |

For Mt. Graham, the old CCN's FY2021 report covers 2021-01-01 to 2021-09-27, and the new CCN's first report covers 2021-09-28 to 2021-12-31. A calendar-year calculation for 2021 needs both.

**CAH to a new number in the short-term range.**

| | Old | New |
|---|---|---|
| Eureka Springs Hospital, Eureka Springs AR | 041304, ends 2023-11-30 | 040780, begins 2023-12-01 |
| Mahnomen Health Center, Mahnomen MN | 241300, ends 2024-04-30 | 240779, begins 2024-05-01 |

**A chain: one hospital, three CCNs.** Fannin Regional Hospital, Blue Ridge GA: 110189 ends 2023-06-30, 110780 runs 2023-07-01 to 2025-06-15, then 111338 (a CAH number, now named Blue Ridge Medical Center) begins 2025-06-16. Saved matches have to allow a new CCN to become an old one later.

## The new numbers at 0779 and above

39 of the 105 pairs have a new CCN whose last four digits are 0779 or higher: all 15 "CAH to short-term" pairs and 24 of the 25 "short-term to short-term" pairs. The earliest begins 2023-02-01. One is named "Irwin County REH".

Rural Emergency Hospitals (REHs) started in January 2023, and CMS documentation confirms a hospital or CAH that converts to an REH gets a new CCN while the old one is end-dated (see `docs/research/ccn-change-sources.md`). So these 39 are very likely REH conversions.

What is not confirmed: that 0779 and above is a range reserved for REHs. 43 CCNs in that range were already filing in FY2020, before REHs existed. Treat "0779 or higher and first seen in 2023 or later" as a hint, not a rule.

One pair runs the other way: 250779 to 250174 (Alliance Healthcare System, Holly Springs MS), with a 198-day gap. That looks like an REH going back to being a hospital, but it is a guess.

## What made matching easy

- The one-day gap. It is by far the best signal, and it comes from two fields that are always filled in.
- Same street and ZIP. True for 100 of 105.
- Staying inside one state (the first two digits of the CCN) keeps the comparison small and avoids look-alike names in other states.

## What was ambiguous or weak

- **Names change at the same time as the CCN.** 9 pairs have names that differ a lot (similarity under 0.85), for example Montevista Hospital to Desert Winds Hospital, or Llano Memorial Hospital to Mid Coast Medical Center-Central. Matching on name alone would miss them. Address and dates caught them.
- **Long gaps.** The 5 pairs with gaps over a month are closures followed by a reopening, sometimes under a new owner and type (Tampa General Rehabilitation Hospital to Tampa Behavioral Hospital, 139 days). Whether that is "the same provider" is a judgment for a person, not the script.
- **Date certified is unreliable.** In 74 pairs the new CCN's date certified equals its first fiscal year begin date, which is useful confirmation. In the other 31 the new CCN carries an older date, sometimes decades old (07/01/1966 shows up several times). It can support a match but can't be required.
- **Recent years.** 21 pairs involve an old CCN whose last report is recent. Most are one-day gaps and look real, but a hospital that is still open and simply hasn't filed, sharing an address with a newly certified unit, would look the same.
- **Street text.** "ONE MEDICAL PLAZA" against "1 MEDICAL PLAZA", "PATTERSON PARKWAY" against "PATTERSON PKWY", and one probable typo ("SOUTH FOURTH STREET" against "SOUTH FORK STREET"). The script handles common abbreviations only.

## What this does not find

- **Mergers.** When one hospital is absorbed into another that keeps its own CCN, there is no new CCN to pair with. The old one just stops.
- **Changes before FY2020 or after the newest report.** Only six file years were read.
- **Changes where the address also changed.** A move to a new building at the same time as a new CCN would be missed unless the name and ZIP stayed the same.
- **How many were missed.** 304 CCNs were last seen in FY2023 or earlier, and 62 of those have a candidate. The other 242 are closures, mergers, or misses, and this chunk did not sort them.

## For the build

- This is evidence that the first "Done when" in `docs/test-cases/hcris-provider-identity.md` is reachable from HCRIS alone: new, missing, and changed CCNs can be listed before any calculation runs.
- The 105 pairs are a ready test set for "CAH conversions visible in public HCRIS are caught".
- A person still confirms each match. The script's job is to put the evidence in one row.
- A late-filing year must not be read as "provider disappeared".
