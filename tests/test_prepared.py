# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import decimal
import unittest
from types import SimpleNamespace

import support

support.install_uno_stubs()

from test_sdbc_objects import ObjectsTestCase, chain
from sdbc_pysqlite import binding
from sdbc_pysqlite import errors


def rows_of(result):
    found = []
    while result.next():
        found.append((result.getInt(1), result.getString(2)))
    return found


class PreparedTests(ObjectsTestCase):
    def prepare(self, sql):
        return self.connection.prepareStatement(sql)

    def test_select_all_rows(self):
        ps = self.prepare('SELECT id, n FROM "t"')
        self.assertEqual(rows_of(ps.executeQuery()), [(1, "a"), (2, "b")])

    def test_where_parameter_and_reuse(self):
        ps = self.prepare("SELECT id, n FROM t WHERE n = ?")
        ps.setString(1, "a")
        self.assertEqual(rows_of(ps.executeQuery()), [(1, "a")])
        ps.setString(1, "b")
        self.assertEqual(rows_of(ps.executeQuery()), [(2, "b")])
        ps.executeQuery()
        ps.clearParameters()
        self.assertEqual(self.code_of(ps.executeQuery), errors.PARAMETER_NOT_SET)

    def test_missing_parameter_runs_nothing(self):
        ps = self.prepare("INSERT INTO t(n) VALUES (?); INSERT INTO t(n) VALUES (?)")
        ps.setString(1, "x")
        self.assertEqual(self.code_of(ps.executeUpdate), errors.PARAMETER_NOT_SET)
        self.assertEqual(self.statement.executeQuery("SELECT count(*) FROM t").next(), True)
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        self.assertEqual(result.getInt(1), 2)

    def test_index_out_of_range(self):
        ps = self.prepare("SELECT * FROM t WHERE n = ?")
        self.assertEqual(self.code_of(ps.setString, 2, "a"), errors.PARAMETER_OUT_OF_RANGE)
        self.assertEqual(self.code_of(ps.setString, 0, "a"), errors.PARAMETER_OUT_OF_RANGE)

    def test_multiple_commands_continuous_numbering(self):
        ps = self.prepare("INSERT INTO t(n) VALUES (?); UPDATE t SET n = ? WHERE id = ?")
        ps.setString(1, "new")
        ps.setString(2, "changed")
        ps.setInt(3, 1)
        self.assertFalse(ps.execute())
        self.assertEqual(ps.getUpdateCount(), 1)
        self.assertFalse(ps.getMoreResults())
        self.assertEqual(ps.getUpdateCount(), 1)
        result = self.statement.executeQuery("SELECT n FROM t ORDER BY id")
        result.next()
        self.assertEqual(result.getString(1), "changed")

    def test_null_and_blob_and_bool(self):
        self.statement.execute("CREATE TABLE b(x, y, z)")
        ps = self.prepare("INSERT INTO b VALUES (?, ?, ?)")
        ps.setNull(1, 12)
        ps.setBytes(2, __import__("uno").ByteSequence(b"\x01\x02"))
        ps.setBoolean(3, True)
        self.assertEqual(ps.executeUpdate(), 1)
        row = self.connection._db.execute("SELECT x, y, z FROM b").fetchone()
        self.assertEqual(row, (None, b"\x01\x02", 1))

    def test_decimal_column_scaled_on_insert(self):
        ps = self.prepare("INSERT INTO t(n, p) VALUES (?, ?)")
        ps.setString(1, "c")
        ps.setDouble(2, 12.34)
        ps.executeUpdate()
        value = self.connection._db.execute("SELECT p FROM t WHERE n = 'c'").fetchone()[0]
        self.assertEqual(value, 1234)

    def test_decimal_column_scaled_in_update_and_compare(self):
        ps = self.prepare("UPDATE t SET p = ? WHERE p = ?")
        ps.setString(1, "0.5")
        ps.setObject(2, decimal.Decimal("12.34"))
        self.assertEqual(ps.executeUpdate(), 1)
        self.assertEqual(self.connection._db.execute("SELECT p FROM t WHERE n = 'a'").fetchone()[0], 50)

    def test_decimal_not_a_number(self):
        ps = self.prepare("INSERT INTO t(n, p) VALUES (?, ?)")
        ps.setString(1, "c")
        ps.setString(2, "abc")
        self.assertEqual(self.code_of(ps.executeUpdate), errors.VALUE_NOT_CONVERTIBLE)

    def test_unmatched_parameter_warns(self):
        ps = self.prepare("SELECT id FROM t LIMIT ?")
        ps.setInt(1, 1)
        result = ps.executeQuery()
        self.assertTrue(result.next())
        self.assertIn("1", chain(ps.getWarnings()))
        self.assertFalse(result.next())

    def test_matched_parameter_no_warning(self):
        ps = self.prepare("SELECT id FROM t WHERE n = ?")
        ps.setString(1, "a")
        ps.executeQuery()
        self.assertIsNone(ps.getWarnings())

    def test_dates(self):
        self.statement.execute("CREATE TABLE dd(a LO_DATE, b LO_TIME, c LO_TIMESTAMP(3))")
        ps = self.prepare("INSERT INTO dd VALUES (?, ?, ?)")
        ps.setDate(1, SimpleNamespace(Year=2026, Month=10, Day=17))
        ps.setTime(2, SimpleNamespace(Hours=14, Minutes=5, Seconds=9, NanoSeconds=0))
        ps.setTimestamp(3, SimpleNamespace(Year=2026, Month=10, Day=17, Hours=14, Minutes=5, Seconds=9,
                                           NanoSeconds=123000000))
        ps.executeUpdate()
        row = self.connection._db.execute("SELECT a, b, c FROM dd").fetchone()
        self.assertEqual(row[0], "2026-10-17")
        self.assertEqual(row[1], "14:05:09")
        self.assertTrue(row[2].startswith("2026-10-17 14:05:09.123"))

    def test_batch_success(self):
        ps = self.prepare("INSERT INTO t(n) VALUES (?)")
        for name in ("x", "y", "z"):
            ps.setString(1, name)
            ps.addBatch()
        self.assertEqual(tuple(ps.executeBatch()), (1, 1, 1))
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        self.assertEqual(result.getInt(1), 5)

    def test_batch_failure_is_atomic_in_autocommit(self):
        ps = self.prepare("INSERT INTO t(n) VALUES (?)")
        ps.setString(1, "ok")
        ps.addBatch()
        ps.setNull(1, 12)
        ps.addBatch()
        try:
            ps.executeBatch()
        except Exception as exception:
            self.assertEqual(exception.ErrorCode, errors.BATCH_ROW_FAILED)
            self.assertIn("2", exception.Message)
        else:
            self.fail("atteso errore")
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        self.assertEqual(result.getInt(1), 2)

    def test_batch_failure_keeps_rows_in_manual_mode(self):
        self.connection.setAutoCommit(False)
        ps = self.prepare("INSERT INTO t(n) VALUES (?)")
        ps.setString(1, "ok")
        ps.addBatch()
        ps.setNull(1, 12)
        ps.addBatch()
        self.assertEqual(self.code_of(ps.executeBatch), errors.BATCH_ROW_FAILED)
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        self.assertEqual(result.getInt(1), 3)
        self.connection.rollback()

    def test_batch_with_rows_not_allowed(self):
        ps = self.prepare("SELECT * FROM t")
        ps.addBatch()
        self.assertEqual(self.code_of(ps.executeBatch), errors.BATCH_RETURNED_ROWS)

    def test_addbatch_needs_all_parameters(self):
        ps = self.prepare("INSERT INTO t(n) VALUES (?)")
        self.assertEqual(self.code_of(ps.addBatch), errors.PARAMETER_NOT_SET)

    def test_get_meta_data_before_execution(self):
        ps = self.prepare('SELECT * FROM "t" WHERE ( 0 = 1 )')
        meta = ps.getMetaData()
        self.assertEqual(meta.getColumnCount(), 4)
        self.assertEqual([meta.getColumnName(i) for i in range(1, 5)], ["id", "n", "d", "p"])
        self.assertEqual(meta.getTableName(2), "t")

    def test_get_meta_data_with_parameter(self):
        ps = self.prepare("SELECT n FROM t WHERE id = ?")
        self.assertEqual(ps.getMetaData().getColumnCount(), 1)

    def test_get_meta_data_translates_outer_join_escape(self):
        ps = self.prepare("SELECT a.id FROM { oj t a LEFT OUTER JOIN t b ON a.id = b.id } WHERE ( 0 = 1 )")
        self.assertEqual(ps.getMetaData().getColumnCount(), 1)

    def test_get_meta_data_of_update_is_empty(self):
        self.assertEqual(self.prepare("DELETE FROM t WHERE id = ?").getMetaData().getColumnCount(), 0)

    def test_get_meta_data_syntax_error(self):
        ps = self.prepare("SELECT * FROM nothere")
        self.assertIsNotNone(self.code_of(ps.getMetaData))

    def test_properties_and_max_rows(self):
        ps = self.prepare("SELECT id FROM t")
        self.assertEqual(ps.getPropertyValue("MaxRows"), 0)
        ps.setPropertyValue("ResultSetType", 1005)
        ps.setPropertyValue("MaxRows", 1)
        result = ps.executeQuery()
        self.assertEqual(result.getPropertyValue("ResultSetType"), 1004)
        self.assertTrue(result.next())
        self.assertFalse(result.next())

    def test_new_execution_new_result(self):
        ps = self.prepare("SELECT id FROM t")
        first = ps.executeQuery()
        second = ps.executeQuery()
        self.assertTrue(first.next())
        self.assertTrue(second.next())

    def test_closed_statement(self):
        ps = self.prepare("SELECT 1")
        ps.close()
        self.assertEqual(self.code_of(ps.executeQuery), errors.STATEMENT_CLOSED)
        self.assertEqual(self.code_of(ps.setInt, 1, 1), errors.STATEMENT_CLOSED)

    def test_execute_query_on_update_warns(self):
        ps = self.prepare("DELETE FROM t WHERE id = ?")
        ps.setInt(1, 99)
        result = ps.executeQuery()
        self.assertFalse(result.next())
        self.assertIn("executeQuery", chain(ps.getWarnings()))

    def test_unsupported_object(self):
        ps = self.prepare("SELECT ?")
        self.assertEqual(self.code_of(ps.setObject, 1, object()), errors.VALUE_NOT_CONVERTIBLE)


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        from sdbc_pysqlite import sqlite
        self.db = sqlite.connect(":memory:")
        self.db.execute("CREATE TABLE a(x LO_DECIMAL(10,2), y TEXT)")
        self.db.execute("CREATE TABLE b(x LO_INTEGER, z LO_DECIMAL(10,3))")

    def kinds(self, sql):
        return [None if s is None else getattr(s, "name", "Compare(%d)" % getattr(s, "scale", 0))
                for piece in binding.analyze(self.db, sql) for s in piece.slots]

    def test_insert_columns(self):
        self.assertEqual(self.kinds("INSERT INTO a (y, x) VALUES (?, ?)"), ["TEXT", "LO_DECIMAL"])

    def test_multi_row_values(self):
        self.assertEqual(self.kinds("INSERT INTO a (x, y) VALUES (?, ?), (?, 'k')"),
                         ["LO_DECIMAL", "TEXT", "LO_DECIMAL"])

    def test_expression_in_values_unmatched(self):
        self.assertEqual(self.kinds("INSERT INTO a (x, y) VALUES (? + 1, ?)"), [None, "TEXT"])

    def test_ambiguous_column(self):
        with self.assertRaises(errors.DriverError) as caught:
            self.kinds("SELECT * FROM a JOIN b ON 1 WHERE x = ?")
        self.assertEqual(caught.exception.code, errors.DECIMAL_AMBIGUOUS)

    def test_qualified_column(self):
        self.assertEqual(self.kinds("SELECT * FROM a JOIN b ON 1 WHERE b.x = ?"), ["LO_INTEGER"])

    def test_operators(self):
        for op in ("<", ">", "<=", ">=", "<>", "!="):
            self.assertEqual(self.kinds("SELECT * FROM a WHERE x %s ?" % op), ["Compare(2)"], op)
        self.assertEqual(self.kinds("SELECT * FROM a WHERE x LIKE ?"), [None])

    def test_numbered_placeholder_ignored(self):
        self.assertEqual(self.kinds("SELECT * FROM a WHERE x = ?1"), [])

    def test_pieces_split(self):
        pieces = binding.analyze(self.db, "UPDATE a SET y = ?; DELETE FROM a WHERE x = ?")
        self.assertEqual([len(p.slots) for p in pieces], [1, 1])


if __name__ == "__main__":
    unittest.main()
