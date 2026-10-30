# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import re
import threading
from collections import namedtuple

from sdbc_pysqlite import errors
from sdbc_pysqlite import results
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.errors import DriverError

Outcome = namedtuple("Outcome", "result count writes")

_BEGIN = {"free": "BEGIN DEFERRED", "blocking": "BEGIN IMMEDIATE", "exclusive": "BEGIN EXCLUSIVE"}
_TRANSACTION_WORDS = ("BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE")
_WRITE_WORDS = ("INSERT", "UPDATE", "DELETE", "REPLACE")
_SQLITE_READ = 20
_PARAMETER_PREFIXES = (":", "@", "$")


def driver_error(exception, path=""):
    if getattr(exception, "sqlite_errorcode", 0) == 9:
        return DriverError(errors.INTERRUPTED)
    return DriverError(None, sqlite=exception, percorso=path)


def probe_text(sql):
    parts = []
    skip_next = False
    previous = None
    for token in sqltext.tokens(sql):
        if skip_next:
            skip_next = False
            if token.kind in ("number", "word") and previous is not None \
                    and token.start == previous.start + len(previous.text):
                previous = None
                continue
        if token.kind == "punct" and (token.text == "?" or token.text in _PARAMETER_PREFIXES):
            parts.append("NULL")
            skip_next = True
            previous = token
            continue
        parts.append(token.text)
        previous = token
    return "".join(parts)


class Engine:

    def __init__(self, db, options, path=""):
        self.db = db
        self.options = options
        self.path = path
        self.autocommit = True
        self._probe_counter = 0
        self._authorizer_lock = threading.RLock()

    @property
    def dirty(self):
        return not self.autocommit and self.db.in_transaction

    def set_autocommit(self, flag):
        if flag and not self.autocommit and self.db.in_transaction:
            self.commit()
        self.autocommit = bool(flag)

    def commit(self):
        if self.db.in_transaction:
            self._guard(lambda: self.db.execute("COMMIT"))

    def rollback(self):
        if self.db.in_transaction:
            self._guard(lambda: self.db.execute("ROLLBACK"))

    def discard(self):
        had = self.dirty
        if self.db.in_transaction:
            try:
                self.db.execute("ROLLBACK")
            except sqlite.Error:
                pass
        return had

    def interrupt(self):
        try:
            self.db.interrupt()
        except sqlite.Error:
            pass

    def _guard(self, action):
        try:
            return action()
        except sqlite.Error as exception:
            raise driver_error(exception, self.path)

    def ensure_transaction(self):
        self._begin_if_needed(["ALTER"])

    def _begin_if_needed(self, words):
        if self.autocommit or self.db.in_transaction:
            return
        if not words or words[0] in _TRANSACTION_WORDS or words[0] in ("SELECT", "VALUES", "EXPLAIN", "PRAGMA"):
            return
        self.db.execute(_BEGIN[self.options.transaction_mode])

    def run(self, sql, params=()):
        try:
            return self._run(sql, params)
        except sqlite.Error as exception:
            raise driver_error(exception, self.path)

    def _run(self, sql, params):
        words = sqltext.first_words(sql, 2)
        self._begin_if_needed(words)
        wrappable = sqltext.is_wrappable_query(sql)
        tables = set()
        version = results.read_data_version(self.db) if wrappable else None
        if wrappable:
            cursor = self._execute_reading(sql, params, tables)
        else:
            cursor = self.db.execute(sql, params)
        description = cursor.description
        if description is None:
            count = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
            cursor.close()
            return Outcome(None, count, True)
        if wrappable:
            return self._query_result(sql, params, cursor, description, tables, version)
        rows = cursor.fetchall()
        count = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else len(rows)
        cursor.close()
        columns = self.describe(sql, params, description, rows[:20], set(), probe=False)
        return Outcome(results.ResultData(columns, results.CompleteStore(rows)), count,
                       bool(words) and words[0] in _WRITE_WORDS)

    def _execute_reading(self, sql, params, tables):
        def authorizer(action, arg1, arg2, arg3, arg4):
            if action == _SQLITE_READ and arg4 is None and arg1 and not arg1.lower().startswith("sqlite_"):
                tables.add(arg1)
            return sqlite.SQLITE_OK
        with self._authorizer_lock:
            self.db.set_authorizer(authorizer)
            try:
                return self.db.execute(sql, params)
            finally:
                self.db.set_authorizer(None)

    def _query_result(self, sql, params, cursor, description, tables, version=None):
        limit = self.options.full_load_limit
        rows = cursor.fetchmany(limit)
        if len(rows) < limit:
            cursor.close()
            columns = self.describe(sql, params, description, rows[:20], tables)
            return Outcome(results.ResultData(columns, results.CompleteStore(rows)), 0, False)
        cursor.close()
        size = self.options.window_size
        columns = self.describe(sql, params, description, rows[:20], tables)
        store = results.WindowStore(self.db, sqltext.strip_trailing(sql), params, size, rows, version)
        return Outcome(results.ResultData(columns, store, "window"), 0, False)

    def begin_atomic(self):
        if self.autocommit and not self.db.in_transaction:
            self._guard(lambda: self.db.execute(_BEGIN[self.options.transaction_mode]))
            return True
        return False

    def end_atomic(self, opened, success):
        if opened:
            if success:
                self.commit()
            else:
                self.discard()

    def generated_key(self, sql):
        table = sqltext.insert_target(sql)
        if table is None:
            return None
        try:
            alias = schema.rowid_alias(self.db, table)
            if alias is None:
                return None
            return alias, self.db.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite.Error:
            return None

    def columns_of(self, sql):
        if not sqltext.is_wrappable_query(sql):
            return None
        tables = set()
        try:
            cursor = self._execute_reading("SELECT * FROM (\n%s\n) LIMIT 0" % sqltext.strip_trailing(probe_text(sql)),
                                           (), tables)
            description = cursor.description
            cursor.close()
        except sqlite.Error as exception:
            raise driver_error(exception, self.path)
        return self.describe(sql, (), description, [], tables)

    def describe(self, sql, params, description, sample, tables, probe=True):
        names = [d[0] for d in description]
        labels = None
        if probe:
            labels = self._probe_labels(sql, len(names))
        if labels is None:
            return [self._computed(name, "", sample, index) for index, name in enumerate(names)]
        shadows = schema.shadow_tables(self.db)
        tables = {t for t in tables if t.lower() not in shadows}
        real = [t for t in tables if schema.object_kind(self.db, t) == "table"]
        if len(tables) == 1 and len(real) == 1:
            return self._single_table(names, labels, real[0], sample)
        return [self._computed(name, label, sample, index) for index, (name, label) in enumerate(zip(names, labels))]

    def _probe_labels(self, sql, count):
        self._probe_counter += 1
        view = "sdbc_probe_%d" % self._probe_counter
        quoted = sqltext.quote_name(view)
        try:
            self.db.execute("CREATE TEMP VIEW %s AS %s" % (quoted, sqltext.strip_trailing(probe_text(sql))))
        except sqlite.Error:
            return None
        try:
            rows = self.db.execute("PRAGMA temp.table_xinfo(%s)" % quoted).fetchall()
        except sqlite.Error:
            rows = []
        finally:
            try:
                self.db.execute("DROP VIEW temp.%s" % quoted)
            except sqlite.Error:
                pass
        rows = [r for r in rows if r[6] != 1]
        if len(rows) != count:
            return None
        return [r[2] or "" for r in rows]

    def _computed(self, name, label, sample, index):
        ctype = ts.classify(label)
        if not label and sample:
            ctype = self._type_from_values(sample, index, ctype)
        return results.Column(name, ctype, results.NULLABLE_UNKNOWN, False, "", True, False)

    @staticmethod
    def _type_from_values(sample, index, default):
        kinds = set()
        for row in sample:
            value = row[index]
            if value is None:
                continue
            if isinstance(value, bool) or isinstance(value, int):
                kinds.add("int")
            elif isinstance(value, float):
                kinds.add("real")
            elif isinstance(value, str):
                kinds.add("text")
            else:
                kinds.add("blob")
        if len(kinds) == 1:
            kind = kinds.pop()
            return {"int": ts.classify("LO_BIGINT"), "real": ts.classify("LO_DOUBLE"),
                    "text": ts.classify("LO_VARCHAR"), "blob": ts.classify("LO_VARBINARY")}[kind]
        return default

    def _single_table(self, names, labels, table, sample):
        columns = schema.table_columns(self.db, table)
        by_name = {c.name.lower(): c for c in columns}
        alias = schema.rowid_alias(self.db, table, columns)
        result = []
        for index, (name, label) in enumerate(zip(names, labels)):
            column = by_name.get(name.lower())
            direct = column is not None and (
                column.label.upper() == label.upper() or (column.label == "" and label.upper() == "BLOB"))
            if not direct:
                result.append(self._computed(name, label, sample, index))
                continue
            ctype = ts.classify(column.label)
            is_alias = column.name == alias
            not_null = column.notnull or is_alias
            generated = column.hidden in (2, 3)
            result.append(results.Column(
                name, ctype, results.NO_NULLS if not_null else results.NULLABLE, is_alias, table,
                generated, not generated))
        return result
