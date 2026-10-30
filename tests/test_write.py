# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os
import unittest

import support

support.install_uno_stubs()

from test_sdbc_objects import ObjectsTestCase
import test_uno_layer
from sdbc_pysqlite import errors
from sdbc_pysqlite import messages
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import sqltext
from sdbc_pysqlite.errors import DriverError


class WriteTestCase(ObjectsTestCase):
    def setUp(self):
        super().setUp()
        self.statement.execute(
            "CREATE TABLE comp(a INTEGER, b INTEGER, PRIMARY KEY (a, b));"
            "CREATE TABLE nokey(x TEXT);"
            "CREATE TABLE norowid(k TEXT PRIMARY KEY, v TEXT) WITHOUT ROWID;"
            "CREATE VIEW vt AS SELECT id, n FROM t")
        self.meta = self.connection.getMetaData()

    def driver_for(self, **options):
        from sdbc_pysqlite.sdbc import driver as driver_module
        return driver_module.Driver(test_uno_layer.make_context(self.dir, "en", CreateIfMissing=True, **options))

    def privileges(self, meta=None, pattern="%"):
        result = (meta or self.meta).getTablePrivileges(None, None, pattern)
        found = {}
        while result.next():
            found.setdefault(result.getString(3), []).append((result.getString(5), result.getString(6)))
        return found

    def insert(self, sql, *params):
        ps = self.connection.prepareStatement(sql)
        for number, value in enumerate(params, 1):
            ps.setObject(number, value) if not isinstance(value, str) else ps.setString(number, value)
        ps.executeUpdate()
        return ps

    def generated(self, ps):
        result = ps.getGeneratedValues()
        rows = []
        while result.next():
            rows.append(result.getLong(1))
        return rows


class PrivilegeTests(WriteTestCase):
    def test_tables_get_data_and_structure_privileges(self):
        found = self.privileges()
        user = self.meta.getUserName()
        wanted = ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REFERENCE")
        for table in ("t", "comp", "nokey", "norowid"):
            self.assertEqual(found[table], [(user, p) for p in wanted], table)

    def test_view_can_be_selected_and_dropped(self):
        self.assertEqual([p for _u, p in self.privileges()["vt"]], ["SELECT", "DROP"])

    def test_grantee_is_the_user_name_base_compares(self):
        self.assertTrue(all(user == self.meta.getUserName() for rows in self.privileges().values()
                            for user, _p in rows))

    def test_pattern_selects_one_table(self):
        self.assertEqual(list(self.privileges(pattern="comp")), ["comp"])

    def test_read_only_connection_gives_select_only(self):
        driver = self.driver_for(ReadOnly=True)
        connection = driver.connect(test_uno_layer.PREFIX + os.path.join(self.dir, "x.db"), ())
        self.addCleanup(connection.close)
        found = self.privileges(connection.getMetaData())
        self.assertTrue(found)
        for table, rows in found.items():
            self.assertEqual([p for _u, p in rows], ["SELECT"], table)

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "il permesso di scrittura non vale per l'amministratore")
    def test_unwritable_file_gives_select_only(self):
        path = os.path.join(self.dir, "x.db")
        os.chmod(path, 0o444)
        connection = self.driver_for().connect(test_uno_layer.PREFIX + path, ())
        self.addCleanup(connection.close)
        self.assertTrue(connection.getMetaData().isReadOnly())
        for table, rows in self.privileges(connection.getMetaData()).items():
            self.assertEqual([p for _u, p in rows], ["SELECT"], table)

    def test_column_privileges_stay_empty(self):
        result = self.meta.getColumnPrivileges(None, None, "t", "%")
        self.assertFalse(result.next())


class GeneratedValuesTests(WriteTestCase):
    def test_insert_returns_the_assigned_number(self):
        ps = self.insert("INSERT INTO t(n) VALUES (?)", "c")
        self.assertEqual(self.generated(ps), [3])
        ps.setString(1, "d")
        ps.executeUpdate()
        self.assertEqual(self.generated(ps), [4])

    def test_number_written_by_the_user_is_returned(self):
        ps = self.insert("INSERT INTO t(id, n) VALUES (?, ?)", 100, "x")
        self.assertEqual(self.generated(ps), [100])

    def test_column_name_is_the_key_column(self):
        ps = self.insert("INSERT INTO t(n) VALUES (?)", "c")
        result = ps.getGeneratedValues()
        self.assertEqual(result.getMetaData().getColumnCount(), 1)
        self.assertEqual(result.getMetaData().getColumnName(1), "id")

    def test_auto_increment_reuse_option_does_not_change_the_rule(self):
        for reuse in (False, True):
            driver = self.driver_for(AutoIncrementReuse=reuse)
            name = "auto-%s.db" % reuse
            connection = driver.connect(test_uno_layer.PREFIX + os.path.join(self.dir, name), ())
            self.addCleanup(connection.close)
            statement = connection.createStatement()
            statement.execute('CREATE TABLE "q" ("id" LO_BIGINT NOT NULL AUTO_INCREMENT, "n" TEXT, PRIMARY KEY ("id"))')
            ps = connection.prepareStatement("INSERT INTO q(n) VALUES (?)")
            ps.setString(1, "a")
            ps.executeUpdate()
            self.assertEqual(self.generated(ps), [1])
            statement.execute("DELETE FROM q")
            ps.executeUpdate()
            self.assertEqual(self.generated(ps), [1 if reuse else 2], reuse)

    def test_ignored_insert_has_no_generated_value(self):
        ps = self.connection.prepareStatement("INSERT OR IGNORE INTO t(id, n) VALUES (?, ?)")
        ps.setInt(1, 1)
        ps.setString(2, "dup")
        ps.executeUpdate()
        self.assertEqual(self.generated(ps), [])

    def test_not_an_insert_gives_empty(self):
        ps = self.connection.prepareStatement("UPDATE t SET n = ? WHERE id = 1")
        ps.setString(1, "z")
        ps.executeUpdate()
        self.assertEqual(self.generated(ps), [])
        ps = self.connection.prepareStatement("SELECT id FROM t")
        ps.executeQuery()
        self.assertEqual(self.generated(ps), [])

    def test_last_command_decides(self):
        ps = self.connection.prepareStatement("INSERT INTO t(n) VALUES (?); DELETE FROM t WHERE id = 1")
        ps.setString(1, "c")
        ps.execute()
        self.assertEqual(self.generated(ps), [])

    def test_before_any_execution_is_empty(self):
        ps = self.connection.prepareStatement("INSERT INTO t(n) VALUES (?)")
        self.assertEqual(self.generated(ps), [])

    def test_tables_without_rowid_alias_give_empty(self):
        for sql in ("INSERT INTO comp VALUES (?, 1)", "INSERT INTO nokey VALUES (?)"):
            ps = self.connection.prepareStatement(sql)
            ps.setObject(1, 5)
            ps.executeUpdate()
            self.assertEqual(self.generated(ps), [], sql)
        ps = self.connection.prepareStatement("INSERT INTO norowid VALUES (?, 'v')")
        ps.setString(1, "k")
        ps.executeUpdate()
        self.assertEqual(self.generated(ps), [])

    def test_insert_target_with_quotes_and_schema(self):
        ps = self.connection.prepareStatement('INSERT INTO main."t"(n) VALUES (?)')
        ps.setString(1, "c")
        ps.executeUpdate()
        self.assertEqual(self.generated(ps), [3])

    def test_batch_keeps_the_last_insert(self):
        ps = self.connection.prepareStatement("INSERT INTO t(n) VALUES (?)")
        for text in ("c", "d", "e"):
            ps.setString(1, text)
            ps.addBatch()
        ps.executeBatch()
        self.assertEqual(self.generated(ps), [5])

    def test_closed_statement_refuses(self):
        ps = self.connection.prepareStatement("INSERT INTO t(n) VALUES (?)")
        ps.close()
        self.assertEqual(self.code_of(ps.getGeneratedValues), errors.STATEMENT_CLOSED)


class DirectCommandPlaceholderTests(WriteTestCase):
    def test_question_mark_in_a_direct_command(self):
        self.assertEqual(self.code_of(self.statement.executeQuery, "SELECT * FROM t WHERE n = ?"),
                         errors.PARAMETER_NOT_SET)
        self.assertEqual(self.code_of(self.statement.executeUpdate, "DELETE FROM t WHERE id = :id"),
                         errors.PARAMETER_NOT_SET)
        self.assertEqual(self.code_of(self.statement.execute, "SELECT ?1"), errors.PARAMETER_NOT_SET)

    def test_nothing_runs_when_a_later_command_has_a_placeholder(self):
        self.assertEqual(self.code_of(self.statement.execute, "DELETE FROM t; SELECT ?"),
                         errors.PARAMETER_NOT_SET)
        result = self.statement.executeQuery("SELECT count(*) FROM t")
        result.next()
        self.assertEqual(result.getInt(1), 2)

    def test_placeholder_characters_in_texts_and_comments_are_fine(self):
        result = self.statement.executeQuery("SELECT 'che? :si @no $mai' AS x /* ? */ -- ?")
        self.assertTrue(result.next())
        self.assertEqual(result.getString(1), "che? :si @no $mai")

    def test_message_explains_both_cases(self):
        for language in ("it", "en"):
            text = messages.describe(DriverError(errors.PARAMETER_NOT_SET, numero=1), language, "").message
            self.assertIn("SQL", text)
            self.assertIn("?", text)

    def test_count_parameters(self):
        self.assertEqual(sqltext.count_parameters("SELECT ?, ?2, :a, @b, $c"), 5)
        self.assertEqual(sqltext.count_parameters("SELECT '?' /* : */ -- @"), 0)


class InsertTargetTests(unittest.TestCase):
    def test_targets(self):
        cases = {
            "INSERT INTO t VALUES (1)": "t",
            "insert or ignore into [Mia tabella](a) values (1)": "Mia tabella",
            'REPLACE INTO main."x y" VALUES (1)': "x y",
            "INSERT OR REPLACE INTO `q` DEFAULT VALUES": "q",
            "UPDATE t SET a = 1": None,
            "SELECT 1": None,
            "": None,
        }
        for sql, expected in cases.items():
            self.assertEqual(sqltext.insert_target(sql), expected, sql)


if __name__ == "__main__":
    unittest.main()
