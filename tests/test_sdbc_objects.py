# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os
import shutil
import tempfile
import unittest

import support

support.install_uno_stubs()

import test_uno_layer
from sdbc_pysqlite import errors
from sdbc_pysqlite.sdbc import driver as driver_module


def chain(warning):
    found = []
    while warning is not None:
        found.append(warning.Message)
        warning = warning.NextException
    return " || ".join(found)


class ObjectsTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        context = test_uno_layer.make_context(self.dir, "en", CreateIfMissing=True)
        self.driver = driver_module.Driver(context)
        self.connection = self.driver.connect(test_uno_layer.PREFIX + os.path.join(self.dir, "x.db"), ())
        self.statement = self.connection.createStatement()
        self.statement.execute(
            "CREATE TABLE t(id INTEGER PRIMARY KEY, n TEXT NOT NULL, d DATE, p LO_DECIMAL(10,2));"
            "INSERT INTO t(n, d, p) VALUES ('a', '2026-10-17', 12.34), ('b', NULL, 0.05)")

    def tearDown(self):
        self.connection.close()

    def code_of(self, function, *args):
        try:
            function(*args)
        except Exception as exception:
            return exception.ErrorCode
        return None


class ReadOnlyTableTriggerTests(ObjectsTestCase):

    MESSAGE = "tabella in sola lettura"

    def setUp(self):
        super().setUp()
        for event in ("INSERT", "UPDATE", "DELETE"):
            self.statement.execute(
                'CREATE TRIGGER "ro_%s" BEFORE %s ON t BEGIN SELECT RAISE(ABORT, \'%s\'); END'
                % (event.lower(), event, self.MESSAGE))

    def count(self):
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        return result.getInt(1)

    def message_of(self, function, *args):
        try:
            function(*args)
        except Exception as exception:
            return str(exception.Message)
        return None

    def test_existing_rows_cannot_be_changed_or_deleted(self):
        for sql in ("INSERT INTO t(n) VALUES ('x')", "UPDATE t SET n = 'z' WHERE id = 1", "DELETE FROM t WHERE id = 1",
                    "DELETE FROM t"):
            with self.subTest(sql=sql):
                message = self.message_of(self.statement.executeUpdate, sql)
                self.assertIsNotNone(message)
                self.assertIn(self.MESSAGE, message)
        self.assertEqual(self.count(), 2)
        result = self.statement.executeQuery("SELECT n FROM t WHERE id = 1")
        result.next()
        self.assertEqual(result.getString(1), "a")

    def test_prepared_statements_are_refused_too(self):
        for sql, params in (("INSERT INTO t(n) VALUES (?)", ("x",)), ("UPDATE t SET n = ? WHERE id = 1", ("z",)),
                            ("DELETE FROM t WHERE id = ?", (1,))):
            with self.subTest(sql=sql):
                prepared = self.connection.prepareStatement(sql)
                prepared.setString(1, str(params[0])) if isinstance(params[0], str) else prepared.setInt(1, params[0])
                self.assertIn(self.MESSAGE, self.message_of(prepared.executeUpdate))
        self.assertEqual(self.count(), 2)

    def test_reading_is_not_affected(self):
        result = self.statement.executeQuery("SELECT n FROM t ORDER BY id")
        names = []
        while result.next():
            names.append(result.getString(1))
        self.assertEqual(names, ["a", "b"])

    def test_dropping_the_table_removes_the_triggers(self):
        self.statement.execute("DROP TABLE t")
        result = self.statement.executeQuery("SELECT count(*) FROM sqlite_master WHERE type = 'trigger'")
        result.next()
        self.assertEqual(result.getInt(1), 0)


class StatementTests(ObjectsTestCase):
    def test_multiple_statements_queue(self):
        self.assertFalse(self.statement.execute("INSERT INTO t(n) VALUES ('c'); SELECT * FROM t; DELETE FROM t"))
        self.assertEqual(self.statement.getUpdateCount(), 1)
        self.assertTrue(self.statement.getMoreResults())
        self.assertEqual(self.statement.getUpdateCount(), -1)
        result = self.statement.getResultSet()
        self.assertTrue(result.next())
        self.assertFalse(self.statement.getMoreResults())
        self.assertEqual(self.statement.getUpdateCount(), 3)
        self.assertFalse(self.statement.getMoreResults())
        self.assertEqual(self.statement.getUpdateCount(), -1)

    def test_error_stops_at_first(self):
        self.assertIsNotNone(self.code_of(self.statement.execute, "INSERT INTO t(n) VALUES ('x'); selec 1; INSERT INTO t(n) VALUES ('y')"))
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        self.assertEqual(result.getInt(1), 3)

    def test_wrong_method_is_tolerated_with_warning(self):
        result = self.statement.executeQuery("INSERT INTO t(n) VALUES ('q')")
        self.assertFalse(result.next())
        self.assertIn("returns no rows", self.statement.getWarnings().Message)
        self.assertEqual(self.statement.executeUpdate("SELECT * FROM t"), 0)
        self.assertIn("rows discarded", self.statement.getWarnings().Message)
        self.statement.executeUpdate("DELETE FROM t WHERE 0")
        self.assertIsNone(self.statement.getWarnings())

    def test_update_count_and_returning(self):
        self.assertEqual(self.statement.executeUpdate("UPDATE t SET n = 'z'"), 2)
        self.assertEqual(self.statement.executeUpdate("INSERT INTO t(n) VALUES ('r') RETURNING id"), 1)
        self.assertIsNone(self.statement.getWarnings())

    def test_batch(self):
        self.statement.addBatch("INSERT INTO t(n) VALUES ('1')")
        self.statement.addBatch("INSERT INTO t(n) VALUES ('2'); INSERT INTO t(n) VALUES ('3')")
        self.assertEqual(self.statement.executeBatch(), (1, 1, 1))
        self.statement.addBatch("INSERT INTO t(n) VALUES ('4')")
        self.statement.addBatch("SELECT * FROM t")
        self.assertEqual(self.code_of(self.statement.executeBatch), errors.BATCH_RETURNED_ROWS)

    def test_closed_statement(self):
        self.statement.close()
        self.assertEqual(self.code_of(self.statement.executeQuery, "SELECT 1"), errors.STATEMENT_CLOSED)

    def test_close_closes_results(self):
        result = self.statement.executeQuery("SELECT * FROM t")
        self.statement.close()
        self.assertEqual(self.code_of(result.next), errors.RESULT_CLOSED)

    def test_max_rows(self):
        self.statement.setPropertyValue("MaxRows", 1)
        result = self.statement.executeQuery("SELECT * FROM t")
        self.assertTrue(result.next())
        self.assertFalse(result.next())

    def test_create_table_is_rewritten(self):
        self.statement.executeUpdate('CREATE TABLE "k" ("ID" LO_BIGINT NOT NULL AUTO_INCREMENT, "n" LO_VARCHAR(5), PRIMARY KEY ("ID"))')
        self.statement.executeUpdate('INSERT INTO "k"("n") VALUES (\'a\')')
        result = self.statement.executeQuery('SELECT "ID" FROM "k"')
        result.next()
        self.assertEqual(result.getInt(1), 1)


class ResultSetTests(ObjectsTestCase):
    def query(self, sql="SELECT * FROM t ORDER BY id"):
        return self.statement.executeQuery(sql)

    def test_metadata(self):
        meta = self.query().getMetaData()
        self.assertEqual(meta.getColumnCount(), 4)
        self.assertEqual([meta.getColumnLabel(i) for i in range(1, 5)], ["id", "n", "d", "p"])
        self.assertTrue(meta.isAutoIncrement(1))
        self.assertEqual(meta.isNullable(2), 0)
        self.assertEqual(meta.getTableName(1), "t")
        self.assertEqual(meta.getColumnTypeName(4), "LO_DECIMAL")
        self.assertEqual((meta.getPrecision(4), meta.getScale(4)), (10, 2))
        self.assertEqual(self.code_of(meta.getColumnLabel, 9), errors.COLUMN_OUT_OF_RANGE)

    def test_values_and_wasnull(self):
        result = self.query()
        self.assertTrue(result.next())
        self.assertEqual((result.getInt(1), result.getString(2)), (1, "a"))
        self.assertEqual(result.getString(4), "12.34")
        d = result.getDate(3)
        self.assertEqual((d.Year, d.Month, d.Day), (2026, 10, 17))
        self.assertTrue(result.next())
        self.assertEqual(result.getString(3), "")
        self.assertTrue(result.wasNull())
        self.assertEqual(result.getInt(3), 0)

    def test_errors(self):
        result = self.query()
        self.assertEqual(self.code_of(result.getInt, 1), errors.NO_CURRENT_ROW)
        result.next()
        self.assertEqual(self.code_of(result.getInt, 9), errors.COLUMN_OUT_OF_RANGE)
        self.assertEqual(self.code_of(result.getInt, 2), errors.VALUE_NOT_CONVERTIBLE)
        self.assertEqual(self.code_of(result.updateString, 2, "x"), errors.RESULT_READ_ONLY)
        self.assertEqual(self.code_of(result.deleteRow), errors.RESULT_READ_ONLY)
        result.close()
        self.assertEqual(self.code_of(result.next), errors.RESULT_CLOSED)

    def test_navigation_and_bookmarks(self):
        result = self.query()
        self.assertTrue(result.last())
        self.assertEqual(result.getRow(), 2)
        bookmark = result.getBookmark()
        self.assertTrue(result.first())
        self.assertTrue(result.moveToBookmark(bookmark))
        self.assertEqual(result.getInt(1), 2)
        self.assertEqual(result.findColumn("N"), 2)

    def test_properties(self):
        result = self.query()
        self.assertEqual(result.getPropertyValue("ResultSetType"), 1004)
        self.assertEqual(result.getPropertyValue("ResultSetConcurrency"), 1007)


class WindowedResultSetTests(unittest.TestCase):

    def test_next_block_reports_a_change_made_by_another_connection(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder, True)
        if True:
            context = test_uno_layer.make_context(folder, "it", CreateIfMissing=True, FullLoadLimit=10, WindowSize=5)
            driver = driver_module.Driver(context)
            url = test_uno_layer.PREFIX + os.path.join(folder, "x.db")
            first = driver.connect(url, ())
            second = driver.connect(url, ())
            try:
                statement = first.createStatement()
                statement.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")
                statement.execute("INSERT INTO t VALUES " + ",".join("(%d)" % n for n in range(1, 31)))
                result = statement.executeQuery("SELECT id FROM t ORDER BY id")
                second.createStatement().execute("DELETE FROM t WHERE id = 3")
                for _ in range(5):
                    self.assertTrue(result.next())
                try:
                    result.next()
                except Exception as exception:
                    self.assertEqual(exception.ErrorCode, errors.RESULT_OUT_OF_DATE)
                    self.assertIn("ATTENZIONE", exception.Message)
                else:
                    self.fail("l'errore non e' arrivato")
                self.assertEqual(result.getRow(), 5)
                self.assertEqual(result.getInt(1), 5)
            finally:
                first.close()
                second.close()


class ConnectionTests(ObjectsTestCase):
    def test_transactions(self):
        self.assertTrue(self.connection.getAutoCommit())
        self.connection.setAutoCommit(False)
        self.statement.executeUpdate("INSERT INTO t(n) VALUES ('t')")
        self.connection.rollback()
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        self.assertEqual(result.getInt(1), 2)
        self.statement.executeUpdate("INSERT INTO t(n) VALUES ('t')")
        self.connection.commit()
        self.connection.setAutoCommit(True)

    def test_open_results_survive_rollback(self):
        self.connection.setAutoCommit(False)
        result = self.statement.executeQuery("SELECT * FROM t")
        self.statement.executeUpdate("INSERT INTO t(n) VALUES ('t')")
        self.connection.rollback()
        self.assertTrue(result.next())

    def test_close_with_uncommitted_changes_warns(self):
        self.connection.setAutoCommit(False)
        self.statement.executeUpdate("INSERT INTO t(n) VALUES ('t')")
        self.connection.close()
        self.assertIn("discarded", chain(self.connection.getWarnings()))
        self.assertEqual(self.code_of(self.connection.createStatement), errors.CONNECTION_CLOSED)

    def test_isolation_warning(self):
        self.connection.setTransactionIsolation(2)
        self.assertIn("READ_COMMITTED", chain(self.connection.getWarnings()))


class MetaDataTests(ObjectsTestCase):
    def setUp(self):
        super().setUp()
        self.meta = self.connection.getMetaData()

    def rows(self, result, *columns):
        found = []
        while result.next():
            found.append(tuple(result.getString(c) for c in columns))
        return found

    def test_identity(self):
        self.assertEqual(self.meta.getDatabaseProductName(), "SQLite")
        self.assertTrue(self.meta.getURL().startswith("sdbc:external:pysqlite:"))
        self.assertFalse(self.meta.isReadOnly())
        self.assertEqual(self.meta.getDatabaseMajorVersion(), 3)

    def test_lists(self):
        self.assertEqual(self.rows(self.meta.getTables(None, None, "%", None), 3, 4), [("t", "TABLE")])
        self.assertEqual([r[0] for r in self.rows(self.meta.getColumns(None, None, "t", "%"), 4)], ["id", "n", "d", "p"])
        self.assertEqual(self.rows(self.meta.getPrimaryKeys(None, None, "t"), 4, 6), [("id", "PK_t")])
        self.assertEqual(len(self.rows(self.meta.getTypeInfo(), 1)), 55)
        self.assertEqual(self.rows(self.meta.getCatalogs()), [])
        self.assertEqual(self.rows(self.meta.getVersionColumns(None, None, "t")), [])

    def test_fixed_answers(self):
        meta = self.meta
        self.assertTrue(meta.supportsMultipleResultSets())
        self.assertTrue(meta.supportsSavepoints())
        self.assertEqual(meta.getResultSetHoldability(), 1)
        self.assertEqual(meta.getDefaultTransactionIsolation(), 8)
        self.assertTrue(meta.supportsTransactionIsolationLevel(8))
        self.assertFalse(meta.supportsTransactionIsolationLevel(2))
        self.assertTrue(meta.supportsResultSetType(1004))
        self.assertFalse(meta.supportsResultSetType(1005))
        self.assertTrue(meta.supportsResultSetConcurrency(1004, 1007))
        self.assertFalse(meta.supportsResultSetConcurrency(1004, 1008))
        self.assertEqual(meta.getSearchStringEscape(), "\\")
        self.assertEqual(meta.getIdentifierQuoteString(), '"')

    def test_convert(self):
        self.assertTrue(self.meta.supportsConvert(4, 12))
        self.assertTrue(self.meta.supportsConvert(93, 12))
        self.assertFalse(self.meta.supportsConvert(-3, 4))


class DriverWarningTests(unittest.TestCase):
    def test_old_library_warned_once(self):
        from sdbc_pysqlite import database
        dir_ = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, dir_, True)
        driver = driver_module.Driver(test_uno_layer.make_context(dir_, "en", CreateIfMissing=True))
        url = test_uno_layer.PREFIX + os.path.join(dir_, "x.db")
        driver_module.Driver._old_library_warned = False
        original = driver_module.old_library_version
        driver_module.old_library_version = lambda: "3.40.0"
        try:
            first = driver.connect(url, ())
            second = driver.connect(url, ())
            self.assertIn("3.40.0", chain(first.getWarnings()))
            self.assertNotIn("3.40.0", chain(second.getWarnings()))
            first.close(); second.close()
        finally:
            driver_module.old_library_version = original
            driver_module.Driver._old_library_warned = False


if __name__ == "__main__":
    unittest.main()
