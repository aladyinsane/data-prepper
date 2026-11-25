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
COLUMN_TYPES = ("text", "integer", "number", "date")
# Text codecs that are not for files: they encode names or escape sequences, not characters.
NOT_FILE_ENCODINGS = {"idna", "punycode", "unicode-escape", "raw-unicode-escape"}

# Sections later chunks will check. Until then they are accepted and ignored.
LATER_SECTIONS = ("merge", "summarize")
STAGE_PREFIXES = ("raw_", "badrows_", "clean_", "reject_", "model_")  # tables the stages make for each table
RULE_HEADER_RE = re.compile(r"--\s*(kind|severity)\s*:(.*)", re.IGNORECASE)


@dataclass
class Source:
    path: str
    delimiter: str
    header: bool
    encoding: str
    member: str | None = None
    quoting: bool = True


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
class Rule:
    """One model rule file. kind is check or transform; severity is set for a check only."""

    path: str  # as listed in the config, relative to the dataset folder
    kind: str
    severity: str | None
    sql: str  # the one select statement, no trailing semicolon, no trailing comment


@dataclass
class Config:
    dataset: str
    folder: Path
    tables: dict[str, Table]
    model: dict[str, list[Rule]] = field(default_factory=dict)  # table name -> rules, in the order listed


def scan_rule_sql(text):
    """Split rule file text into header values and statements.

    Returns (header, statements): header maps "kind" / "severity" to the value in a
    leading "-- kind: ..." line; statements is a list of statement texts with comments
    and the closing semicolon left off. Quotes and comments are skipped, so a ";" or a
    "--" inside a string does not count. Raises ValueError with a short problem text.
    """
    header, statements = {}, []
    i, n = 0, len(text)
    start = last = None  # start of the current statement, end of its last token
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            if start is None and not statements:  # still in the header
                m = RULE_HEADER_RE.fullmatch(text[i:j].rstrip())
                if m:
                    key = m.group(1).lower()
                    if key in header:
                        raise ValueError(f"header '{key}' appears twice")
                    header[key] = m.group(2).strip()
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            if j < 0:
                raise ValueError("a /* comment is never closed")
            i = j + 2
        elif c == ";":
            if start is not None:
                statements.append(text[start:last])
                start = last = None
            i += 1
        else:
            if start is None:
                start = i
            if c in "'\"`[":
                close = "]" if c == "[" else c
                j = i + 1
                while True:
                    j = text.find(close, j)
                    if j < 0:
                        raise ValueError(f"a quote ({c}) is never closed")
                    if close != "]" and text.startswith(close, j + 1):  # doubled quote is a literal quote
                        j += 2
                        continue
                    break
                i = j + 1
            else:
                i += 1
            last = i
    if start is not None:
        statements.append(text[start:last])
    return header, statements


def main_verb(statement):
    """The word that says what a statement does: its first word, or for "with" the first
    word after the list of named queries (the one outside every bracket)."""
    words, depth, i, n = [], 0, 0, len(statement)
    while i < n:
        c = statement[i]
        if statement.startswith("--", i):
            j = statement.find("\n", i)
            i = n if j < 0 else j
        elif statement.startswith("/*", i):
            j = statement.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in "'\"`[":
            close = "]" if c == "[" else c
            j = i + 1
            while True:
                j = statement.find(close, j)
                if j < 0:
                    return ""
                if close != "]" and statement.startswith(close, j + 1):
                    j += 2
                    continue
                break
            i = j + 1
        elif c == "(":
            depth += 1
            i += 1
        elif c == ")":
            depth -= 1
            i += 1
        elif c.isalnum() or c == "_":
            m = re.compile(r"\w+").match(statement, i)
            if depth == 0:
                words.append(m.group(0).lower())
            i = m.end()
        else:
            i += 1
        if words and words[0] != "with":
            break
    if not words:
        return statement[:1]
    if words[0] != "with":
        return words[0]
    for w in words[1:]:
        if w in ("select", "insert", "update", "delete", "replace", "values"):
            return w
    return "with"


def read_rule(folder, listed, where):
    """Read one rule file. Raises ConfigError (one line, naming the file) when it is not a valid rule."""
    path = Path(folder) / listed

    def fail(problem):
        raise ConfigError(f"{path}: {problem}")

    if not path.is_file():
        raise ConfigError(f"{where}: rule file {listed!r} not found")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        fail(f"cannot read the rule file as UTF-8: {e}")
    try:
        header, statements = scan_rule_sql(text)
    except ValueError as e:
        fail(str(e))
    if "kind" not in header:
        fail("missing header '-- kind: check' or '-- kind: transform'")
    kind = header["kind"].lower()
    if kind not in ("check", "transform"):
        fail(f"header kind is {kind!r}, must be check or transform")
    severity = header["severity"].lower() if "severity" in header else None
    if kind == "check":
        if severity is None:
            fail("a check needs a header '-- severity: error' or '-- severity: warn'")
        if severity not in ("error", "warn"):
            fail(f"header severity is {severity!r}, must be error or warn")
    elif severity is not None:
        fail("a transform cannot have a severity header")
    if not statements:
        fail("no statement found")
    if len(statements) > 1:
        fail(f"{len(statements)} statements found, a rule file holds exactly one select")
    word = main_verb(statements[0])
    if word != "select":
        fail(f"the statement must be a select (it may start with with), not {word!r}")
    return Rule(listed, kind, severity, statements[0])


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
        if pattern is not None and not pattern.fullmatch(v):
            fail(f"{where}.{key}", f"{v!r} is not a valid name (letters, digits, underscore; start with a letter)")
        return v

    def entries(obj, where):
        """Items of an object whose keys are names; a string under "note" is ignored."""
        if not isinstance(obj, dict):
            fail(where, "must be an object")
        return [(k, v) for k, v in obj.items() if not (k == "note" and isinstance(v, str))]

    check_keys(raw, "", ["dataset", "tables"], ("model",) + LATER_SECTIONS)
    dataset = raw["dataset"]
    if not isinstance(dataset, str) or not DATASET_RE.fullmatch(dataset):
        fail("dataset", "must be a name (letters, digits, underscore, hyphen)")
    for sec, kind in (("model", dict), ("merge", list), ("summarize", list)):
        if sec in raw and not isinstance(raw[sec], kind):
            fail(sec, f"must be {'an object' if kind is dict else 'a list'}")

    tables = {}
    for tname, traw in entries(raw["tables"], "tables"):
        if not NAME_RE.fullmatch(tname):
            fail(f"tables.{tname}", "table name must be letters, digits, underscore; start with a letter")
        if tname.lower() in {t.lower() for t in tables}:
            fail(f"tables.{tname}", "table name repeats another one (names are not case sensitive)")
        where = f"tables.{tname}"
        check_keys(traw, where, ["source", "columns"], ["key"])

        sraw = traw["source"]
        swhere = f"{where}.source"
        check_keys(sraw, swhere, ["path", "delimiter", "header", "encoding"], ["member", "quoting"])
        path = check_str(sraw, "path", swhere)
        delimiter = sraw["delimiter"]
        if not isinstance(delimiter, str) or len(delimiter) != 1 or delimiter in "\r\n\"":
            fail(f"{swhere}.delimiter", "must be a single character (not a quote or a line break)")
        if not isinstance(sraw["header"], bool):
            fail(f"{swhere}.header", "must be true or false")
        encoding = check_str(sraw, "encoding", swhere)
        try:
            "".encode(encoding)  # also turns down codecs that are not text encodings, like base64
            known = codecs.lookup(encoding).name not in NOT_FILE_ENCODINGS
        except (LookupError, ValueError):
            known = False
        if not known:
            fail(f"{swhere}.encoding", f"unknown encoding {encoding!r}")
        quoting = sraw.get("quoting", True)
        if not isinstance(quoting, bool):
            fail(f"{swhere}.quoting", "must be true or false")
        member = None
        if "member" in sraw:
            member = check_str(sraw, "member", swhere)
            if not path.lower().endswith(".zip"):
                fail(f"{swhere}.member", "only allowed when path ends in .zip")
        source = Source(path, delimiter, sraw["header"], encoding, member, quoting)

        columns = []
        seen = set()
        for cname, craw in entries(traw["columns"], f"{where}.columns"):
            cwhere = f"{where}.columns.{cname}"
            if not NAME_RE.fullmatch(cname):
                fail(cwhere, "column name must be letters, digits, underscore; start with a letter")
            if cname.lower() == "reason":
                fail(cwhere, "column name 'reason' is reserved (reject_<table> has a reason column); rename it")
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
            if ctype == "date" and fmt is None:
                fail(f"{cwhere}.format", "missing key (a date column needs a strptime format)")
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
    lowered = {t.lower(): t for t in tables}
    for t in tables:
        for prefix in STAGE_PREFIXES:
            other = lowered.get(prefix + t.lower())
            if other is not None:
                fail(f"tables.{other}", f"name clashes with the {prefix}<table> table the stages make for {t!r}; rename one")

    # Rule files are read now, so a bad one stops the run before any stage starts.
    model = {}
    for tname, listed in entries(raw.get("model", {}), "model"):
        where = f"model.{tname}"
        if tname not in tables:
            fail(where, "not a table in tables")
        if not isinstance(listed, list) or not all(isinstance(f, str) and f for f in listed):
            fail(where, "must be a list of rule file names")
        model[tname] = [read_rule(folder, f, f"{cfg_path}: {where}") for f in listed]
    return Config(dataset, folder, tables, model)
