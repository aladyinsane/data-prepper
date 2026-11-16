"""Shared test helpers: build a small dataset folder and run the command line on it."""

import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from data_prepper import cli


def src(path, header=True, **extra):
    s = {"path": path, "delimiter": ",", "header": header, "encoding": "utf-8"}
    s.update(extra)
    return s


def config(tables, **extra):
    c = {"dataset": "t", "tables": tables}
    c.update(extra)
    return c


class Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.folder = self.root / "ds"
        self.folder.mkdir()
        self.runs = self.root / "runs"

    def write(self, rel, text):
        p = self.folder / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return p

    def write_zip(self, rel, members):
        p = self.folder / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            for name, text in members.items():
                z.writestr(name, text)
        return p

    def write_config(self, cfg):
        if isinstance(cfg, str):
            self.write("dataset.json", cfg)
        else:
            self.write("dataset.json", json.dumps(cfg))

    def run_cli(self, *extra):
        """Run the CLI. Returns (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["run", str(self.folder), "--runs", str(self.runs), *extra])
        return code, out.getvalue(), err.getvalue()

    def latest_run(self):
        ds = self.runs / "t"
        return sorted(ds.iterdir())[-1]

    def report(self):
        return json.loads((self.latest_run() / "reports" / "01-load.json").read_text(encoding="utf-8"))

    def query(self, sql):
        import sqlite3

        con = sqlite3.connect(self.latest_run() / "work.db")
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()
