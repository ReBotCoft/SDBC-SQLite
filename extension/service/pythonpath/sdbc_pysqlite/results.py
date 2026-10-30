# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from collections import namedtuple

from sdbc_pysqlite import errors
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.errors import DriverError

NO_NULLS = 0
NULLABLE = 1
NULLABLE_UNKNOWN = 2

Column = namedtuple("Column", "label ctype nullable auto_increment table read_only writable")


def declared_column(name, code, nullable=NULLABLE):
    kind = {ts.INTEGER: ts.K_INT, ts.SMALLINT: ts.K_INT, ts.BIGINT: ts.K_INT, ts.BOOLEAN: ts.K_BOOL}.get(
        code, ts.K_TEXT)
    names = {ts.INTEGER: "INTEGER", ts.SMALLINT: "SMALLINT", ts.BIGINT: "BIGINT", ts.BOOLEAN: "BOOLEAN"}
    size = 0 if kind != ts.K_TEXT else ts.UNLIMITED
    ctype = ts.ColumnType(code, names.get(code, "VARCHAR"), size, 0, kind, False, None, None)
    return Column(name, ctype, nullable, False, "", True, False)


def read_data_version(db):
    try:
        row = db.execute("PRAGMA data_version").fetchone()
        return row[0] if row else None
    except Exception:
        return None


class CompleteStore:

    def __init__(self, rows):
        self._rows = rows

    def get(self, pos):
        if 1 <= pos <= len(self._rows):
            return self._rows[pos - 1]
        return None

    def count(self):
        return len(self._rows)

    def known_count(self):
        return len(self._rows)

    def sample(self, how_many):
        return self._rows[:how_many]

    def close(self):
        self._rows = []


class WindowStore:

    def __init__(self, db, sql, params, window_size, first_rows, data_version=None):
        self._db = db
        self._sql = sql
        self._params = tuple(params)
        self._size = window_size
        self._block = list(first_rows[:window_size])
        self._start = 0
        self._count = None
        self._stream = None
        self._stream_next = None
        self._version = data_version if data_version is not None else read_data_version(db)
        self._stale = False

    def _check_unchanged(self):
        if self._stale:
            raise DriverError(errors.RESULT_OUT_OF_DATE)
        if self._version is None:
            return
        current = read_data_version(self._db)
        if current is not None and current != self._version:
            self._stale = True
            self._close_stream()
            raise DriverError(errors.RESULT_OUT_OF_DATE)

    def _wrapped(self, offset):
        return "SELECT * FROM (\n%s\n) LIMIT -1 OFFSET %d" % (self._sql, offset)

    def _close_stream(self):
        if self._stream is not None:
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
            self._stream_next = None

    def _load(self, start):
        self._check_unchanged()
        if self._stream is not None and self._stream_next == start:
            cursor = self._stream
        else:
            self._close_stream()
            cursor = self._db.execute(self._wrapped(start), self._params)
            self._stream = cursor
        rows = cursor.fetchmany(self._size)
        self._start = start
        self._block = rows
        self._stream_next = start + len(rows)
        if len(rows) < self._size:
            self._count = start + len(rows)
            self._close_stream()

    def get(self, pos):
        if pos < 1:
            return None
        index = pos - 1
        if self._count is not None and index >= self._count:
            return None
        if not (self._start <= index < self._start + len(self._block)):
            self._load((index // self._size) * self._size)
        offset = index - self._start
        if 0 <= offset < len(self._block):
            return self._block[offset]
        return None

    def known_count(self):
        return self._count

    def count(self):
        if self._count is None:
            self._check_unchanged()
            row = self._db.execute("SELECT COUNT(*) FROM (\n%s\n)" % self._sql, self._params).fetchone()
            self._count = row[0]
        return self._count

    def sample(self, how_many):
        return self._block[:how_many]

    def close(self):
        self._close_stream()
        self._block = []


class ResultData:

    def __init__(self, columns, store, mode="complete"):
        self.columns = list(columns)
        self.store = store
        self.mode = mode
        self.pos = 0
        self.closed = False

    def row(self):
        if self.pos < 1:
            return None
        return self.store.get(self.pos)

    def _after_last(self):
        self.pos = self.store.count() + 1

    def next(self):
        if self.store.get(self.pos + 1) is not None:
            self.pos += 1
            return True
        known = self.store.known_count()
        if known is not None and self.pos > known:
            return False
        self._after_last()
        return False

    def previous(self):
        if self.pos <= 1:
            self.pos = 0
            return False
        self.pos -= 1
        return True

    def first(self):
        if self.store.get(1) is None:
            return False
        self.pos = 1
        return True

    def last(self):
        count = self.store.count()
        if count == 0:
            return False
        self.pos = count
        return True

    def before_first(self):
        self.pos = 0

    def after_last(self):
        self._after_last()

    def absolute(self, row):
        if row > 0:
            if self.store.get(row) is not None:
                self.pos = row
                return True
            self._after_last()
            return False
        if row < 0:
            target = self.store.count() + row + 1
            if target >= 1:
                self.pos = target
                return True
            self.pos = 0
            return False
        self.pos = 0
        return False

    def relative(self, rows):
        if rows == 0:
            return self.row() is not None
        target = self.pos + rows
        if target < 1:
            self.pos = 0
            return False
        return self.absolute(target)

    def is_before_first(self):
        return self.pos == 0 and self.store.get(1) is not None

    def is_after_last(self):
        if self.pos < 1:
            return False
        return self.row() is None and self.store.get(1) is not None

    def is_first(self):
        return self.pos == 1 and self.row() is not None

    def is_last(self):
        return self.row() is not None and self.store.get(self.pos + 1) is None

    def get_row(self):
        return self.pos if self.row() is not None else 0

    def close(self):
        if not self.closed:
            self.closed = True
            self.store.close()


def memory_result(declared, rows):
    columns = [declared_column(name, code) for name, code in declared]
    return ResultData(columns, CompleteStore(list(rows)))
