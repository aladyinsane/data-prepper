# 004: Find out what the remote desktop can run

- **Status:** Waiting on Lauren
- **Who:** Lauren
- **Goal:** know exactly what the package is allowed to depend on.
- **Inputs:** access to the remote desktop. Nothing to copy over; the commands below can be typed by hand.
- **Output:** the answers, pasted into this file's Handoff section (or told to Claude in chat). No client names, hostnames, or data.
- **Done when:**
  - [ ] Python version and SQLite version: `python -c "import sys, sqlite3; print(sys.version); print(sqlite3.sqlite_version)"`
  - [ ] Installed libraries: `python -m pip list` (if pip is blocked, say so). Note whether `openpyxl` is there: pandas needs it to read .xlsx.
  - [ ] Whether a new folder of .py files can be copied onto the desktop and imported.
  - [x] Rough size of a "very large" dataset (rows, GB) and the format it arrives in. Answered 2026-11-13, see Handoff.
  - [ ] Memory on the remote desktop, roughly.
- **Out of scope:** installing anything, asking IT for anything.

## Handoff

**2026-11-13, partial (Lauren, on the repo status board):**

- Size: usually hundreds of thousands to several million rows; sometimes tens of millions of rows with hundreds of columns. File size in GB not given.
- Formats: usually CSV and other delimited text, Excel usually for supplemental data. SAS datasets and SQL Server tables possible later.

Still open: Python and SQLite versions, installed libraries (including openpyxl), whether a copied folder of .py files imports, memory.
