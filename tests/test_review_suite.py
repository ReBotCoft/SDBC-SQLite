# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from collections import namedtuple

import support

from sdbc_pysqlite import engine
from sdbc_pysqlite import errors
from sdbc_pysqlite import messages
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.errors import DriverError

Options = namedtuple("Options", "full_load_limit window_size transaction_mode")

ROWS = 50
LONG = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT count(*) FROM c"
FINITE = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c WHERE x < 1500000) SELECT count(*) FROM c"
BUSY = 5
SCRIPT_THREADS = """
import sys, threading
import support
from collections import namedtuple
from sdbc_pysqlite import engine, sqlite
Options = namedtuple("Options", "full_load_limit window_size transaction_mode")
connection = sqlite.connect(%(path)r, timeout=5)
engine_ = engine.Engine(connection, Options(1000, 5, "free"), %(path)r)
failures = []
def work(number):
    try:
        for index in range(40):
            engine_.run("INSERT INTO t(id, n) VALUES (?, 'x')", (1000 + number * 100 + index,))
            engine_.run("SELECT count(*) FROM t")
    except BaseException as exception:
        failures.append(repr(exception))
threads = [threading.Thread(target=work, args=(number,)) for number in range(4)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()
count = engine_.run("SELECT count(*) FROM t").result.store.get(1)[0]
connection.close()
print("failures", failures)
print("ok", count - 50 if not failures else -1)
"""
WAIT = 30


class FileTestCase(unittest.TestCase):

    journal = "delete"

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.path = os.path.join(self._dir.name, "prova.db")
        self.connections = []
        self.addCleanup(self.close_all)
        setup = self.connect()
        if self.journal != "delete":
            setup.execute("PRAGMA journal_mode = %s" % self.journal).fetchall()
        setup.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, n TEXT)")
        setup.execute("BEGIN")
        for number in range(1, ROWS + 1):
            setup.execute("INSERT INTO t VALUES (?, ?)", (number, "riga %d" % number))
        setup.execute("COMMIT")

    def connect(self, timeout=0.3):
        connection = sqlite.connect(self.path, timeout=timeout)
        self.connections.append(connection)
        return connection

    def close_all(self):
        for connection in self.connections:
            try:
                connection.close()
            except sqlite.Error:
                pass

    def make_engine(self, full_load_limit=10, window_size=5, mode="free", timeout=0.3):
        return engine.Engine(self.connect(timeout), Options(full_load_limit, window_size, mode), self.path)

    def ids(self, store, *positions):
        return [store.get(position)[0] if store.get(position) else None for position in positions]


class WindowedResultTests(FileTestCase):

    def window(self, mode="free"):
        self.engine = self.make_engine(10, 5, mode)
        outcome = self.engine.run("SELECT id FROM t ORDER BY id")
        self.assertEqual(outcome.result.mode, "window")
        return outcome.result.store

    def test_below_the_limit_the_result_is_complete_and_does_not_change(self):
        engine_ = self.make_engine(full_load_limit=ROWS + 1)
        outcome = engine_.run("SELECT id FROM t ORDER BY id")
        self.assertEqual(outcome.result.mode, "complete")
        other = self.connect()
        other.execute("DELETE FROM t WHERE id = 3")
        store = outcome.result.store
        self.assertEqual(self.ids(store, 3, 6), [3, 6])
        self.assertEqual(store.count(), ROWS)

    def test_limit_smaller_than_window_does_not_truncate_the_result(self):
        for limit, size in ((3, 5), (1, 5), (4, 4), (5, 3)):
            with self.subTest(limit=limit, window=size):
                engine_ = self.make_engine(limit, size)
                outcome = engine_.run("SELECT id FROM t ORDER BY id")
                self.assertEqual(outcome.result.mode, "window")
                store = outcome.result.store
                self.assertEqual(self.ids(store, 1, limit, limit + 1, 11, 50, 51), [1, limit, limit + 1, 11, 50, None])
                self.assertEqual(store.count(), ROWS)

    def test_window_without_changes_is_consistent(self):
        store = self.window()
        self.assertEqual(self.ids(store, 1, 5, 6, 11, 50, 51), [1, 5, 6, 11, 50, None])
        self.assertEqual(store.count(), ROWS)

    def test_deletion_by_another_connection_is_reported_before_the_next_block(self):
        store = self.window()
        other = self.connect()
        other.execute("DELETE FROM t WHERE id = 3")
        self.assertEqual(self.ids(store, 1, 2, 3, 4, 5), [1, 2, 3, 4, 5])
        with self.assertRaises(DriverError) as raised:
            store.get(6)
        self.assertEqual(raised.exception.code, errors.RESULT_OUT_OF_DATE)
        self.assertEqual(self.ids(store, 3), [3])

    def test_insertion_by_another_connection_is_reported(self):
        store = self.window()
        other = self.connect()
        other.execute("INSERT INTO t VALUES (0, 'prima di tutte')")
        with self.assertRaises(DriverError) as raised:
            store.get(6)
        self.assertEqual(raised.exception.code, errors.RESULT_OUT_OF_DATE)

    def test_update_by_another_connection_is_reported(self):
        store = self.window()
        self.connect().execute("UPDATE t SET n = 'cambiata' WHERE id = 20")
        with self.assertRaises(DriverError):
            store.get(11)

    def test_count_is_checked_too(self):
        store = self.window()
        self.connect().execute("DELETE FROM t WHERE id = 3")
        with self.assertRaises(DriverError) as raised:
            store.count()
        self.assertEqual(raised.exception.code, errors.RESULT_OUT_OF_DATE)

    def test_the_error_stays_until_the_query_is_run_again(self):
        store = self.window()
        self.connect().execute("DELETE FROM t WHERE id = 3")
        for _ in range(2):
            with self.assertRaises(DriverError):
                store.get(6)
        with self.assertRaises(DriverError):
            store.count()
        again = self.engine.run("SELECT id FROM t ORDER BY id").result.store
        self.assertEqual(self.ids(again, 3, 6, 11), [4, 7, 12])
        self.assertEqual(again.count(), ROWS - 1)

    def test_no_false_alarm_without_changes(self):
        store = self.window()
        self.assertEqual(self.ids(store, 6, 11, 1, 50), [6, 11, 1, 50])
        self.assertEqual(store.count(), ROWS)

    def test_a_change_made_before_the_query_is_not_a_drift(self):
        self.connect().execute("DELETE FROM t WHERE id = 3")
        store = self.window()
        self.assertEqual(self.ids(store, 6, 11), [7, 12])

    def test_read_only_changes_of_another_connection_do_not_matter(self):
        store = self.window()
        reader = self.connect()
        reader.execute("SELECT * FROM t").fetchall()
        self.assertEqual(self.ids(store, 6), [6])

    def test_error_message_names_the_refresh_command(self):
        text = messages.describe(DriverError(errors.RESULT_OUT_OF_DATE), "it", "ResultSet.next").message
        self.assertIn("ATTENZIONE", text)
        self.assertIn("«Aggiorna»", text)
        text = messages.describe(DriverError(errors.RESULT_OUT_OF_DATE), "en", "ResultSet.next").message
        self.assertIn("WARNING", text)
        self.assertIn("Refresh", text)

    def test_own_writes_are_not_followed_either(self):
        store = self.window()
        self.engine.run("DELETE FROM t WHERE id = 3")
        self.assertEqual(self.ids(store, 3), [3])
        self.assertEqual(self.ids(store, 6), [7])
        self.assertEqual(self.ids(store, 3), [4])
        self.assertEqual(store.count(), ROWS - 1)

    def test_open_window_blocks_other_writers_in_the_default_journal(self):
        store = self.window()
        self.assertIsNone(store._stream)
        store.get(8)
        self.assertIsNotNone(store._stream)
        other = self.connect(timeout=0.2)
        with self.assertRaises(sqlite.Error) as raised:
            other.execute("DELETE FROM t WHERE id = 3")
        self.assertEqual(raised.exception.sqlite_errorcode & 0xFF, BUSY)
        self.assertEqual(self.ids(store, 6, 11), [6, 11])
        store.close()
        other.execute("DELETE FROM t WHERE id = 3")


class WindowedResultWalTests(FileTestCase):
    journal = "wal"

    def test_in_wal_an_open_window_keeps_a_stable_view(self):
        engine_ = self.make_engine(10, 5)
        store = engine_.run("SELECT id FROM t ORDER BY id").result.store
        store.get(8)
        self.assertIsNotNone(store._stream)
        other = self.connect()
        other.execute("DELETE FROM t WHERE id = 3")
        self.assertEqual(self.ids(store, 6, 11), [6, 11])
        store.close()
        self.assertEqual(self.ids(engine_.run("SELECT id FROM t ORDER BY id").result.store, 6), [7])

    def test_in_wal_a_change_after_the_first_block_is_reported(self):
        engine_ = self.make_engine(10, 5)
        store = engine_.run("SELECT id FROM t ORDER BY id").result.store
        self.connect().execute("DELETE FROM t WHERE id = 3")
        with self.assertRaises(DriverError) as raised:
            store.get(6)
        self.assertEqual(raised.exception.code, errors.RESULT_OUT_OF_DATE)

    def test_in_wal_with_the_stream_open_the_following_blocks_stay_consistent(self):
        engine_ = self.make_engine(10, 5)
        store = engine_.run("SELECT id FROM t ORDER BY id").result.store
        store.get(8)
        self.connect().execute("DELETE FROM t WHERE id = 3")
        self.assertEqual(self.ids(store, 11, 16), [11, 16])
        store.close()
        with self.assertRaises(DriverError):
            store2 = engine_.run("SELECT id FROM t ORDER BY id").result.store
            self.connect().execute("DELETE FROM t WHERE id = 4")
            store2.get(21)

    def test_in_wal_own_writes_are_not_reported(self):
        engine_ = self.make_engine(10, 5)
        store = engine_.run("SELECT id FROM t ORDER BY id").result.store
        engine_.run("DELETE FROM t WHERE id = 3")
        self.assertEqual(self.ids(store, 6), [7])


class ConcurrencyTests(FileTestCase):
    def run_threads(self, targets):
        failures = []

        def guard(target):
            try:
                target()
            except BaseException as exception:
                failures.append(exception)
        threads = [threading.Thread(target=guard, args=(target,)) for target in targets]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(WAIT)
        self.assertFalse([thread for thread in threads if thread.is_alive()], "un thread non e' terminato")
        return failures

    def test_engine_used_by_several_threads(self):
        code = SCRIPT_THREADS % {"path": self.path}
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([support.PYTHONPATH, os.path.dirname(os.path.abspath(__file__))])
        try:
            done = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                                  timeout=120)
        except OSError:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exec(compile(code, "<thread-script>", "exec"), {"__name__": "__thread_script__"})
            self.assertIn("ok 160", output.getvalue())
            return
        self.assertEqual(done.returncode, 0, "codice di uscita %s\n%s" % (done.returncode, done.stderr[-2000:]))
        self.assertIn("ok 160", done.stdout)

    def test_two_cursors_read_in_turn_from_two_threads(self):
        db = self.connect()
        db.execute("CREATE TABLE big(i INTEGER)")
        db.execute("BEGIN")
        for number in range(2000):
            db.execute("INSERT INTO big VALUES (?)", (number,))
        db.execute("COMMIT")
        sums = {}

        def read(name, order):
            def run():
                cursor = db.execute("SELECT i FROM big ORDER BY i %s" % order)
                total = 0
                while True:
                    row = cursor.fetchone()
                    if row is None:
                        break
                    total += row[0]
                sums[name] = total
            return run
        self.assertEqual(self.run_threads([read("up", "ASC"), read("down", "DESC")]), [])
        self.assertEqual(sums, {"up": 1999000, "down": 1999000})

    def test_close_waits_for_a_running_command(self):
        db = self.connect()
        result = []

        def work():
            try:
                result.append(db.execute(FINITE).fetchall())
            except sqlite.Error as exception:
                result.append(exception)
        worker = threading.Thread(target=work)
        worker.start()
        time.sleep(0.2)
        started = time.time()
        db.close()
        waited = time.time() - started
        worker.join(WAIT)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(result), 1)
        self.assertLess(waited, WAIT)

    def test_interrupt_then_close_ends_a_command_that_never_finishes(self):
        db = self.connect()
        result = []

        def work():
            try:
                db.execute(LONG).fetchall()
                result.append("finito")
            except sqlite.Error as exception:
                result.append(exception.sqlite_errorcode)
        worker = threading.Thread(target=work)
        worker.start()
        time.sleep(0.3)
        db.interrupt()
        closer = threading.Thread(target=db.close)
        closer.start()
        closer.join(WAIT)
        worker.join(WAIT)
        self.assertFalse(closer.is_alive())
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [9])

    def test_interrupt_and_close_at_the_same_time(self):
        for _ in range(5):
            db = self.connect()
            outcome = []

            def work():
                try:
                    db.execute(LONG).fetchall()
                except sqlite.Error as exception:
                    outcome.append(exception.sqlite_errorcode)
            worker = threading.Thread(target=work)
            worker.start()
            time.sleep(0.1)
            interrupter = threading.Thread(target=db.interrupt)
            closer = threading.Thread(target=db.close)
            interrupter.start()
            closer.start()
            for thread in (interrupter, closer, worker):
                thread.join(WAIT)
                self.assertFalse(thread.is_alive())
            self.assertEqual(outcome, [9])

    def test_connection_stays_usable_after_an_interrupt(self):
        engine_ = self.make_engine(1000, 5)
        timer = threading.Timer(0.3, engine_.interrupt)
        timer.start()
        with self.assertRaises(DriverError) as raised:
            engine_.run(LONG)
        timer.join()
        self.assertEqual(raised.exception.code, errors.INTERRUPTED)
        self.assertEqual(engine_.run("SELECT count(*) FROM t").result.store.get(1), (ROWS,))


class TransactionStartTests(FileTestCase):
    MODES = ("free", "blocking", "exclusive")

    def each_mode(self):
        for mode in self.MODES:
            with self.subTest(mode=mode):
                self.engine = self.make_engine(1000, 5, mode)
                self.engine.set_autocommit(False)
                yield mode
                self.engine.discard()
                self.engine.set_autocommit(True)

    def count(self, connection):
        return connection.execute("SELECT count(*) FROM t").fetchone()[0]

    def test_with_insert_update_delete_open_a_transaction_that_can_be_rolled_back(self):
        for _ in self.each_mode():
            for sql in ("WITH s(v) AS (SELECT 1) INSERT INTO t(id, n) SELECT 900, 'w' FROM s",
                        "WITH s(v) AS (SELECT 'u') UPDATE t SET n = (SELECT v FROM s) WHERE id = 1",
                        "WITH s(v) AS (SELECT 2) DELETE FROM t WHERE id IN (SELECT v FROM s)"):
                self.engine.run(sql)
                self.assertTrue(self.engine.db.in_transaction, sql)
                self.assertTrue(self.engine.dirty)
                self.engine.rollback()
            self.assertEqual(self.count(self.engine.db), ROWS)
            self.assertEqual(self.engine.db.execute("SELECT n FROM t WHERE id = 1").fetchone(), ("riga 1",))

    def test_returning_opens_a_transaction_and_returns_the_rows(self):
        for _ in self.each_mode():
            outcome = self.engine.run("INSERT INTO t(id, n) VALUES (901, 'r') RETURNING id, n")
            self.assertEqual(outcome.result.store.get(1), (901, "r"))
            self.assertTrue(self.engine.db.in_transaction)
            outcome = self.engine.run("UPDATE t SET n = 'v' WHERE id = 901 RETURNING n")
            self.assertEqual(outcome.result.store.get(1), ("v",))
            outcome = self.engine.run("DELETE FROM t WHERE id = 901 RETURNING id")
            self.assertEqual(outcome.result.store.get(1), (901,))
            self.engine.run("INSERT INTO t(id, n) VALUES (902, 'r') RETURNING id")
            self.engine.rollback()
            self.assertEqual(self.count(self.engine.db), ROWS)

    def test_returning_is_visible_to_others_only_after_the_commit(self):
        for mode in self.each_mode():
            self.engine.run("INSERT INTO t(id, n) VALUES (903, 'r') RETURNING id")
            other = self.connect()
            if mode != "exclusive":
                self.assertEqual(self.count(other), ROWS)
            self.engine.commit()
            self.assertFalse(self.engine.db.in_transaction)
            self.assertEqual(self.count(other), ROWS + 1)
            self.engine.run("DELETE FROM t WHERE id = 903")
            self.engine.commit()

    def test_structure_changes_open_a_transaction_and_roll_back(self):
        for _ in self.each_mode():
            self.engine.run("CREATE TABLE nuova(a)")
            self.assertTrue(self.engine.db.in_transaction)
            self.engine.run("ALTER TABLE t ADD COLUMN extra")
            self.engine.run("CREATE INDEX ix_nuova ON nuova(a)")
            self.engine.rollback()
            tables = {row[0] for row in self.engine.db.execute("SELECT name FROM sqlite_master")}
            self.assertNotIn("nuova", tables)
            columns = [row[1] for row in self.engine.db.execute("PRAGMA table_info(t)")]
            self.assertNotIn("extra", columns)

    def test_pragma_that_changes_state_does_not_open_a_transaction(self):
        for _ in self.each_mode():
            self.engine.run("PRAGMA user_version = 7")
            self.assertFalse(self.engine.db.in_transaction)
            self.engine.rollback()
            self.assertEqual(self.engine.db.execute("PRAGMA user_version").fetchone(), (7,))
            self.engine.run("PRAGMA user_version = 0")

    def test_pragma_inside_an_open_transaction_stays_in_it(self):
        for _ in self.each_mode():
            self.engine.run("INSERT INTO t(id, n) VALUES (904, 'p')")
            self.engine.run("PRAGMA foreign_keys")
            self.assertTrue(self.engine.db.in_transaction)
            self.engine.rollback()
            self.assertEqual(self.count(self.engine.db), ROWS)

    def test_reading_with_a_with_clause_opens_a_transaction_in_the_safe_direction(self):
        for _ in self.each_mode():
            self.engine.run("WITH s AS (SELECT id FROM t) SELECT count(*) FROM s")
            self.assertTrue(self.engine.db.in_transaction)
            self.assertEqual(self.count(self.engine.db), ROWS)
            self.engine.commit()
            self.assertFalse(self.engine.db.in_transaction)

    def test_plain_reads_and_transaction_words_do_not_start_a_second_transaction(self):
        for _ in self.each_mode():
            for sql in ("SELECT 1", "VALUES (1)", "EXPLAIN SELECT 1", "PRAGMA table_info(t)"):
                self.engine.run(sql)
                self.assertFalse(self.engine.db.in_transaction, sql)
            self.engine.run("BEGIN")
            self.assertTrue(self.engine.db.in_transaction)
            self.engine.run("INSERT INTO t(id, n) VALUES (905, 'b')")
            self.engine.run("COMMIT")
            self.assertFalse(self.engine.db.in_transaction)
            self.engine.run("DELETE FROM t WHERE id = 905")
            self.engine.commit()

    def test_what_other_connections_can_do_while_the_transaction_is_open(self):
        engine_ = self.make_engine(1000, 5, "free")
        engine_.set_autocommit(False)
        engine_.run("SELECT 1")
        other = self.connect(timeout=0.1)
        other.execute("INSERT INTO t VALUES (950, 'altro')")
        other.execute("DELETE FROM t WHERE id = 950")
        engine_.run("INSERT INTO t(id, n) VALUES (951, 'mio')")
        self.assertEqual(self.count(other), ROWS)
        with self.assertRaises(sqlite.Error) as raised:
            other.execute("INSERT INTO t VALUES (952, 'altro')")
        self.assertEqual(raised.exception.sqlite_errorcode & 0xFF, BUSY)
        engine_.rollback()

        blocking = self.make_engine(1000, 5, "blocking")
        blocking.set_autocommit(False)
        blocking.run("INSERT INTO t(id, n) VALUES (953, 'mio')")
        self.assertEqual(self.count(other), ROWS)
        with self.assertRaises(sqlite.Error):
            other.execute("INSERT INTO t VALUES (954, 'altro')")
        blocking.rollback()

        exclusive = self.make_engine(1000, 5, "exclusive")
        exclusive.set_autocommit(False)
        exclusive.run("INSERT INTO t(id, n) VALUES (955, 'mio')")
        with self.assertRaises(sqlite.Error) as raised:
            self.count(other)
        self.assertEqual(raised.exception.sqlite_errorcode & 0xFF, BUSY)
        exclusive.rollback()
        self.assertEqual(self.count(other), ROWS)


class LockWaitTests(FileTestCase):
    def holder(self, mode="free"):
        holder = self.make_engine(1000, 5, mode)
        holder.set_autocommit(False)
        holder.run("INSERT INTO t(id, n) VALUES (960, 'tengo il blocco')")
        return holder

    def test_error_arrives_after_the_configured_wait(self):
        holder = self.holder()
        for timeout in (0, 0.5, 1):
            writer = self.connect(timeout=timeout)
            started = time.time()
            with self.assertRaises(sqlite.Error) as raised:
                writer.execute("INSERT INTO t VALUES (961, 'attendo')")
            elapsed = time.time() - started
            self.assertEqual(raised.exception.sqlite_errorcode & 0xFF, BUSY)
            self.assertGreaterEqual(elapsed, timeout - 0.05)
            self.assertLess(elapsed, timeout + 1.5)
        holder.rollback()

    def test_user_message_names_the_option_in_both_languages(self):
        holder = self.holder()
        engine_ = self.make_engine(1000, 5, timeout=0.1)
        with self.assertRaises(DriverError) as raised:
            engine_.run("INSERT INTO t(id, n) VALUES (962, 'attendo')")
        for language in ("it", "en"):
            described = messages.describe(raised.exception, language, "test")
            self.assertIn("LockTimeoutSeconds", described.message)
        holder.rollback()

    def test_second_write_succeeds_once_the_first_is_closed(self):
        holder = self.holder()
        writer = self.make_engine(1000, 5, timeout=0.1)
        with self.assertRaises(DriverError):
            writer.run("INSERT INTO t(id, n) VALUES (963, 'attendo')")
        holder.commit()
        writer.run("INSERT INTO t(id, n) VALUES (963, 'attendo')")
        self.assertEqual(writer.db.execute("SELECT count(*) FROM t").fetchone(), (ROWS + 2,))

    def test_wait_is_enough_when_the_first_write_finishes_in_time(self):
        holder = self.holder()
        writer = self.make_engine(1000, 5, timeout=5)
        timer = threading.Timer(0.4, holder.commit)
        timer.start()
        started = time.time()
        writer.run("INSERT INTO t(id, n) VALUES (964, 'ho aspettato')")
        elapsed = time.time() - started
        timer.join()
        self.assertGreaterEqual(elapsed, 0.3)
        self.assertLess(elapsed, 4)
        self.assertEqual(writer.db.execute("SELECT count(*) FROM t").fetchone(), (ROWS + 2,))

    def test_wait_applies_in_every_transaction_mode(self):
        for mode in ("free", "blocking", "exclusive"):
            with self.subTest(mode=mode):
                holder = self.holder(mode)
                writer = self.make_engine(1000, 5, mode, timeout=0.2)
                writer.set_autocommit(False)
                try:
                    started = time.time()
                    with self.assertRaises(DriverError):
                        writer.run("INSERT INTO t(id, n) VALUES (965, 'attendo')")
                    self.assertGreaterEqual(time.time() - started, 0.15)
                    self.assertEqual(writer.dirty, mode == "free")
                finally:
                    holder.discard()
                    writer.discard()


if __name__ == "__main__":
    unittest.main()
