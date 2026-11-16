# Public sources that link an old CCN to a new one

Chunk 002, 2026-11-16. Web research, plus one test against the CMS data API. No data files are in the repo.

Not checked by anyone but the agent that wrote it.

## Recommendation

**Use the Provider of Services (POS) file as the first source, and the HCRIS dates-and-address method as the second. Neither is complete alone.**

- POS has a field, `CROSS_REF_PROVIDER_NUMBER`, that holds the other CCN. On the old CCN's row it holds the new one. It covers hospital to critical access hospital (CAH) conversions, goes back decades, and keeps terminated providers.
- It is not complete. Of the 105 changes found from HCRIS in chunk 003, POS agrees on 82, is blank for 22, and points somewhere else for 1.
- HCRIS is not complete either. It cannot see a hospital absorbed into another, a change too recent to have a cost report, or a change in the first file year. POS has those.
- So: take the link from POS when it is there, propose a link from HCRIS when POS is blank, and have a person confirm every one. A match both sources agree on needs the least attention.

## Sources checked

### 1. Provider of Services file (CMS, from the survey and certification system)

- **Link:** data.cms.gov. The hospital file is now titled "Provider of Services File - Quality Improvement and Evaluation System" (earlier quarters: "Hospital & Non-Hospital Facilities"). Each quarter is its own dataset with a CSV and an API. The catalog at `https://data.cms.gov/data.json` lists them.
- **Update frequency:** quarterly, per the CMS catalog entry.
- **Fields that matter:** `PRVDR_NUM` (the CCN), `CROSS_REF_PROVIDER_NUMBER`, `PGM_TRMNTN_CD` (termination code), `TRMNTN_EXPRTN_DT` (termination date), `ORGNL_PRTCPTN_DT` (first participation date), `FAC_NAME`, `ST_ADR`, `CITY_NAME`, `STATE_CD`, `PRVDR_CTGRY_CD` (`01` is hospital). There is also `RELATED_PROVIDER_NUMBER`, blank in every row looked at.
- **Does it link old to new CCN?** Yes, confirmed from the data on 2026-11-16 (Q3 2026 file, 13,598 hospital rows, 3,781 with a cross reference).
  - Mt. Graham Regional Medical Center: row 030068 is terminated 2021-09-27 and its cross reference is 031319. Row 031319 began 2021-09-28. This matches HCRIS to the day.
  - The link often runs both ways. Many active CAH rows point back to the old hospital number.
- **What the field's definition says:** not read. The CMS layout PDF could not be read as text. What is written here comes from the data, not the documentation.
- **Termination codes:** rows with a cross reference mostly have code `07` (1,784 rows), then `01` (947) and `00`, which is active (938). The meaning of each code was not looked up. `07` is the code on every confirmed type conversion checked.

**Tested against the 105 HCRIS candidates** (`scripts/pos_check.py`):

| Result | Pairs |
|---|---|
| POS agrees with the HCRIS pair | 82 |
| POS cross reference is blank | 22 |
| POS points to a different CCN | 1 |

- The 22 blanks include 9 hospital to CAH conversions and 5 of the likely Rural Emergency Hospital conversions. Most have a one-day gap, the same name, and the same address in HCRIS, and the POS termination date matches the HCRIS year end. They look like real changes that POS did not link.
- The one disagreement: 070040 (Hebrew Home & Hospital, West Hartford CT). HCRIS pairs it with 074017, a psychiatric number. POS points to 072008, a long-term number. Possibly the hospital split into two. Needs a person.

**Tested the other way.** POS has 327 hospital rows with a cross reference and a termination date in 2020 to 2025:

| What the HCRIS method did | Rows |
|---|---|
| New number is not a hospital CCN (it has a letter, mostly surgery centers) | 125 |
| New CCN already existed a year or more earlier (absorbed into an existing hospital) | 88 |
| Found by the HCRIS method | 82 |
| 2025 change, new CCN has probably not filed a cost report yet | 16 |
| Other miss, 2021 to 2024 | 8 |
| 2020 change, new CCN was already in the first HCRIS file year | 7 |
| New CCN is not a hospital row in POS | 1 |

- The 125 are not hospital-to-hospital changes and can be ignored for cost report work.
- The 88 are the mergers that HCRIS cannot see. These categories come from a simple rule in the script and were not checked one by one.
- Three of the 8 "other" misses are Texas hospitals whose new CCN starts with 67 while the old one starts with 45. **Texas has two CCN state prefixes.** The HCRIS script only compares CCNs with the same first two digits, so it missed them. Other states with a second prefix would have the same problem. This is a bug to fix in `scripts/ccn_changes.py`, listed as a follow-up.

**Limits:**

- The cross reference is blank for about one in five recent changes.
- Dates can differ from HCRIS. Evanston Regional (WY) is terminated 2024-12-06 in POS, but its last cost report runs to 2025-02-06.
- One quarter's file is a snapshot. Whether a blank gets filled in a later quarter was not tested.

### 2. Hospital Enrollments (CMS, from PECOS)

- **Link:** data.cms.gov, "Hospital Enrollments". Guidance read: [Hospital Data Guidance, version 1.6, July 2026](https://data.cms.gov/sites/default/files/2026-07/Hospital_Data_Guidance.pdf).
- **Update frequency:** not stated in the guidance. It refers to monthly versions, so monthly is likely. Not confirmed.
- **Fields that matter:** `CCN`, `ENROLLMENT ID`, `ASSOCIATE ID` (the PAC ID, which stays with the organization), `NPI`, names, practice address, `PROVIDER TYPE CODE` (hospital, REH, or CAH), and three REH fields: `REH CONVERSION FLAG`, `REH CONVERSION DATE`, `CAH OR HOSPITAL CCN`.
- **Does it link old to new CCN?** Yes, for Rural Emergency Hospital (REH) conversions only. Per the guidance, the last field holds the end-dated CCN of the hospital or CAH that was deactivated when it converted. Confirmed from the data dictionary, not from the data.
- **Limits:** nothing for other type changes. Current enrollments only, with no history. The REH fields exist from the July 2023 version on.
- **Use:** a second confirmation for the REH conversions where POS is blank. Also the only source found that says outright that a conversion is to an REH.

### 3. Hospital Change of Ownership (CMS, from PECOS)

- **Link:** data.cms.gov, "Hospital Change of Ownership". Read: [data dictionary, July 2026](https://data.cms.gov/sites/default/files/2026-07/Hospital_CHOW_Data_Dictionary.pdf) and [guidance, version 1.3, July 2026](https://data.cms.gov/sites/default/files/2026-07/Hospital_CHOW_Data_Guidance.pdf).
- **Update frequency:** not stated in the guidance. Not confirmed.
- **Fields that matter:** `CCN - BUYER`, `CCN - SELLER`, `EFFECTIVE DATE`, `CHOW TYPE CODE` (`CH` change of ownership, `AM` acquisition or merger, `CO` consolidation), plus enrollment ID, PAC ID, NPI, and names for both sides.
- **Does it link old to new CCN?** Partly, for ownership events only. In a plain change of ownership the guidance says the seller's number normally passes to the new owner, so there is nothing to link. In an acquisition or merger the seller's number is dissolved and only the buyer's remains. In a consolidation both are dissolved and a new one is assigned; the guidance calls these rare.
- **Limits:** only changes effective on or after 2016-01-01, only for currently approved enrollments. Type conversions are not ownership changes and are not here.
- **Use:** explains why a CCN was absorbed into another. Lower priority now that POS shows the same links.

### 4. HCRIS itself

Not a linking source. No field names the other CCN. See `docs/research/ccn-changes-in-hcris.md` for the dates-and-address method.

## Looked for and not found

- A CMS list of CCN changes or of CAH conversions published as its own file. POS is the nearest thing.
- The CCN number range for REHs. The data shows new numbers at xx0779 and above, and Texas REH-like numbers starting 67. Not confirmed from a CMS document.

Not looked at: state licensing lists, the Flex Monitoring Team's CAH list, the Sheps Center rural hospital lists, and NPPES as a bridge.

## What this means for the build

- Provider matching becomes: load POS as supplemental data, join the last run's provider list to it, and list every provider whose CCN has a cross reference or a termination date. That is a merge-stage job, which data-prepper already plans to do.
- The HCRIS method stays as the fallback for the blanks, and as a check on POS.
- Each saved match records its source: POS, HCRIS, both, or a person's decision.
- A person still confirms every match, as the test case says.

## Follow-ups (not chunks yet)

1. Fix the state-prefix bug in `scripts/ccn_changes.py` (Texas 45 and 67, and any other state with two prefixes).
2. Look up what the POS termination codes mean, and read the real definition of the cross reference field.
3. Check the 22 blanks against Hospital Enrollments (REH field, PAC ID, NPI).
4. Check whether an older or newer POS quarter fills any of the 22 blanks.
