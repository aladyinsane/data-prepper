"""selftest: build a small made-up dataset, run every stage, compare to known answers.

Needs no data files, so it is the check to run on the remote desktop.
Later chunks add their stage to CHECKS.
"""

import contextlib
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

from . import run as run_mod

CLINICS = 20
VISITS = 300
BAD_VISITS = (7, 150, 299)  # 1-based line numbers: too few, too many, empty-ish


def make_dataset(folder):
    """Write dataset.json and input files under folder. Returns known answers."""
    folder = Path(folder)
    (folder / "input").mkdir(parents=True)
    config = {
        "dataset": "selftest",
        "tables": {
            "clinics": {
                "source": {"path": "input/clinics.csv", "delimiter": ",", "header": True, "encoding": "utf-8"},
                "columns": {"clinic_id": {"type": "text"}, "county": {"type": "text"}},
                "key": ["clinic_id"],
            },
            "visits": {
                "source": {"path": "input/visits.zip", "member": "visits.csv", "delimiter": ",",
                           "header": False, "encoding": "utf-8"},
                "columns": {"visit_id": {"type": "text"}, "clinic_id": {"type": "text"},
                            "paid_amount": {"type": "number"}},
            },
        },
    }
    (folder / "dataset.json").write_text(json.dumps(config), encoding="utf-8")
    with open(folder / "input" / "clinics.csv", "w", encoding="utf-8", newline="") as f:
        f.write("clinic_id,county\r\n")
        for i in range(1, CLINICS + 1):
            f.write(f"C{i:02d},County {i % 4}\r\n")
    lines = []
    for i in range(1, VISITS + 1):
        if i == BAD_VISITS[0]:
            lines.append(f"V{i},C01")  # too few fields
        elif i == BAD_VISITS[1]:
            lines.append(f"V{i},C02,10.5,extra")  # too many
        elif i == BAD_VISITS[2]:
            lines.append("")  # empty line
        else:
            lines.append(f' V{i},C{i % CLINICS + 1:02d},{i}.25')  # leading space must survive
    with zipfile.ZipFile(folder / "input" / "visits.zip", "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("visits.csv", "\r\n".join(lines) + "\r\n")
    return {
        "clinics": (CLINICS, CLINICS, 0),
        "visits": (VISITS, VISITS - len(BAD_VISITS), len(BAD_VISITS)),
    }


def check_load(run, code, known, folder):
    """Compare the load report and raw tables to the known answers. Returns a list of problems."""
    problems = []
    report = json.loads((run.reports_dir / "01-load.json").read_text(encoding="utf-8"))
    for name, (read, loaded, bad) in known.items():
        t = report["tables"][name]
        got = (t["rows_read"], t["rows_loaded"], t["rows_bad"])
        if got != (read, loaded, bad):
            problems.append(f"{name}: rows read/loaded/bad {got}, expected {(read, loaded, bad)}")
    zip_sha = hashlib.sha256((Path(folder) / "input" / "visits.zip").read_bytes()).hexdigest()
    if report["tables"]["visits"]["files"][0]["sha256"] != zip_sha:
        problems.append("visits: zip hash does not match")
    con = sqlite3.connect(run.db_path)
    try:
        n_raw = con.execute('select count(*) from "raw_visits"').fetchone()[0]
        n_bad = con.execute('select count(*) from "badrows_visits"').fetchone()[0]
        first = con.execute('select _row, visit_id from "raw_visits" order by _row limit 1').fetchone()
        bad_rows = [r[0] for r in con.execute('select _row from "badrows_visits" order by _row')]
    finally:
        con.close()
    if (n_raw, n_bad) != (VISITS - len(BAD_VISITS), len(BAD_VISITS)):
        problems.append(f"visits: table counts {(n_raw, n_bad)}")
    if first != (1, " V1"):
        problems.append(f"visits: first row {first!r}, expected (1, ' V1') with the space kept")
    if bad_rows != list(BAD_VISITS):
        problems.append(f"visits: bad row line numbers {bad_rows}, expected {list(BAD_VISITS)}")
    # visits has bad rows on purpose, so the run must stop with exit code 1
    if code != 1:
        problems.append(f"exit code {code}, expected 1 (visits has bad rows on purpose)")
    return problems


CHECKS = [("load", check_load)]


def main():
    print(f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}")
    with tempfile.TemporaryDirectory(prefix="data_prepper_selftest_") as tmp:
        folder = Path(tmp) / "selftest_dataset"
        known = make_dataset(folder)
        try:
            with contextlib.redirect_stdout(io.StringIO()):  # hide the run's own progress lines
                code, run = run_mod.execute(folder, runs_root=Path(tmp) / "runs")
        except Exception as e:  # selftest must report, not crash
            print(f"FAIL load: run stopped: {e}")
            return 1
        print("(the made-up visits table has 3 bad rows on purpose, so the run stops with exit code 1)")
        ok = True
        for stage, fn in CHECKS:
            problems = fn(run, code, known, folder)
            if problems:
                ok = False
                print(f"FAIL {stage}")
                for p in problems:
                    print(f"  {p}")
            else:
                print(f"PASS {stage}")
    return 0 if ok else 1
