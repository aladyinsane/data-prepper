# Public sources that link an old CCN to a new one

Chunk 002, 2026-11-16. Web research only. No data files were downloaded.

Not checked by anyone but the agent that wrote it.

## Recommendation

**No single public source links old and new CCNs for the case that matters most (a hospital becoming a critical access hospital).** Do the matching from HCRIS itself, the way `docs/research/ccn-changes-in-hcris.md` shows, and use the two CMS enrollment files below to confirm the kinds of change they cover.

- Use **Hospital Enrollments** to confirm Rural Emergency Hospital (REH) conversions. It has a field holding the old CCN. This is the only direct old-to-new link found.
- Use **Hospital Change of Ownership** to explain a change that came from a merger or consolidation.
- **Provider of Services** is the best remaining lead and is not settled. It has a field called "cross reference provider number", but its definition was not read. One cheap test would settle it (see the end).

## Sources checked

### 1. Hospital Enrollments (CMS, from PECOS)

- **Link:** data.cms.gov, "Hospital Enrollments". Guidance read: [Hospital Data Guidance, version 1.6, July 2026](https://data.cms.gov/sites/default/files/2026-07/Hospital_Data_Guidance.pdf).
- **Update frequency:** not stated in the guidance. It refers to monthly versions ("the January 2023 version"), so monthly is likely. Not confirmed.
- **Fields that matter:** `CCN`, `ENROLLMENT ID`, `ASSOCIATE ID` (the PAC ID, which stays with the organization), `NPI`, `ORGANIZATION NAME`, `DOING BUSINESS AS NAME`, practice address, `PROVIDER TYPE CODE` (hospital, REH, or CAH), and three REH fields: `REH CONVERSION FLAG`, `REH CONVERSION DATE`, `CAH OR HOSPITAL CCN`.
- **Does it link old to new CCN?** Yes, for REH conversions only. Per the guidance, the last field holds the end-dated CCN of the hospital or CAH that was deactivated when it converted. If there are several, they are joined with `|`. Confirmed from the data dictionary (Appendix A), not from a sample of the data.
- **Limits:**
  - Nothing equivalent for a hospital becoming a CAH, or any other type change.
  - Current enrollments only. The guidance says the files hold no historical enrollment information. A hospital that later closed drops out.
  - The REH fields exist from the July 2023 version on.
- **Why it still helps beyond REHs:** the PAC ID and NPI may stay the same across a CCN change. If an old and a new CCN share a PAC ID or NPI in two different monthly versions, that is outside confirmation of a match. This was not tested.

### 2. Hospital Change of Ownership (CMS, from PECOS)

- **Link:** data.cms.gov, "Hospital Change of Ownership". Read: [data dictionary, July 2026](https://data.cms.gov/sites/default/files/2026-07/Hospital_CHOW_Data_Dictionary.pdf) and [guidance, version 1.3, July 2026](https://data.cms.gov/sites/default/files/2026-07/Hospital_CHOW_Data_Guidance.pdf).
- **Update frequency:** not stated in the guidance. Not confirmed.
- **Fields that matter:** `CCN - BUYER`, `CCN - SELLER`, `EFFECTIVE DATE`, `CHOW TYPE CODE` (`CH` change of ownership, `AM` acquisition or merger, `CO` consolidation), plus enrollment ID, PAC ID, NPI, and names for both sides.
- **Does it link old to new CCN?** Partly, and only for ownership events.
  - In a plain change of ownership (`CH`, the most common kind) the guidance says the seller's number normally stays as it is and passes to the new owner. So buyer and seller CCN are usually the same and there is nothing to link.
  - In an acquisition or merger (`AM`) the seller's number is dissolved and only the buyer's remains. This is the row that explains a CCN that simply stops, which the HCRIS method cannot see.
  - In a consolidation (`CO`) both old numbers dissolve and a new one is assigned. The guidance says these are rare.
- **Limits:** only changes effective on or after 2016-01-01, only for enrollments that are currently approved, and a small number of records with data problems are left out. Type conversions are not ownership changes and are not here.

### 3. Provider of Services file (CMS, from the survey and certification system)

- **Link:** data.cms.gov, "Provider of Services File - Hospital & Non-Hospital Facilities". A record layout exists: [September 2022 layout](https://data.cms.gov/sites/default/files/2022-10/58ee74d6-9221-48cf-b039-5b7a773bf39a/Layout%20Sep%2022%20Other.pdf).
- **Update frequency:** quarterly, going by the layout file names. Not confirmed from a CMS statement.
- **Fields that matter:** a search result for the layout lists `CROSS_REF_PROVIDER_NUMBER`, 10 characters, labelled "Cross reference provider number". The file is also known to carry name, address, a termination code, and termination and participation dates, but those were not read from the layout in this chunk.
- **Does it link old to new CCN?** **Not confirmed.** The layout PDF could not be read as text here, so the field's definition is unknown. It may hold the related CCN after a change, or it may be something else entirely. Do not rely on it until tested.
- **Why it is still the best lead:** unlike the two enrollment files, this one keeps terminated providers, so an old CCN should still be in it.

### 4. HCRIS itself

Not a linking source, but the one that works. See `docs/research/ccn-changes-in-hcris.md`: 105 likely changes found from dates and addresses, 47 of them hospital to CAH. No field in HCRIS names the other CCN.

## Looked for and not found

- A CMS list or crosswalk of CCN changes, or of CAH conversions with old and new numbers. None turned up in search. That is not proof none exists.
- The CCN number range for REHs. One unofficial page says the CCN format has a marker for emergency hospitals; no CMS document was found that gives a range. The HCRIS data suggests new numbers at xx0779 and above, unconfirmed.

Not looked at: state licensing lists, the Flex Monitoring Team's CAH list, the Sheps Center rural hospital lists, and NPPES as a bridge. These are leads for a later chunk if the test below fails.

## One cheap test that would settle Provider of Services

Download one recent Provider of Services hospital file (outside the repo) and look up three known pairs from chunk 003:

| Old CCN | New CCN | Kind |
|---|---|---|
| 030068 | 031319 | hospital to CAH (Mt. Graham, AZ) |
| 041304 | 040780 | CAH to likely REH (Eureka Springs, AR) |
| 110189, then 110780 | 111338 | a chain (Fannin Regional, GA) |

If the cross reference field on either row of a pair holds the other CCN, Provider of Services is the linking source and the recommendation above changes. The same three pairs can test whether PAC ID or NPI carries across in Hospital Enrollments.

## What this means for the build

- Matching stays "the script proposes with evidence, a person confirms", as the test case already says.
- The confirm screen can show outside evidence when it exists: an REH row from Hospital Enrollments, or a merger row from Change of Ownership.
- Saved matches need to record where the confirmation came from, since some will be HCRIS-only.
