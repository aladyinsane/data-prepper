import json
import unittest

from helpers import Case, config, src

from data_prepper.config import load_config

GOOD = config({
    "visits": {
        "source": src("v.csv"),
        "columns": {"id": {"type": "text", "required": True}, "paid": {"type": "number"},
                    "day": {"type": "date", "format": "%Y-%m-%d"}},
        "key": ["id"],
    }
})


class GoodConfig(Case):
    def test_good_config_keeps_column_order(self):
        self.write_config(GOOD)
        c = load_config(self.folder)
        self.assertEqual(c.dataset, "t")
        self.assertEqual(c.tables["visits"].column_names, ["id", "paid", "day"])
        self.assertTrue(c.tables["visits"].columns[0].required)

    def test_note_is_ignored_everywhere(self):
        cfg = json.loads(json.dumps(GOOD))
        cfg["note"] = "a"
        cfg["tables"]["note"] = "b"
        t = cfg["tables"]["visits"]
        t["note"] = "c"
        t["source"]["note"] = "d"
        t["columns"]["note"] = "e"
        t["columns"]["id"]["note"] = "f"
        self.write_config(cfg)
        c = load_config(self.folder)
        self.assertEqual(c.tables["visits"].column_names, ["id", "paid", "day"])

    def test_later_sections_accepted(self):
        cfg = dict(GOOD, model={}, merge=[], summarize=[])
        self.write_config(cfg)
        load_config(self.folder)


class BadConfig(Case):
    def assert_exit2_one_line(self, expect_in_message):
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        lines = err.strip().splitlines()
        self.assertEqual(len(lines), 1, err)
        self.assertNotIn("Traceback", err)
        self.assertIn("dataset.json", lines[0])
        self.assertIn(expect_in_message, lines[0])

    def mutate(self, fn):
        cfg = json.loads(json.dumps(GOOD))
        fn(cfg)
        self.write_config(cfg)

    def test_missing_key(self):
        self.mutate(lambda c: c["tables"]["visits"]["source"].pop("delimiter"))
        self.assert_exit2_one_line("tables.visits.source.delimiter")

    def test_missing_top_level_key(self):
        self.mutate(lambda c: c.pop("tables"))
        self.assert_exit2_one_line("tables")

    def test_unknown_key(self):
        self.mutate(lambda c: c["tables"]["visits"].update(colums={}))
        self.assert_exit2_one_line("tables.visits.colums")

    def test_wrong_type_header(self):
        self.mutate(lambda c: c["tables"]["visits"]["source"].update(header="yes"))
        self.assert_exit2_one_line("tables.visits.source.header")

    def test_wrong_type_column_type(self):
        self.mutate(lambda c: c["tables"]["visits"]["columns"]["paid"].update(type="int"))
        self.assert_exit2_one_line("tables.visits.columns.paid.type")

    def test_key_not_a_column(self):
        self.mutate(lambda c: c["tables"]["visits"].update(key=["nope"]))
        self.assert_exit2_one_line("tables.visits.key")

    def test_bad_json(self):
        self.write_config('{"dataset": "t", "tables": {')
        self.assert_exit2_one_line("bad JSON")

    def test_duplicate_column_in_json(self):
        self.write_config('{"dataset":"t","tables":{"a":{"source":{"path":"a","delimiter":",",'
                          '"header":true,"encoding":"utf-8"},"columns":{"x":{"type":"text"},"x":{"type":"text"}}}}}')
        self.assert_exit2_one_line("appears twice")

    def test_encoding_idna_is_not_a_file_encoding(self):
        self.mutate(lambda c: c["tables"]["visits"]["source"].update(encoding="idna"))
        self.assert_exit2_one_line("tables.visits.source.encoding")

    def test_dataset_name_ending_in_a_line_break(self):
        self.mutate(lambda c: c.update(dataset="t\n"))
        self.assert_exit2_one_line("dataset")

    def test_column_name_ending_in_a_line_break(self):
        self.mutate(lambda c: c["tables"]["visits"]["columns"].update({"x\n": {"type": "text"}}))
        self.assert_exit2_one_line("column name must be")

    def test_no_config_file(self):
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(len(err.strip().splitlines()), 1)

    def test_bad_arguments_exit_2(self):
        from data_prepper import cli

        with self.assertRaises(SystemExit) as cm:
            import contextlib, io

            with contextlib.redirect_stderr(io.StringIO()):
                cli.main(["run"])
        self.assertEqual(cm.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
