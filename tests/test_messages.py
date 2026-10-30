# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest

import support

from sdbc_pysqlite import errors
from sdbc_pysqlite import messages
from sdbc_pysqlite import parameters
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.errors import DriverError

WHERE = "sdbc.driver.Driver.connect"


def sqlite_failure(sql, setup=()):
    connection = sqlite.connect(":memory:")
    for statement in setup:
        connection.execute(statement)
    try:
        connection.execute(sql)
    except sqlite.Error as exception:
        return exception
    finally:
        connection.close()
    raise AssertionError("nessun errore")


class DriverMessageTests(unittest.TestCase):

    def test_every_code_has_text_in_both_languages(self):
        for code, (kind, state, text_it, text_en) in messages._CATALOG.items():
            self.assertIn(kind, ("E", "A"), code)
            self.assertEqual(len(state), 5, code)
            self.assertTrue(text_it and text_en, code)
            import re
            self.assertEqual(sorted(re.findall(r"{(\w+)}", text_it)),
                             sorted(re.findall(r"{(\w+)}", text_en)), code)

    def test_message_ends_with_location_and_language_follows(self):
        error = DriverError(errors.FILE_NOT_FOUND, percorso=r"C:\x.db")
        italian = messages.describe(error, "it", WHERE)
        english = messages.describe(error, "en", WHERE)
        self.assertTrue(italian.message.endswith("\n\n[codice 50001 · SQLState 08001 · %s]" % WHERE))
        self.assertTrue(english.message.endswith("\n\n[code 50001 · SQLState 08001 · %s]" % WHERE))
        other = messages.describe(DriverError(errors.NOT_A_DATABASE, percorso="x"), "it", WHERE)
        self.assertTrue(other.message.endswith("\n\n[codice 50003 · SQLState 08001 · %s]" % WHERE))
        self.assertIn("Il file del database non esiste ancora", italian.message)
        self.assertIn("Dettaglio: il file non esiste: C:\\x.db", italian.message)
        self.assertIn("The database file does not exist yet", english.message)
        self.assertIn("Detail: the file does not exist: C:\\x.db", english.message)
        self.assertEqual((italian.sqlstate, italian.error_code, italian.is_warning),
                         ("08001", 50001, False))

    def test_the_three_path_cases_share_one_guide_and_differ_in_the_detail(self):
        cases = {errors.FILE_NOT_FOUND: ("percorso", "il file non esiste"),
                 errors.FOLDER_NOT_FOUND: ("cartella", "la cartella non esiste"),
                 errors.PATH_IS_FOLDER: ("percorso", "è una cartella")}
        guide = None
        for code, (name, detail) in cases.items():
            text = messages.describe(DriverError(code, **{name: "C:\\Dati"}), "it", WHERE).message
            head, _, tail = text.partition("Dettaglio: ")
            guide = guide or head
            self.assertEqual(head, guide)
            self.assertIn(detail, tail)
            self.assertIn("Modifica → Database → Impostazioni PySQLite", head)
            self.assertNotIn("registro", head)
            self.assertIn("scegli «sì» in «Crea il database se non esiste»", head)
            self.assertNotIn("spunta", head)
        english = messages.describe(DriverError(errors.FILE_NOT_FOUND, percorso="C:\\Dati"), "en", WHERE).message
        self.assertIn("choose \"yes\" in \"Create the database if it does not exist\"", english)
        self.assertNotIn("tick", english)

    def test_other_languages_use_english(self):
        error = DriverError(errors.FILE_NOT_FOUND, percorso="x")
        self.assertIn("does not exist", messages.describe(error, "fr", WHERE).message)
        self.assertIn("non esiste", messages.describe(error, "it-IT", WHERE).message)

    def test_warnings_are_flagged(self):
        warning = DriverError(errors.JOURNAL_MODE_NOT_OBTAINED, richiesto="wal", effettivo="delete")
        described = messages.describe(warning, "it", WHERE)
        self.assertTrue(described.is_warning)
        self.assertEqual(described.sqlstate, "01000")
        self.assertIn("wal", described.message)
        self.assertIn("delete", described.message)

    def test_address_comes_first_in_address_errors(self):
        url = "sdbc:external:pysqlite:C:\\x.db?Foo=1"
        for error in (DriverError(errors.UNKNOWN_PARAMETER, nome="Foo", indirizzo=url, ammessi="a, b"),
                      DriverError(errors.PARAMETER_NO_EQUALS, gruppo="Foo", indirizzo=url),
                      DriverError(errors.PARAMETER_REPEATED, nome="Foo", indirizzo=url),
                      DriverError(errors.INVALID_VALUE, nome="Foo", valore="x", indirizzo=url, ammessi="a")):
            for language, start in (("it", "Indirizzo ricevuto: «%s»." % url),
                                    ("en", "Address received: \"%s\"." % url)):
                self.assertTrue(messages.describe(error, language, WHERE).message.startswith(start),
                                (error.code, language))

    def test_invalid_value_from_options_has_no_address(self):
        error = DriverError(errors.INVALID_VALUE, nome="LockTimeoutSeconds", valore="-1")
        message = messages.describe(error, "it", WHERE).message
        self.assertNotIn("Indirizzo ricevuto", message)
        self.assertIn("un numero intero da 0 in su", message)

    def test_unknown_parameter_lists_all_names(self):
        error = DriverError(errors.UNKNOWN_PARAMETER, nome="Foo", indirizzo="u",
                            ammessi=", ".join(parameters.PARAMETER_NAMES))
        message = messages.describe(error, "en", WHERE).message
        for name in parameters.PARAMETER_NAMES:
            self.assertIn(name, message)

    def test_unknown_code_does_not_fail(self):
        described = messages.describe(DriverError(59999), "en", WHERE)
        self.assertIn("59999", described.message)

    def test_missing_value_does_not_fail(self):
        described = messages.describe(DriverError(errors.FILE_NOT_FOUND), "en", WHERE)
        self.assertIn("{percorso}", described.message)


class SqliteMessageTests(unittest.TestCase):

    def test_busy_message_is_the_agreed_one(self):
        connection_a = sqlite.connect("file:busy?mode=memory&cache=shared", uri=True, isolation_level=None)
        connection_b = sqlite.connect("file:busy?mode=memory&cache=shared", uri=True, isolation_level=None, timeout=0)
        connection_a.execute("create table t(a)")
        connection_a.execute("begin immediate")
        try:
            connection_b.execute("begin immediate")
        except sqlite.Error as exception:
            failure = exception
        else:
            self.skipTest("SQLite non ha dato errore di blocco")
        connection_a.close()
        connection_b.close()
        error = DriverError(None, sqlite=failure, percorso=r"C:\dati\prova.db")
        described = messages.describe(error, "it", "sdbc.connection.Connection.commit")
        self.assertIn(failure.sqlite_errorname, described.message)
        self.assertIn("File: C:\\dati\\prova.db", described.message)
        self.assertIn("(%s)" % failure, described.message)
        self.assertTrue(described.message.endswith(" · sdbc.connection.Connection.commit]"))
        self.assertEqual(described.error_code, failure.sqlite_errorcode)

    def test_constraint_subtypes(self):
        cases = (
            ("insert into t values (null)", ("create table t(a not null)",), 1299,
             "CAMPO OBBLIGATORIO VUOTO", "REQUIRED FIELD EMPTY"),
            ("insert into t values (1)", ("create table t(a unique)", "insert into t values (1)"), 2067,
             "VALORE DUPLICATO", "DUPLICATE VALUE"),
            ("insert into t values (1)", ("create table t(a primary key)", "insert into t values (1)"), 1555,
             "CHIAVE PRIMARIA DUPLICATA", "PRIMARY KEY DUPLICATE"),
            ("insert into t values (-1)", ("create table t(a check (a > 0))",), 275,
             "CONDIZIONE DI CONTROLLO NON RISPETTATA", "CHECK CONDITION FAILED"),
        )
        for sql, setup, code, label_it, label_en in cases:
            failure = sqlite_failure(sql, setup)
            self.assertEqual(failure.sqlite_errorcode, code)
            error = DriverError(None, sqlite=failure)
            italian = messages.describe(error, "it", WHERE)
            english = messages.describe(error, "en", WHERE)
            self.assertTrue(italian.message.startswith(label_it), italian.message)
            self.assertTrue(english.message.startswith(label_en), english.message)
            self.assertEqual(italian.sqlstate, "23000")

    def test_foreign_key_violation(self):
        connection = sqlite.connect(":memory:", isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("create table p(id integer primary key)")
        connection.execute("create table c(p references p(id))")
        with self.assertRaises(sqlite.Error) as caught:
            connection.execute("insert into c values (99)")
        connection.close()
        described = messages.describe(DriverError(None, sqlite=caught.exception), "en", WHERE)
        self.assertTrue(described.message.startswith("FOREIGN KEY VIOLATED"))

    def test_sql_error(self):
        failure = sqlite_failure("select * from non_esiste")
        described = messages.describe(DriverError(None, sqlite=failure), "it", WHERE)
        self.assertTrue(described.message.startswith("ERRORE SQL"))
        self.assertEqual(described.sqlstate, "42000")

    def test_all_principal_codes_have_complete_entries(self):
        self.assertEqual(sorted(messages._SQLITE), list(range(1, 29)))
        for code, entry in messages._SQLITE.items():
            self.assertEqual(len(entry), 6, code)
            self.assertEqual(len(entry[1]), 5, code)
            self.assertTrue(all(entry), code)

    def test_extended_code_uses_principal_entry_and_shows_extended_name(self):
        class Fake(Exception):
            sqlite_errorcode = 266
            sqlite_errorname = "SQLITE_IOERR_READ"
        described = messages.describe(DriverError(None, sqlite=Fake("disk I/O error")), "en", WHERE)
        self.assertTrue(described.message.startswith("DISK I/O ERROR (SQLITE_IOERR_READ 266, SQLState HY000)"))
        self.assertEqual(described.error_code, 266)

    def test_exception_without_sqlite_attributes(self):
        described = messages.describe(DriverError(None, sqlite=sqlite.Error("boh")), "en", WHERE)
        self.assertTrue(described.message.startswith("SQL ERROR"))


if __name__ == "__main__":
    unittest.main()
