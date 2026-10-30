# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os
import re
import tempfile
import unittest

import support

support.install_uno_stubs()

from sdbc_pysqlite import CONFIG_PATH
from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import configuration
from sdbc_pysqlite import errors
from sdbc_pysqlite import logger
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.sdbc import driver as driver_module

PREFIX = "sdbc:external:pysqlite:"
LINE = re.compile(r"^(?P<time>[^|]+) \| (?P<level>\w+) \| (?P<code>[0-9a-f]*) \| (?P<label>[^|]+) \| (?P<message>.*)$")


def make_context(log_dir, language="en", **overrides):
    values = {"Trace": True, "LogPath": log_dir, "LogRetentionDays": 14,
              "CreateIfMissing": False, "LockTimeoutSeconds": 5, "ForeignKeys": False,
              "ReadOnly": False, "JournalMode": "delete", "FullLoadLimit": 50000,
              "WindowSize": 1000, "TransactionMode": "free", "DateTimeFormat": "text",
              "DateTimeZone": "local", "NamesLanguage": "auto", "AutoIncrementReuse": False, "RowIdAsKey": False, "OldLibraryWarning": True,
              "DefensiveMode": False, "UntrustedSchema": False, "LimitsProfile": "none"}
    values.update(overrides)
    return support.FakeContext({
        CONFIG_PATH: values,
        "/org.openoffice.Setup/L10N": {"ooLocale": language},
    })


class UnoLayerTests(unittest.TestCase):

    def setUp(self):
        original = driver_module.old_library_version
        driver_module.old_library_version = lambda: ""
        self.addCleanup(setattr, driver_module, "old_library_version", original)
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.dir = self._dir.name
        self.log_dir = os.path.join(self.dir, "log")
        os.makedirs(self.log_dir)
        self.db = os.path.join(self.dir, "prova.db")
        connection = sqlite.connect(self.db)
        connection.execute("create table t(a)")
        connection.commit()
        connection.close()
        self.connections = []

    def tearDown(self):
        for connection in self.connections:
            connection.close()
        handler = logger._state["handler"]
        if handler is not None:
            logger._logger.removeHandler(handler)
            handler.close()
        logger._state.update(file=None, days=None, handler=None)

    def driver(self, **kwargs):
        language = kwargs.pop("language", "en")
        return driver_module.Driver(make_context(self.log_dir, language, **kwargs))

    def connect(self, driver, url):
        connection = driver.connect(url, ())
        self.connections.append(connection)
        return connection

    def log_lines(self):
        path = os.path.join(self.log_dir, "sdbc-pysqlite.log")
        with open(path, encoding="utf-8") as handle:
            lines = [line.rstrip("\n") for line in handle if line.strip()]
        parsed = []
        for line in lines:
            match = LINE.match(line)
            self.assertIsNotNone(match, line)
            parsed.append(match.groupdict())
        return parsed

    def test_read_settings(self):
        settings = configuration.read_settings(
            make_context(self.log_dir, "it_IT", LockTimeoutSeconds=9, JournalMode="wal", ForeignKeys=True))
        self.assertEqual((settings.lock_timeout_seconds, settings.journal_mode, settings.foreign_keys),
                         (9, "wal", True))
        self.assertEqual(settings.language, "it")
        self.assertEqual(settings.error, "")
        self.assertEqual(settings.connection_values()["JournalMode"], "wal")

    def test_missing_setting_keeps_the_others(self):
        context = make_context(self.log_dir)
        del context.nodes[CONFIG_PATH]["JournalMode"]
        settings = configuration.read_settings(context)
        self.assertEqual(settings.journal_mode, "delete")
        self.assertEqual(settings.log_path, self.log_dir)
        self.assertIn("JournalMode", settings.error)

    def test_unreadable_configuration_gives_defaults(self):
        settings = configuration.read_settings(support.FakeContext({}))
        self.assertTrue(settings.error)
        self.assertEqual(settings.language, "en")

    def test_unknown_language_is_english(self):
        context = support.FakeContext({CONFIG_PATH: make_context(self.log_dir).nodes[CONFIG_PATH]})
        self.assertEqual(configuration.read_settings(context).language, "en")

    def test_connect_returns_open_connection(self):
        connection = self.connect(self.driver(), PREFIX + self.db)
        self.assertFalse(connection.isClosed())
        self.assertFalse(connection.isReadOnly())
        self.assertEqual(connection.getTransactionIsolation(), 8)
        self.assertIsNone(connection.getWarnings())
        self.assertEqual(connection._db.execute("select count(*) from sqlite_master").fetchone()[0], 1)

    def test_other_url_is_not_accepted(self):
        driver = self.driver()
        self.assertFalse(driver.acceptsURL("sdbc:mysql:x"))
        self.assertIsNone(driver.connect("sdbc:mysql:x", ()))

    def test_close(self):
        connection = self.connect(self.driver(), PREFIX + self.db)
        connection.close()
        self.assertTrue(connection.isClosed())
        connection.close()
        with self.assertRaises(sqlite.ProgrammingError):
            connection._db.execute("select 1")

    def test_dispose_closes(self):
        connection = self.connect(self.driver(), PREFIX + self.db)
        connection.dispose()
        self.assertTrue(connection.isClosed())

    def test_read_only_from_address_and_from_options(self):
        driver = self.driver()
        self.assertTrue(self.connect(driver, PREFIX + self.db + "?ReadOnly=true").isReadOnly())
        driver = self.driver(ReadOnly=True)
        self.assertTrue(self.connect(driver, PREFIX + self.db).isReadOnly())
        self.assertFalse(self.connect(driver, PREFIX + self.db + "?ReadOnly=false").isReadOnly())

    def test_set_read_only_is_only_a_hint(self):
        connection = self.connect(self.driver(), PREFIX + self.db)
        connection.setReadOnly(True)
        self.assertFalse(connection.isReadOnly())
        statement = connection.createStatement()
        statement.execute("CREATE TABLE r(a INTEGER); INSERT INTO r VALUES (1)")
        self.assertEqual(connection._db.execute("select count(*) from r").fetchone()[0], 1)
        connection.setReadOnly(False)
        self.assertFalse(connection.isReadOnly())
        locked = self.connect(self.driver(), PREFIX + self.db + "?ReadOnly=true")
        locked.setReadOnly(False)
        self.assertTrue(locked.isReadOnly())

    def test_creation_warning_chain_in_italian(self):
        new = os.path.join(self.dir, "x", "nuovo.db")
        connection = self.connect(self.driver(language="it_IT"),
                                  PREFIX + new + "?CreateIfMissing=true&JournalMode=wal")
        warning = connection.getWarnings()
        self.assertEqual((warning.ErrorCode, warning.SQLState), (50006, "01000"))
        self.assertIn("Il nuovo database è stato creato", warning.Message)
        self.assertIsNone(warning.NextException)
        connection.clearWarnings()
        self.assertIsNone(connection.getWarnings())

    def test_two_warnings_are_chained(self):
        connection = self.connect(self.driver(), PREFIX + self.db + "?ReadOnly=true&JournalMode=wal")
        first = connection.getWarnings()
        self.assertEqual(first.ErrorCode, 50106)
        connection.setTransactionIsolation(2)
        first = connection.getWarnings()
        self.assertEqual(first.ErrorCode, 50106)
        self.assertEqual(first.NextException.ErrorCode, 50202)
        self.assertIn("READ_COMMITTED", first.NextException.Message)

    def test_serializable_request_gives_no_warning(self):
        connection = self.connect(self.driver(), PREFIX + self.db)
        connection.setTransactionIsolation(8)
        self.assertIsNone(connection.getWarnings())

    def test_error_is_a_sql_exception_in_the_ui_language(self):
        driver = self.driver(language="it")
        with self.assertRaises(Exception) as caught:
            driver.connect(PREFIX + os.path.join(self.dir, "manca.db"), ())
        exception = caught.exception
        self.assertEqual((exception.ErrorCode, exception.SQLState), (50001, "08001"))
        self.assertIn("Il file del database non esiste ancora", exception.Message)
        self.assertTrue(exception.Message.endswith("[codice 50001 · SQLState 08001 · sdbc.driver.Driver.connect]"))

    def test_log_of_an_error_is_english_once_and_has_the_code(self):
        driver = self.driver(language="it")
        with self.assertRaises(Exception):
            driver.connect(PREFIX + self.db + "?Boh=1", ())
        errors_in_log = [line for line in self.log_lines() if line["level"] == "ERROR"]
        mine = [line for line in errors_in_log if "Unknown parameter" in line["message"]]
        self.assertEqual(len(mine), 1)
        self.assertEqual(len(errors_in_log), 1, errors_in_log)
        self.assertEqual(len(mine[0]["code"]), 6)
        self.assertNotIn("Parametro", mine[0]["message"])

    def test_sql_exception_passing_through_a_traced_method_is_not_logged_again(self):
        from com.sun.star.sdbc import SQLException

        @logger.traced
        class Pass:
            def fail(self):
                raise SQLException("gia' scritto", None, "HY000", 50999, None)

        self.driver()
        with self.assertRaises(SQLException):
            Pass().fail()
        self.assertEqual([line for line in self.log_lines() if line["level"] == "ERROR"], [])

    def test_unexpected_exception_passing_through_a_traced_method_is_logged(self):
        @logger.traced
        class Boom:
            def fail(self):
                raise ValueError("boom")

        self.driver()
        with self.assertRaises(ValueError):
            Boom().fail()
        logged = [line for line in self.log_lines() if line["level"] == "ERROR"]
        self.assertEqual(len(logged), 1)
        self.assertIn("ValueError: boom", logged[0]["message"])

    def test_every_error_is_logged_once_in_english_with_the_code(self):
        driver = self.driver(language="it")
        for suffix in ("?Boh=1", "?ReadOnly=si", "?ReadOnly=true&ReadOnly=false"):
            with self.assertRaises(Exception):
                driver.connect(PREFIX + self.db + suffix, ())
        with self.assertRaises(Exception):
            driver.connect(PREFIX + os.path.join(self.dir, "manca.db"), ())
        errors_in_log = [line for line in self.log_lines() if line["level"] == "ERROR"]
        self.assertEqual(len(errors_in_log), 4, errors_in_log)
        for line in errors_in_log:
            self.assertRegex(line["code"], r"^[0-9a-f]{6}$")
            self.assertNotRegex(line["message"], r"Parametro|Indirizzo ricevuto|non esiste|SQLException")

    def test_unexpected_exception_becomes_error_50901(self):
        original = driver_module.open_database
        driver_module.open_database = lambda *a, **k: 1 / 0
        self.addCleanup(setattr, driver_module, "open_database", original)
        with self.assertRaises(Exception) as caught:
            self.driver().connect(PREFIX + self.db, ())
        self.assertEqual(caught.exception.ErrorCode, errors.UNEXPECTED)
        self.assertIn("ZeroDivisionError", caught.exception.Message)

    def test_driver_version_is_the_extension_version(self):
        class Provider:
            def getExtensionVersion(self, identifier):
                return "1.0.0" if identifier == IDENTIFIER else ""

        context = make_context(self.log_dir)
        context.getValueByName = lambda name: Provider() if name.endswith("PackageInformationProvider") else None
        driver = driver_module.Driver(context)
        self.assertEqual((driver.getMajorVersion(), driver.getMinorVersion()), (1, 0))
        meta = self.connect(driver, PREFIX + self.db).getMetaData()
        self.assertEqual(meta.getDriverVersion(), "1.0.0")
        self.assertEqual((meta.getDriverMajorVersion(), meta.getDriverMinorVersion()), (1, 0))

    def test_driver_version_unreadable_is_zero(self):
        driver = self.driver()
        self.assertEqual((driver.getMajorVersion(), driver.getMinorVersion()), (0, 0))
        meta = self.connect(driver, PREFIX + self.db).getMetaData()
        self.assertEqual(meta.getDriverVersion(), "")

    def test_log_folder_not_writable(self):
        blocker = os.path.join(self.dir, "file-in-mezzo")
        with open(blocker, "w", encoding="utf-8"):
            pass
        context = make_context(os.path.join(blocker, "registro"))
        driver = driver_module.Driver(context)
        with self.assertRaises(Exception) as caught:
            driver.connect(PREFIX + self.db, ())
        self.assertEqual(caught.exception.ErrorCode, errors.LOG_NOT_WRITABLE)
        self.assertIn("registro", caught.exception.Message)

    def test_missing_log_folder_is_created_with_all_levels(self):
        folder = os.path.join(self.dir, "non-esiste", "sotto", "registro")
        driver = driver_module.Driver(make_context(folder))
        self.connect(driver, PREFIX + self.db)
        self.assertTrue(os.path.isdir(folder))
        self.assertTrue(os.path.isfile(os.path.join(folder, "sdbc-pysqlite.log")))

    def test_every_line_has_five_fields_and_connection_lines_share_one_code(self):
        driver = self.driver()
        connection = self.connect(driver, PREFIX + self.db)
        statement = connection.createStatement()
        statement.getResultSet()
        connection.getMetaData()
        lines = self.log_lines()
        opened = [line for line in lines if line["message"].startswith("opened:")]
        self.assertEqual(len(opened), 1)
        code = opened[0]["code"]
        self.assertRegex(code, r"^[0-9a-f]{6}$")
        self.assertIn("address=<%s>" % (PREFIX + self.db), opened[0]["message"])
        self.assertIn("path=<%s>" % self.db, opened[0]["message"])
        by_label = {line["label"].strip(): line["code"] for line in lines}
        self.assertEqual(by_label["sdbc.connection.Connection.createStatement"], code)
        self.assertEqual(by_label["sdbc.statement.Statement.getResultSet"], code)
        self.assertEqual(by_label["sdbc.connection.Connection.getMetaData"], code)

    def test_two_connections_have_different_codes(self):
        driver = self.driver()
        self.connect(driver, PREFIX + self.db)
        self.connect(driver, PREFIX + self.db + "?ReadOnly=true")
        codes = [line["code"] for line in self.log_lines() if line["message"].startswith("opened:")]
        self.assertEqual(len(codes), 2)
        self.assertNotEqual(codes[0], codes[1])

    def test_lines_without_connection_have_empty_code(self):
        driver = self.driver()
        driver.acceptsURL(PREFIX + "x")
        lines = [line for line in self.log_lines() if line["label"].strip().endswith("Driver.acceptsURL")]
        self.assertEqual(lines[0]["code"], "")

    def test_warning_goes_to_the_log_even_with_trace_off(self):
        driver = self.driver(Trace=False)
        self.connect(driver, PREFIX + self.db + "?ReadOnly=true&JournalMode=wal")
        lines = self.log_lines()
        self.assertEqual([line["level"] for line in lines], ["WARNING"])
        self.assertIn("Journal mode requested: wal", lines[0]["message"])

    def test_nothing_but_errors_with_trace_off(self):
        driver = self.driver(Trace=False)
        self.connect(driver, PREFIX + self.db)
        path = os.path.join(self.log_dir, "sdbc-pysqlite.log")
        self.assertFalse(os.path.exists(path) and os.path.getsize(path) > 0)


if __name__ == "__main__":
    unittest.main()
