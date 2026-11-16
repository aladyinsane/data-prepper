# 012: Trial on the remote desktop

- **Status:** Ready, after 010 is merged (after 011 is better)
- **Who:** Lauren (an agent can't reach the remote desktop)
- **Goal:** prove the package runs there with only what is installed, and on a file too big for memory. These are the fourth and fifth "Done when" in `PROBLEM.md`.
- **Inputs:** the `data_prepper/` folder and the `datasets/` folder from `main`. Access to the remote desktop. A large delimited file that is already there.
- **Output:** the answers below, pasted into this file's Handoff from home, or told to Claude in chat. Numbers only. No client names, hostnames, file names, column names, or data.

## Steps

1. Copy `data_prepper/` onto the remote desktop.
2. In the folder that holds it, run `python -m data_prepper selftest`. Note PASS or FAIL per stage and the two version lines it prints.
3. Check free disk in the folder you'll work in: `python -c "import shutil; print(round(shutil.disk_usage('.').free/1e9), 'GB free')"`.
4. Write a config for one large file already there. Text types for every column is enough; the point is size, not rules. Keep the config there. It does not come back to this repo.
5. Run it. Watch memory in Task Manager while it loads.

- **Done when:**
  - [ ] `selftest` passes on the remote desktop. If it fails, the failing stage and the error text are noted (errors from `selftest` contain only made-up data).
  - [ ] Free disk is noted.
  - [ ] A large file runs through. Noted: rough rows, rough columns, rough size in GB, minutes taken, peak memory, and the size of `work.db`.
  - [ ] If the run failed or was too slow to be usable, say which. That is what reopens the SAS fallback in the ADR.
- **Out of scope:** installing anything. Asking IT for anything. Bringing any data, config, or output back.

## Handoff

(not started)
