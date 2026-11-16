"""Read and check a dataset's dataset.json.

Any problem with the config raises ConfigError. Its message is one line that
names the file and the key. The command line prints it and exits with code 2.
"""

import codecs
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


class ConfigError(Exception):
    """Bad config or bad arguments. Always a single line, no traceback."""


NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
DATASET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
COLUMN_TYPES = ("text", "number", "date")

# Sections later chunks will check. Until then they are accepted and ignored.
LATER_SECTIONS = ("model", "merge", "summarize")


@dataclass
class Source:
    path: str
    delimiter: str
    header: bool
    encoding: str
    member: str | None = None


@dataclass
class Column:
    name: str
    type: str
    required: bool = False
    format: str | None = None


@dataclass
class Table:
    name: str
    source: Source
    columns: list[Column]
    key: list[str] = field(default_factory=list)

    @property
    def column_names(self):
        return [c.name for c in self.columns]


@dataclass
class Config:
    dataset: str
    folder: Path
    tables: dict[str, Table]


def _no_duplicate_keys(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"key {k!r} appears twice")
        seen[k] = v
    return seen


def load_config(folder):
    """Read <folder>/dataset.json and return a Config, or raise ConfigError."""
    folder = Path(folder)
    cfg_path = folder / "dataset.json"
    if not folder.is_dir():
        raise ConfigError(f"{folder}: dataset folder not found")
    if not cfg_path.is_file():
        raise ConfigError(f"{cfg_path}: file not found")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            raw = json.load(f, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as e:
        raise ConfigError(f"{cfg_path}: bad JSON at line {e.lineno} column {e.colno}: {e.msg}") from None
    except (ValueError, OSError) as e:
        raise ConfigError(f"{cfg_path}: cannot read: {e}") from None

    def fail(where, problem):
        raise ConfigError(f"{cfg_path}: {where}: {problem}")

    def check_keys(obj, where, required, optional=()):
        if not isinstance(obj, dict):
            fail(where, "must be an object")
        for k in obj:
            if k != "note" and k not in required and k not in optional:
                fail(f"{where}.{k}" if where else k, "unknown key")
        for k in required:
            if k not in obj:
                fail(f"{where}.{k}" if where else k, "missing key")

    def check_str(obj, key, where, pattern=None):
        v = obj[key]
        if not isinstance(v, str) or not v:
            fail(f"{where}.{key}", "must be a non-empty string")
        if pattern is not None and not pattern.match(v):
            fail(f"{where}.{key}", f"{v!r} is not a valid name (letters, digits, underscore; start with a letter)")
        return v

    def entries(obj, where):
        """Items of an object whose keys are names; a string under "note" is ignored."""
        if not isinstance(obj, dict):
            fail(where, "must be an object")
        return [(k, v) for k, v in obj.items() if not (k == "note" and isinstance(v, str))]

    check_keys(raw, "", ["dataset", "tables"], LATER_SECTIONS)
    dataset = raw["dataset"]
    if not isinstance(dataset, str) or not DATASET_RE.match(dataset):
        fail("dataset", "must be a name (letters, digits, underscore, hyphen)")
    for sec, kind in (("model", dict), ("merge", list), ("summarize", list)):
        if sec in raw and not isinstance(raw[sec], kind):
            fail(sec, f"must be {'an object' if kind is dict else 'a list'}")

    tables = {}
    for tname, traw in entries(raw["tables"], "tables"):
        if not NAME_RE.match(tname):
            fail(f"tables.{tname}", "table name must be letters, digits, underscore; start with a letter")
        if tname.lower() in {t.lower() for t in tables}:
            fail(f"tables.{tname}", "table name repeats another one (names are not case sensitive)")
        where = f"tables.{tname}"
        check_keys(traw, where, ["source", "columns"], ["key"])

        sraw = traw["source"]
        swhere = f"{where}.source"
        check_keys(sraw, swhere, ["path", "delimiter", "header", "encoding"], ["member"])
        path = check_str(sraw, "path", swhere)
        delimiter = sraw["delimiter"]
        if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in "\r\n\"":
            fail(f"{swhere}.delimiter", "must be a single character (not a quote or a line break)")
        if not isinstance(sraw["header"], bool):
            fail(f"{swhere}.header", "must be true or false")
        encoding = check_str(sraw, "encoding", swhere)
        try:
            codecs.lookup(encoding)
        except LookupError:
            fail(f"{swhere}.encoding", f"unknown encoding {encoding!r}")
        member = None
        if "member" in sraw:
            member = check_str(sraw, "member", swhere)
            if not path.lower().endswith(".zip"):
                fail(f"{swhere}.member", "only allowed when path ends in .zip")
        source = Source(path, delimiter, sraw["header"], encoding, member)

        columns = []
        seen = set()
        for cname, craw in entries(traw["columns"], f"{where}.columns"):
            cwhere = f"{where}.columns.{cname}"
            if not NAME_RE.match(cname):
                fail(cwhere, "column name must be letters, digits, underscore; start with a letter")
            if cname.lower() in seen:
                fail(cwhere, "column name repeats another one (names are not case sensitive)")
            seen.add(cname.lower())
            check_keys(craw, cwhere, ["type"], ["required", "format"])
            ctype = craw["type"]
            if ctype not in COLUMN_TYPES:
                fail(f"{cwhere}.type", f"must be one of {', '.join(COLUMN_TYPES)}")
            required = craw.get("required", False)
            if not isinstance(required, bool):
                fail(f"{cwhere}.required", "must be true or false")
            fmt = None
            if "format" in craw:
                fmt = check_str(craw, "format", cwhere)
                if ctype != "date":
                    fail(f"{cwhere}.format", "only allowed when type is date")
            columns.append(Column(cname, ctype, required, fmt))
        if not columns:
            fail(f"{where}.columns", "needs at least one column")

        key = traw.get("key", [])
        if not isinstance(key, list) or not all(isinstance(k, str) for k in key):
            fail(f"{where}.key", "must be a list of column names")
        for k in key:
            if k.lower() not in seen:
                fail(f"{where}.key", f"{k!r} is not one of the table's columns")
        tables[tname] = Table(tname, source, columns, key)

    if not tables:
        fail("tables", "needs at least one table")
    return Config(dataset, folder, tables)
