# Working in this repo

This repo uses a problem-first, chunked workflow. It keeps sessions short and keeps state in files, not chat history.

## Files

- `PROBLEM.md`: what we're solving and why. Changes only with Lauren's OK.
- `STATUS.md`: the board. Current state only, no log. Git history records what happened.
- `chunks/`: one file per piece of work. Copy `chunks/_TEMPLATE.md` for a new one.

## Rules

1. **One chunk per session.** At the start, read `STATUS.md`, `PROBLEM.md`, and the one chunk you're working on. Don't read other chunks unless that chunk links to them.
2. Mark the chunk "In progress" in `STATUS.md` before starting.
3. **Questions go to Lauren, not into guesses.** If you need a decision or information, add it under "Waiting on Lauren" in `STATUS.md`, note it in the chunk's Handoff, then stop or work on a part that doesn't depend on it.
4. **End every session with a handoff.** Fill in the chunk's Handoff section and update `STATUS.md`. If the work isn't finished, the handoff says exactly where to pick up.
5. **Too big? Split it.** If a chunk won't fit in one session, stop and split it into new chunk files instead of pushing on.
6. **New work becomes a new chunk.** Anything found along the way goes into `STATUS.md` as a new chunk (Ready or Waiting on Lauren), not into the current one.
7. Nothing outside `PROBLEM.md`'s scope without Lauren's OK.

## Data

- Public data only. No work or client data, names, or results in this repo.
- `C:\dev\daita` is read-only reference. Its HCRIS files under `data\bronze` can be read, never changed.
