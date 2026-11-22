"""The model stage: run a dataset's .sql rule files against the clean tables.

At the start every table gets model_<table>, a copy of clean_<table>, and a temp
view with the plain table name that selects from it. Rules use the plain names.

- A check is a select that returns the rows breaking the rule. Nothing changes.
- A transform is a select whose result becomes the new model_<table> for the
  table it is listed under.

All rules run, the report is written, and only then does run.py stop the run if
an error check failed. The one exception: after a failed error check on a table,
later transforms on that table are skipped.
"""

import sqlite3
import time

from .config import ConfigError

SAMPLE = 20  # failing rows shown in the report for each check


def q(name):
    return '"' + name + '"'


def count_rows(con, table):
    return con.execute(f"SELECT count(*) FROM {q(table)}").fetchone()[0]


def make_view(con, table):
    con.execute(f"DROP VIEW IF EXISTS temp.{q(table)}")
    con.execute(f"CREATE TEMP VIEW {q(table)} AS SELECT * FROM {q('model_' + table)}")


def json_value(v):
    return v.hex() if isinstance(v, bytes) else v


def rule_error(rule, e):
    """A SQL error in a rule file is a bad rule: one line, exit 2."""
    if isinstance(e, sqlite3.OperationalError) and getattr(e, "sqlite_errorcode", None) == sqlite3.SQLITE_ERROR:
        return ConfigError(f"{rule.path}: SQL error: {e}")
    return None


def run_check(con, rule):
    """Returns (rows_failing, sample)."""
    body = f"(\n{rule.sql}\n)"  # newlines so a comment at the end of the query cannot eat the bracket
    failing = con.execute(f"SELECT count(*) FROM {body}").fetchone()[0]
    sample = []
    if failing:
        cur = con.execute(f"SELECT * FROM {body} LIMIT {SAMPLE}")
        names = [d[0] for d in cur.description]
        sample = [dict(zip(names, map(json_value, row))) for row in cur.fetchall()]
    return failing, sample


def run_transform(con, table, rule):
    """Replace model_<table> with the rule's result. Returns (rows_before, rows_after)."""
    model, new = q("model_" + table), q("_new_model_" + table)  # the underscore name cannot clash with a table
    before = count_rows(con, "model_" + table)
    con.execute(f"DROP TABLE IF EXISTS {new}")
    try:
        con.execute(f"CREATE TABLE {new} AS\n{rule.sql}")  # the view is still there, so the rule can read the old table
    except sqlite3.Error:
        con.execute(f"DROP TABLE IF EXISTS {new}")
        raise
    con.execute(f"DROP VIEW IF EXISTS temp.{q(table)}")
    con.execute(f"DROP TABLE {model}")
    con.execute(f"ALTER TABLE {new} RENAME TO {model}")
    make_view(con, table)
    return before, count_rows(con, "model_" + table)


def run_stage(run, con, config, data_root):
    """Run every rule. Returns the body of the model report."""
    tables = {}
    for name in config.tables:
        con.execute(f"DROP TABLE IF EXISTS {q('model_' + name)}")
        con.execute(f"CREATE TABLE {q('model_' + name)} AS SELECT * FROM {q('clean_' + name)}")
        make_view(con, name)
        tables[name] = {"rows_in": count_rows(con, "model_" + name)}

    rules, blocked = [], set()  # blocked: tables with a failed error check
    for table, table_rules in config.model.items():
        for rule in table_rules:
            entry = {"table": table, "file": rule.path, "kind": rule.kind, "severity": rule.severity}
            t0 = time.perf_counter()
            try:
                if rule.kind == "transform" and table in blocked:
                    entry["status"] = "skipped"
                    entry["rows_before"] = entry["rows_after"] = None
                elif rule.kind == "check":
                    failing, sample = run_check(con, rule)
                    entry["status"] = "fail" if failing else "pass"
                    entry["rows_failing"] = failing
                    entry["sample"] = sample
                    if failing and rule.severity == "error":
                        blocked.add(table)
                else:
                    entry["rows_before"], entry["rows_after"] = run_transform(con, table, rule)
                    entry["status"] = "applied"
            except sqlite3.Error as e:
                err = rule_error(rule, e)
                if err is None:
                    raise
                raise err from None
            entry["seconds"] = round(time.perf_counter() - t0, 2)
            rules.append(entry)

    for name in config.tables:
        tables[name]["rows_out"] = count_rows(con, "model_" + name)
    return {"tables": tables, "rules": rules}
