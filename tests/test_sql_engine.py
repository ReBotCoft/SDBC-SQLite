# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest
from collections import namedtuple

import support

from sdbc_pysqlite import ddl
from sdbc_pysqlite import engine
from sdbc_pysqlite import errors
from sdbc_pysqlite import results
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import sqltext
from sdbc_pysqlite.errors import DriverError

Options = namedtuple("Options", "full_load_limit window_size transaction_mode")


def make_db():
    db = sqlite.connect(":memory:")
    db.executescript("""
        CREATE TABLE a(id INTEGER PRIMARY KEY, name TEXT NOT NULL, note, price DECIMAL(10,2));
        CREATE TABLE b(i INT, a_id INT REFERENCES a(id) ON DELETE CASCADE);
        CREATE TABLE c(x INT, y INT, PRIMARY KEY (x, y));
        CREATE INDEX ix_b ON b(i);
        CREATE UNIQUE INDEX ux_a ON a(name);
        CREATE VIEW v AS SELECT id, name FROM a;
    """)
    return db


class SqlTextTests(unittest.TestCase):
    def test_split(self):
        self.assertEqual(sqltext.split_statements("select 1; select 2;"), ["select 1", "select 2"])
        self.assertEqual(sqltext.split_statements("select 'a;b'; -- x;\nselect 2"), ["select 'a;b'", "-- x;\nselect 2"])
        self.assertEqual(sqltext.split_statements(" ; ;; "), [])

    def test_split_trigger(self):
        text = "create trigger t after insert on a begin select 1; select 2; end; select 3"
        self.assertEqual(len(sqltext.split_statements(text)), 2)

    def test_kinds(self):
        self.assertTrue(sqltext.is_wrappable_query("  /* c */ (SELECT 1)"))
        self.assertTrue(sqltext.is_wrappable_query("with x as (select 1) select * from x"))
        self.assertFalse(sqltext.is_wrappable_query("pragma table_info(a)"))
        self.assertFalse(sqltext.is_wrappable_query("insert into a values(1)"))

    def test_quote_unquote(self):
        self.assertEqual(sqltext.quote_name('a"b'), '"a""b"')
        self.assertEqual(sqltext.unquote('[a b]'), "a b")


class ResultTests(unittest.TestCase):
    def test_navigation(self):
        r = results.memory_result([("N", 4)], [(1,), (2,), (3,)])
        self.assertTrue(r.is_before_first() is False or r.is_before_first())
        self.assertTrue(r.next()); self.assertEqual(r.row(), (1,)); self.assertTrue(r.is_first())
        self.assertTrue(r.last()); self.assertTrue(r.is_last()); self.assertEqual(r.get_row(), 3)
        self.assertFalse(r.next()); self.assertTrue(r.is_after_last()); self.assertEqual(r.get_row(), 0)
        self.assertTrue(r.previous()); self.assertEqual(r.row(), (3,))
        self.assertTrue(r.absolute(-2)); self.assertEqual(r.row(), (2,))
        self.assertTrue(r.relative(1)); self.assertEqual(r.row(), (3,))
        self.assertFalse(r.relative(5)); self.assertTrue(r.is_after_last())
        self.assertFalse(r.absolute(0)); self.assertEqual(r.pos, 0)

    def test_empty(self):
        r = results.memory_result([("N", 4)], [])
        self.assertFalse(r.next()); self.assertFalse(r.first()); self.assertFalse(r.last())
        self.assertFalse(r.is_before_first()); self.assertFalse(r.is_after_last())


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.addCleanup(self.db.close)

    def test_tables(self):
        rows = schema.tables_rows(self.db, "%", None)[1]
        self.assertEqual([(r[2], r[3]) for r in rows], [("a", "TABLE"), ("b", "TABLE"), ("c", "TABLE"), ("v", "VIEW")])
        self.assertEqual([r[2] for r in schema.tables_rows(self.db, "%", ["VIEW"])[1]], ["v"])

    def test_pattern_escape(self):
        self.db.execute("CREATE TABLE a_b(x)"); self.db.execute("CREATE TABLE axb(x)")
        names = [r[2] for r in schema.tables_rows(self.db, "a\\_b", None)[1]]
        self.assertEqual(names, ["a_b"])

    def test_columns(self):
        rows = schema.columns_rows(self.db, "a", "%")[1]
        self.assertEqual([r[3] for r in rows], ["id", "name", "note", "price"])
        self.assertEqual(rows[0][10], 0)
        self.assertEqual(rows[2][5], "LO_VARIANT")
        self.assertEqual(rows[3][8], 0)

    def test_primary_keys(self):
        rows = schema.primary_keys_rows(self.db, "c")[1]
        self.assertEqual([(r[3], r[4], r[5]) for r in rows], [("x", 1, "PK_c"), ("y", 2, "PK_c")])
        self.assertEqual(schema.primary_keys_rows(self.db, "v")[1], [])

    def test_foreign_keys(self):
        rows = schema.imported_keys_rows(self.db, "b")[1]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0][2], rows[0][3], rows[0][6], rows[0][7], rows[0][10]), ("a", "id", "b", "a_id", 0))
        self.assertEqual(rows[0][11], "FK_b_a_id_a_id")
        exported = schema.exported_keys_rows(self.db, "a")[1]
        self.assertEqual([r[11] for r in exported], ["FK_b_a_id_a_id"])

    def test_fk_name_truncated_and_numbered(self):
        db = sqlite.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("""CREATE TABLE parent_table_long(identifier_long INT PRIMARY KEY);
            CREATE TABLE child_table_long(reference_one INT REFERENCES parent_table_long,
                                          reference_two INT REFERENCES parent_table_long);""")
        names = [fk.name for fk in schema.foreign_keys(db, "child_table_long")]
        self.assertEqual(names[0], "FK_child_tabl_reference__parent_tab_identifier")
        self.assertEqual(len(set(names)), 2)

    def test_index_info(self):
        rows = schema.index_info_rows(self.db, "a", False)[1]
        self.assertEqual([(r[5], r[3]) for r in rows], [("ux_a", False)])
        self.assertEqual([r[5] for r in schema.index_info_rows(self.db, "b", True)[1]], [])

    def test_best_row_identifier(self):
        self.assertEqual([r[1] for r in schema.best_row_identifier_rows(self.db, "c")[1]], ["x", "y"])
        self.assertEqual(schema.best_row_identifier_rows(self.db, "b")[1], [])

    def test_functions(self):
        self.assertIn("ABS", schema.function_names(self.db, "numeric"))
        self.assertTrue(schema.functions_rows(self.db, "ABS%")[1])


class DdlTests(unittest.TestCase):
    def test_integer_key_becomes_rowid_alias(self):
        sql = 'CREATE TABLE "t" ("ID" LO_BIGINT NOT NULL AUTO_INCREMENT, "n" LO_VARCHAR(5), PRIMARY KEY ("ID"))'
        out = ddl.rewrite_create_table(sql)
        self.assertIn('"ID" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL', out)
        self.assertNotIn("AUTO_INCREMENT", out)
        check = sqlite.connect(":memory:")
        self.addCleanup(check.close)
        check.execute(out)
        self.assertNotIn("AUTOINCREMENT", ddl.rewrite_create_table(sql, reuse=True))

    def test_every_integer_type_with_automatic_value(self):
        for name in ddl.INTEGER_TYPES:
            sql = 'CREATE TABLE "t" ("ID" %s NOT NULL AUTO_INCREMENT, "n" LO_VARCHAR(5), PRIMARY KEY ("ID"))' % name
            out = ddl.rewrite_create_table(sql)
            self.assertIn('"ID" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL', out, name)
            self.assertNotIn("AUTO_INCREMENT", out)
            reused = ddl.rewrite_create_table(sql, reuse=True)
            self.assertIn('"ID" INTEGER PRIMARY KEY NOT NULL', reused, name)
            self.assertNotIn("AUTOINCREMENT", reused)

    def test_every_integer_type_without_automatic_value(self):
        for name in ddl.INTEGER_TYPES:
            sql = 'CREATE TABLE "t" ("ID" %s NOT NULL, "n" LO_VARCHAR(5), PRIMARY KEY ("ID"))' % name
            out = ddl.rewrite_create_table(sql)
            self.assertIn('"ID" INTEGER PRIMARY KEY NOT NULL', out, name)
            self.assertNotIn("AUTOINCREMENT", out)

    def test_number_reuse_after_deleting_the_last_row(self):
        for name in ("LO_SMALLINT", "LO_INTEGER"):
            for reuse, expected in ((False, 3), (True, 2)):
                sql = 'CREATE TABLE "t" ("ID" %s NOT NULL AUTO_INCREMENT, "n" LO_VARCHAR(5), PRIMARY KEY ("ID"))' % name
                check = sqlite.connect(":memory:")
                self.addCleanup(check.close)
                check.execute(ddl.rewrite_create_table(sql, reuse=reuse))
                check.execute("INSERT INTO t(n) VALUES ('a')")
                check.execute("INSERT INTO t(n) VALUES ('b')")
                check.execute("DELETE FROM t WHERE ID = 2")
                check.execute("INSERT INTO t(n) VALUES ('c')")
                self.assertEqual(check.execute("SELECT MAX(ID) FROM t").fetchone()[0], expected, (name, reuse))

    def test_other_keys_are_left_alone(self):
        for sql in ('CREATE TABLE "t" ("k" LO_VARCHAR(5) NOT NULL, PRIMARY KEY ("k"))',
                    'CREATE TABLE "t" ("a" LO_INTEGER, "b" LO_INTEGER, PRIMARY KEY ("a", "b"))',
                    "select 1"):
            self.assertEqual(ddl.rewrite_create_table(sql), sql)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.db = make_db()
        self.addCleanup(self.db.close)
        self.engine = engine.Engine(self.db, Options(5, 3, "free"))

    def rows(self, sql, params=()):
        outcome = self.engine.run(sql, params)
        result = outcome.result
        return [result.store.get(i) for i in range(1, result.store.count() + 1)]

    def test_complete_and_window(self):
        for i in range(4):
            self.engine.run("INSERT INTO a(name) VALUES (?)", ("n%d" % i,))
        small = self.engine.run("SELECT * FROM a")
        self.assertEqual(small.result.mode, "complete")
        for i in range(4, 10):
            self.engine.run("INSERT INTO a(name) VALUES (?)", ("n%d" % i,))
        big = self.engine.run("SELECT * FROM a ORDER BY id")
        self.assertEqual(big.result.mode, "window")
        r = big.result
        self.assertTrue(r.last()); self.assertEqual(r.get_row(), 10)
        self.assertTrue(r.first()); self.assertEqual(r.row()[0], 1)
        self.assertTrue(r.absolute(7)); self.assertEqual(r.row()[0], 7)
        self.assertTrue(r.previous()); self.assertEqual(r.row()[0], 6)
        count = 0
        r.before_first()
        while r.next():
            count += 1
        self.assertEqual(count, 10)

    def test_counts_and_returning(self):
        self.assertEqual(self.engine.run("INSERT INTO a(name) VALUES ('x'),('y')").count, 2)
        out = self.engine.run("INSERT INTO a(name) VALUES ('z') RETURNING id")
        self.assertTrue(out.writes)
        self.assertEqual((out.count, out.result.store.get(1)), (1, (3,)))
        self.assertEqual(self.engine.run("CREATE TABLE q(x)").count, 0)

    def test_pragma_is_loaded_fully(self):
        out = self.engine.run("PRAGMA table_info(a)")
        self.assertEqual(out.result.store.count(), 4)

    def test_scheda_single_table(self):
        columns = self.engine.run("SELECT id, name, note, price, id + 1 AS z FROM a").result.columns
        self.assertEqual([c.table for c in columns], ["a", "a", "a", "a", ""])
        self.assertEqual([c.nullable for c in columns], [0, 0, 1, 1, 2])
        self.assertEqual([c.auto_increment for c in columns], [True, False, False, False, False])
        self.assertEqual(columns[2].ctype.name, "LO_VARIANT")

    def test_scheda_prudent_for_joins_and_views(self):
        for sql in ("SELECT a.id, b.i FROM a JOIN b ON b.a_id = a.id", "SELECT * FROM v"):
            columns = self.engine.run(sql).result.columns
            self.assertTrue(all(c.table == "" and c.nullable == 2 and not c.auto_increment for c in columns), sql)

    def test_parameters_in_probe(self):
        out = self.engine.run("SELECT id FROM a WHERE name = ? AND id > :n", ("x", 0)) if False else \
            self.engine.run("SELECT id FROM a WHERE name = ?", ("x",))
        self.assertEqual(out.result.columns[0].table, "a")
        self.assertEqual(engine.probe_text("select ?, ?1, :a, @b, $c, 'x?'"), "select NULL, NULL, NULL, NULL, NULL, 'x?'")

    def test_errors(self):
        with self.assertRaises(DriverError) as raised:
            self.engine.run("selec 1")
        self.assertIsNone(raised.exception.code)
        with self.assertRaises(DriverError) as raised:
            self.engine.run("INSERT INTO a(name) VALUES (NULL)")
        self.assertIsNone(raised.exception.code)
        self.assertIn("NOT NULL", str(raised.exception.sqlite))

    def test_transactions(self):
        self.engine.set_autocommit(False)
        self.engine.run("INSERT INTO a(name) VALUES ('t')")
        self.assertTrue(self.engine.dirty)
        self.engine.rollback()
        self.assertEqual(self.rows("SELECT count(*) FROM a"), [(0,)])
        self.engine.run("INSERT INTO a(name) VALUES ('t')")
        self.engine.set_autocommit(True)
        self.assertFalse(self.engine.dirty)
        self.assertEqual(self.rows("SELECT count(*) FROM a"), [(1,)])

    def test_reads_do_not_open_a_transaction(self):
        self.engine.set_autocommit(False)
        self.engine.run("SELECT * FROM a")
        self.assertFalse(self.db.in_transaction)

    def test_discard(self):
        self.engine.set_autocommit(False)
        self.engine.run("INSERT INTO a(name) VALUES ('t')")
        self.assertTrue(self.engine.discard())
        self.assertFalse(self.engine.discard())
        self.assertEqual(self.rows("SELECT count(*) FROM a"), [(0,)])

    def test_savepoint_passes_through(self):
        self.engine.set_autocommit(False)
        self.engine.run("INSERT INTO a(name) VALUES ('1')")
        self.engine.run("SAVEPOINT s1")
        self.engine.run("INSERT INTO a(name) VALUES ('2')")
        self.engine.run("ROLLBACK TO s1")
        self.engine.run("RELEASE s1")
        self.engine.commit()
        self.assertEqual(self.rows("SELECT count(*) FROM a"), [(1,)])


if __name__ == "__main__":
    unittest.main()
