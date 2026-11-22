import json
import sqlite3
import unittest

from helpers import Case, config, src

from data_prepper import clean
from data_prepper.config import load_config

COLS = {
    "id": {"type": "text", "required": True},
    "clinic": {"type": "text"},
    "visit_date": {"type": "date", "format": "%Y-%m-%d"},
    "paid": {"type": "number"},
    "qty": {"type": "integer"},
}

# Line numbers (header is line 1): V3 4, V4 5, the empty id 6, V6 7, V7 8 and 9, V8 10 and 11, V9 12, V10 13.
KNOWN_BAD = (
    "id,clinic,visit_date,paid,qty\n"
    "V1,C1,2023-01-05,10.5,2\n"
    "V2, C2 ,2023-01-06, 7 , 3 \n"  # spaces around values
    "V3,C1,2023-01-07,abc,1\n"  # bad number
    "V4,C1,2023-13-01,5,1\n"  # bad date
    ",C1,2023-01-08,5,1\n"  # missing required value
    "V6,C1,2023-02-30,12abc,1\n"  # two problems
    "V7,C1,2023-01-09,1,1\n"  # duplicate key, different rows
    "V7,C2,2023-01-10,2,2\n"
    "V8,C1,2023-01-11,3,1\n"  # exact duplicate rows
    "V8,C1,2023-01-11,3,1\n"
    "V9,C1,,,\n"  # nulls are fine
    "V10, ,2023-01-12,4,1\n"  # only spaces is null
)


def one(cols=COLS, key=("id",), **source):
    t = {"source": src("in.csv", **source), "columns": cols}
    if key:
        t["key"] = list(key)
    return config({"t1": t})


class Functions(unittest.TestCase):
    def test_integer(self):
        for v, want in [("12", 12), ("-3", -3), ("+5", 5), (" 7 ", 7), ("007", 7), ("9223372036854775807", 2**63 - 1)]:
            self.assertEqual(clean.convert_integer(v), want, v)
        for v in ["1.0", "1e3", "1,000", "abc", "--1", "+", "1 2", "٣", "9223372036854775808", "-9223372036854775809", "1\n"]:
            with self.assertRaises(ValueError, msg=v):
                clean.convert_integer(v)

    def test_number(self):
        for v, want in [("12", 12.0), ("-3.5", -3.5), ("+0.25", 0.25), ("1e3", 1000.0), ("-1.5E-3", -0.0015),
                        (" 7 ", 7.0), ("1.50", 1.5), ("007", 7.0)]:
            self.assertEqual(clean.convert_number(v), want, v)
        for v in ["abc", "1,000", "$5", "NaN", "nan", "inf", "-inf", "Infinity", "1e999", "1e", "1.", ".5", "1_0", "0x10",
                  "1.2.3", "٣", "1\n"]:
            with self.assertRaises(ValueError, msg=v):
                clean.convert_number(v)

    def test_date(self):
        self.assertEqual(clean.convert_date("10/01/2022", "%m/%d/%Y"), "2022-10-01")
        self.assertEqual(clean.convert_date(" 2022-10-01 ", "%Y-%m-%d"), "2022-10-01")
        self.assertEqual(clean.convert_date("01OCT2022", "%d%b%Y"), "2022-10-01")
        for v, fmt in [("13/01/2022", "%m/%d/%Y"), ("02/30/2022", "%m/%d/%Y"), ("2022-10-01", "%m/%d/%Y"),
                       ("abc", "%Y-%m-%d"), ("10/01/22", "%m/%d/%Y")]:
            with self.assertRaises(ValueError, msg=v):
                clean.convert_date(v, fmt)

    def test_null_passes_every_type(self):
        for v in [None, "", " ", "   "]:
            self.assertIsNone(clean.convert_integer(v))
            self.assertIsNone(clean.convert_number(v))
            self.assertIsNone(clean.convert_date(v, "%Y-%m-%d"))

    def test_registered_sql_functions(self):
        con = sqlite3.connect(":memory:")
        clean.register_functions(con)
        rows = con.execute(
            "select dp_bad_integer('1'), dp_bad_integer('x'), dp_bad_integer(''), dp_bad_integer(null),"
            " dp_bad_number('1.5'), dp_bad_number('1,5'), dp_bad_number(' '),"
            " dp_bad_date('2022-01-02', '%Y-%m-%d'), dp_bad_date('02/01/2022', '%Y-%m-%d'), dp_bad_date('', '%Y-%m-%d'),"
            " dp_to_integer(' 4 '), dp_to_number('1e2'), dp_to_date('03/04/2022', '%m/%d/%Y'), dp_to_integer('')"
        ).fetchone()
        self.assertEqual(rows, (0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 4, 100.0, "2022-03-04", None))
        con.close()


class CleanStage(Case):
    def clean_report(self):
        return json.loads((self.latest_run() / "reports" / "02-clean.json").read_text(encoding="utf-8"))

    def test_known_bad_rows(self):
        self.write("in.csv", KNOWN_BAD)
        self.write_config(one())
        code, out, err = self.run_cli()
        self.assertEqual(code, 1, err)  # two duplicate keys, an error check
        self.assertIn("clean: report written", out)

        self.assertEqual(self.query("select * from clean_t1 order by _row"), [
            ("in.csv", 2, "V1", "C1", "2023-01-05", 10.5, 2),
            ("in.csv", 3, "V2", "C2", "2023-01-06", 7.0, 3),
            ("in.csv", 8, "V7", "C1", "2023-01-09", 1.0, 1),
            ("in.csv", 9, "V7", "C2", "2023-01-10", 2.0, 2),
            ("in.csv", 10, "V8", "C1", "2023-01-11", 3.0, 1),
            ("in.csv", 11, "V8", "C1", "2023-01-11", 3.0, 1),
            ("in.csv", 12, "V9", "C1", None, None, None),
            ("in.csv", 13, "V10", None, "2023-01-12", 4.0, 1),
        ])
        self.assertEqual(self.query("select typeof(paid), typeof(qty) from clean_t1 where _row = 2"), [("real", "integer")])
        # raw text is kept unchanged in the reject table, in the config's column order
        self.assertEqual(self.query("select * from reject_t1 order by _row"), [
            ("in.csv", 4, "paid: not a number", "V3", "C1", "2023-01-07", "abc", "1"),
            ("in.csv", 5, "visit_date: not a date (%Y-%m-%d)", "V4", "C1", "2023-13-01", "5", "1"),
            ("in.csv", 6, "id: required value is missing", "", "C1", "2023-01-08", "5", "1"),
            ("in.csv", 7, "visit_date: not a date (%Y-%m-%d); paid: not a number", "V6", "C1", "2023-02-30", "12abc", "1"),
        ])
        self.assertEqual([r[1] for r in self.query("pragma table_info(reject_t1)")][:4], ["_file", "_row", "reason", "id"])

        t = self.clean_report()["tables"]["t1"]
        self.assertEqual((t["rows_in"], t["rows_out"], t["rows_rejected"]), (12, 8, 4))
        self.assertEqual(t["rejected_by_reason"], {
            "id: required value is missing": 1,
            "visit_date: not a date (%Y-%m-%d)": 2,
            "paid: not a number": 2,
        })
        self.assertEqual(t["nulls"], {"id": 0, "clinic": 1, "visit_date": 1, "paid": 1, "qty": 1})
        self.assertEqual(t["duplicate_keys"], 2)
        self.assertEqual(t["duplicate_key_sample"],
                         [{"key": {"id": "V7"}, "rows": 2}, {"key": {"id": "V8"}, "rows": 2}])
        self.assertEqual(t["exact_duplicate_rows"], 1)
        self.assertIsInstance(t["seconds"], float)

        checks = {c["name"]: (c["severity"], c["status"], c["count"]) for c in self.clean_report()["checks"]}
        self.assertEqual(checks, {
            "t1: rows in = rows out + rows rejected": ("error", "pass", 0),
            "t1: no duplicate keys": ("error", "fail", 2),
            "t1: no exact duplicate rows": ("warn", "fail", 1),
            "t1: no rejected rows": ("warn", "fail", 4),
        })

    def test_rejects_and_exact_duplicates_alone_do_not_stop_the_run(self):
        self.write("in.csv", "id,paid\nA,1\nA,1\nB,x\n")
        cols = {"id": {"type": "text"}, "paid": {"type": "number"}}
        self.write_config(one(cols, key=()))  # no key
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        rep = self.clean_report()
        t = rep["tables"]["t1"]
        self.assertEqual((t["rows_in"], t["rows_out"], t["rows_rejected"]), (3, 2, 1))
        self.assertEqual(t["exact_duplicate_rows"], 1)
        self.assertIsNone(t["duplicate_keys"])
        self.assertEqual(t["duplicate_key_sample"], [])
        names = [c["name"] for c in rep["checks"]]
        self.assertFalse(any("duplicate keys" in n for n in names))  # no key, no key check
        self.assertEqual([(c["severity"], c["status"]) for c in rep["checks"] if "exact" in c["name"] or "rejected rows" in c["name"]],
                         [("warn", "fail"), ("warn", "fail")])

    def test_three_exact_copies_count_two_extra_rows(self):
        self.write("in.csv", "id\nA\nA\nA\nB\n")
        self.write_config(one({"id": {"type": "text"}}, key=()))
        self.run_cli()
        self.assertEqual(self.clean_report()["tables"]["t1"]["exact_duplicate_rows"], 2)

    def test_exact_duplicates_are_compared_after_trimming(self):
        self.write("in.csv", "id,n\nA,1\n A ,1.0\n")
        self.write_config(one({"id": {"type": "text"}, "n": {"type": "number"}}, key=()))
        self.run_cli()
        self.assertEqual(self.clean_report()["tables"]["t1"]["exact_duplicate_rows"], 1)

    def test_compound_key_and_sample_is_capped_at_20(self):
        rows = "".join(f"A,{i},x\nA,{i},y\n" for i in range(30)) + "B,1,z\n"
        self.write("in.csv", "a,b,c\n" + rows)
        cols = {"a": {"type": "text"}, "b": {"type": "integer"}, "c": {"type": "text"}}
        self.write_config(one(cols, key=("a", "b")))
        code, _, _ = self.run_cli()
        self.assertEqual(code, 1)
        t = self.clean_report()["tables"]["t1"]
        self.assertEqual(t["duplicate_keys"], 30)
        self.assertEqual(len(t["duplicate_key_sample"]), 20)
        self.assertEqual(t["duplicate_key_sample"][0], {"key": {"a": "A", "b": 0}, "rows": 2})

    def test_nothing_is_dropped_or_fixed(self):
        self.write("in.csv", KNOWN_BAD)
        self.write_config(one())
        self.run_cli()
        self.assertEqual(self.query("select count(*) from raw_t1"), [(12,)])
        self.assertEqual(self.query("select count(*) from clean_t1 c join raw_t1 r on r._row = c._row where r.id = c.id"), [(8,)])

    def test_every_row_is_in_exactly_one_place(self):
        self.write("in.csv", KNOWN_BAD)
        self.write_config(one())
        self.run_cli()
        self.assertEqual(self.query(
            "select count(*) from raw_t1 r where (select count(*) from clean_t1 c where c._row = r._row)"
            " + (select count(*) from reject_t1 j where j._row = r._row) = 1"), [(12,)])

    def test_required_empty_in_a_typed_column(self):
        self.write("in.csv", "n\n\n \n5\n")
        self.write_config(one({"n": {"type": "integer", "required": True}}, key=()))
        # a one-column file: blank lines are empty values
        self.run_cli()
        t = self.clean_report()["tables"]["t1"]
        self.assertEqual((t["rows_in"], t["rows_out"], t["rows_rejected"]), (3, 1, 2))
        self.assertEqual(t["rejected_by_reason"], {"n: required value is missing": 2})

    def test_integer_and_number_edges_through_sql(self):
        self.write("in.csv", "i,n\n+5,1e3\n1.0,1\n9223372036854775808,1\n1,NaN\n1,1e999\n")
        self.write_config(one({"i": {"type": "integer"}, "n": {"type": "number"}}, key=()))
        self.run_cli()
        self.assertEqual(self.query("select i, n from clean_t1"), [(5, 1000.0)])
        self.assertEqual(self.query("select _row, reason from reject_t1 order by _row"), [
            (3, "i: not an integer"), (4, "i: not an integer"), (5, "n: not a number"), (6, "n: not a number")])

    def test_quote_in_a_date_format_does_not_break_the_sql(self):
        self.write("in.csv", "d\n2023'05\n2023-05\n")
        self.write_config(one({"d": {"type": "date", "format": "%Y'%m"}}, key=()))
        self.run_cli()
        self.assertEqual(self.query("select d from clean_t1"), [("2023-05-01",)])
        self.assertEqual(self.query("select reason from reject_t1"), [("d: not a date (%Y'%m)",)])

    def test_a_failed_load_check_stops_before_clean(self):
        self.write("in.csv", "a,b\n1,2\n1\n")
        self.write_config(one({"a": {"type": "text"}, "b": {"type": "text"}}, key=()))
        code, out, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertFalse((self.latest_run() / "reports" / "02-clean.json").exists())

    def test_column_named_p_is_counted_correctly(self):
        # an alias named p used to lose to a real column named p
        self.write("in.csv", "id,p,n\n1,x,abc\n2,,5\n3,y,zz\n")
        self.write_config(one({"id": {"type": "text"}, "p": {"type": "text"}, "n": {"type": "number"}}, key=()))
        self.run_cli()
        t = self.clean_report()["tables"]["t1"]
        self.assertEqual((t["rows_rejected"], t["rejected_by_reason"]), (2, {"n: not a number": 2}))

    def test_a_column_named_reason_is_a_config_error(self):
        self.write("in.csv", "Reason\nx\n")
        self.write_config(one({"Reason": {"type": "text"}}, key=()))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("reserved", err)

    def test_more_than_a_thousand_checked_columns(self):
        # a long || chain of this many pieces is deeper than SQLite's expression limit of 1000
        n = 1100
        names = [f"c{i}" for i in range(n)]
        row_ok = ",".join("1" for _ in names)
        row_bad = ",".join("x" if i in (0, n - 1) else "2" for i in range(n))
        self.write("in.csv", ",".join(names) + "\n" + row_ok + "\n" + row_bad + "\n")
        self.write_config(one({c: {"type": "number"} for c in names}, key=()))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        t = self.clean_report()["tables"]["t1"]
        self.assertEqual((t["rows_out"], t["rows_rejected"]), (1, 1))
        self.assertEqual(t["rejected_by_reason"], {"c0: not a number": 1, "c1099: not a number": 1})
        self.assertEqual(self.query("select reason from reject_t1"), [("c0: not a number; c1099: not a number",)])

    def test_too_many_columns_for_the_clean_tables_is_exit_2(self):
        # load can make raw_ with this many columns plus _row and _file; reject_ needs one more
        n = 1998
        names = [f"c{i}" for i in range(n)]
        self.write("in.csv", ",".join(names) + "\n" + ",".join("1" for _ in names) + "\n")
        self.write_config(one({c: {"type": "text"} for c in names}, key=()))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("cannot make the clean and reject tables", err)

    def test_the_row_count_check_can_fail(self):
        """Break the clean insert so it loses a row: the check must fail and say how many."""
        self.write("in.csv", "id,n\nA,1\nB,2\nC,3\n")
        self.write_config(one({"id": {"type": "text"}, "n": {"type": "integer"}}, key=()))
        self.assertEqual(self.run_cli()[0], 0)

        class Sabotage(sqlite3.Connection):
            def execute(self, sql, *args):
                if sql.startswith('INSERT INTO "clean_'):
                    sql += " AND _row != 3"
                return super().execute(sql, *args)

        table = load_config(self.folder).tables["t1"]
        con = sqlite3.connect(self.latest_run() / "work.db", factory=Sabotage)
        try:
            con.execute("DROP TABLE clean_t1")
            con.execute("DROP TABLE reject_t1")
            clean.register_functions(con)
            entry, checks = clean.clean_table(con, table)
        finally:
            con.close()
        self.assertEqual((entry["rows_in"], entry["rows_out"], entry["rows_rejected"]), (3, 2, 0))
        failed = [(c["name"], c["severity"], c["count"]) for c in checks if c["status"] == "fail"]
        self.assertEqual(failed, [("t1: rows in = rows out + rows rejected", "error", 1)])

    def test_date_column_needs_a_format(self):
        self.write("in.csv", "d\n2023-01-01\n")
        self.write_config(one({"d": {"type": "date"}}, key=()))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("tables.t1.columns.d.format", err)


if __name__ == "__main__":
    unittest.main()
