# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest

import support

from test_sql_engine import Options as EngineOptions
from test_structure import StructureCase

from sdbc_pysqlite import engine
from sdbc_pysqlite import errors
from sdbc_pysqlite import messages
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import structure
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.structure import ColumnSpec


class StrictTypeEntryTests(unittest.TestCase):
    def test_five_strict_entries_with_native_names(self):
        names = [e["name"] for e in ts.TYPE_ENTRIES if e["name"].endswith(ts.STRICT_SUFFIX)]
        self.assertEqual(sorted(names), ["ANY_ST", "BLOB_ST", "INTEGER_ST", "REAL_ST", "TEXT_ST"])
        self.assertEqual(ts.STRICT_NATIVE["TEXT_ST"], "TEXT")
        self.assertEqual(len({e["name"] for e in ts.TYPE_ENTRIES}), len(ts.TYPE_ENTRIES))

    def test_order_inside_a_code_group_is_plain_then_st_then_lo(self):
        order = [e["name"] for e in ts.TYPE_ENTRIES]
        for plain, st, lo in (("TEXT", "TEXT_ST", "LO_VARCHAR"), ("INTEGER", "INTEGER_ST", "LO_BIGINT"),
                              ("DOUBLE", "REAL_ST", "LO_DOUBLE"), ("BLOB", "BLOB_ST", "LO_LONGVARBINARY")):
            self.assertLess(order.index(plain), order.index(st), st)
            self.assertLess(order.index(st), order.index(lo), st)

    def test_first_entry_of_each_code_is_unchanged(self):
        first = {}
        for e in ts.TYPE_ENTRIES:
            first.setdefault(e["code"], e["name"])
        self.assertEqual(first[ts.BIGINT], "INTEGER")
        self.assertEqual(first[ts.VARCHAR], "TEXT")
        self.assertEqual(first[ts.DOUBLE], "DOUBLE")
        self.assertEqual(first[ts.LONGVARBINARY], "BLOB")

    def test_st_entries_are_not_lo_types(self):
        for e in ts.TYPE_ENTRIES:
            if e["name"].endswith("_ST"):
                self.assertFalse(e["lo"])
                self.assertFalse(e["auto_increment"])

    def test_label_strips_the_suffix(self):
        for name, native in (("INTEGER_ST", "INTEGER"), ("REAL_ST", "REAL"), ("TEXT_ST", "TEXT"),
                             ("BLOB_ST", "BLOB"), ("ANY_ST", "ANY")):
            self.assertEqual(structure.column_label(name, 0, 0), native)
        self.assertEqual(structure.column_label("INTEGER", 0, 0), "INTEGER")
        self.assertEqual(structure.column_label("LO_VARCHAR", 50, 0), "LO_VARCHAR(50)")

    def test_strict_accepts_only_native_names(self):
        for label in ("INT", "integer", "REAL", "TEXT", "BLOB", "ANY"):
            self.assertTrue(ts.strict_accepts(label), label)
        for label in ("LO_TINYINT", "VARCHAR", "TEXT(5)", "DATE", "LO_VARCHAR(50)"):
            self.assertFalse(ts.strict_accepts(label), label)


class StrictTableTests(StructureCase):
    def setUp(self):
        super().setUp()
        self.sql("CREATE TABLE r (id INTEGER PRIMARY KEY, voto INTEGER, nome TEXT) STRICT")
        self.sql("INSERT INTO r(voto, nome) VALUES (7, 'a')")
        self.sql("CREATE TABLE n (id INTEGER PRIMARY KEY, voto INTEGER)")

    def test_is_strict(self):
        self.assertTrue(schema.is_strict(self.db, "r"))
        self.assertFalse(schema.is_strict(self.db, "n"))

    def test_lo_type_on_strict_table_gives_a_clear_error(self):
        error = self.expect(
            errors.STRICT_TYPE_NOT_ALLOWED,
            lambda: structure.alter_column(self.engine, "r", "voto", ColumnSpec("voto", "LO_TINYINT", False, None, False)),
            tabella="r", colonna="voto", tipo="LO_TINYINT")
        text = messages.describe(error, "it", "prova").message
        self.assertIn("STRICT", text)
        self.assertIn("INTEGER_ST", text)
        self.assertNotIn("sdbc_new", text)
        self.assertEqual(self.master("r").count("STRICT"), 1)

    def test_native_non_strict_name_is_refused_too(self):
        self.expect(errors.STRICT_TYPE_NOT_ALLOWED,
                    lambda: structure.alter_column(self.engine, "r", "nome", ColumnSpec("nome", "VARCHAR", False, None, False)))

    def test_native_type_works_and_table_stays_strict(self):
        structure.alter_column(self.engine, "r", "voto", ColumnSpec("voto", structure.column_label("REAL_ST", 0, 0),
                                                                     False, None, False))
        self.assertIn("STRICT", self.master("r"))
        self.assertEqual(self.all("SELECT voto FROM r"), [(7.0,)])

    def test_unchanged_column_is_not_checked(self):
        structure.alter_column(self.engine, "r", "voto", ColumnSpec("voto2", "INTEGER", False, None, False))
        self.assertEqual([c[0] for c in self.columns("r")], ["id", "voto2", "nome"])

    def test_add_column_to_strict_table(self):
        self.expect(errors.STRICT_TYPE_NOT_ALLOWED,
                    lambda: structure.add_column(self.engine, "r", ColumnSpec("x", "LO_DATE", False, None, False)))
        structure.add_column(self.engine, "r", ColumnSpec("x", structure.column_label("TEXT_ST", 0, 0), False, None, False))
        self.assertIn(("x", "TEXT", False), self.columns("r"))

    def test_normal_table_accepts_lo_types_and_st_types(self):
        structure.alter_column(self.engine, "n", "voto", ColumnSpec("voto", "LO_TINYINT", False, None, False))
        structure.add_column(self.engine, "n", ColumnSpec("t", structure.column_label("TEXT_ST", 0, 0), False, None, False))
        self.assertIn(("t", "TEXT", False), self.columns("n"))


class GeneratedAndVirtualTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:", isolation_level=None)
        self.addCleanup(self.db.close)
        self.engine = engine.Engine(self.db, EngineOptions(100, 50, "free"))

    def columns(self, sql):
        return self.engine.run(sql).result.columns

    def test_generated_columns_are_read_only(self):
        self.db.execute("CREATE TABLE ep (id INTEGER PRIMARY KEY, sec INT, "
                        "min INT GENERATED ALWAYS AS (sec/60) VIRTUAL, st INT GENERATED ALWAYS AS (sec*2) STORED)")
        self.db.execute("INSERT INTO ep(sec) VALUES (120)")
        cols = {c.label: c for c in self.columns("SELECT * FROM ep")}
        for name in ("min", "st"):
            self.assertTrue(cols[name].read_only, name)
            self.assertFalse(cols[name].writable, name)
        for name in ("id", "sec"):
            self.assertFalse(cols[name].read_only, name)
            self.assertTrue(cols[name].writable, name)

    def _fts(self):
        try:
            self.db.execute("CREATE VIRTUAL TABLE x_trame USING fts5(titolo, testo)")
        except sqlite.Error:
            self.skipTest("FTS5 non disponibile in questa libreria")
        self.db.execute("INSERT INTO x_trame VALUES ('Mazinga', 'robot gigante')")

    def test_shadow_tables_are_hidden(self):
        self._fts()
        self.db.execute("CREATE TABLE altra (a)")
        names = [name for name, _kind in schema.list_objects(self.db)]
        self.assertEqual(sorted(names), ["altra", "x_trame"])
        self.assertIn("x_trame_data", schema.shadow_tables(self.db))

    def test_reading_a_virtual_table_is_a_single_table(self):
        self._fts()
        cols = self.columns("SELECT titolo, testo FROM x_trame")
        for c in cols:
            self.assertEqual(c.table, "x_trame")
            self.assertEqual(c.ctype.name, "LO_VARIANT")

    def test_reading_a_virtual_table_with_match(self):
        self._fts()
        result = self.engine.run("SELECT titolo FROM x_trame WHERE x_trame MATCH 'robot'").result
        self.assertEqual(result.store.get(1), ("Mazinga",))
        self.assertEqual(result.columns[0].ctype.name, "LO_VARIANT")

    def test_generic_error_text_is_neutral(self):
        text = messages._SQLITE[1][4]
        self.assertNotIn("sintassi", text)
        self.assertNotIn("inesistente", text)
        self.assertNotIn("syntax", messages._SQLITE[1][5])


class TablesCatalogShadowTests(unittest.TestCase):

    def test_catalog_hides_shadow_tables(self):
        import support as _support
        _support.install_uno_stubs()
        from test_sdbc_objects import ObjectsTestCase

        class Case(ObjectsTestCase):
            def runTest(self):
                self.statement.execute("CREATE VIRTUAL TABLE x_trame USING fts5(titolo, testo)")
                self.statement.execute("CREATE TABLE altra (a)")
                tables = self.driver.getDataDefinitionByConnection(self.connection).getTables()
                self.assertEqual(sorted(tables.getElementNames()), ["altra", "t", "x_trame"])
                self.assertFalse(tables.hasByName("x_trame_data"))

        case = Case()
        case.setUp()
        try:
            case.runTest()
        finally:
            case.tearDown()


if __name__ == "__main__":
    unittest.main()
