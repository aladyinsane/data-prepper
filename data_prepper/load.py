"""The load stage: source files into raw_<table> in work.db, nothing changed.

Files are streamed, never read whole. Rows go in as text exactly as read.
A row with the wrong number of fields goes to badrows_<table> instead.
"""

import csv
import fnmatch
import glob
import hashlib
import io
import zipfile
from pathlib import Path

from .config import ConfigError

BATCH = 50_000
HASH_BLOCK = 1024 * 1024
# A field longer than this means a stray quote. Stop instead of eating memory.
FIELD_LIMIT = 16 * 1024 * 1024
csv.field_size_limit(FIELD_LIMIT)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(HASH_BLOCK):
            h.update(block)
    return h.hexdigest()


def find_files(table, data_root):
    """Source files for a table: a list of (path, member name or None)."""
    pattern = Path(table.source.path)
    if not pattern.is_absolute():
        pattern = Path(data_root) / pattern
    paths = sorted(Path(p) for p in glob.glob(str(pattern)))
    paths = [p for p in paths if p.is_file()]
    if not paths:
        raise ConfigError(f"table {table.name}: no files match {pattern}")
    found = []
    for p in paths:
        if p.suffix.lower() != ".zip":
            found.append((p, None))
            continue
        with zipfile.ZipFile(p) as z:
            names = [i.filename for i in z.infolist() if not i.is_dir()]
        if table.source.member:
            want = table.source.member.lower()
            hits = [n for n in names if fnmatch.fnmatchcase(n.lower(), want)]
        else:
            hits = names
        if not hits:
            raise ConfigError(f"table {table.name}: no member of {p} matches {table.source.member!r}")
        if not table.source.member and len(hits) > 1:
            raise ConfigError(f"table {table.name}: {p} has several members; set source.member")
        found.extend((p, n) for n in sorted(hits))
    return found


def _label(path, member):
    return f"{path.name}:{member}" if member else path.name


def _load_one(con, table, path, member, stats):
    """Stream one file (or one zip member) into the table. Updates stats."""
    cols = table.column_names
    n = len(cols)
    label = _label(path, member)
    good_sql = f'INSERT INTO "raw_{table.name}" VALUES ({",".join("?" * (n + 2))})'
    bad_sql = f'INSERT INTO "badrows_{table.name}" VALUES (?,?,?,?)'
    delim = table.source.delimiter

    def run(raw):
        with io.TextIOWrapper(raw, encoding=table.source.encoding, newline="") as text:
            _copy(csv.reader(text, delimiter=delim))

    def _copy(reader):
        prev = 0  # last line number used by the previous record
        if table.source.header:
            head = next(reader, None)
            prev = reader.line_num
            if head != cols:
                raise ConfigError(
                    f"table {table.name}: header of {label} does not match the config: "
                    f"file has {head}; config has {cols}"
                )
        good, bad = [], []
        for rec in reader:
            start = prev + 1  # a quoted field can span lines; _row is where the row starts
            prev = reader.line_num
            stats["rows_read"] += 1
            if len(rec) == n:
                good.append((start, label, *rec))
                if len(good) >= BATCH:
                    con.executemany(good_sql, good)
                    stats["rows_loaded"] += len(good)
                    good = []
            else:
                bad.append((label, start, len(rec), delim.join(rec)))
                stats["rows_bad"] += 1
                if len(bad) >= BATCH:
                    con.executemany(bad_sql, bad)
                    bad = []
        if good:
            con.executemany(good_sql, good)
            stats["rows_loaded"] += len(good)
        if bad:
            con.executemany(bad_sql, bad)
        con.commit()

    try:
        if member:
            with zipfile.ZipFile(path) as z, z.open(member) as raw:
                run(raw)
        else:
            with open(path, "rb") as raw:
                run(raw)
    except UnicodeDecodeError as e:
        raise ConfigError(
            f"table {table.name}: {label} is not valid {table.source.encoding}: {e.reason} at byte {e.start}; "
            "check source.encoding"
        ) from None
    except csv.Error as e:
        raise ConfigError(f"table {table.name}: {label}: cannot parse near line {stats['rows_read'] + 1}: {e}") from None


def run_stage(run, con, config, data_root):
    """Load every table. Returns the body of the load report."""
    tables_report = {}
    checks = []
    for table in config.tables.values():
        files = find_files(table, data_root)
        cols = table.column_names
        coldefs = ", ".join(f'"{c}" TEXT' for c in cols)
        con.execute(f'CREATE TABLE "raw_{table.name}" (_row INTEGER, _file TEXT, {coldefs})')
        con.execute(
            f'CREATE TABLE "badrows_{table.name}" (_file TEXT, _row INTEGER, n_fields INTEGER, row_text TEXT)'
        )
        stats = {"rows_read": 0, "rows_loaded": 0, "rows_bad": 0}
        hashes = {}  # hash each file on disk once, even if several members come from it
        file_entries = []
        for path, member in files:
            if path not in hashes:
                hashes[path] = (path.stat().st_size, sha256_of(path))
            size, digest = hashes[path]
            file_entries.append({"file": path.name, "member": member, "bytes": size, "sha256": digest})
            _load_one(con, table, path, member, stats)
        tables_report[table.name] = {"files": file_entries, **stats}
        checks.append(
            {
                "name": f"{table.name}: no rows with the wrong number of fields",
                "severity": "error",
                "status": "pass" if stats["rows_bad"] == 0 else "fail",
                "count": stats["rows_bad"],
            }
        )
        diff = stats["rows_read"] - stats["rows_loaded"] - stats["rows_bad"]
        checks.append(
            {
                "name": f"{table.name}: rows read = rows loaded + rows bad",
                "severity": "error",
                "status": "pass" if diff == 0 else "fail",
                "count": abs(diff),
            }
        )
    return {"tables": tables_report, "checks": checks}
