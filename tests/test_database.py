# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request

import support

from sdbc_pysqlite import database
from sdbc_pysqlite import parameters
from sdbc_pysqlite import errors
from sdbc_pysqlite import messages
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.errors import DriverError

PREFIX = "sdbc:external:pysqlite:"
NO_SETTINGS = {}


def file_url_to_path(url):
    return urllib.request.url2pathname(urllib.parse.urlparse(url).path)


def options_with_defaults(*five):
    rest = [parameters.DEFAULTS[name] for name in parameters.PARAMETER_NAMES[5:]]
    return database.ConnectionOptions(*five, *rest)


class DatabaseTestCase(unittest.TestCase):

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.dir = self._dir.name
        self.opened = []

    def tearDown(self):
        for opened in self.opened:
            try:
                opened.connection.close()
            except sqlite.Error:
                pass

    def path(self, *parts):
        return os.path.join(self.dir, *parts)

    def make_db(self, *parts):
        path = self.path(*parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        connection = sqlite.connect(path)
        connection.execute("create table t(a)")
        connection.commit()
        connection.close()
        return path

    def open(self, text, settings=NO_SETTINGS):
        opened = database.open_database(text, settings, file_url_to_path)
        self.opened.append(opened)
        return opened

    def fails(self, text, settings=NO_SETTINGS):
        with self.assertRaises(DriverError) as caught:
            self.open(text, settings)
        return caught.exception

    def warning_codes(self, opened):
        return [warning.code for warning in opened.warnings]


class OpenTests(DatabaseTestCase):

    def test_open_existing_with_defaults(self):
        path = self.make_db("prova.db")
        opened = self.open(PREFIX + path)
        self.assertEqual(opened.path, path)
        self.assertEqual(opened.warnings, [])
        self.assertEqual(opened.options, options_with_defaults(False, 5, False, False, "delete"))
        self.assertEqual(opened.connection.execute("select count(*) from sqlite_master").fetchone()[0], 1)
        self.assertEqual(opened.connection.execute("PRAGMA foreign_keys").fetchone()[0], 0)
        self.assertEqual(opened.connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(opened.connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000)

    def test_path_with_spaces_apostrophe_accents_and_hash(self):
        path = self.make_db("L'archivio dati", "è prova #1 (copia).db")
        for text in (PREFIX + path, '"%s"' % path, PREFIX + PREFIX + '"%s"' % path):
            self.assertEqual(self.open(text).path, path)

    def test_file_url(self):
        path = self.make_db("prova.db")
        opened = self.open(PREFIX + "file://" + urllib.request.pathname2url(path))
        self.assertEqual(opened.path, path)

    def test_options_after_quoted_path(self):
        path = self.make_db("prova.db")
        opened = self.open('"%s"?ForeignKeys=true' % path)
        self.assertTrue(opened.options.foreign_keys)

    def test_connection_usable_from_another_thread(self):
        opened = self.open(self.make_db("prova.db"))
        result = []
        thread = threading.Thread(
            target=lambda: result.append(opened.connection.execute("select 1").fetchone()[0]))
        thread.start()
        thread.join()
        self.assertEqual(result, [1])

    def test_empty_file_is_a_valid_database(self):
        path = self.path("vuoto.db")
        open(path, "wb").close()
        self.assertEqual(self.open(path).warnings, [])


class FileProblemsTests(DatabaseTestCase):

    def test_missing_file(self):
        error = self.fails(PREFIX + self.path("manca.db"))
        self.assertEqual(error.code, errors.FILE_NOT_FOUND)
        self.assertEqual(error.values["percorso"], self.path("manca.db"))
        self.assertFalse(os.path.exists(self.path("manca.db")))

    def test_forgotten_question_mark_shows_the_whole_path(self):
        error = self.fails(PREFIX + self.path("prova.db&ReadOnly=true"))
        self.assertEqual(error.code, errors.FILE_NOT_FOUND)
        self.assertTrue(error.values["percorso"].endswith("prova.db&ReadOnly=true"))
        self.assertEqual(os.listdir(self.dir), [])

    def test_missing_folder(self):
        error = self.fails(PREFIX + self.path("manca", "prova.db"))
        self.assertEqual(error.code, errors.FOLDER_NOT_FOUND)
        self.assertEqual(error.values["cartella"], self.path("manca"))
        self.assertFalse(os.path.exists(self.path("manca")))

    def test_path_is_a_folder(self):
        os.makedirs(self.path("cartella"))
        self.assertEqual(self.fails(PREFIX + self.path("cartella")).code, errors.PATH_IS_FOLDER)

    def test_not_a_database(self):
        path = self.path("testo.db")
        with open(path, "wb") as handle:
            handle.write(b"questo non e' un database SQLite" * 20)
        error = self.fails(PREFIX + path)
        self.assertEqual(error.code, errors.NOT_A_DATABASE)
        self.assertEqual(error.values["percorso"], path)

    def test_not_a_database_read_only(self):
        path = self.path("testo.db")
        with open(path, "wb") as handle:
            handle.write(b"questo non e' un database SQLite" * 20)
        self.assertEqual(self.fails(PREFIX + path + "?ReadOnly=true").code, errors.NOT_A_DATABASE)

    def test_errors_in_the_address_come_before_touching_files(self):
        self.assertEqual(self.fails(PREFIX).code, errors.ADDRESS_INVALID)
        self.assertEqual(self.fails(PREFIX + '""').code, errors.ADDRESS_INVALID)
        self.assertEqual(self.fails(PREFIX + "?ReadOnly=true").code, errors.ADDRESS_INVALID)
        self.assertEqual(self.fails(PREFIX + "C:\\a<b.db").code, errors.PATH_BAD_CHARACTERS)
        self.assertEqual(self.fails(PREFIX + self.path("a.db") + "?Boh=1").code, errors.UNKNOWN_PARAMETER)


class CreateIfMissingTests(DatabaseTestCase):

    def test_creates_file_and_folders_with_a_warning(self):
        path = self.path("uno", "due", "nuovo.db")
        opened = self.open(PREFIX + path + "?CreateIfMissing=true")
        self.assertTrue(os.path.isfile(path))
        self.assertEqual(self.warning_codes(opened), [errors.FILE_CREATED])
        self.assertEqual(opened.warnings[0].values["percorso"], path)
        opened.connection.execute("create table t(a)")

    def test_creates_file_in_existing_folder(self):
        path = self.path("nuovo.db")
        opened = self.open(PREFIX + path + "?CreateIfMissing=true")
        self.assertEqual(self.warning_codes(opened), [errors.FILE_CREATED])
        self.assertTrue(os.path.isfile(path))

    def test_existing_file_gives_no_warning(self):
        path = self.make_db("prova.db")
        self.assertEqual(self.open(PREFIX + path + "?CreateIfMissing=true").warnings, [])

    def test_off_creates_nothing(self):
        path = self.path("uno", "nuovo.db")
        self.assertEqual(self.fails(PREFIX + path + "?CreateIfMissing=false").code, errors.FOLDER_NOT_FOUND)
        self.assertFalse(os.path.exists(self.path("uno")))

    def test_read_only_wins_over_create(self):
        error = self.fails(PREFIX + self.path("nuovo.db") + "?CreateIfMissing=true&ReadOnly=true")
        self.assertEqual(error.code, errors.FILE_NOT_FOUND)
        error = self.fails(PREFIX + self.path("x", "nuovo.db") + "?CreateIfMissing=true&ReadOnly=true")
        self.assertEqual(error.code, errors.FOLDER_NOT_FOUND)
        self.assertEqual(os.listdir(self.dir), [])

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "serve un utente senza privilegi su un sistema POSIX")
    def test_cannot_create_in_read_only_folder(self):
        os.chmod(self.dir, 0o500)
        self.addCleanup(os.chmod, self.dir, 0o700)
        error = self.fails(PREFIX + self.path("nuovo.db") + "?CreateIfMissing=true")
        self.assertEqual(error.code, errors.CANNOT_CREATE)


class ParameterEffectsTests(DatabaseTestCase):

    def test_foreign_keys_on_and_off(self):
        path = self.make_db("prova.db")
        on = self.open(PREFIX + path + "?ForeignKeys=true")
        self.assertEqual(on.connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        off = self.open(PREFIX + path + "?ForeignKeys=false")
        self.assertEqual(off.connection.execute("PRAGMA foreign_keys").fetchone()[0], 0)

    def test_foreign_keys_really_checked(self):
        path = self.path("fk.db")
        setup = sqlite.connect(path)
        setup.executescript("create table p(id integer primary key); create table c(p references p(id));")
        setup.close()
        on = self.open(PREFIX + path + "?ForeignKeys=true")
        with self.assertRaises(sqlite.IntegrityError):
            on.connection.execute("insert into c values (99)")
        off = self.open(PREFIX + path)
        off.connection.execute("insert into c values (99)")

    def test_lock_timeout(self):
        path = self.make_db("prova.db")
        self.assertEqual(self.open(PREFIX + path + "?LockTimeoutSeconds=0").connection
                         .execute("PRAGMA busy_timeout").fetchone()[0], 0)
        self.assertEqual(self.open(PREFIX + path + "?LockTimeoutSeconds=12").connection
                         .execute("PRAGMA busy_timeout").fetchone()[0], 12000)

    def test_busy_database_with_zero_timeout(self):
        path = self.make_db("prova.db")
        writer = self.open(PREFIX + path)
        writer.connection.execute("begin immediate")
        other = self.open(PREFIX + path + "?LockTimeoutSeconds=0")
        with self.assertRaises(sqlite.OperationalError) as caught:
            other.connection.execute("begin immediate")
        self.assertEqual(caught.exception.sqlite_errorcode, 5)

    def test_read_only(self):
        path = self.make_db("prova.db")
        opened = self.open(PREFIX + path + "?ReadOnly=true")
        self.assertTrue(opened.options.read_only)
        self.assertEqual(opened.connection.execute("select count(*) from t").fetchone()[0], 0)
        with self.assertRaises(sqlite.OperationalError) as caught:
            opened.connection.execute("insert into t values (1)")
        self.assertEqual(caught.exception.sqlite_errorcode, 8)
        self.assertEqual(opened.warnings, [])

    def test_read_only_path_with_special_characters(self):
        path = self.make_db("L'archivio dati", "è prova #1.db")
        opened = self.open(PREFIX + path + "?ReadOnly=true")
        self.assertEqual(opened.connection.execute("select count(*) from t").fetchone()[0], 0)

    def test_all_journal_modes(self):
        for mode in ("delete", "truncate", "persist", "memory", "wal", "off"):
            path = self.make_db("modo-%s.db" % mode)
            opened = self.open(PREFIX + path + "?JournalMode=" + mode)
            self.assertEqual(opened.connection.execute("PRAGMA journal_mode").fetchone()[0], mode)
            self.assertEqual(opened.warnings, [], mode)

    def test_wal_is_kept_in_the_file_and_default_goes_back_to_delete(self):
        path = self.make_db("prova.db")
        self.open(PREFIX + path + "?JournalMode=wal").connection.close()
        again = self.open(PREFIX + path)
        self.assertEqual(again.connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_other_program_keeps_a_wal_file_open_and_the_default_cannot_be_applied(self):
        path = self.make_db("prova.db")
        other = sqlite.connect(path)
        self.addCleanup(other.close)
        other.execute("PRAGMA journal_mode = wal").fetchone()
        other.execute("CREATE TABLE IF NOT EXISTS z(i)")
        other.execute("INSERT INTO z VALUES (1), (2), (3)")
        if other.in_transaction:
            other.execute("COMMIT")
        reading = other.execute("SELECT i FROM z")
        reading.fetchone()
        with self.assertRaises(DriverError) as raised:
            self.open(PREFIX + path + "?LockTimeoutSeconds=1")
        self.assertEqual(raised.exception.code, errors.JOURNAL_MODE_IN_USE)
        self.assertEqual(raised.exception.values, {"richiesto": "delete", "effettivo": "wal"})
        text = messages.describe(raised.exception, "it", "Driver.connect").message
        self.assertIn("«DELETE»", text)
        self.assertIn("JournalMode=wal", text)
        self.assertIn("Impostazioni PySQLite", text)
        text = messages.describe(raised.exception, "en", "Driver.connect").message
        self.assertIn("\"WAL\"", text)

    def test_other_program_keeps_a_wal_file_open_and_the_same_mode_opens(self):
        path = self.make_db("prova.db")
        other = sqlite.connect(path)
        self.addCleanup(other.close)
        other.execute("PRAGMA journal_mode = wal").fetchone()
        opened = self.open(PREFIX + path + "?JournalMode=wal")
        self.assertEqual(self.warning_codes(opened), [])
        self.assertEqual(opened.connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")

    def test_journal_mode_not_obtained_gives_a_warning(self):
        path = self.make_db("prova.db")
        opened = self.open(PREFIX + path + "?ReadOnly=true&JournalMode=wal")
        self.assertEqual(self.warning_codes(opened), [errors.JOURNAL_MODE_NOT_OBTAINED])
        self.assertEqual(opened.warnings[0].values, {"richiesto": "wal", "effettivo": "delete"})

    def test_read_only_on_wal_database_asks_default_and_warns(self):
        path = self.make_db("prova.db")
        setup = sqlite.connect(path)
        setup.execute("PRAGMA journal_mode = wal")
        setup.close()
        opened = self.open(PREFIX + path + "?ReadOnly=true")
        self.assertEqual(self.warning_codes(opened), [errors.JOURNAL_MODE_NOT_OBTAINED])
        self.assertEqual(opened.warnings[0].values["effettivo"], "wal")

    def test_created_file_with_wal(self):
        path = self.path("nuovo.db")
        opened = self.open(PREFIX + path + "?CreateIfMissing=true&JournalMode=wal")
        self.assertEqual(self.warning_codes(opened), [errors.FILE_CREATED])


class PrecedenceTests(DatabaseTestCase):

    def test_options_are_used_when_address_is_silent(self):
        path = self.make_db("prova.db")
        settings = {"ForeignKeys": True, "LockTimeoutSeconds": 9, "ReadOnly": False,
                    "CreateIfMissing": False, "JournalMode": "truncate"}
        opened = self.open(PREFIX + path, settings)
        self.assertEqual(opened.options, options_with_defaults(False, 9, True, False, "truncate"))

    def test_address_wins_over_options(self):
        path = self.make_db("prova.db")
        settings = {"ForeignKeys": True, "LockTimeoutSeconds": 9, "JournalMode": "truncate"}
        opened = self.open(PREFIX + path + "?ForeignKeys=false&JournalMode=delete", settings)
        self.assertEqual(opened.options, options_with_defaults(False, 9, False, False, "delete"))

    def test_missing_options_use_code_defaults(self):
        path = self.make_db("prova.db")
        opened = self.open(PREFIX + path, {"ForeignKeys": None})
        self.assertEqual(opened.options, options_with_defaults(False, 5, False, False, "delete"))

    def test_invalid_option_is_an_error_but_not_if_the_address_overrides_it(self):
        path = self.make_db("prova.db")
        error = self.fails(PREFIX + path, {"LockTimeoutSeconds": -1})
        self.assertEqual(error.code, errors.INVALID_VALUE)
        self.assertEqual(error.values["nome"], "LockTimeoutSeconds")
        self.assertNotIn("indirizzo", error.values)
        self.assertEqual(self.fails(PREFIX + path, {"JournalMode": "boh"}).code, errors.INVALID_VALUE)
        self.assertEqual(self.fails(PREFIX + path, {"ReadOnly": "true"}).code, errors.INVALID_VALUE)
        self.assertEqual(self.open(PREFIX + path + "?LockTimeoutSeconds=2", {"LockTimeoutSeconds": -1})
                         .options.lock_timeout_seconds, 2)


if __name__ == "__main__":
    unittest.main()
