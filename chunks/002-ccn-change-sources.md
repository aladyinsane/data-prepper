# 002: Find public sources that link old and new CCNs

- **Status:** Waiting on Lauren (review)
- **Who:** agent
- **Goal:** find out whether CMS publishes anything that ties a provider's old CCN to its new one (for example after a CAH conversion or change of ownership).
- **Inputs:** web search and CMS sites (data.cms.gov, cms.gov). Candidates to check include the Provider of Services (POS) file and any hospital ownership or enrollment datasets, but don't assume any of them has the link until you see the fields.
- **Output:** `docs/research/ccn-change-sources.md`
- **Done when:**
  - [ ] Each candidate source has: link, update frequency, the fields that matter, and whether it actually links old to new CCN, confirmed by looking at the data dictionary or a sample.
  - [ ] A short recommendation: which source to use, or "none, matching has to be done another way."
- **Out of scope:** downloading full files into the repo, building anything.

## Handoff

**2026-11-16 (agent):**

- Wrote `docs/research/ccn-change-sources.md` and `scripts/pos_check.py`.
- Answer: the Provider of Services (POS) file links old and new CCNs through its `CROSS_REF_PROVIDER_NUMBER` field, including hospital to CAH conversions. Confirmed from the data (Q3 2026, read through the CMS data API with Lauren's OK, nothing saved in the repo).
- It is not complete: of the 105 changes chunk 003 found in HCRIS, POS agrees on 82, is blank for 22, and disagrees on 1. HCRIS in turn cannot see mergers, which POS has. Recommendation: POS first, HCRIS as fallback, a person confirms.
- Hospital Enrollments (PECOS) links REH conversions only. Hospital Change of Ownership covers mergers. Both confirmed from data dictionaries only.
- Not done: the meaning of POS termination codes and the official definition of the cross reference field were not read. Update frequency is unconfirmed for the two PECOS files.
- Found a bug in chunk 003's script: states with two CCN prefixes (Texas 45 and 67) are not compared across prefixes.
- Follow-ups are listed at the end of the note. Not checked by a fresh agent.
