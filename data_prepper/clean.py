"""The clean stage: raw_<table> into clean_<table> (typed) and reject_<table>.

A row is rejected when any value fails its type or a required column is empty.
Rejected rows are set aside with the reasons, never fixed. Duplicate keys and
exact duplicate rows are counted and reported, never removed.

The type checks are small Python functions registered with SQLite and called
from SQL, because SQLite accepts bad numbers silently and cannot parse a date
by an arbitrary format.
"""

import math
import re
import sqlite3
import time
from datetime import datetime

from .config import ConfigError

SAMPLE = 20  # duplicate key values shown in the report
INT_MIN, INT_MAX = -(2**63), 2**63 - 1  # what an SQLite INTEGER holds
INTEGER_RE = re.compile(r"[+-]?[0-9]+")
NUMBER_RE = re.compile(r"[+-]?[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?")


def is_null(value):
    """None, an empty value, or one that is only spaces."""
    return value is None or value.strip(" ") == ""


def convert_integer(value):
    """None for null, an int when valid, ValueError when not."""
    if is_null(value):
        return None
    v = value.strip(" ")
    if not INTEGER_RE.fullmatch(v):
        raise ValueError(value)
    n = int(v)
    if not INT_MIN <= n <= INT_MAX:
        raise ValueError(value)
    return n


def convert_number(value):
    """None for null, a float when valid, ValueError when not (no NaN, no inf, no overflow)."""
    if is_null(value):
        return None
    v = value.strip(" ")
    if not NUMBER_RE.fullmatch(v):
        raise ValueError(value)
    x = float(v)
    if not math.isfinite(x):  # an exponent too big for a float
        raise ValueError(value)
    return x


def convert_date(value, fmt):
    """None for null, 'YYYY-MM-DD' when strptime accepts it, ValueError when not."""
    if is_null(value):
        return None
    return datetime.strptime(value.strip(" "), fmt).date().isoformat()


CONVERTERS = {"integer": convert_integer, "number": convert_number, "date": convert_date}
PROBLEMS = {"integer": "not an integer", "number": "not a number", "date": "not a date"}


def _bad(convert):
    """An SQL function that is 1 when the value fails its type, 0 when it passes or is null."""

    def bad(*args):
        try:
            convert(*args)
        except ValueError:
            return 1
        return 0

    return bad


def register_functions(con):
    for kind, convert in CONVERTERS.items():
        n = 2 if kind == "date" else 1
        con.create_function(f"dp_bad_{kind}", n, _bad(convert), deterministic=True)
        con.create_function(f"dp_to_{kind}", n, convert, deterministic=True)


def q(name):
    return '"' + name + '"'


def lit(text):
    return "'" + text.replace("'", "''") + "'"


def problem_exprs(table):
    """For each column that can fail: (column, SQL expression that is the problem text or NULL)."""
    out = []
    for c in table.columns:
        col = q(c.name)
        branches = []
        if c.required:
            branches.append(f"WHEN nullif(trim({col}), '') IS NULL THEN {lit(c.name + ': required value is missing')}")
        if c.type != "text":
            if c.type == "date":
                call = f"dp_bad_date({col}, {lit(c.format)})"
                msg = f"{c.name}: {PROBLEMS['date']} ({c.format})"
            else:
                call = f"dp_bad_{c.type}({col})"
                msg = f"{c.name}: {PROBLEMS[c.type]}"
            branches.append(f"WHEN {call} THEN {lit(msg)}")
        if branches:
            out.append((c.name, "CASE " + " ".join(branches) + " END"))
    return out


def reason_expr(probs):
    """SQL for the reason text: every problem in column order, joined with '; ', '' when none.

    The pieces are joined in a balanced tree, not one long chain, because SQLite
    stops at an expression 1,000 levels deep and a table can have more columns than that.
    """
    parts = [f"coalesce('; ' || ({e}), '')" for _, e in probs]
    if not parts:
        return "''"
    while len(parts) > 1:
        parts = [f"({' || '.join(parts[i:i + 2])})" for i in range(0, len(parts), 2)]
    return f"substr({parts[0]}, 3)"


def create_table(con, name, ncols, sql):
    try:
        con.execute(sql)
    except sqlite3.OperationalError as e:
        if "too many columns" not in str(e):
            raise
        raise ConfigError(f"table {name}: SQLite cannot make the clean and reject tables with {ncols} config columns: {e}") from None


def convert_expr(c):
    col = q(c.name)
    if c.type == "text":
        return f"nullif(trim({col}), '')"
    if c.type == "date":
        return f"dp_to_date({col}, {lit(c.format)})"
    return f"dp_to_{c.type}({col})"


def sql_type(c):
    return {"text": "TEXT", "integer": "INTEGER", "number": "REAL", "date": "TEXT"}[c.type]


def clean_table(con, table):
    """Clean one table. Returns its report entry and its checks."""
    t0 = time.perf_counter()
    name = table.name
    cols = table.columns
    raw, clean, reject = f'"raw_{name}"', f'"clean_{name}"', f'"reject_{name}"'
    probs = problem_exprs(table)
    reason = reason_expr(probs)

    create_table(con, name, len(cols),
                 f"CREATE TABLE {clean} (_file TEXT, _row INTEGER, {', '.join(f'{q(c.name)} {sql_type(c)}' for c in cols)})")
    create_table(con, name, len(cols),
                 f"CREATE TABLE {reject} (_file TEXT, _row INTEGER, reason TEXT, {', '.join(f'{q(c.name)} TEXT' for c in cols)})")
    raw_list = ", ".join(q(c.name) for c in cols)
    con.execute(f"INSERT INTO {reject} SELECT _file, _row, {reason}, {raw_list} FROM {raw} WHERE {reason} != ''")
    con.execute(
        f"INSERT INTO {clean} SELECT _file, _row, {', '.join(convert_expr(c) for c in cols)} FROM {raw} WHERE {reason} = ''"
    )
    con.commit()

    rows_in = con.execute(f"SELECT count(*) FROM {raw}").fetchone()[0]
    rows_out = con.execute(f"SELECT count(*) FROM {clean}").fetchone()[0]
    rows_rejected = con.execute(f"SELECT count(*) FROM {reject}").fetchone()[0]

    # Each single problem, counted on the reject table (same column names, as text).
    by_reason = {}
    if rows_rejected:
        for _, expr in probs:
            # _problem cannot clash with a column name: those start with a letter
            for text, n in con.execute(
                f"SELECT {expr} AS _problem, count(*) FROM {reject} WHERE _problem IS NOT NULL GROUP BY _problem"
            ):
                by_reason[text] = n

    counts = con.execute(
        f"SELECT {', '.join(f'count(*) - count({q(c.name)})' for c in cols)} FROM {clean}"
    ).fetchone()
    nulls = {c.name: n for c, n in zip(cols, counts)}

    duplicate_keys, sample = None, []
    if table.key:
        keys = ", ".join(q(k) for k in table.key)
        duplicate_keys = 0
        cur = con.execute(f"SELECT {keys}, count(*) FROM {clean} GROUP BY {keys} HAVING count(*) > 1 ORDER BY {keys}")
        for *values, n in cur:
            duplicate_keys += 1
            if len(sample) < SAMPLE:
                sample.append({"key": dict(zip(table.key, values)), "rows": n})
    all_cols = ", ".join(q(c.name) for c in cols)
    exact = con.execute(
        f"SELECT coalesce(sum(n - 1), 0) FROM (SELECT count(*) AS n FROM {clean} GROUP BY {all_cols} HAVING count(*) > 1)"
    ).fetchone()[0]
    con.commit()

    entry = {
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_rejected": rows_rejected,
        "rejected_by_reason": by_reason,
        "nulls": nulls,
        "duplicate_keys": duplicate_keys,
        "duplicate_key_sample": sample,
        "exact_duplicate_rows": exact,
        "seconds": round(time.perf_counter() - t0, 2),
    }

    def check(label, severity, count):
        return {"name": f"{name}: {label}", "severity": severity, "status": "pass" if count == 0 else "fail", "count": count}

    checks = [check("rows in = rows out + rows rejected", "error", abs(rows_in - rows_out - rows_rejected))]
    if table.key:
        checks.append(check("no duplicate keys", "error", duplicate_keys))
    checks.append(check("no exact duplicate rows", "warn", exact))
    checks.append(check("no rejected rows", "warn", rows_rejected))
    return entry, checks


def run_stage(run, con, config, data_root):
    """Clean every table. Returns the body of the clean report."""
    register_functions(con)
    tables, checks = {}, []
    for table in config.tables.values():
        tables[table.name], table_checks = clean_table(con, table)
        checks.extend(table_checks)
    return {"tables": tables, "checks": checks}
