import contextlib
import io
import json
import sqlite3
import unittest
import zipfile
from pathlib import Path

from helpers import Case, config, src

from data_prepper import cli, model
from data_prepper.config import ConfigError, Rule, read_rule, scan_rule_sql

VISITS = (
    "id,clinic,paid\n"
    "V1,C1,10\n"
    "V2,C1,-5\n"  # negative
    "V3,C2,7\n"
    "V4,C9,-1\n"  # negative, and a clinic that is not in clinics
    "V5,C2,3\n"
)
CLINICS = "clinic,county\nC1,North\nC2,South\n"

COLS = {"id": {"type": "text"}, "clinic": {"type": "text"}, "paid": {"type": "number"}}


def header(kind, severity=None, note="Rows returned are the failures."):
    lines = [f"-- kind: {kind}"]
    if severity:
        lines.append(f"-- severity: {severity}")
    lines.append(f"-- {note}")
    return "\n".join(lines) + "\n"


NEGATIVE = header("check", "error") + "select id, paid from visits where paid < 0;\n"
NEGATIVE_WARN = header("check", "warn") + "select id, paid from visits where paid < 0;\n"
DROP_NEGATIVE = header("transform") + "select * from visits where paid >= 0;\n"
ADD_COLUMN = header("transform") + "select *, paid * 2 as double_paid from visits;\n"
NO_ROWS = header("check", "error") + "select id from visits where 1 = 0;\n"


class ModelCase(Case):
    def setUp(self):
        super().setUp()
        self.write("visits.csv", VISITS)
        self.write("clinics.csv", CLINICS)

    def make(self, model, **rules):
        """Write rule files (name -> text) and the config; model maps a table to rule names."""
        for name, text in rules.items():
            self.write(f"rules/{name}.sql", text)
        cfg = config(
            {"visits": {"source": src("visits.csv"), "columns": COLS, "key": ["id"]},
             "clinics": {"source": src("clinics.csv"),
                         "columns": {"clinic": {"type": "text"}, "county": {"type": "text"}}}},
            model={t: [f"rules/{n}.sql" for n in names] for t, names in model.items()},
        )
        self.write_config(cfg)

    def model_report(self):
        return json.loads((self.latest_run() / "reports" / "03-model.json").read_text(encoding="utf-8"))

    def rule(self, report, i):
        return report["rules"][i]


class Checks(ModelCase):
    def test_passing_check(self):
        self.make({"visits": ["a"]}, a=NO_ROWS)
        code, out, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        r = self.rule(self.model_report(), 0)
        self.assertEqual((r["status"], r["rows_failing"], r["sample"]), ("pass", 0, []))
        self.assertEqual((r["table"], r["file"], r["kind"], r["severity"]), ("visits", "rules/a.sql", "check", "error"))
        self.assertIn("seconds", r)

    def test_failing_warn_check_goes_on(self):
        self.make({"visits": ["a"]}, a=NEGATIVE_WARN)
        code, out, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        r = self.rule(self.model_report(), 0)
        self.assertEqual((r["status"], r["rows_failing"]), ("fail", 2))
        self.assertEqual(r["sample"], [{"id": "V2", "paid": -5.0}, {"id": "V4", "paid": -1.0}])

    def test_failing_error_check_writes_report_then_exit_1(self):
        self.make({"visits": ["a"], "clinics": ["b"]}, a=NEGATIVE,
                  b=header("check", "warn") + "select * from clinics where county = 'West';\n")
        code, out, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertIn("FAILED (error)", out)
        rep = self.model_report()
        # all rules ran, including the one listed after the failed one
        self.assertEqual([r["status"] for r in rep["rules"]], ["fail", "pass"])
        self.assertEqual(rep["rules"][0]["rows_failing"], 2)
        self.assertEqual({row["id"] for row in rep["rules"][0]["sample"]}, {"V2", "V4"})

    def test_check_changes_nothing(self):
        self.make({"visits": ["a"]}, a=NEGATIVE_WARN)
        self.run_cli()
        self.assertEqual(self.query("select count(*) from model_visits"), [(5,)])
        self.assertEqual(self.query("select count(*) from model_visits"), self.query("select count(*) from clean_visits"))

    def test_sample_is_limited_to_20(self):
        rows = "".join(f"V{i},C1,-{i}\n" for i in range(1, 26))
        self.write("visits.csv", "id,clinic,paid\n" + rows)
        self.make({"visits": ["a"]}, a=NEGATIVE_WARN)
        self.run_cli()
        r = self.rule(self.model_report(), 0)
        self.assertEqual((r["rows_failing"], len(r["sample"])), (25, 20))

    def test_rule_can_read_another_table(self):
        self.make({"visits": ["a"]},
                  a=header("check", "warn") + "select v.id from visits v left join clinics c on c.clinic = v.clinic where c._row is null;\n")
        self.run_cli()
        r = self.rule(self.model_report(), 0)
        self.assertEqual(r["sample"], [{"id": "V4"}])

    def test_comment_at_the_end_of_a_check(self):
        self.make({"visits": ["a"]}, a=header("check", "warn") + "select id from visits where paid < 0 -- trailing\n")
        code, _, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.rule(self.model_report(), 0)["rows_failing"], 2)

    def test_with_statement_is_allowed(self):
        self.make({"visits": ["a"]},
                  a=header("check", "warn") + "with neg as (select id from visits where paid < 0) select * from neg;\n")
        code, _, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.rule(self.model_report(), 0)["rows_failing"], 2)


class Transforms(ModelCase):
    def test_transform_drops_rows(self):
        self.make({"visits": ["a"]}, a=DROP_NEGATIVE)
        code, _, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.query("select id from model_visits order by id"), [("V1",), ("V3",), ("V5",)])
        self.assertEqual(self.query("select count(*) from clean_visits"), [(5,)])  # clean is untouched
        rep = self.model_report()
        r = self.rule(rep, 0)
        self.assertEqual((r["status"], r["rows_before"], r["rows_after"]), ("applied", 5, 3))
        self.assertEqual(rep["tables"]["visits"], {"rows_in": 5, "rows_out": 3})
        self.assertEqual(rep["tables"]["clinics"], {"rows_in": 2, "rows_out": 2})

    def test_transform_adds_column(self):
        self.make({"visits": ["a"]}, a=ADD_COLUMN)
        self.run_cli()
        rows = self.query("select id, double_paid from model_visits order by id")
        self.assertEqual(rows[0], ("V1", 20.0))
        self.assertEqual(len(rows), 5)
        # the model table keeps the typed columns of the clean table
        types = {r[1]: r[2] for r in self.query("pragma table_info(model_visits)")}
        self.assertEqual((types["paid"], types["id"]), ("REAL", "TEXT"))

    def test_file_and_row_survive_only_when_selected(self):
        self.make({"visits": ["a"]}, a=header("transform") + "select id from visits;\n")
        self.run_cli()
        cols = [r[1] for r in self.query("pragma table_info(model_visits)")]
        self.assertEqual(cols, ["id"])
        self.make({"visits": ["a"]}, a=header("transform") + "select _file, _row, id from visits;\n")
        self.run_cli()
        cols = [r[1] for r in self.query("pragma table_info(model_visits)")]
        self.assertEqual(cols, ["_file", "_row", "id"])

    def test_later_rule_sees_the_result(self):
        # after the transform drops the negatives, the check finds none; the added column is visible too
        self.make({"visits": ["a", "b", "c"]}, a=DROP_NEGATIVE, b=ADD_COLUMN,
                  c=header("check", "error") + "select id from visits where paid < 0 or double_paid is null;\n")
        code, _, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        rep = self.model_report()
        self.assertEqual([r["status"] for r in rep["rules"]], ["applied", "applied", "pass"])
        self.assertEqual(rep["rules"][1]["rows_before"], 3)

    def test_order_changes_the_answer(self):
        self.make({"visits": ["a", "b"]}, a=NEGATIVE_WARN, b=DROP_NEGATIVE)
        self.run_cli()
        first = self.model_report()
        self.assertEqual([(r["status"], r.get("rows_failing")) for r in first["rules"]], [("fail", 2), ("applied", None)])
        self.make({"visits": ["b", "a"]})  # same files, other order
        self.run_cli()
        second = self.model_report()
        self.assertEqual([(r["status"], r.get("rows_failing")) for r in second["rules"]], [("applied", None), ("pass", 0)])
        self.assertEqual([r["file"] for r in second["rules"]], ["rules/b.sql", "rules/a.sql"])

    def test_tables_run_in_the_order_of_the_model_section(self):
        self.make({"clinics": ["b"], "visits": ["a"]}, a=NO_ROWS, b=header("check", "warn") + "select * from clinics where 1 = 0;\n")
        self.run_cli()
        self.assertEqual([r["table"] for r in self.model_report()["rules"]], ["clinics", "visits"])

    def test_transform_after_failed_error_check_is_skipped(self):
        self.make({"visits": ["a", "b", "c", "d"], "clinics": ["e"]},
                  a=NEGATIVE, b=DROP_NEGATIVE, c=NEGATIVE_WARN, d=ADD_COLUMN,
                  e=header("transform") + "select * from clinics where county = 'North';\n")
        code, _, _ = self.run_cli()
        self.assertEqual(code, 1)
        rep = self.model_report()
        self.assertEqual([r["status"] for r in rep["rules"]], ["fail", "skipped", "fail", "skipped", "applied"])
        self.assertEqual((rep["rules"][1]["rows_before"], rep["rules"][1]["rows_after"]), (None, None))
        # visits is unchanged, the other table's transform still ran
        self.assertEqual(self.query("select count(*) from model_visits"), [(5,)])
        self.assertEqual(self.query("select count(*) from model_clinics"), [(1,)])
        self.assertEqual(rep["tables"]["visits"], {"rows_in": 5, "rows_out": 5})

    def test_transform_after_failed_warn_check_still_runs(self):
        self.make({"visits": ["a", "b"]}, a=NEGATIVE_WARN, b=DROP_NEGATIVE)
        code, _, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(self.model_report()["rules"][1]["status"], "applied")

    def test_table_without_rules_is_copied(self):
        self.make({}, )
        code, _, _ = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(self.query("select count(*) from model_visits"), [(5,)])
        self.assertEqual(self.query("select count(*) from model_clinics"), [(2,)])
        self.assertEqual(self.model_report()["rules"], [])

    def test_same_input_twice_gives_the_same_result(self):
        self.make({"visits": ["a", "b", "c"], "clinics": ["d"]},
                  a=NEGATIVE_WARN, b=DROP_NEGATIVE, c=ADD_COLUMN,
                  d=header("transform") + "select *, upper(county) as county_upper from clinics;\n")

        def snapshot():
            con = sqlite3.connect(self.latest_run() / "work.db")
            try:
                tables = {}
                for (name,) in con.execute("select name from sqlite_master where type = 'table' and name like 'model\\_%' escape '\\'"):
                    tables[name] = sorted(con.execute(f'select * from "{name}"').fetchall(), key=repr)
            finally:
                con.close()
            rep = self.model_report()
            rep = {k: v for k, v in rep.items() if k not in ("started", "finished", "run_id")}
            for r in rep["rules"]:
                del r["seconds"]
            return tables, rep

        self.run_cli()
        one = snapshot()
        first_run = self.latest_run().name
        self.run_cli()
        two = snapshot()
        self.assertNotEqual(first_run, self.latest_run().name)  # a second run folder
        self.assertEqual(one, two)
        self.assertEqual(set(one[0]), {"model_visits", "model_clinics"})


class BadRuleFiles(ModelCase):
    def bad(self, text, expect, name="a"):
        self.make({"visits": [name]}, **{name: text})
        code, out, err = self.run_cli()
        self.assertEqual(code, 2, err)
        self.assertEqual(out, "")  # before any stage runs
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn(f"{name}.sql", err)
        self.assertIn(expect, err)
        self.assertFalse(self.runs.exists())  # no run folder was made

    def test_missing_kind(self):
        self.bad("-- severity: error\nselect 1;\n", "missing header")

    def test_unknown_kind(self):
        self.bad("-- kind: audit\n-- severity: error\nselect 1;\n", "kind is 'audit'")

    def test_check_without_severity(self):
        self.bad("-- kind: check\nselect 1;\n", "needs a header")

    def test_unknown_severity(self):
        self.bad("-- kind: check\n-- severity: fatal\nselect 1;\n", "severity is 'fatal'")

    def test_transform_with_severity(self):
        self.bad("-- kind: transform\n-- severity: warn\nselect 1;\n", "cannot have a severity")

    def test_empty_header_value(self):
        self.bad("-- kind:\nselect 1;\n", "kind is ''")

    def test_repeated_header(self):
        self.bad("-- kind: check\n-- kind: transform\nselect 1;\n", "appears twice")

    def test_two_statements(self):
        self.bad(header("check", "error") + "select 1; select 2;\n", "2 statements")

    def test_not_a_select(self):
        self.bad(header("transform") + "delete from visits;\n", "must be a select")
        self.bad(header("transform") + "drop table model_visits;\n", "must be a select", name="b")

    def test_no_statement(self):
        self.bad(header("check", "error"), "no statement")

    def test_unclosed_quote(self):
        self.bad(header("check", "error") + "select 'abc from visits;\n", "never closed")

    def test_unclosed_block_comment(self):
        self.bad(header("check", "error") + "/* oops\nselect 1;\n", "never closed")

    def test_not_utf8(self):
        self.write("rules/a.sql", "")
        (self.folder / "rules" / "a.sql").write_bytes(b"-- kind: check\n\xff\xfe\nselect 1;")
        self.make({"visits": ["a"]})
        (self.folder / "rules" / "a.sql").write_bytes(b"-- kind: check\n\xff\xfe\nselect 1;")
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_missing_rule_file(self):
        self.make({"visits": []})
        self.write_config(config(
            {"visits": {"source": src("visits.csv"), "columns": COLS}}, model={"visits": ["rules/nope.sql"]}))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("nope.sql", err)

    def test_model_table_not_in_tables(self):
        self.write_config(config(
            {"visits": {"source": src("visits.csv"), "columns": COLS}}, model={"ghost": []}))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("model.ghost", err)

    def test_model_wrong_shape(self):
        for model in ({"visits": "rules/a.sql"}, {"visits": [1]}, ["rules/a.sql"]):
            self.write_config(config({"visits": {"source": src("visits.csv"), "columns": COLS}}, model=model))
            code, out, err = self.run_cli()
            self.assertEqual(code, 2, model)
            self.assertEqual(len(err.strip().splitlines()), 1)

    def test_second_file_bad_nothing_runs(self):
        self.make({"visits": ["a", "b"]}, a=DROP_NEGATIVE, b="-- kind: check\nselect 1;\n")
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertFalse(self.runs.exists())

    def test_sql_error_in_a_rule_is_one_line_exit_2(self):
        self.make({"visits": ["a"]}, a=header("check", "error") + "select nope from visits;\n")
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("a.sql", err)
        self.assertIn("no such column", err)

    def test_sql_error_in_a_transform_leaves_the_table_alone(self):
        self.make({"visits": ["a"]}, a=header("transform") + "select nope from visits;\n")
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(self.query("select count(*) from model_visits"), [(5,)])
        self.assertEqual(self.query("select count(*) from sqlite_master where name like '%new_model%'"), [(0,)])


class MoreBadRules(ModelCase):
    bad = BadRuleFiles.bad

    def test_with_then_not_a_select(self):
        self.bad(header("check", "error") + "with x as (select 1) delete from visits;\n", "must be a select")
        self.bad(header("check", "error") + "with x as (select 1) insert into visits select * from x;\n", "must be a select", name="b")

    def test_with_recursive_and_several_named_queries_are_selects(self):
        self.make({"visits": ["a"]}, a=header("check", "warn") + (
            "with recursive n(i) as (select 1 union all select i + 1 from n where i < 3), "
            "b as (select 'delete' as w) select i from n, b;\n"))
        code, _, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.rule(self.model_report(), 0)["rows_failing"], 3)

    def test_word_that_only_starts_like_select(self):
        self.bad(header("check", "error") + "select1 from visits;\n", "must be a select")

    def test_header_values_are_not_case_sensitive(self):
        self.make({"visits": ["a"]}, a="-- Kind: Check\n-- SEVERITY: Warn\nselect id from visits where paid < 0;\n")
        code, _, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        r = self.rule(self.model_report(), 0)
        self.assertEqual((r["kind"], r["severity"]), ("check", "warn"))

    def test_runtime_data_error_is_exit_2_not_a_traceback(self):
        self.make({"visits": ["a"]}, a=header("check", "error") + "select cast(x'ff' as text) as a from visits;\n")
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("a.sql", err)

    def test_non_finite_numbers_stay_valid_json(self):
        self.make({"visits": ["a"]}, a=header("check", "warn") + "select 1e999 as big, x'ab' as blob from visits limit 1;\n")
        code, _, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))
        text = (self.latest_run() / "reports" / "03-model.json").read_text(encoding="utf-8")
        row = json.loads(text, parse_constant=lambda c: self.fail(f"{c} in the report"))["rules"][0]["sample"][0]
        self.assertEqual(row, {"big": "inf", "blob": "ab"})


class NameClashes(ModelCase):
    def clash(self, a, b):
        self.write_config(config({a: {"source": src("visits.csv"), "columns": COLS},
                                  b: {"source": src("visits.csv"), "columns": COLS}}))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2, (a, b))
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertFalse(self.runs.exists())

    def test_names_clash_whatever_the_case(self):
        self.clash("x", "MODEL_X")
        self.clash("X", "clean_x")

    def test_names_that_only_look_alike_are_fine(self):
        self.write_config(config({n: {"source": src("visits.csv"), "columns": COLS}
                                  for n in ("x", "modelx", "xclean_x", "model", "raw")}))
        code, out, err = self.run_cli()
        self.assertEqual((code, err), (0, ""))

    def test_tables_named_like_the_stage_tables_are_turned_down(self):
        for prefix in ("raw_", "badrows_", "clean_", "reject_", "model_"):
            with self.subTest(prefix=prefix):
                self.clash("x", prefix + "x")
                self.clash(prefix + "x", "x")


class HcrisRules(Case):
    """The real HCRIS config and rule files, run on a few made-up rows in a made-up zip."""

    HCRIS = Path(__file__).resolve().parent.parent / "datasets" / "hcris"

    def rows(self, table, overrides):
        cfg = json.loads((self.HCRIS / "dataset.json").read_text(encoding="utf-8"))
        fake = {"integer": "1", "number": "1.5", "text": "x", "date": "01/01/2023"}
        base = {"FY_BGN_DT": "01/01/2023", "FY_END_DT": "12/31/2023"}  # dates in order unless a test says otherwise
        cols = cfg["tables"][table]["columns"]
        return "\n".join(",".join({**base, **ov}.get(c, fake[v["type"]]) for c, v in cols.items()) for ov in overrides) + "\n"

    def run_hcris(self, rpt, nmrc):
        data = self.root / "data"
        data.mkdir()
        with zipfile.ZipFile(data / "HOSP10FY2023.ZIP", "w") as z:
            z.writestr("HOSP10_2023_rpt.csv", self.rows("rpt", rpt))
            z.writestr("HOSP10_2023_nmrc.csv", self.rows("nmrc", nmrc))
            z.writestr("HOSP10_2023_alpha.csv", self.rows("alpha", [{}]))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["run", str(self.HCRIS), "--data-root", str(data), "--runs", str(self.runs)])
        run = sorted((self.runs / "hcris").iterdir())[-1]
        rep = json.loads((run / "reports" / "03-model.json").read_text(encoding="utf-8"))
        return code, {r["file"].split("/")[-1]: r for r in rep["rules"]}

    def test_good_data_passes_both_rules(self):
        code, rules = self.run_hcris(
            [{"RPT_REC_NUM": "1", "FY_BGN_DT": "01/01/2023", "FY_END_DT": "12/31/2023"}],
            [{"RPT_REC_NUM": "1"}])
        self.assertEqual(code, 0)
        self.assertEqual([r["rows_failing"] for r in rules.values()], [0, 0])

    def test_orphan_nmrc_rows_fail_rule_010(self):
        code, rules = self.run_hcris(
            [{"RPT_REC_NUM": "1"}],
            [{"RPT_REC_NUM": "1"}, {"RPT_REC_NUM": "99", "WKSHT_CD": "A000000"}, {"RPT_REC_NUM": "98"}])
        self.assertEqual(code, 1)
        r = rules["010_nmrc_has_report.sql"]
        self.assertEqual((r["status"], r["rows_failing"]), ("fail", 2))
        self.assertEqual(sorted(row["RPT_REC_NUM"] for row in r["sample"]), [98, 99])
        self.assertEqual(rules["020_fy_dates_in_order.sql"]["status"], "pass")

    def test_dates_out_of_order_fail_rule_020(self):
        rpt = [
            {"RPT_REC_NUM": "1", "FY_BGN_DT": "01/01/2023", "FY_END_DT": "12/31/2023"},  # fine
            {"RPT_REC_NUM": "2", "FY_BGN_DT": "06/01/2023", "FY_END_DT": "06/01/2023"},  # same day: fails
            {"RPT_REC_NUM": "3", "FY_BGN_DT": "06/01/2023", "FY_END_DT": "05/31/2023"},  # reversed: fails
            {"RPT_REC_NUM": "4", "FY_BGN_DT": "06/01/2023", "FY_END_DT": ""},  # empty: not flagged
            {"RPT_REC_NUM": "5", "FY_BGN_DT": "12/31/2022", "FY_END_DT": "01/02/2023"},  # across a year: fine
        ]
        code, rules = self.run_hcris(rpt, [{"RPT_REC_NUM": str(i)} for i in range(1, 6)])
        self.assertEqual(code, 1)
        r = rules["020_fy_dates_in_order.sql"]
        self.assertEqual((r["status"], r["rows_failing"]), ("fail", 2))
        self.assertEqual(sorted(row["RPT_REC_NUM"] for row in r["sample"]), [2, 3])
        self.assertEqual(rules["010_nmrc_has_report.sql"]["status"], "pass")


class RuleErrors(unittest.TestCase):
    RULE = Rule("rules/a.sql", "check", "error", "select 1")

    def test_disk_errors_are_left_to_the_command_line(self):
        for code in (sqlite3.SQLITE_FULL, sqlite3.SQLITE_IOERR, sqlite3.SQLITE_CANTOPEN, sqlite3.SQLITE_READONLY,
                     sqlite3.SQLITE_BUSY, sqlite3.SQLITE_CORRUPT):
            e = sqlite3.OperationalError("disk trouble")
            e.sqlite_errorcode = code
            self.assertIsNone(model.rule_error(self.RULE, e), code)

    def test_sql_and_data_errors_are_rule_errors(self):
        for code in (sqlite3.SQLITE_ERROR, sqlite3.SQLITE_TOOBIG, None):
            e = sqlite3.OperationalError("no such column: nope")
            e.sqlite_errorcode = code
            err = model.rule_error(self.RULE, e)
            self.assertIsInstance(err, ConfigError)
            self.assertIn("rules/a.sql", str(err))


class Scanner(unittest.TestCase):
    def test_semicolon_and_dashes_inside_a_string_are_text(self):
        header_, stmts = scan_rule_sql("-- kind: check\n-- severity: warn\nselect ';--' as x /* ; */ from t;\n")
        self.assertEqual(header_, {"kind": "check", "severity": "warn"})
        self.assertEqual(stmts, ["select ';--' as x /* ; */ from t"])

    def test_header_is_not_case_sensitive_but_values_are_kept(self):
        header_, _ = scan_rule_sql("-- KIND: check\n--severity :warn\nselect 1")
        self.assertEqual(header_, {"kind": "check", "severity": "warn"})

    def test_doubled_quote_does_not_end_the_string(self):
        _, stmts = scan_rule_sql("select 'it''s; fine'")
        self.assertEqual(stmts, ["select 'it''s; fine'"])

    def test_stray_semicolons_are_not_statements(self):
        _, stmts = scan_rule_sql(";; select 1 ;; ;")
        self.assertEqual(stmts, ["select 1"])

    def test_kind_line_after_the_statement_is_not_header(self):
        header_, _ = scan_rule_sql("select 1;\n-- kind: check\n")
        self.assertEqual(header_, {})

    def test_read_rule_returns_the_rule(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "r.sql").write_text(header("check", "warn") + "select 1;\n", encoding="utf-8")
            rule = read_rule(d, "r.sql", "x")
        self.assertEqual((rule.kind, rule.severity, rule.sql), ("check", "warn", "select 1"))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ConfigError):
                read_rule(d, "missing.sql", "x")


if __name__ == "__main__":
    unittest.main()
