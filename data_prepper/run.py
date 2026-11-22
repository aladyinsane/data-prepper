"""The run folder, the stage report writer, and the stage loop."""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from . import clean, load, model
from .config import ConfigError, load_config

# (report number, stage name, function). Later chunks add their stage here.
STAGES = [
    (1, "load", load.run_stage),
    (2, "clean", clean.run_stage),
    (3, "model", model.run_stage),
]


def utc_now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class Run:
    """One run's folder: <runs>/<dataset>/<run id>/ with work.db, reports/, out/."""

    def __init__(self, dataset, runs_root):
        base = Path(runs_root) / dataset
        base.mkdir(parents=True, exist_ok=True)
        while True:
            self.started = utc_now()
            self.run_id = self.started.strftime("%Y%m%dT%H%M%SZ")
            self.dir = base / self.run_id
            try:
                self.dir.mkdir()
                break
            except FileExistsError:
                time.sleep(0.25)  # another run began in the same second
        self.dataset = dataset
        self.db_path = self.dir / "work.db"
        self.reports_dir = self.dir / "reports"
        self.out_dir = self.dir / "out"
        self.reports_dir.mkdir()
        self.out_dir.mkdir()

    def connect(self):
        """Open work.db. It can be rebuilt from the source files, so no journal and no sync."""
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA journal_mode=OFF")
        con.execute("PRAGMA synchronous=OFF")
        return con

    def write_report(self, number, stage, started, body):
        """Write reports/<nn>-<stage>.json. Every stage uses this."""
        report = {
            "stage": stage,
            "dataset": self.dataset,
            "run_id": self.run_id,
            "started": iso(started),
            "finished": iso(utc_now()),
        }
        report.update(body)
        path = self.reports_dir / f"{number:02d}-{stage}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
            f.write("\n")
        return report


def failed_errors(report):
    """Failed error checks in a report: its "checks" list, and the check rules in a model report."""
    bad = [c for c in report.get("checks", []) if c["severity"] == "error" and c["status"] == "fail"]
    for r in report.get("rules", []):
        if r["kind"] == "check" and r["severity"] == "error" and r["status"] == "fail":
            bad.append({"name": f"{r['table']}: {r['file']}", "count": r["rows_failing"]})
    return bad


def execute(dataset_folder, data_root=None, runs_root="runs"):
    """Run every stage. Returns (exit code, Run or None). Prints one line per stage."""
    config = load_config(dataset_folder)
    data_root = Path(data_root) if data_root else Path(dataset_folder)
    if not data_root.is_dir():
        raise ConfigError(f"{data_root}: data root folder not found")
    try:
        run = Run(config.dataset, runs_root)
    except OSError as e:  # e.g. --runs is a file
        raise ConfigError(f"{runs_root}: cannot make the run folder: {e.strerror or e}") from None
    con = run.connect()
    try:
        for number, stage, fn in STAGES:
            started = utc_now()
            body = fn(run, con, config, data_root)
            con.commit()
            report = run.write_report(number, stage, started, body)
            bad = failed_errors(report)
            print(f"{stage}: report written to {run.reports_dir / f'{number:02d}-{stage}.json'}")
            if bad:
                for c in bad:
                    print(f"  FAILED (error): {c['name']} (count {c['count']})")
                return 1, run
    finally:
        con.close()
    return 0, run
