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
        code, out, err = self.run_cli()
        self.assertEqual(self.query("select _row, b from raw_t1 order by _row"), [(2, "two\nlines"), (4, "4")])
        # a field that spans lines cannot be told from a stray quote, so the lines check fails
        self.assertEqual(code, 1)
        self.assertEqual(self.failed_checks(), [("t1: lines in the files = rows read", 1)])

    def failed_checks(self):
        return [(c["name"], c["count"]) for c in self.report()["checks"] if c["status"] == "fail"]

    def test_stray_quote_fails_the_lines_check(self):
        self.write("in.csv", 'a,b\n1,x\n2,"y\n3,z\n4,w\n')
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(self.report()["tables"]["t1"]["rows_read"], 2)
        self.assertEqual(self.failed_checks(), [("t1: lines in the files = rows read", 2)])

    def test_stray_quote_on_the_last_line_fails_the_lines_check(self):
        self.write("in.csv", 'a,b\n1,x\n2,"y\n')
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 1)
        self.assertEqual(self.failed_checks(), [("t1: lines in the files = rows read", 1)])

    def test_blank_line_bad_rows_are_written_in_batches(self):
        from data_prepper import load

        old = load.BATCH
        load.BATCH = 10
        self.addCleanup(setattr, load, "BATCH", old)
        self.write("in.csv", "a,b\n" + "1,2\n\n\n" * 25 + "\n\n")
        self.write_config(one_table(src("in.csv")))
        self.assertEqual(self.run_cli()[0], 1)
        t = self.report()["tables"]["t1"]
        # 24 pairs of blank lines sit between rows (bad); the four after the last row are ignored
        self.assertEqual((t["rows_read"], t["rows_loaded"], t["rows_bad"]), (73, 25, 48))
        self.assertEqual(self.query("select count(*), min(_row), max(_row) from badrows_t1"), [(48, 3, 73)])
        self.assertEqual(self.failed_checks(), [("t1: no rows with the wrong number of fields", 48)])

    def test_encoding_undefined_is_a_config_error(self):
        self.write("in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv", encoding="undefined")))
        self.assert_exit2_one_line("tables.t1.source.encoding")

    def test_damaged_zip_member_is_a_config_error(self):
        import zipfile

        p = self.folder / "in.zip"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_STORED) as z:
            z.writestr("m.csv", "1,2\n3,4\n")
        b = bytearray(p.read_bytes())
        i = bytes(b).index(b"1,2")
        b[i] = ord("9")
        p.write_bytes(bytes(b))
        self.write_config(one_table(src("in.zip", header=False)))
        self.assert_exit2_one_line("the zip is damaged")

    def test_quoting_off_keeps_quotes_as_text(self):
        self.write("in.csv", 'a,b\n1,x\n2,"y\n3,z\n4,"w"\n')
        self.write_config(one_table(src("in.csv", quoting=False)))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.query("select _row, b from raw_t1 order by _row"),
                         [(2, "x"), (3, '"y'), (4, "z"), (5, '"w"')])

    def test_quoting_must_be_true_or_false(self):
        self.write("in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv", quoting="no")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("tables.t1.source.quoting", err)

    def test_blank_lines_at_the_end_are_ignored(self):
        self.write("in.csv", "a,b\n1,2\n3,4\n\n\n")
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        t = self.report()["tables"]["t1"]
        self.assertEqual((t["rows_read"], t["rows_loaded"], t["rows_bad"]), (2, 2, 0))
        self.assertEqual(self.query("select count(*) from badrows_t1"), [(0,)])

    def test_data_root_with_brackets_in_its_name(self):
        self.write("data [2023]/in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli("--data-root", str(self.folder / "data [2023]"))
        self.assertEqual(code, 0, err)

    def test_brackets_in_source_path_are_not_a_pattern(self):
        self.write("in[1].csv", "a,b\n1,2\n")
        self.write("in1.csv", "a,b\n9,9\n")
        self.write_config(one_table(src("in[1].csv")))
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.query("select _file, a from raw_t1"), [("in[1].csv", "1")])

    def assert_exit2_one_line(self, expect):
        code, out, err = self.run_cli()
        self.assertEqual(code, 2, err)
        self.assertEqual(len(err.strip().splitlines()), 1, err)
        self.assertNotIn("Traceback", err)
        self.assertIn(expect, err)

    def test_encoding_that_is_not_a_text_encoding(self):
        self.write("in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv", encoding="base64")))
        self.assert_exit2_one_line("tables.t1.source.encoding")

    def test_zip_that_is_not_a_zip(self):
        self.write("in.zip", "this is not a zip")
        self.write_config(one_table(src("in.zip", header=False)))
        self.assert_exit2_one_line("is not a zip file")

    def test_parse_error_names_the_line_in_its_own_file(self):
        import csv

        from data_prepper import load

        csv.field_size_limit(1000)
        self.addCleanup(csv.field_size_limit, load.FIELD_LIMIT)
        self.write("p1.csv", "a,b\n" + "1,2\n" * 10)
        self.write("p2.csv", 'a,b\n1,2\n3,"' + "x" * 2000 + "\n")
        self.write_config(one_table(src("p*.csv")))
        self.assert_exit2_one_line("p2.csv: cannot parse near line 3")

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


    # Third qa-peer review (2026-11-16) and Lauren's answers (2026-11-20)

    def test_rows_loaded_is_counted_from_the_table(self):
        # If the insert into raw_<table> is skipped, the report must not say the rows were loaded.
        import sqlite3

        from data_prepper.run import Run

        class SkipRawInserts:
            def __init__(self, con):
                self._con = con

            def executemany(self, sql, rows):
                if 'INTO "raw_' in sql:
                    return None
                return self._con.executemany(sql, rows)

            def __getattr__(self, name):
                return getattr(self._con, name)

        real = Run.connect
        Run.connect = lambda run: SkipRawInserts(real(run))
        self.addCleanup(setattr, Run, "connect", real)
        self.write("in.csv", "a,b\n1,2\n3,4\n")
        self.write_config(one_table(src("in.csv")))
        code, out, err = self.run_cli()
        self.assertEqual(code, 1, err)
        t = self.report()["tables"]["t1"]
        self.assertEqual((t["rows_read"], t["rows_loaded"], t["rows_bad"]), (2, 0, 0))
        self.assertEqual(self.failed_checks(), [("t1: rows read = rows loaded + rows bad", 2)])

    def test_unsupported_zip_method_is_one_line_exit_2(self):
        import zipfile

        p = self.folder / "in.zip"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_STORED) as z:
            z.writestr("m.csv", "1,2\n")
        b = bytearray(p.read_bytes())
        # mark the member as Deflate64 (method 9) in the local header and the central directory
        local = bytes(b).index(b"PK\x03\x04")
        central = bytes(b).index(b"PK\x01\x02")
        b[local + 8] = 9
        b[central + 10] = 9
        p.write_bytes(bytes(b))
        self.write_config(one_table(src("in.zip", header=False)))
        self.assert_exit2_one_line("cannot read this zip member")

    def test_encrypted_zip_member_is_one_line_exit_2(self):
        import zipfile

        p = self.folder / "in.zip"
        with zipfile.ZipFile(p, "w", zipfile.ZIP_STORED) as z:
            z.writestr("m.csv", "1,2\n")
        b = bytearray(p.read_bytes())
        b[bytes(b).index(b"PK\x03\x04") + 6] |= 1  # the "encrypted" flag, local header
        b[bytes(b).index(b"PK\x01\x02") + 8] |= 1  # and central directory
        p.write_bytes(bytes(b))
        self.write_config(one_table(src("in.zip", header=False)))
        self.assert_exit2_one_line("the zip member is encrypted")

    def _sqlite_error_on_insert(self, error):
        from data_prepper.run import Run

        class Fails:
            def __init__(self, con):
                self._con = con

            def executemany(self, sql, rows):
                raise error

            def __getattr__(self, name):
                return getattr(self._con, name)

        real = Run.connect
        Run.connect = lambda run: Fails(real(run))
        self.addCleanup(setattr, Run, "connect", real)
        self.write("in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv")))

    def test_disk_full_is_one_line_exit_2(self):
        import sqlite3

        e = sqlite3.OperationalError("database or disk is full")
        e.sqlite_errorcode = sqlite3.SQLITE_FULL
        self._sqlite_error_on_insert(e)
        self.assert_exit2_one_line("database or disk is full")

    def test_sqlite_error_from_a_bug_keeps_its_traceback(self):
        import sqlite3

        e = sqlite3.OperationalError('near "FRM": syntax error')
        e.sqlite_errorcode = sqlite3.SQLITE_ERROR
        self._sqlite_error_on_insert(e)
        with self.assertRaises(sqlite3.OperationalError):
            self.run_cli()

    def test_runs_path_that_is_a_file_is_one_line_exit_2(self):
        self.write("in.csv", "a,b\n1,2\n")
        self.write_config(one_table(src("in.csv")))
        self.runs.write_text("not a folder", encoding="utf-8")
        self.assert_exit2_one_line("cannot make the run folder")

    def test_too_many_columns_for_sqlite_is_one_line_exit_2(self):
        cols = [f"c{i}" for i in range(2100)]
        self.write("in.csv", ",".join("1" for _ in cols) + "\n")
        self.write_config(one_table(src("in.csv", header=False), cols=cols))
        self.assert_exit2_one_line("SQLite cannot make raw_t1 with 2100 columns")

    def test_row_numbers_across_several_files_without_header(self):
        self.write("p1.csv", "1,1\n2,2\n3,3\n")
        self.write("p2.csv", "4,4\n5,5\n")
        self.write_config(one_table(src("p*.csv", header=False)))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.query("select _file, _row, a from raw_t1 order by _file, _row"),
                         [("p1.csv", 1, "1"), ("p1.csv", 2, "2"), ("p1.csv", 3, "3"),
                          ("p2.csv", 1, "4"), ("p2.csv", 2, "5")])

    def test_utf8_byte_order_mark_is_dropped(self):
        for header in (True, False):
            with self.subTest(header=header):
                text = ("a,b\n" if header else "") + "1,2\n"
                (self.folder / "in.csv").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
                self.write_config(one_table(src("in.csv", header=header)))
                code, out, err = self.run_cli()
                self.assertEqual(code, 0, err)
                self.assertEqual(self.query("select a from raw_t1"), [("1",)])

    def test_byte_order_mark_in_a_zip_member_is_dropped(self):
        self.write_zip("in.zip", {"m.csv": "\ufeff1,2\n"})
        self.write_config(one_table(src("in.zip", header=False)))
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.query("select a from raw_t1"), [("1",)])

    def test_one_column_blank_lines_are_empty_values(self):
        # at the end and in the middle alike; two or more columns keep the old rule
        self.write("in.csv", "a\n1\n\n2\n\n")
        self.write_config(one_table(src("in.csv"), cols=("a",)))
        code, out, err = self.run_cli()
        self.assertEqual(code, 0, err)
        t = self.report()["tables"]["t1"]
        self.assertEqual((t["rows_read"], t["rows_loaded"], t["rows_bad"]), (4, 4, 0))
        self.assertEqual(self.query("select _row, a from raw_t1 order by _row"),
                         [(2, "1"), (3, ""), (4, "2"), (5, "")])

    def test_one_column_without_final_blank_line(self):
        self.write("in.csv", "1\n2\n")
        self.write_config(one_table(src("in.csv", header=False), cols=("a",)))
        self.assertEqual(self.run_cli()[0], 0)
        self.assertEqual(self.query("select _row, a from raw_t1 order by _row"), [(1, "1"), (2, "2")])


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
