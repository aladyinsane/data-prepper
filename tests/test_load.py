import hashlib
import unittest

from helpers import Case, config, src


def one_table(source, cols=("a", "b")):
    return config({"t1": {"source": source, "columns": {c: {"type": "text"} for c in cols}}})


class Load(Case):
    def test_plain_file_with_header(self):
        self.write("in.csv", "a,b\r\n1, x \r\n2,y\r\n")
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        rep = self.report()
        t = rep["tables"]["t1"]
        self.assertEqual((t["rows_read"], t["rows_loaded"], t["rows_bad"]), (2, 2, 0))
        # exactly as read, and _row is the line number in the file (header is line 1)
        self.assertEqual(self.query('select _row, _file, a, b from raw_t1 order by _row'),
                         [(2, "in.csv", "1", " x "), (3, "in.csv", "2", "y")])
        self.assertTrue((self.latest_run() / "out").is_dir())
        self.assertEqual(rep["stage"], "load")
        self.assertEqual(rep["dataset"], "t")

    def test_sha256_and_bytes_of_the_file_on_disk(self):
        p = self.write("in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv")))
        self.run_cli()
        f = self.report()["tables"]["t1"]["files"][0]
        self.assertEqual(f["sha256"], hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(f["bytes"], p.stat().st_size)
        self.assertIsNone(f["member"])

    def test_header_false_takes_names_from_config(self):
        self.write("in.csv", "1,2\n3,4\n")
        self.write_config(one_table(src("in.csv", header=False)))
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.query("select _row, a, b from raw_t1 order by _row"), [(1, "1", "2"), (2, "3", "4")])

    def test_header_mismatch_stops_and_shows_both_lists(self):
        self.write("in.csv", "a,c\n1,2\n")
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("['a', 'c']", err)
        self.assertIn("['a', 'b']", err)

    def test_header_order_matters(self):
        self.write("in.csv", "b,a\n1,2\n")
        self.write_config(one_table(src("in.csv")))
        self.assertEqual(self.run_cli()[0], 2)

    def test_file_inside_a_zip(self):
        zp = self.write_zip("in.zip", {"data_2023.csv": "1,2\n3,4\n", "other.csv": "9,9\n"})
        self.write_config(one_table(src("in.zip", header=False, member="data_*.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        f = self.report()["tables"]["t1"]["files"]
        self.assertEqual(len(f), 1)
        self.assertEqual((f[0]["file"], f[0]["member"]), ("in.zip", "data_2023.csv"))
        # the hash is of the zip itself
        self.assertEqual(f[0]["sha256"], hashlib.sha256(zp.read_bytes()).hexdigest())
        self.assertEqual(self.query("select count(*) from raw_t1"), [(2,)])

    def test_zip_member_with_no_match_is_a_config_error(self):
        self.write_zip("in.zip", {"x.csv": "1,2\n"})
        self.write_config(one_table(src("in.zip", header=False, member="nope*.csv")))
        self.assertEqual(self.run_cli()[0], 2)

    def test_several_files_match_one_pattern(self):
        self.write("in/p_1.csv", "a,b\n1,1\n2,2\n")
        self.write("in/p_2.csv", "a,b\n3,3\n")
        self.write("in/other.csv", "a,b\n9,9\n")
        self.write_config(one_table(src("in/p_*.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        t = self.report()["tables"]["t1"]
        self.assertEqual([f["file"] for f in t["files"]], ["p_1.csv", "p_2.csv"])
        self.assertEqual((t["rows_read"], t["rows_loaded"]), (3, 3))
        # each file's own line numbers
        self.assertEqual(self.query("select _file, _row, a from raw_t1 order by _file, _row"),
                         [("p_1.csv", 2, "1"), ("p_1.csv", 3, "2"), ("p_2.csv", 2, "3")])

    def test_no_files_match_is_a_config_error(self):
        self.write_config(one_table(src("missing_*.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_data_root(self):
        self.write("elsewhere/in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv")))
        self.assertEqual(self.run_cli("--data-root", str(self.folder / "elsewhere"))[0], 0)

    def test_wrong_field_count_goes_to_badrows_and_exit_1(self):
        self.write("in.csv", "a,b\n1,2\n3\n4,5,6\n\n7,8\n")
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 1)
        t = self.report()["tables"]["t1"]
        self.assertEqual((t["rows_read"], t["rows_loaded"], t["rows_bad"]), (5, 2, 3))
        self.assertEqual(self.query("select _file, _row, n_fields, row_text from badrows_t1 order by _row"),
                         [("in.csv", 3, 1, "3"), ("in.csv", 4, 3, "4,5,6"), ("in.csv", 5, 0, "")])
        failed = [c for c in self.report()["checks"] if c["status"] == "fail"]
        self.assertEqual([(c["severity"], c["count"]) for c in failed], [("error", 3)])

    def test_rows_read_equals_loaded_plus_bad(self):
        # more rows than one batch, with bad rows spread through
        from data_prepper import load

        old = load.BATCH
        load.BATCH = 10
        self.addCleanup(setattr, load, "BATCH", old)
        rows = ["a,b"] + [("x" if i % 7 == 0 else f"{i},{i}") for i in range(95)]
        self.write("in.csv", "\n".join(rows) + "\n")
        self.write_config(one_table(src("in.csv")))
        self.run_cli()
        t = self.report()["tables"]["t1"]
        self.assertEqual(t["rows_read"], 95)
        self.assertEqual(t["rows_read"], t["rows_loaded"] + t["rows_bad"])
        self.assertEqual(self.query("select count(*) from raw_t1"), [(t["rows_loaded"],)])
        self.assertEqual(self.query("select count(*) from badrows_t1"), [(t["rows_bad"],)])
        self.assertGreater(t["rows_bad"], 0)

    def test_quoted_field_spanning_lines_uses_start_line(self):
        self.write("in.csv", 'a,b\n1,"two\nlines"\n3,4\n')
        self.write_config(one_table(src("in.csv")))
        self.run_cli()
        self.assertEqual(self.query("select _row, b from raw_t1 order by _row"), [(2, "two\nlines"), (4, "4")])

    def test_tab_delimiter_and_encoding(self):
        p = self.folder / "in.tsv"
        p.write_bytes("a\tb\nca\xe9\t2\n".encode("latin-1"))
        s = src("in.tsv", encoding="latin-1")
        s["delimiter"] = "\t"
        self.write_config(one_table(s))
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.query("select a from raw_t1"), [("ca\xe9",)])

    def test_wrong_encoding_is_a_config_error(self):
        (self.folder / "in.csv").write_bytes(b"a,b\n\xff\xfe,2\n")
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_work_db_has_journal_and_sync_off(self):
        from data_prepper.run import Run

        run = Run("t", self.runs)
        con = run.connect()
        try:
            self.assertEqual(con.execute("PRAGMA journal_mode").fetchone()[0], "off")
            self.assertEqual(con.execute("PRAGMA synchronous").fetchone()[0], 0)
        finally:
            con.close()

    def test_two_runs_get_different_folders(self):
        self.write("in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv")))
        self.run_cli()
        self.run_cli()
        self.assertEqual(len(list((self.runs / "t").iterdir())), 2)


class SelfTest(Case):
    def test_selftest_passes(self):
        import contextlib, io
        from data_prepper import selftest

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = selftest.main()
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn("PASS load", out.getvalue())


if __name__ == "__main__":
    unittest.main()
