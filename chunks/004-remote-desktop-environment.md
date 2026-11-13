# 004: Find out what the remote desktop can run

- **Status:** Done (2026-11-13)
- **Who:** Lauren
- **Goal:** know exactly what the package is allowed to depend on.
- **Inputs:** access to the remote desktop. Nothing to copy over; the commands below can be typed by hand.
- **Output:** the answers, pasted into this file's Handoff section (or told to Claude in chat). No client names, hostnames, or data.
- **Done when:**
  - [x] Python version and SQLite version: `python -c "import sys, sqlite3; print(sys.version); print(sqlite3.sqlite_version)"`. Answered 2026-11-13, see Handoff.
  - [x] Installed libraries: `python -m pip list` (if pip is blocked, say so). Note whether `openpyxl` is there: pandas needs it to read .xlsx. Answered 2026-11-13, see Handoff.
  - [x] Whether a new folder of .py files can be copied onto the desktop and imported. Answered 2026-11-13, see Handoff.
  - [x] Rough size of a "very large" dataset (rows, GB) and the format it arrives in. Answered 2026-11-13, see Handoff.
  - [x] Memory on the remote desktop, roughly. Answered 2026-11-13, see Handoff.
- **Out of scope:** installing anything, asking IT for anything.

## Handoff

**2026-11-13, partial (Lauren, on the repo status board):**

- Size: usually hundreds of thousands to several million rows; sometimes tens of millions of rows with hundreds of columns. File size in GB not given.
- Formats: usually CSV and other delimited text, Excel usually for supplemental data. SAS datasets and SQL Server tables possible later.

**2026-11-13, second pass (Lauren, in chat):**

- Python: 3.13.2, 64-bit (AMD64), Windows build (MSC v.1942).
- SQLite: 3.45.3, and `sqlite3` imports.
- Installed libraries (`pip list` ran, so pip itself isn't blocked for listing): numpy, pandas, pip, pyodbc, python-dateutil, pytz, six, tzdata. **No openpyxl**, so pandas can't read .xlsx there as-is. Versions not recorded. Whether `pip install` works wasn't tested and is out of scope.
- Copied folder of .py files: copying a folder onto the desktop works, and importing a module from it works.
- Memory: 64 GB installed RAM. Memory actually free to one session (it's a remote desktop, possibly shared) not measured.

Nothing left open. Chunk 005 (package-design ADR) can start from these answers.
