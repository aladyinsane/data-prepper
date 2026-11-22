"""selftest: build small made-up datasets, run every stage, compare to known answers.

Needs no data files, so it is the check to run on the remote desktop.
Two datasets: one with rows of the wrong field count (the run stops after load,
on purpose), and one for the clean stage, which runs every stage to the end.
Later chunks add their stage to the second one.
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


# The clean dataset. Line numbers: header 1, then one row per line.
CLEAN_FILE = (
    "id,day,amount,n\n"
    "A1,2023-01-05,10.5,2\n"
    " A2 ,2023-01-06, 7 ,3\n"  # spaces around values are removed
    "A3,2023-01-07,abc,1\n"  # bad number
    "A4,2023-13-01,5,1\n"  # bad date
    ",2023-01-08,5,1\n"  # missing required value
    "A6,2023-02-30,12abc,1\n"  # two problems
    "A7,,,\n"  # empty values are null, not a failure
    "A8,2023-01-09,3,1\n"
    "A8,2023-01-09,3,1\n"  # an exact copy: counted, kept
)
CLEAN_KNOWN = {"rows_in": 9, "rows_out": 5, "rows_rejected": 4, "exact_duplicate_rows": 1, "duplicate_keys": 1}


def make_clean_dataset(folder):
    folder = Path(folder)
    folder.mkdir(parents=True)
    config = {
        "dataset": "selftest_clean",
        "tables": {
            "t": {
                "source": {"path": "t.csv", "delimiter": ",", "header": True, "encoding": "utf-8"},
                "columns": {
                    "id": {"type": "text", "required": True},
                    "day": {"type": "date", "format": "%Y-%m-%d"},
                    "amount": {"type": "number"},
                    "n": {"type": "integer"},
                },
                "key": ["id"],
            }
        },
    }
    (folder / "dataset.json").write_text(json.dumps(config), encoding="utf-8")
    (folder / "t.csv").write_text(CLEAN_FILE, encoding="utf-8", newline="")


def check_clean(run, code):
    """Compare the clean report and tables to the known answers. Returns a list of problems."""
    problems = []
    report = json.loads((run.reports_dir / "02-clean.json").read_text(encoding="utf-8"))
    t = report["tables"]["t"]
    for k, want in CLEAN_KNOWN.items():
        if t[k] != want:
            problems.append(f"t: {k} is {t[k]}, expected {want}")
    if sum(t["rejected_by_reason"].values()) != 5:  # the row with two problems counts under both
        problems.append(f"t: rejected_by_reason {t['rejected_by_reason']}")
    con = sqlite3.connect(run.db_path)
    try:
        rows = con.execute('select _row, id, day, amount, n from "clean_t" order by _row').fetchall()
        reasons = [r[0] for r in con.execute('select reason from "reject_t" order by _row')]
    finally:
        con.close()
    if rows[:2] != [(2, "A1", "2023-01-05", 10.5, 2), (3, "A2", "2023-01-06", 7.0, 3)]:
        problems.append(f"t: first clean rows {rows[:2]!r}")
    if reasons != ["amount: not a number", "day: not a date (%Y-%m-%d)", "id: required value is missing",
                   "day: not a date (%Y-%m-%d); amount: not a number"]:
        problems.append(f"t: reject reasons {reasons!r}")
    # the duplicate key is an error check, so the run stops after clean with exit code 1
    if code != 1:
        problems.append(f"exit code {code}, expected 1 (a duplicate key on purpose)")
    return problems


def main():
    print(f"Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}")
    ok = True

    def report(stage, problems):
        nonlocal ok
        if problems:
            ok = False
            print(f"FAIL {stage}")
            for p in problems:
                print(f"  {p}")
        else:
            print(f"PASS {stage}")

    def run_quietly(folder, tmp):
        with contextlib.redirect_stdout(io.StringIO()):  # hide the run's own progress lines
            return run_mod.execute(folder, runs_root=Path(tmp) / "runs")

    with tempfile.TemporaryDirectory(prefix="data_prepper_selftest_") as tmp:
        folder = Path(tmp) / "selftest_dataset"
        known = make_dataset(folder)
        try:
            code, run = run_quietly(folder, tmp)
        except Exception as e:  # selftest must report, not crash
            print(f"FAIL load: run stopped: {e}")
            return 1
        print("(the made-up visits table has 3 bad rows on purpose, so the run stops with exit code 1)")
        report("load", check_load(run, code, known, folder))

        clean_folder = Path(tmp) / "selftest_clean_dataset"
        make_clean_dataset(clean_folder)
        try:
            code, run = run_quietly(clean_folder, tmp)
        except Exception as e:
            print(f"FAIL clean: run stopped: {e}")
            return 1
        print("(the made-up clean table has a duplicate key on purpose, so the run stops with exit code 1)")
        report("clean", check_clean(run, code))
    return 0 if ok else 1
