# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import contextlib
import os
import sqlite3 as reference
import sys
import tempfile
import threading
import unittest

import support

from sdbc_pysqlite import database
from sdbc_pysqlite import errors
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.errors import DriverError


def run_both(script, query, params=()):
    answers = []
    for module in (sqlite, reference):
        db = module.connect(":memory:", isolation_level=None) if module is reference else module.connect(":memory:")
        db.executescript(script)
        try:
            cursor = db.execute(query, params)
            rows = cursor.fetchall()
            answers.append(("ok", rows, [d[0] for d in cursor.description] if cursor.description else None,
                            cursor.rowcount))
        except Exception as exception:
            answers.append(("error", type(exception).__name__, getattr(exception, "sqlite_errorcode", None),
                            getattr(exception, "sqlite_errorname", None), str(exception)))
        db.close()
    return answers


class TestLoading(unittest.TestCase):
    def test_version(self):
        self.assertIsInstance(sqlite.sqlite_version, str)
        self.assertEqual(sqlite.sqlite_version_info, tuple(int(p) for p in sqlite.sqlite_version.split(".")))
        self.assertGreaterEqual(sqlite.sqlite_version_info, (3, 54, 1))

    def test_unknown_attribute(self):
        with self.assertRaises(AttributeError):
            sqlite.nonexistent_name

    def test_default_path_name(self):
        if sys.platform == "win32":
            path = sqlite.default_library_path()
            self.assertTrue(path.endswith(os.path.join("native", "win-x64", "sdbcsql.dll")))
        else:
            with self.assertRaises(sqlite.LibraryError) as caught:
                sqlite.default_library_path()
            self.assertIsNone(caught.exception.path)

    @staticmethod
    @contextlib.contextmanager
    def library_not_loaded(path):
        saved = (sqlite._api, sqlite._library_override)
        sqlite._api, sqlite._library_override = None, path
        try:
            yield
        finally:
            sqlite._api, sqlite._library_override = saved

    def test_missing_library_is_an_error_not_a_fallback(self):
        missing = os.path.join(tempfile.gettempdir(), "does-not-exist", "x.dll")
        with self.library_not_loaded(missing):
            with self.assertRaises(sqlite.LibraryError) as caught:
                sqlite.connect(":memory:")
            self.assertEqual(caught.exception.path, missing)
            with self.assertRaises(DriverError) as driver_error:
                database.open_database("sdbc:external:pysqlite:/tmp/x.db", {}, lambda url: url)
            self.assertEqual(driver_error.exception.code, errors.SQLITE_LIBRARY)
            self.assertEqual(driver_error.exception.values["percorso"], missing)

    def test_not_a_sqlite_library(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = os.path.join(folder, "fake.dll")
            with open(fake, "wb") as out:
                out.write(b"this is not a library")
            with self.library_not_loaded(fake):
                with self.assertRaises(sqlite.LibraryError) as caught:
                    sqlite.connect(":memory:")
        self.assertIn("cannot load the library", caught.exception.reason)


class TestValues(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:")
        self.db.execute("CREATE TABLE t(a, b)")

    def tearDown(self):
        self.db.close()

    def roundtrip(self, value):
        self.db.execute("DELETE FROM t")
        self.db.execute("INSERT INTO t(a) VALUES (?)", (value,))
        return self.db.execute("SELECT a FROM t").fetchone()[0]

    def test_integers(self):
        for value in (0, 1, -1, 2 ** 31, -2 ** 31 - 1, 2 ** 63 - 1, -2 ** 63):
            self.assertEqual(self.roundtrip(value), value)

    def test_integer_too_large(self):
        with self.assertRaises(OverflowError):
            self.roundtrip(2 ** 63)
        with self.assertRaises(OverflowError):
            self.roundtrip(-2 ** 63 - 1)

    def test_bool_is_integer(self):
        self.assertEqual(self.roundtrip(True), 1)
        self.assertIs(type(self.roundtrip(True)), int)

    def test_floats(self):
        for value in (0.0, 1.5, -2.25, 1e300, 5e-324, 0.1):
            self.assertEqual(self.roundtrip(value), value)

    def test_text(self):
        for value in ("", "abc", "è à ü", "日本語", "emoji \U0001F600", "con\0nul", "x" * 100000):
            self.assertEqual(self.roundtrip(value), value)

    def test_blob(self):
        for value in (b"", b"\x00", b"\x00\x01\xff", bytes(range(256)) * 100):
            result = self.roundtrip(value)
            self.assertEqual(result, value)
            self.assertIsInstance(result, bytes)

    def test_blob_types(self):
        self.assertEqual(self.roundtrip(bytearray(b"ab")), b"ab")
        self.assertEqual(self.roundtrip(memoryview(b"ab")), b"ab")

    def test_null(self):
        self.assertIsNone(self.roundtrip(None))

    def test_unsupported_type(self):
        for value in ([1], {1: 2}, object(), complex(1, 2)):
            with self.assertRaises(sqlite.ProgrammingError) as caught:
                self.roundtrip(value)
            self.assertIn("Error binding parameter 1", str(caught.exception))

    def test_lone_surrogate_cannot_be_encoded(self):
        with self.assertRaises(UnicodeEncodeError):
            self.roundtrip("\ud800")

    def test_invalid_utf8_text_on_read(self):
        self.db.execute("INSERT INTO t(a) VALUES (CAST(x'ff41' AS TEXT))")
        with self.assertRaises(sqlite.OperationalError) as caught:
            self.db.execute("SELECT a FROM t").fetchall()
        self.assertIn("Could not decode to UTF-8 column 'a'", str(caught.exception))

    def test_same_as_reference_for_types(self):
        script = ("CREATE TABLE v(i INTEGER, r REAL, t TEXT, b BLOB, n);"
                  "INSERT INTO v VALUES (1, 2.5, 'x', x'0102', NULL), (9223372036854775807, -0.0, '', x'', 3);")
        ours, theirs = run_both(script, "SELECT *, typeof(i), typeof(b), typeof(n) FROM v ORDER BY i")
        self.assertEqual(ours, theirs)


class TestSameAsReference(unittest.TestCase):
    def check(self, script, query, params=()):
        ours, theirs = run_both(script, query, params)
        if ours[0] == "error":
            self.assertEqual(ours[:4], theirs[:4], (ours, theirs))
        else:
            self.assertEqual(ours, theirs)

    def test_queries(self):
        script = ("CREATE TABLE a(id INTEGER PRIMARY KEY, name TEXT, v REAL);"
                  "INSERT INTO a(name, v) VALUES ('x', 1.5), ('y', NULL), ('z', 3);")
        for query in ("SELECT * FROM a", "SELECT name FROM a WHERE id > ?", "SELECT count(*) AS n FROM a",
                      "SELECT 1 WHERE 0", "VALUES (1), (2)", "PRAGMA table_info(a)",
                      "SELECT id, sum(v) OVER (ORDER BY id) FROM a", "SELECT json_extract('{\"a\":[1,2]}', '$.a[1]')"):
            params = (1,) if "?" in query else ()
            self.check(script, query, params)

    def test_dml_rowcount(self):
        script = "CREATE TABLE a(id INTEGER PRIMARY KEY, n);INSERT INTO a(n) VALUES (1),(2),(3);"
        for query in ("UPDATE a SET n = n + 1", "DELETE FROM a WHERE id > 1", "INSERT INTO a(n) VALUES (9)",
                      "UPDATE a SET n = 0 WHERE 0", "CREATE TABLE b(x)", "INSERT INTO a(n) VALUES (5) RETURNING id",
                      "REPLACE INTO a(id, n) VALUES (1, 7)", "  \n delete from a"):
            self.check(script, query)

    def test_errors(self):
        script = "CREATE TABLE a(id INTEGER PRIMARY KEY, n NOT NULL UNIQUE);INSERT INTO a VALUES (1, 10);"
        for query in ("SELECT * FROM missing", "SELEC 1", "INSERT INTO a VALUES (1, 11)",
                      "INSERT INTO a VALUES (2, 10)", "INSERT INTO a VALUES (3, NULL)",
                      "SELECT * FROM a WHERE", "CREATE TABLE a(x)", "DROP TABLE missing",
                      "SELECT nofunction(1)", "SELECT 1/0", "SELECT abs(-9223372036854775808)",
                      "PRAGMA foo = bar", "ATTACH '/nonexistent/folder/x.db' AS other"):
            self.check(script, query)

    def test_too_big(self):
        self.check("", "SELECT zeroblob(2000000000)")


class TestCursor(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:")
        self.db.executescript("CREATE TABLE a(id INTEGER PRIMARY KEY, n); "
                              "INSERT INTO a(n) VALUES (10),(20),(30),(40),(50);")

    def tearDown(self):
        self.db.close()

    def test_fetch_one_many_all(self):
        cursor = self.db.execute("SELECT n FROM a ORDER BY id")
        self.assertEqual(cursor.fetchone(), (10,))
        self.assertEqual(cursor.fetchmany(2), [(20,), (30,)])
        self.assertEqual(cursor.fetchall(), [(40,), (50,)])
        self.assertIsNone(cursor.fetchone())
        self.assertEqual(cursor.fetchmany(3), [])
        self.assertEqual(cursor.fetchall(), [])

    def test_fetchmany_default_size_is_arraysize(self):
        cursor = self.db.execute("SELECT n FROM a")
        self.assertEqual(len(cursor.fetchmany()), 1)
        cursor.arraysize = 3
        self.assertEqual(len(cursor.fetchmany()), 3)

    def test_iteration(self):
        self.assertEqual([r[0] for r in self.db.execute("SELECT n FROM a ORDER BY id")], [10, 20, 30, 40, 50])
        self.assertEqual(list(self.db.execute("SELECT 1 WHERE 0")), [])

    def test_description_only_for_queries(self):
        self.assertIsNone(self.db.execute("INSERT INTO a(n) VALUES (1)").description)
        self.assertIsNone(self.db.execute("CREATE TABLE z(x)").description)
        self.assertIsNone(self.db.execute("PRAGMA foreign_keys = ON").description)
        description = self.db.execute("SELECT n AS valore, 1 FROM a").description
        self.assertEqual(description[0], ("valore", None, None, None, None, None, None))
        self.assertEqual(len(description), 2)
        self.assertIsNotNone(self.db.execute("INSERT INTO a(n) VALUES (1) RETURNING id").description)

    def test_description_available_without_rows(self):
        self.assertEqual(self.db.execute("SELECT n FROM a WHERE 0").description[0][0], "n")

    def test_rowcount_with_returning_is_final_after_fetching(self):
        cursor = self.db.execute("UPDATE a SET n = n + 1 RETURNING id")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 5)
        self.assertEqual(cursor.rowcount, 5)

    def test_several_cursors_open_at_once(self):
        first = self.db.execute("SELECT n FROM a ORDER BY id")
        second = self.db.execute("SELECT n FROM a ORDER BY id DESC")
        self.assertEqual(first.fetchone(), (10,))
        self.assertEqual(second.fetchone(), (50,))
        self.assertEqual(first.fetchone(), (20,))

    def test_reuse_cursor(self):
        cursor = self.db.cursor()
        cursor.execute("SELECT 1")
        cursor.execute("SELECT 2")
        self.assertEqual(cursor.fetchall(), [(2,)])

    def test_close_cursor(self):
        cursor = self.db.execute("SELECT n FROM a")
        cursor.close()
        cursor.close()
        with self.assertRaises(sqlite.ProgrammingError):
            cursor.fetchone()
        with self.assertRaises(sqlite.ProgrammingError):
            cursor.execute("SELECT 1")

    def test_executemany(self):
        cursor = self.db.cursor()
        cursor.executemany("INSERT INTO a(n) VALUES (?)", [(1,), (2,), (3,)])
        self.assertEqual(cursor.rowcount, 3)
        self.assertEqual(self.db.execute("SELECT count(*) FROM a").fetchone()[0], 8)

    def test_executescript(self):
        self.db.executescript("CREATE TABLE s1(x); INSERT INTO s1 VALUES (1); ; -- c\n INSERT INTO s1 VALUES (2);")
        self.assertEqual(self.db.execute("SELECT x FROM s1 ORDER BY x").fetchall(), [(1,), (2,)])
        with self.assertRaises(sqlite.OperationalError):
            self.db.executescript("INSERT INTO s1 VALUES (3); INSERT INTO nope VALUES (1);")
        self.assertEqual(self.db.execute("SELECT count(*) FROM s1").fetchone()[0], 3)


class TestParameters(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def test_positional(self):
        self.assertEqual(self.db.execute("SELECT ?, ?", [1, "a"]).fetchone(), (1, "a"))
        self.assertEqual(self.db.execute("SELECT ?2, ?1", (1, 2)).fetchone(), (2, 1))

    def test_named(self):
        self.assertEqual(self.db.execute("SELECT :a, :b, :a", {"a": 1, "b": 2}).fetchone(), (1, 2, 1))
        self.assertEqual(self.db.execute("SELECT @x, $y", {"x": 1, "y": 2}).fetchone(), (1, 2))

    def test_wrong_number(self):
        with self.assertRaises(sqlite.ProgrammingError) as caught:
            self.db.execute("SELECT ?, ?", (1,))
        self.assertIn("Incorrect number of bindings supplied. The current statement uses 2, and there are 1 supplied.",
                      str(caught.exception))
        with self.assertRaises(sqlite.ProgrammingError):
            self.db.execute("SELECT 1", (1,))

    def test_missing_named(self):
        with self.assertRaises(sqlite.ProgrammingError) as caught:
            self.db.execute("SELECT :a", {"b": 1})
        self.assertIn("You did not supply a value for binding parameter :a.", str(caught.exception))

    def test_dictionary_with_unnamed_placeholder(self):
        with self.assertRaises(sqlite.ProgrammingError):
            self.db.execute("SELECT ?", {"a": 1})

    def test_none_means_no_parameters(self):
        self.assertEqual(self.db.execute("SELECT 5", None).fetchone(), (5,))


class TestStatements(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def test_only_one_statement(self):
        with self.assertRaises(sqlite.ProgrammingError) as caught:
            self.db.execute("SELECT 1; SELECT 2")
        self.assertIn("You can only execute one statement at a time.", str(caught.exception))

    def test_trailing_semicolon_space_and_comments_are_fine(self):
        self.assertEqual(self.db.execute("SELECT 1;").fetchone(), (1,))
        self.assertEqual(self.db.execute("SELECT 1; -- fine\n /* ok */ ").fetchone(), (1,))

    def test_comment_only_does_nothing(self):
        cursor = self.db.execute("-- niente")
        self.assertIsNone(cursor.description)
        self.assertEqual(cursor.rowcount, -1)
        self.assertIsNone(cursor.fetchone())

    def test_null_character_in_query(self):
        with self.assertRaises(sqlite.ProgrammingError):
            self.db.execute("SELECT 1\0")

    def test_query_must_be_text(self):
        with self.assertRaises(TypeError):
            self.db.execute(b"SELECT 1")

    def test_complete_statement(self):
        self.assertTrue(sqlite.complete_statement("SELECT 1;"))
        self.assertFalse(sqlite.complete_statement("SELECT 1"))
        self.assertFalse(sqlite.complete_statement("SELECT ';"))
        self.assertTrue(sqlite.complete_statement("SELECT ';';"))
        self.assertFalse(sqlite.complete_statement("CREATE TRIGGER t AFTER INSERT ON a BEGIN SELECT 1;"))
        self.assertTrue(sqlite.complete_statement("CREATE TRIGGER t AFTER INSERT ON a BEGIN SELECT 1; END;"))
        self.assertTrue(sqlite.complete_statement("SELECT 1; -- ciao\n"))
        self.assertFalse(sqlite.complete_statement("SELECT 1; -- ciao"))
        self.assertTrue(sqlite.complete_statement("è;"))


class TestTransactions(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:")
        self.db.execute("CREATE TABLE a(n)")

    def tearDown(self):
        self.db.close()

    def test_no_implicit_transactions(self):
        self.db.execute("INSERT INTO a VALUES (1)")
        self.assertFalse(self.db.in_transaction)

    def test_begin_commit_rollback(self):
        self.db.execute("BEGIN")
        self.assertTrue(self.db.in_transaction)
        self.db.execute("INSERT INTO a VALUES (1)")
        self.db.rollback()
        self.assertFalse(self.db.in_transaction)
        self.assertEqual(self.db.execute("SELECT count(*) FROM a").fetchone()[0], 0)
        self.db.execute("BEGIN")
        self.db.execute("INSERT INTO a VALUES (2)")
        self.db.commit()
        self.assertEqual(self.db.execute("SELECT count(*) FROM a").fetchone()[0], 1)

    def test_commit_rollback_without_transaction_do_nothing(self):
        self.db.commit()
        self.db.rollback()

    def test_context_manager(self):
        with self.db:
            self.db.execute("BEGIN")
            self.db.execute("INSERT INTO a VALUES (1)")
        self.assertEqual(self.db.execute("SELECT count(*) FROM a").fetchone()[0], 1)
        with self.assertRaises(ValueError):
            with self.db:
                self.db.execute("BEGIN")
                self.db.execute("INSERT INTO a VALUES (2)")
                raise ValueError
        self.assertEqual(self.db.execute("SELECT count(*) FROM a").fetchone()[0], 1)

    def test_implicit_transactions_cannot_be_requested(self):
        with self.assertRaises(sqlite.NotSupportedError):
            sqlite.connect(":memory:", isolation_level="DEFERRED")
        with self.assertRaises(sqlite.NotSupportedError):
            sqlite.connect(":memory:", autocommit=False)
        sqlite.connect(":memory:", isolation_level=None, autocommit=True, check_same_thread=False).close()


class TestConnection(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "prova.db")

    def tearDown(self):
        self.folder.cleanup()

    def test_close_twice_and_use_after_close(self):
        db = sqlite.connect(":memory:")
        cursor = db.execute("SELECT 1")
        db.close()
        db.close()
        with self.assertRaises(sqlite.ProgrammingError) as caught:
            db.execute("SELECT 1")
        self.assertIn("Cannot operate on a closed database.", str(caught.exception))
        with self.assertRaises(sqlite.ProgrammingError):
            db.cursor()
        with self.assertRaises(sqlite.ProgrammingError):
            db.in_transaction
        with self.assertRaises(sqlite.ProgrammingError):
            cursor.fetchone()

    def test_close_with_open_cursor_lets_the_file_go(self):
        db = sqlite.connect(self.path)
        db.execute("CREATE TABLE a(x)")
        cursor = db.execute("SELECT * FROM a")
        db.close()
        del cursor
        os.remove(self.path)

    def test_open_creates_missing_file_like_reference(self):
        sqlite.connect(self.path).close()
        self.assertTrue(os.path.exists(self.path))

    def test_open_unwritable_path(self):
        with self.assertRaises(sqlite.OperationalError) as caught:
            sqlite.connect(os.path.join(self.folder.name, "nessuna", "cartella", "x.db"))
        self.assertEqual(caught.exception.sqlite_errorcode, 14)
        self.assertEqual(caught.exception.sqlite_errorname, "SQLITE_CANTOPEN")

    def test_not_a_database(self):
        with open(self.path, "wb") as out:
            out.write(b"questo non e' un database SQLite" * 10)
        db = sqlite.connect(self.path)
        with self.assertRaises(sqlite.DatabaseError) as caught:
            db.execute("PRAGMA schema_version").fetchone()
        self.assertEqual(caught.exception.sqlite_errorcode, 26)
        db.close()

    def test_path_with_accents_and_spaces(self):
        path = os.path.join(self.folder.name, "cartella è ù", "file di prova.db")
        os.makedirs(os.path.dirname(path))
        db = sqlite.connect(path)
        db.execute("CREATE TABLE a(x)")
        db.close()
        self.assertTrue(os.path.exists(path))

    def test_pathlike(self):
        import pathlib
        sqlite.connect(pathlib.Path(self.path)).close()
        self.assertTrue(os.path.exists(self.path))

    def test_read_only_uri(self):
        db = sqlite.connect(self.path)
        db.execute("CREATE TABLE a(x)")
        db.close()
        import pathlib
        uri = pathlib.Path(self.path).as_uri() + "?mode=ro"
        ro = sqlite.connect(uri, uri=True)
        self.assertEqual(ro.execute("SELECT count(*) FROM a").fetchone()[0], 0)
        with self.assertRaises(sqlite.OperationalError) as caught:
            ro.execute("INSERT INTO a VALUES (1)")
        self.assertEqual(caught.exception.sqlite_errorcode & 0xFF, 8)
        ro.close()

    def test_busy_database(self):
        first = sqlite.connect(self.path)
        first.execute("CREATE TABLE a(x)")
        first.execute("BEGIN IMMEDIATE")
        second = sqlite.connect(self.path, timeout=0)
        with self.assertRaises(sqlite.OperationalError) as caught:
            second.execute("BEGIN IMMEDIATE")
        self.assertEqual(caught.exception.sqlite_errorcode & 0xFF, 5)
        self.assertIn("locked", str(caught.exception))
        first.rollback()
        second.execute("BEGIN IMMEDIATE")
        second.rollback()
        first.close()
        second.close()

    def test_busy_timeout_waits(self):
        first = sqlite.connect(self.path)
        first.execute("CREATE TABLE a(x)")
        first.execute("BEGIN IMMEDIATE")
        second = sqlite.connect(self.path, timeout=0.3)
        started = threading.Event()
        timer = threading.Timer(0.1, lambda: (first.rollback(), started.set()))
        timer.start()
        second.execute("BEGIN IMMEDIATE")
        self.assertTrue(started.wait(2))
        second.rollback()
        first.close()
        second.close()

    def test_foreign_keys_and_journal_pragmas(self):
        db = sqlite.connect(self.path)
        self.assertEqual(db.execute("PRAGMA journal_mode = wal").fetchone(), ("wal",))
        db.execute("PRAGMA foreign_keys = ON")
        self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone(), (1,))
        db.close()

    def test_extended_error_codes(self):
        db = sqlite.connect(":memory:")
        db.execute("CREATE TABLE a(x UNIQUE)")
        db.execute("INSERT INTO a VALUES (1)")
        with self.assertRaises(sqlite.IntegrityError) as caught:
            db.execute("INSERT INTO a VALUES (1)")
        self.assertEqual(caught.exception.sqlite_errorcode, 2067)
        self.assertEqual(caught.exception.sqlite_errorname, "SQLITE_CONSTRAINT_UNIQUE")
        db.close()

    def test_error_hierarchy(self):
        for cls in (sqlite.InterfaceError, sqlite.DatabaseError):
            self.assertTrue(issubclass(cls, sqlite.Error))
        for cls in (sqlite.DataError, sqlite.OperationalError, sqlite.IntegrityError, sqlite.InternalError,
                    sqlite.ProgrammingError, sqlite.NotSupportedError):
            self.assertTrue(issubclass(cls, sqlite.DatabaseError))
        self.assertFalse(issubclass(sqlite.LibraryError, sqlite.Error))

    def test_many_connections_do_not_leak_or_crash(self):
        for _ in range(200):
            db = sqlite.connect(":memory:")
            db.execute("SELECT 1").fetchall()
            db.close()


class TestInterrupt(unittest.TestCase):
    LONG = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c"

    def test_interrupt_from_another_thread(self):
        db = sqlite.connect(":memory:")
        timer = threading.Timer(0.3, db.interrupt)
        timer.start()
        with self.assertRaises(sqlite.OperationalError) as caught:
            db.execute(self.LONG).fetchall()
        timer.join()
        self.assertEqual(caught.exception.sqlite_errorcode, 9)
        self.assertEqual(caught.exception.sqlite_errorname, "SQLITE_INTERRUPT")
        self.assertEqual(db.execute("SELECT 1").fetchone(), (1,))
        db.close()

    def test_interrupt_without_running_command_does_nothing(self):
        db = sqlite.connect(":memory:")
        db.interrupt()
        self.assertEqual(db.execute("SELECT 1").fetchone(), (1,))
        db.close()


class TestAuthorizer(unittest.TestCase):
    def setUp(self):
        self.db = sqlite.connect(":memory:")
        self.db.execute("CREATE TABLE a(id INTEGER PRIMARY KEY, n)")

    def tearDown(self):
        self.db.close()

    def test_sees_table_reads(self):
        seen = set()

        def authorizer(action, arg1, arg2, arg3, arg4):
            if action == 20 and arg1:
                seen.add((arg1, arg2))
            return sqlite.SQLITE_OK
        self.db.set_authorizer(authorizer)
        self.db.execute("SELECT n FROM a").fetchall()
        self.db.set_authorizer(None)
        self.assertIn(("a", "n"), seen)

    def test_can_deny(self):
        self.db.set_authorizer(lambda action, *args: sqlite.SQLITE_DENY if action == 18 else sqlite.SQLITE_OK)
        with self.assertRaises(sqlite.DatabaseError) as caught:
            self.db.execute("INSERT INTO a(n) VALUES (1)")
        self.assertEqual(caught.exception.sqlite_errorcode, 23)
        self.db.set_authorizer(None)
        self.db.execute("INSERT INTO a(n) VALUES (1)")

    def test_exception_in_authorizer_means_deny(self):
        def broken(*args):
            raise RuntimeError("boom")
        self.db.set_authorizer(broken)
        with self.assertRaises(sqlite.DatabaseError):
            self.db.execute("SELECT 1 FROM a")

    def test_set_and_clear_repeatedly(self):
        for _ in range(50):
            self.db.set_authorizer(lambda *args: sqlite.SQLITE_OK)
            self.db.execute("SELECT * FROM a").fetchall()
        self.db.set_authorizer(None)
        self.db.execute("SELECT * FROM a").fetchall()

    def test_authorizer_none_arguments_are_none(self):
        arguments = []
        self.db.set_authorizer(lambda *args: (arguments.append(args), sqlite.SQLITE_OK)[1])
        self.db.execute("SELECT 1").fetchall()
        self.assertTrue(arguments)
        self.assertTrue(all(len(a) == 5 for a in arguments))


class TestThreads(unittest.TestCase):
    def test_use_from_several_threads(self):
        db = sqlite.connect(":memory:")
        db.execute("CREATE TABLE a(n)")
        failures = []

        def work(number):
            try:
                for index in range(50):
                    db.execute("INSERT INTO a VALUES (?)", (number * 1000 + index,))
                    db.execute("SELECT count(*) FROM a").fetchone()
            except Exception as exception:
                failures.append(exception)
        threads = [threading.Thread(target=work, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(db.execute("SELECT count(*) FROM a").fetchone()[0], 200)
        db.close()


class TestCatalogEntry(unittest.TestCase):
    def test_library_error_has_a_message_in_both_languages(self):
        from sdbc_pysqlite import messages
        from sdbc_pysqlite.errors import DriverError
        error = DriverError(errors.SQLITE_LIBRARY, percorso="C:\\x\\sdbcsql.dll", dettaglio="file not found")
        for language, word in (("it", "Reinstalla"), ("en", "Reinstall")):
            described = messages.describe(error, language, "test")
            self.assertIn(word, described.message)
            self.assertIn("sdbcsql.dll", described.message)
            self.assertFalse(described.is_warning)


if __name__ == "__main__":
    unittest.main()
