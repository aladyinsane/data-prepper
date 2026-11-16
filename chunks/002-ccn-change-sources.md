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

- Wrote `docs/research/ccn-change-sources.md`.
- Answer: no public source links old and new CCNs for hospital to CAH conversions. Hospital Enrollments (PECOS) links them for Rural Emergency Hospital conversions only, through its `CAH OR HOSPITAL CCN` field. Hospital Change of Ownership explains mergers. Both confirmed from CMS data dictionaries, not from data samples.
- Not met: the Provider of Services file was a named candidate and is not settled. It has a "cross reference provider number" field whose definition could not be read. Update frequency is also unconfirmed for all three files. The first "Done when" box is only partly met because of this.
- Pick up: the note ends with a small test (three known CCN pairs looked up in one Provider of Services file) that would settle it. That needs a file download, so it needs Lauren's OK.
- Not checked by a fresh agent.
