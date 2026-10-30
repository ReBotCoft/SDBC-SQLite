# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import random
import unittest
from decimal import Decimal

import support

support.install_uno_stubs()

from test_sdbc_objects import ObjectsTestCase
from sdbc_pysqlite import decimals
from sdbc_pysqlite import errors
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.errors import DriverError

SCHEMA = """
CREATE TABLE persone(id INTEGER PRIMARY KEY, nome TEXT, importo LO_DECIMAL(10,2));
CREATE TABLE ordini(id INTEGER PRIMARY KEY, importo REAL, pid INTEGER);
CREATE TABLE tre(id INTEGER PRIMARY KEY, v LO_DECIMAL(10,3));
CREATE TABLE zero(id INTEGER PRIMARY KEY, q LO_DECIMAL(10,0));
"""

REWRITES = [
    ("SELECT importo FROM persone", "SELECT importo FROM persone"),
    ("SELECT * FROM persone", "SELECT * FROM persone"),
    ("SELECT p.importo, nome FROM persone p WHERE p.importo > 12.5 ORDER BY importo",
     "SELECT p.importo, nome FROM persone p WHERE p.importo > 1250 ORDER BY importo"),
    ("SELECT SUM(importo), AVG(DISTINCT importo) FROM persone",
     'SELECT (SUM(importo) / 100.0) AS "SUM(importo)", (AVG(DISTINCT importo) / 100.0) AS "AVG(DISTINCT importo)" FROM persone'),
    ("SELECT MAX(importo) FROM persone", 'SELECT (MAX(importo) / 100.0) AS "MAX(importo)" FROM persone'),
    ("SELECT SUM(importo) OVER (ORDER BY id) FROM persone",
     'SELECT SUM((importo / 100.0)) OVER (ORDER BY id) AS "SUM(importo) OVER (ORDER BY id)" FROM persone'),
    ("SELECT ROUND(importo, 1) FROM persone", 'SELECT (ROUND(importo / 10.0) / 10.0) AS "ROUND(importo, 1)" FROM persone'),
    ("SELECT ROUND(importo), ROUND(p.importo, 0) FROM persone p",
     'SELECT ROUND(importo / 100.0) AS "ROUND(importo)", ROUND(p.importo / 100.0) AS "ROUND(p.importo, 0)" FROM persone p'),
    ("SELECT ROUND(v, 2), ROUND(v, 3), ROUND(v, 1 + 0) FROM tre",
     'SELECT (ROUND(v / 10.0) / 100.0) AS "ROUND(v, 2)", ROUND((v / 1000.0), 3) AS "ROUND(v, 3)", ROUND((v / 1000.0), 1 + 0) AS "ROUND(v, 1 + 0)" FROM tre'),
    ("SELECT ROUND(importo * 2, 1) FROM persone", 'SELECT ROUND((importo / 100.0) * 2, 1) AS "ROUND(importo * 2, 1)" FROM persone'),
    ("SELECT importo * 2 FROM persone", 'SELECT (importo / 100.0) * 2 AS "importo * 2" FROM persone'),
    ("SELECT importo FROM persone WHERE importo BETWEEN 1 AND 20.5 AND id IN (1,2)",
     "SELECT importo FROM persone WHERE importo BETWEEN 100 AND 2050 AND id IN (1,2)"),
    ("SELECT importo FROM persone WHERE importo NOT IN (1, 2.5)",
     "SELECT importo FROM persone WHERE importo NOT IN (100, 250)"),
    ("SELECT id FROM persone WHERE 12.5 < importo", "SELECT id FROM persone WHERE 1250 < importo"),
    ("SELECT id FROM persone WHERE importo >= -0.5", "SELECT id FROM persone WHERE importo >= -50"),
    ("SELECT id FROM persone WHERE importo = '7.25'", "SELECT id FROM persone WHERE importo = 725"),
    ("SELECT id FROM persone WHERE importo > 12.345", "SELECT id FROM persone WHERE importo > 1234.5"),
    ("SELECT id FROM persone WHERE importo > 5 + 1", "SELECT id FROM persone WHERE (importo / 100.0) > 5 + 1"),
    ("SELECT id FROM persone WHERE importo = id", "SELECT id FROM persone WHERE (importo / 100.0) = id"),
    ("SELECT id FROM persone WHERE importo IS NULL OR importo IS NOT NULL",
     "SELECT id FROM persone WHERE importo IS NULL OR importo IS NOT NULL"),
    ("SELECT CASE WHEN importo > 10 THEN 'a' ELSE 'b' END FROM persone",
     "SELECT CASE WHEN importo > 1000 THEN 'a' ELSE 'b' END AS \"CASE WHEN importo > 10 THEN 'a' ELSE 'b' END\" FROM persone"),
    ("SELECT nome FROM persone GROUP BY importo HAVING SUM(importo) > 100",
     "SELECT nome FROM persone GROUP BY importo HAVING (SUM(importo) / 100.0) > 100"),
    ("SELECT CAST(importo AS TEXT) FROM persone", 'SELECT CAST((importo / 100.0) AS TEXT) AS "CAST(importo AS TEXT)" FROM persone'),
    ("SELECT persone.importo FROM persone JOIN ordini ON persone.id = ordini.pid",
     "SELECT persone.importo FROM persone JOIN ordini ON persone.id = ordini.pid"),
    ("SELECT ordini.importo FROM persone JOIN ordini ON persone.id = ordini.pid WHERE ordini.importo > 5",
     "SELECT ordini.importo FROM persone JOIN ordini ON persone.id = ordini.pid WHERE ordini.importo > 5"),
    ("SELECT importo FROM persone UNION SELECT importo FROM ordini",
     'SELECT (importo / 100.0) AS "importo" FROM persone UNION SELECT importo FROM ordini'),
    ("SELECT a FROM (SELECT importo AS a FROM persone)", "SELECT a FROM (SELECT (importo / 100.0) AS a FROM persone)"),
    ("WITH t(a) AS (SELECT importo FROM persone) SELECT a FROM t",
     'WITH t(a) AS (SELECT (importo / 100.0) AS "importo" FROM persone) SELECT a FROM t'),
    ("SELECT id FROM persone WHERE importo > (SELECT AVG(importo) FROM persone)",
     'SELECT id FROM persone WHERE (importo / 100.0) > (SELECT (AVG(importo) / 100.0) AS "AVG(importo)" FROM persone)'),
    ("INSERT INTO persone(nome, importo) VALUES ('x', 12.345), ('y', 3)",
     "INSERT INTO persone(nome, importo) VALUES ('x', 1235), ('y', 300)"),
    ("INSERT INTO persone VALUES (9, 'x', 12.5)", "INSERT INTO persone VALUES (9, 'x', 1250)"),
    ("INSERT INTO persone(importo) SELECT importo FROM persone", "INSERT INTO persone(importo) SELECT importo FROM persone"),
    ("INSERT INTO persone(importo) SELECT v FROM tre",
     "INSERT INTO persone(importo) SELECT CAST(ROUND(100 * ((v / 1000.0))) AS INTEGER) FROM tre"),
    ("INSERT INTO persone(id, importo) VALUES (1, 5) ON CONFLICT(id) DO UPDATE SET importo = excluded.importo",
     "INSERT INTO persone(id, importo) VALUES (1, 500) ON CONFLICT(id) DO UPDATE SET importo = excluded.importo"),
    ("INSERT INTO persone(id, importo) VALUES (1, 5) ON CONFLICT(id) DO UPDATE SET importo = excluded.importo + 1 WHERE importo < 100",
     "INSERT INTO persone(id, importo) VALUES (1, 500) ON CONFLICT(id) DO UPDATE SET importo = CAST(ROUND(100 * ((excluded.importo / 100.0) + 1)) AS INTEGER) WHERE importo < 10000"),
    ("UPDATE persone SET importo = 12.5 WHERE importo > 3", "UPDATE persone SET importo = 1250 WHERE importo > 300"),
    ("UPDATE persone SET importo = importo + 1, nome = 'a' WHERE id = 3",
     "UPDATE persone SET importo = CAST(ROUND(100 * ((importo / 100.0) + 1)) AS INTEGER), nome = 'a' WHERE id = 3"),
    ("UPDATE persone SET importo = importo WHERE id = 3", "UPDATE persone SET importo = importo WHERE id = 3"),
    ("UPDATE persone SET importo = NULL", "UPDATE persone SET importo = NULL"),
    ("UPDATE persone SET importo = ? WHERE id = 3 RETURNING importo",
     'UPDATE persone SET importo = ? WHERE id = 3 RETURNING (importo / 100.0) AS "importo"'),
    ("DELETE FROM persone WHERE importo = 0.07", "DELETE FROM persone WHERE importo = 7"),
    ("INSERT INTO persone(nome) VALUES ('x') RETURNING importo",
     'INSERT INTO persone(nome) VALUES (\'x\') RETURNING (importo / 100.0) AS "importo"'),
    ("CREATE VIEW v AS SELECT importo FROM persone", 'CREATE VIEW v AS SELECT (importo / 100.0) AS "importo" FROM persone'),
    ("CREATE TABLE n AS SELECT importo FROM persone", 'CREATE TABLE n AS SELECT (importo / 100.0) AS "importo" FROM persone'),
    ("SELECT COUNT(*) FROM persone WHERE nome = 'importo'", "SELECT COUNT(*) FROM persone WHERE nome = 'importo'"),
    ("SELECT id, importo FROM ordini WHERE importo > 5", "SELECT id, importo FROM ordini WHERE importo > 5"),
    ("SELECT v FROM tre", "SELECT v FROM tre"),
    ("SELECT SUM(q) FROM zero WHERE q > 5", "SELECT SUM(q) FROM zero WHERE q > 5"),
    ("CREATE INDEX ip ON persone(importo)", "CREATE INDEX ip ON persone(importo)"),
    ("PRAGMA table_info(persone)", "PRAGMA table_info(persone)"),
    ("EXPLAIN QUERY PLAN SELECT * FROM persone WHERE importo > 12.5",
     "EXPLAIN QUERY PLAN SELECT * FROM persone WHERE importo > 1250"),
]

REJECTS = [
    ("SELECT importo FROM persone JOIN ordini ON persone.id = ordini.pid", errors.DECIMAL_AMBIGUOUS),
    ("SELECT * FROM persone NATURAL JOIN ordini", errors.DECIMAL_NATURAL_JOIN),
    ("SELECT * FROM persone JOIN ordini USING (importo)", errors.DECIMAL_NATURAL_JOIN),
    ("CREATE TRIGGER tr AFTER INSERT ON persone BEGIN UPDATE persone SET importo = 1 WHERE id = new.id; END",
     errors.DECIMAL_TRIGGER),
    ("INSERT INTO persone(importo) SELECT * FROM tre", errors.DECIMAL_NOT_UNDERSTOOD),
    ("INSERT INTO persone(id, nome, importo) VALUES (1, 'x')", errors.DECIMAL_NOT_UNDERSTOOD),
    ("UPDATE persone SET (nome, importo) = ('a', 5)", errors.DECIMAL_NOT_UNDERSTOOD),
    ("SELECT importo FROM persone WHERE (id = 1", errors.DECIMAL_NOT_UNDERSTOOD),
]


class TranslatorTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:")
        self.db.executescript(SCHEMA)

    def tearDown(self):
        self.db.close()

    def test_rewrites(self):
        for sql, expected in REWRITES:
            with self.subTest(sql=sql):
                self.assertEqual(decimals.translate(self.db, sql).text, expected)

    def test_rewrites_are_valid_sql(self):
        for sql, expected in REWRITES:
            if sql.startswith(("CREATE INDEX", "PRAGMA")) or "VALUES (1, 500) ON CONFLICT" in expected:
                continue
            with self.subTest(sql=sql):
                if expected.startswith(("SELECT", "WITH", "EXPLAIN")):
                    self.db.execute(expected.replace("?", "1"), ()).fetchall()
                else:
                    self.db.execute("SAVEPOINT s")
                    try:
                        self.db.execute(expected.replace("?", "1"), ())
                    finally:
                        self.db.execute("ROLLBACK TO s")

    def test_rejects(self):
        for sql, code in REJECTS:
            with self.subTest(sql=sql):
                with self.assertRaises(DriverError) as caught:
                    decimals.translate(self.db, sql)
                self.assertEqual(caught.exception.code, code)

    def test_warnings(self):
        self.assertEqual([w.code for w in decimals.translate(self.db, "CREATE VIEW v AS SELECT importo FROM persone").warnings],
                         [errors.DECIMAL_VIEW_PLAIN])
        self.assertEqual([w.code for w in decimals.translate(self.db, "CREATE TABLE n AS SELECT importo FROM persone").warnings],
                         [errors.DECIMAL_NEW_TABLE_PLAIN])
        self.assertEqual(decimals.translate(self.db, "CREATE TABLE n2 AS SELECT id FROM ordini").warnings, [])

    def test_placeholders(self):
        t = decimals.translate(self.db, "UPDATE persone SET importo = ? WHERE importo > ? AND id = ?")
        self.assertEqual(t.text, "UPDATE persone SET importo = ? WHERE importo > ? AND id = ?")
        self.assertEqual(t.slots[0].scale, 2)
        self.assertEqual(t.slots[1], decimals.Compare(2))
        self.assertNotIn(2, t.slots)
        t = decimals.translate(self.db, "SELECT id FROM persone WHERE importo BETWEEN ? AND ? OR importo IN (?, ?)")
        self.assertEqual(sorted(t.slots), [0, 1, 2, 3])
        self.assertTrue(all(s == decimals.Compare(2) for s in t.slots.values()))
        t = decimals.translate(self.db, "INSERT INTO persone(nome, importo) VALUES (?, ?)")
        self.assertNotIn(0, t.slots)
        self.assertEqual(t.slots[1].scale, 2)
        t = decimals.translate(self.db, "UPDATE persone SET importo = ? + 1")
        self.assertEqual(t.slots, {})

    def test_named_parameters(self):
        t = decimals.translate(self.db, "SELECT id FROM persone WHERE importo > :importo AND importo < @top AND importo <> :importo")
        self.assertEqual(sorted(t.slots), [0, 1])
        self.assertTrue(all(s == decimals.Compare(2) for s in t.slots.values()))
        t = decimals.translate(self.db, "UPDATE persone SET importo = $nuovo WHERE 7 < importo")
        self.assertEqual(t.text, "UPDATE persone SET importo = $nuovo WHERE 700 < importo")
        self.assertEqual(t.slots[0].scale, 2)

    def test_schema_cache_follows_changes(self):
        self.assertEqual(decimals.translate(self.db, "SELECT SUM(w) FROM extra").text, "SELECT SUM(w) FROM extra")
        self.db.execute("CREATE TABLE extra(w LO_DECIMAL(8,1))")
        self.assertEqual(decimals.translate(self.db, "SELECT SUM(w) FROM extra").text,
                         'SELECT (SUM(w) / 10.0) AS "SUM(w)" FROM extra')

    def test_no_decimal_columns_at_all(self):
        db = sqlite.connect(":memory:")
        db.execute("CREATE TABLE a(x INTEGER)")
        t = decimals.translate(db, "SELECT x FROM a WHERE x > 1")
        self.assertFalse(t.decimal)
        db.close()


class ResultTests(unittest.TestCase):

    def setUp(self):
        self.db = sqlite.connect(":memory:")
        self.db.executescript(SCHEMA)

    def tearDown(self):
        self.db.close()

    def run_sql(self, sql, params=()):
        t = decimals.translate(self.db, sql)
        return self.db.execute(t.text, params).fetchall()

    def test_insert_update_read(self):
        self.run_sql("INSERT INTO persone(nome, importo) VALUES ('a', 12.345), ('b', 0.07), ('c', -12.345), ('d', 3)")
        self.assertEqual(self.db.execute("SELECT importo FROM persone ORDER BY id").fetchall(),
                         [(1235,), (7,), (-1235,), (300,)])
        self.assertAlmostEqual(self.run_sql("SELECT SUM(importo) FROM persone")[0][0], 3.07, places=9)
        self.assertEqual(self.run_sql("SELECT MAX(importo), MIN(importo) FROM persone"), [(12.35, -12.35)])
        self.assertEqual(self.run_sql("SELECT nome FROM persone WHERE importo = 0.07"), [("b",)])
        self.assertEqual(self.run_sql("SELECT nome FROM persone WHERE importo = 0.07 * 1"), [("b",)])
        self.assertEqual(self.run_sql("SELECT nome FROM persone WHERE importo > 12.345"), [("a",)])
        self.assertEqual(self.run_sql("SELECT nome FROM persone WHERE importo > 12.344 ORDER BY id"), [("a",)])
        self.run_sql("UPDATE persone SET importo = importo + 1 WHERE nome = 'd'")
        self.assertEqual(self.db.execute("SELECT importo FROM persone WHERE nome = 'd'").fetchall(), [(400,)])
        self.run_sql("UPDATE persone SET importo = 7.25 WHERE nome = 'd'")
        self.assertEqual(self.db.execute("SELECT importo FROM persone WHERE nome = 'd'").fetchall(), [(725,)])
        self.assertEqual(self.run_sql("UPDATE persone SET importo = 1.5 WHERE nome = 'd' RETURNING importo"), [(1.5,)])

    def test_copy_between_scales(self):
        self.db.execute("INSERT INTO tre(v) VALUES (12345), (-12345), (1)")
        self.run_sql("INSERT INTO persone(importo) SELECT importo FROM persone")
        self.run_sql("INSERT INTO persone(importo) SELECT v FROM tre ORDER BY id")
        self.assertEqual(self.db.execute("SELECT importo FROM persone ORDER BY id").fetchall(),
                         [(1235,), (-1235,), (0,)])

    def test_upsert(self):
        self.run_sql("INSERT INTO persone(id, importo) VALUES (1, 5)")
        self.run_sql("INSERT INTO persone(id, importo) VALUES (1, 7.5) ON CONFLICT(id) DO UPDATE SET importo = excluded.importo")
        self.assertEqual(self.db.execute("SELECT importo FROM persone").fetchall(), [(750,)])
        self.run_sql("INSERT INTO persone(id, importo) VALUES (1, 1) ON CONFLICT(id) DO UPDATE SET importo = importo + excluded.importo")
        self.assertEqual(self.db.execute("SELECT importo FROM persone").fetchall(), [(850,)])

    def test_models_equal_general_rule(self):
        rng = random.Random(7)
        rows = [(i, rng.randint(-100000, 100000)) for i in range(1, 400)]
        self.db.cursor().executemany("INSERT INTO persone(id, importo) VALUES (?, ?)", rows)
        self.db.execute("CREATE INDEX ip ON persone(importo)")
        for func in ("SUM", "AVG", "MAX", "MIN"):
            model = self.run_sql("SELECT %s(importo) FROM persone" % func)[0][0]
            general = self.db.execute("SELECT %s(importo / 100.0) FROM persone" % func).fetchone()[0]
            self.assertAlmostEqual(model, general, places=6, msg=func)
        for op in ("=", "<", ">", "<=", ">=", "<>"):
            for literal in ("0", "12.5", "-3.07", "999.99", "12.345"):
                model = self.run_sql("SELECT id FROM persone WHERE importo %s %s ORDER BY id" % (op, literal))
                exact = [(i,) for i, v in rows if _compare(Decimal(v) / 100, op, Decimal(literal))]
                self.assertEqual(model, exact, (op, literal))
        model = self.run_sql("SELECT id FROM persone WHERE importo BETWEEN -5.5 AND 7.25 ORDER BY id")
        self.assertEqual(model, [(i,) for i, v in rows if Decimal("-5.5") <= Decimal(v) / 100 <= Decimal("7.25")])
        self.run_sql("UPDATE persone SET importo = importo * 3 / 2")
        again = dict(self.db.execute("SELECT id, importo FROM persone").fetchall())
        for i, v in rows:
            self.assertAlmostEqual(again[i], round(v * 3 / 2 + 1e-9), delta=1, msg=i)

    def test_round_is_exact(self):
        from decimal import ROUND_HALF_UP
        rng = random.Random(11)
        values = [rng.randint(-10 ** 7, 10 ** 7) for _ in range(5000)] + [1235, -1235, 125, -125, 5, -5, 0, 1250]
        self.db.cursor().executemany("INSERT INTO persone(importo) VALUES (?)", [(v,) for v in values])
        self.db.cursor().executemany("INSERT INTO tre(v) VALUES (?)", [(v,) for v in values])
        for digits, column, table, scale in ((0, "importo", "persone", 2), (1, "importo", "persone", 2),
                                             (0, "v", "tre", 3), (1, "v", "tre", 3), (2, "v", "tre", 3)):
            sql = "SELECT ROUND(%s, %d) FROM %s ORDER BY id" % (column, digits, table) if digits else \
                  "SELECT ROUND(%s) FROM %s ORDER BY id" % (column, table)
            got = [r[0] for r in self.run_sql(sql)]
            exact = [float((Decimal(v) / 10 ** scale).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))
                     for v in values]
            self.assertEqual(got, exact, (digits, column))

    def test_index_is_used(self):
        self.db.execute("CREATE INDEX ip ON persone(importo)")
        for sql in ("SELECT id FROM persone WHERE importo > 12.5", "SELECT MAX(importo) FROM persone",
                    "SELECT id FROM persone ORDER BY importo"):
            plan = " ".join(str(r[-1]) for r in self.run_sql("EXPLAIN QUERY PLAN " + sql))
            self.assertIn("ip", plan, sql)

    def test_column_names_kept(self):
        self.db.execute("INSERT INTO persone(nome, importo) VALUES ('a', 1250)")
        cur = self.db.execute(decimals.translate(self.db, "SELECT SUM(importo), importo * 2 FROM persone").text)
        self.assertEqual([d[0] for d in cur.description], ["SUM(importo)", "importo * 2"])
        cur = self.db.execute(decimals.translate(self.db, "SELECT importo FROM persone UNION SELECT importo FROM ordini").text)
        self.assertEqual([d[0] for d in cur.description], ["importo"])

    def test_cte_and_subquery_values(self):
        self.db.execute("INSERT INTO persone(nome, importo) VALUES ('a', 1250)")
        self.assertEqual(self.run_sql("WITH t(a) AS (SELECT importo FROM persone) SELECT a FROM t"), [(12.5,)])
        self.assertEqual(self.run_sql("SELECT a FROM (SELECT importo AS a FROM persone)"), [(12.5,)])
        self.assertEqual(self.run_sql("SELECT importo FROM persone UNION SELECT importo FROM ordini"), [(12.5,)])
        self.assertEqual(self.run_sql("SELECT nome FROM persone WHERE importo > (SELECT AVG(importo) / 2 FROM persone)"),
                         [("a",)])

    def test_view_and_ctas(self):
        self.db.execute("INSERT INTO persone(nome, importo) VALUES ('a', 1250)")
        self.run_sql("CREATE VIEW v AS SELECT importo FROM persone")
        self.run_sql("CREATE TABLE n AS SELECT importo FROM persone")
        self.assertEqual(self.db.execute("SELECT importo FROM v").fetchall(), [(12.5,)])
        self.assertEqual(self.db.execute("SELECT importo FROM n").fetchall(), [(12.5,)])
        self.assertNotIn("LO_DECIMAL", self.db.execute("SELECT sql FROM sqlite_master WHERE name = 'n'").fetchone()[0])


def _compare(a, op, b):
    return {"=": a == b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b, "<>": a != b}[op]


class DriverPathTests(ObjectsTestCase):

    def setUp(self):
        super().setUp()
        self.statement.execute("CREATE TABLE persone(id INTEGER PRIMARY KEY, nome TEXT, importo LO_DECIMAL(10,2));"
                               "CREATE TABLE ordini(id INTEGER PRIMARY KEY, importo REAL, pid INTEGER)")

    def rows(self, sql):
        result = self.connection.createStatement().executeQuery(sql)
        out = []
        while result.next():
            out.append(result.getString(1))
        return out

    def test_statement(self):
        self.statement.executeUpdate("INSERT INTO persone(nome, importo) VALUES ('a', 12.5), ('b', 3.333)")
        self.assertEqual(self.rows("SELECT importo FROM persone ORDER BY id"), ["12.50", "3.33"])
        self.assertEqual(self.rows("SELECT SUM(importo) FROM persone"), ["15.83"])
        self.assertEqual(self.rows("SELECT nome FROM persone WHERE importo > 5"), ["a"])
        self.assertEqual(self.statement.executeUpdate("UPDATE persone SET importo = importo * 2 WHERE nome = 'b'"), 1)
        self.assertEqual(self.rows("SELECT importo FROM persone WHERE nome = 'b'"), ["6.66"])

    def test_statement_reject(self):
        self.assertEqual(self.code_of(self.statement.executeQuery,
                                      "SELECT importo FROM persone JOIN ordini ON persone.id = ordini.pid"),
                         errors.DECIMAL_AMBIGUOUS)

    def test_statement_warning(self):
        self.statement.executeUpdate("CREATE VIEW vv AS SELECT importo FROM persone")
        self.assertIsNotNone(self.statement.getWarnings())

    def test_prepared(self):
        insert = self.connection.prepareStatement("INSERT INTO persone(nome, importo) VALUES (?, ?)")
        for name, value in (("a", 12.5), ("b", 3.335), ("c", 1)):
            insert.setString(1, name)
            insert.setDouble(2, value)
            insert.executeUpdate()
        self.assertEqual(self.rows("SELECT importo FROM persone ORDER BY id"), ["12.50", "3.34", "1.00"])
        select = self.connection.prepareStatement("SELECT nome FROM persone WHERE importo > ? ORDER BY id")
        select.setDouble(1, 3.335)
        result = select.executeQuery()
        names = []
        while result.next():
            names.append(result.getString(1))
        self.assertEqual(names, ["a", "b"])
        select.setDouble(1, 3.34)
        result = select.executeQuery()
        names = []
        while result.next():
            names.append(result.getString(1))
        self.assertEqual(names, ["a"])

    def test_prepared_named_parameters(self):
        self.statement.executeUpdate("INSERT INTO persone(nome, importo) VALUES ('a', 12.35), ('b', 8.5), ('c', 0.07)")
        select = self.connection.prepareStatement("SELECT nome FROM persone WHERE importo > :soglia ORDER BY id")
        select.setDouble(1, 10)
        result = select.executeQuery()
        self.assertTrue(result.next())
        self.assertEqual(result.getString(1), "a")
        self.assertFalse(result.next())
        self.assertEqual(self.code_of(select.setDouble, 2, 1.0), errors.PARAMETER_OUT_OF_RANGE)
        twice = self.connection.prepareStatement(
            "SELECT nome FROM persone WHERE importo > :basso AND importo < :alto AND id <> :basso ORDER BY id")
        twice.setDouble(1, 0.07)
        twice.setDouble(2, 9)
        result = twice.executeQuery()
        self.assertTrue(result.next())
        self.assertEqual(result.getString(1), "b")
        self.assertFalse(result.next())
        self.assertEqual(self.code_of(twice.setDouble, 3, 1.0), errors.PARAMETER_OUT_OF_RANGE)

    def test_prepared_reject_at_preparation(self):
        self.assertEqual(self.code_of(self.connection.prepareStatement,
                                      "SELECT importo FROM persone JOIN ordini ON persone.id = ordini.pid"),
                         errors.DECIMAL_AMBIGUOUS)

    def test_prepared_two_tables(self):
        self.statement.executeUpdate("INSERT INTO persone(nome, importo) VALUES ('a', 12.5)")
        self.statement.executeUpdate("INSERT INTO ordini(importo, pid) VALUES (2.5, 1)")
        select = self.connection.prepareStatement(
            "SELECT p.nome FROM persone p JOIN ordini o ON o.pid = p.id WHERE p.importo > ? AND o.importo < ?")
        select.setDouble(1, 12.4)
        select.setDouble(2, 3)
        result = select.executeQuery()
        self.assertTrue(result.next())
        self.assertEqual(result.getString(1), "a")


if __name__ == "__main__":
    unittest.main()
