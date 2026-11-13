# Test case: HCRIS provider identity

This was the repo's first problem statement (2026-11-01). Lauren replaced it on 2026-11-11 with the general framing in `PROBLEM.md`. It stays here as the first test case: HCRIS is dataset 1, and provider matching across releases is one of its semantic rules. Chunks 001 to 003 belong to this test case.

## Pain events

What actually happened, in Lauren's words.

- On the last HCRIS refresh, the longest part was making sure the providers I calculated CCRs and per diems for were the right ones. A couple of hospitals got new CCNs from CMS after converting to critical access hospitals (CAHs).
- The fragile, error-prone steps are mapping cost centers to revenue codes and mapping provider IDs. The rest is routine.
- The pain is mostly reloading a new release and producing new results, not first loads.
- This happens most at work.

## The bundle, split

1. **Provider identity across releases:** knowing which provider in the new release is which provider from the last run, including CCN changes.
2. **Cost center to revenue code mapping:** checking the mapping still holds for the new release.
3. **Rerunning CCRs and per diems** on the new release.

Lauren says 3 is routine. 1 and 2 are where the errors come from.

## Problem chosen (proposed)

When a new HCRIS release comes in, I can't quickly see which providers changed since the last run, so I re-check provider IDs by hand, and mistakes there flow straight into CCRs and per diems.

Start with provider identity, since it took the longest. Cost center mapping is the likely second problem, framed separately once this one works.

## Done when (proposed)

- [ ] Given last run's provider list and a new HCRIS release, a report lists every provider that is new, missing, or has a changed CCN, before any calculation runs.
- [ ] Each flagged provider shows enough evidence (name, address, dates) to confirm or reject a match in a minute or two.
- [ ] Confirmed matches are saved and reused, so the same match is never confirmed twice.
- [ ] Tested on real public cases: CAH conversions visible in public HCRIS are caught.

## Out of scope (proposed)

- A general data lake, catalog, or release system (that was daita).
- Analyses and methodology choices.
- Other datasets, until this works for HCRIS.
- Automatic matching without review. A person confirms every match.

## Constraints

- Built at home on public HCRIS only. No work or client data here.
- Has to run at work eventually. What's allowed there is an open question below.

## Open questions

- What does the current refresh look like, step by step, and where do the provider mappings live today? (chunk 001)
- Does CMS publish anything that links an old CCN to a new one? (chunk 002)
- How do CCN changes show up in HCRIS itself across years? (chunk 003)
- What can run on the work laptop: Python, which packages, or SAS/SQL only for some steps?
- Is the cost center to revenue code mapping standard, or set per client or state?
- Are there other datasets with the same reload pain, or is HCRIS the main one?
