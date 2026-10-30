# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import ctypes
import os
import platform
import struct
import sys
import threading
import weakref

SQLITE_OK = 0
SQLITE_DENY = 1
SQLITE_IGNORE = 2

_ROW = 100
_DONE = 101
_NOMEM = 7
_INTEGER, _FLOAT, _TEXT, _BLOB, _NULL = 1, 2, 3, 4, 5
_OPEN_READWRITE = 0x00000002
_OPEN_CREATE = 0x00000004
_OPEN_URI = 0x00000040
_INT64_MIN = -(2 ** 63)
_INT64_MAX = 2 ** 63 - 1
_UTF8 = 1
_DETERMINISTIC = 0x800
_INNOCUOUS = 0x200000

DBCONFIG_DEFENSIVE = 1010
DBCONFIG_TRUSTED_SCHEMA = 1017
LIMITS = {
    "LENGTH": 0, "SQL_LENGTH": 1, "COLUMN": 2, "EXPR_DEPTH": 3, "COMPOUND_SELECT": 4, "VDBE_OP": 5,
    "FUNCTION_ARG": 6, "ATTACHED": 7, "LIKE_PATTERN_LENGTH": 8, "VARIABLE_NUMBER": 9, "TRIGGER_DEPTH": 10,
}

LIBRARY_NAME = "sdbcsql.dll"
LIBRARY_FOLDER = os.path.join("native", "win-x64")

_CODE_NAMES = {
    0: "SQLITE_OK",
    1: "SQLITE_ERROR",
    2: "SQLITE_INTERNAL",
    3: "SQLITE_PERM",
    4: "SQLITE_ABORT",
    5: "SQLITE_BUSY",
    6: "SQLITE_LOCKED",
    7: "SQLITE_NOMEM",
    8: "SQLITE_READONLY",
    9: "SQLITE_INTERRUPT",
    10: "SQLITE_IOERR",
    11: "SQLITE_CORRUPT",
    12: "SQLITE_NOTFOUND",
    13: "SQLITE_FULL",
    14: "SQLITE_CANTOPEN",
    15: "SQLITE_PROTOCOL",
    16: "SQLITE_EMPTY",
    17: "SQLITE_SCHEMA",
    18: "SQLITE_TOOBIG",
    19: "SQLITE_CONSTRAINT",
    20: "SQLITE_MISMATCH",
    21: "SQLITE_MISUSE",
    22: "SQLITE_NOLFS",
    23: "SQLITE_AUTH",
    24: "SQLITE_FORMAT",
    25: "SQLITE_RANGE",
    26: "SQLITE_NOTADB",
    27: "SQLITE_NOTICE",
    28: "SQLITE_WARNING",
    100: "SQLITE_ROW",
    101: "SQLITE_DONE",
}
_EXTENDED_NAMES = """
ERROR_MISSING_COLLSEQ 1 1
ERROR_RETRY 1 2
ERROR_SNAPSHOT 1 3
ERROR_RESERVESIZE 1 4
ERROR_KEY 1 5
ERROR_UNABLE 1 6
IOERR_READ 10 1
IOERR_SHORT_READ 10 2
IOERR_WRITE 10 3
IOERR_FSYNC 10 4
IOERR_DIR_FSYNC 10 5
IOERR_TRUNCATE 10 6
IOERR_FSTAT 10 7
IOERR_UNLOCK 10 8
IOERR_RDLOCK 10 9
IOERR_DELETE 10 10
IOERR_BLOCKED 10 11
IOERR_NOMEM 10 12
IOERR_ACCESS 10 13
IOERR_CHECKRESERVEDLOCK 10 14
IOERR_LOCK 10 15
IOERR_CLOSE 10 16
IOERR_DIR_CLOSE 10 17
IOERR_SHMOPEN 10 18
IOERR_SHMSIZE 10 19
IOERR_SHMLOCK 10 20
IOERR_SHMMAP 10 21
IOERR_SEEK 10 22
IOERR_DELETE_NOENT 10 23
IOERR_MMAP 10 24
IOERR_GETTEMPPATH 10 25
IOERR_CONVPATH 10 26
IOERR_VNODE 10 27
IOERR_AUTH 10 28
IOERR_BEGIN_ATOMIC 10 29
IOERR_COMMIT_ATOMIC 10 30
IOERR_ROLLBACK_ATOMIC 10 31
IOERR_DATA 10 32
IOERR_CORRUPTFS 10 33
IOERR_IN_PAGE 10 34
IOERR_BADKEY 10 35
IOERR_CODEC 10 36
LOCKED_SHAREDCACHE 6 1
LOCKED_VTAB 6 2
BUSY_RECOVERY 5 1
BUSY_SNAPSHOT 5 2
BUSY_TIMEOUT 5 3
CANTOPEN_NOTEMPDIR 14 1
CANTOPEN_ISDIR 14 2
CANTOPEN_FULLPATH 14 3
CANTOPEN_CONVPATH 14 4
CANTOPEN_DIRTYWAL 14 5
CANTOPEN_SYMLINK 14 6
CORRUPT_VTAB 11 1
CORRUPT_SEQUENCE 11 2
CORRUPT_INDEX 11 3
READONLY_RECOVERY 8 1
READONLY_CANTLOCK 8 2
READONLY_ROLLBACK 8 3
READONLY_DBMOVED 8 4
READONLY_CANTINIT 8 5
READONLY_DIRECTORY 8 6
ABORT_ROLLBACK 4 2
CONSTRAINT_CHECK 19 1
CONSTRAINT_COMMITHOOK 19 2
CONSTRAINT_FOREIGNKEY 19 3
CONSTRAINT_FUNCTION 19 4
CONSTRAINT_NOTNULL 19 5
CONSTRAINT_PRIMARYKEY 19 6
CONSTRAINT_TRIGGER 19 7
CONSTRAINT_UNIQUE 19 8
CONSTRAINT_VTAB 19 9
CONSTRAINT_ROWID 19 10
CONSTRAINT_PINNED 19 11
CONSTRAINT_DATATYPE 19 12
NOTICE_RECOVER_WAL 27 1
NOTICE_RECOVER_ROLLBACK 27 2
NOTICE_RBU 27 3
WARNING_AUTOINDEX 28 1
AUTH_USER 23 1
OK_LOAD_PERMANENTLY 0 1
OK_SYMLINK 0 2
"""
for _line in _EXTENDED_NAMES.strip().splitlines():
    _name, _primary, _number = _line.split()
    _CODE_NAMES[int(_primary) | (int(_number) << 8)] = "SQLITE_" + _name
del _line, _name, _primary, _number


class Warning(Exception):
    pass


class Error(Exception):
    pass


class InterfaceError(Error):
    pass


class DatabaseError(Error):
    pass


class DataError(DatabaseError):
    pass


class OperationalError(DatabaseError):
    pass


class IntegrityError(DatabaseError):
    pass


class InternalError(DatabaseError):
    pass


class ProgrammingError(DatabaseError):
    pass


class NotSupportedError(DatabaseError):
    pass


class LibraryError(Exception):

    def __init__(self, path, reason):
        super().__init__("%s (%s)" % (reason, path) if path else reason)
        self.path = path
        self.reason = reason


_PRIMARY_CLASSES = {
    2: InternalError, 12: InternalError,
    1: OperationalError, 3: OperationalError, 4: OperationalError, 5: OperationalError,
    6: OperationalError, 8: OperationalError, 9: OperationalError, 10: OperationalError,
    13: OperationalError, 14: OperationalError, 15: OperationalError, 16: OperationalError,
    17: OperationalError,
    18: DataError,
    19: IntegrityError, 20: IntegrityError,
    21: InterfaceError, 25: InterfaceError,
}


_library_override = None
_api = None
_load_lock = threading.Lock()


def set_library_path(path):
    global _library_override
    if _api is not None:
        raise RuntimeError("the SQLite library is already loaded")
    _library_override = path


def default_library_path():
    machine = platform.machine().lower()
    if sys.platform != "win32" or struct.calcsize("P") != 8 or machine not in ("amd64", "x86_64"):
        raise LibraryError(None, "unsupported system (only 64-bit Windows is supported): %s, %s, %d-bit" % (
            sys.platform, platform.machine() or "?", struct.calcsize("P") * 8))
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), LIBRARY_FOLDER, LIBRARY_NAME)


class _Api:

    def __init__(self, dll):
        c_void_p, c_int, c_char_p = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
        c_int64, c_uint64, c_double = ctypes.c_int64, ctypes.c_uint64, ctypes.c_double
        pointer = ctypes.POINTER

        def declare(name, restype, *argtypes):
            function = getattr(dll, name)
            function.restype = restype
            function.argtypes = argtypes
            return function

        self.libversion = declare("sqlite3_libversion", c_char_p)
        self.libversion_number = declare("sqlite3_libversion_number", c_int)
        self.open_v2 = declare("sqlite3_open_v2", c_int, c_char_p, pointer(c_void_p), c_int, c_char_p)
        self.close_v2 = declare("sqlite3_close_v2", c_int, c_void_p)
        self.extended_result_codes = declare("sqlite3_extended_result_codes", c_int, c_void_p, c_int)
        self.busy_timeout = declare("sqlite3_busy_timeout", c_int, c_void_p, c_int)
        self.errmsg = declare("sqlite3_errmsg", c_char_p, c_void_p)
        self.extended_errcode = declare("sqlite3_extended_errcode", c_int, c_void_p)
        self.prepare_v2 = declare("sqlite3_prepare_v2", c_int, c_void_p, c_void_p, c_int,
                                  pointer(c_void_p), pointer(c_void_p))
        self.step = declare("sqlite3_step", c_int, c_void_p)
        self.reset = declare("sqlite3_reset", c_int, c_void_p)
        self.finalize = declare("sqlite3_finalize", c_int, c_void_p)
        self.column_count = declare("sqlite3_column_count", c_int, c_void_p)
        self.column_name = declare("sqlite3_column_name", c_char_p, c_void_p, c_int)
        self.column_type = declare("sqlite3_column_type", c_int, c_void_p, c_int)
        self.column_int64 = declare("sqlite3_column_int64", c_int64, c_void_p, c_int)
        self.column_double = declare("sqlite3_column_double", c_double, c_void_p, c_int)
        self.column_text = declare("sqlite3_column_text", c_void_p, c_void_p, c_int)
        self.column_blob = declare("sqlite3_column_blob", c_void_p, c_void_p, c_int)
        self.column_bytes = declare("sqlite3_column_bytes", c_int, c_void_p, c_int)
        self.bind_parameter_count = declare("sqlite3_bind_parameter_count", c_int, c_void_p)
        self.bind_parameter_name = declare("sqlite3_bind_parameter_name", c_char_p, c_void_p, c_int)
        self.bind_null = declare("sqlite3_bind_null", c_int, c_void_p, c_int)
        self.bind_int64 = declare("sqlite3_bind_int64", c_int, c_void_p, c_int, c_int64)
        self.bind_double = declare("sqlite3_bind_double", c_int, c_void_p, c_int, c_double)
        self.bind_text64 = declare("sqlite3_bind_text64", c_int, c_void_p, c_int, c_char_p, c_uint64,
                                   c_void_p, ctypes.c_ubyte)
        self.bind_blob64 = declare("sqlite3_bind_blob64", c_int, c_void_p, c_int, c_char_p, c_uint64, c_void_p)
        self.bind_zeroblob = declare("sqlite3_bind_zeroblob", c_int, c_void_p, c_int, c_int)
        self.changes = declare("sqlite3_changes", c_int, c_void_p)
        self.last_insert_rowid = declare("sqlite3_last_insert_rowid", c_int64, c_void_p)
        self.get_autocommit = declare("sqlite3_get_autocommit", c_int, c_void_p)
        self.interrupt = declare("sqlite3_interrupt", None, c_void_p)
        self.complete = declare("sqlite3_complete", c_int, c_char_p)
        self.authorizer_type = ctypes.CFUNCTYPE(c_int, c_void_p, c_int, c_char_p, c_char_p, c_char_p, c_char_p)
        self.set_authorizer = declare("sqlite3_set_authorizer", c_int, c_void_p, self.authorizer_type, c_void_p)
        self.db_config = declare("sqlite3_db_config", c_int, c_void_p, c_int, c_int, pointer(c_int))
        self.limit = declare("sqlite3_limit", c_int, c_void_p, c_int, c_int)
        self.function_type = ctypes.CFUNCTYPE(None, c_void_p, c_int, pointer(c_void_p))
        self.collation_type = ctypes.CFUNCTYPE(c_int, c_void_p, c_int, c_void_p, c_int, c_void_p)
        self.create_function_v2 = declare("sqlite3_create_function_v2", c_int, c_void_p, c_char_p, c_int, c_int,
                                          c_void_p, self.function_type, c_void_p, c_void_p, c_void_p)
        self.create_collation_v2 = declare("sqlite3_create_collation_v2", c_int, c_void_p, c_char_p, c_int,
                                           c_void_p, self.collation_type, c_void_p)
        self.value_type = declare("sqlite3_value_type", c_int, c_void_p)
        self.value_int64 = declare("sqlite3_value_int64", c_int64, c_void_p)
        self.value_double = declare("sqlite3_value_double", c_double, c_void_p)
        self.value_text = declare("sqlite3_value_text", c_void_p, c_void_p)
        self.value_blob = declare("sqlite3_value_blob", c_void_p, c_void_p)
        self.value_bytes = declare("sqlite3_value_bytes", c_int, c_void_p)
        self.result_null = declare("sqlite3_result_null", None, c_void_p)
        self.result_int64 = declare("sqlite3_result_int64", None, c_void_p, c_int64)
        self.result_double = declare("sqlite3_result_double", None, c_void_p, c_double)
        self.result_text64 = declare("sqlite3_result_text64", None, c_void_p, c_char_p, c_uint64, c_void_p,
                                     ctypes.c_ubyte)
        self.result_blob64 = declare("sqlite3_result_blob64", None, c_void_p, c_char_p, c_uint64, c_void_p)
        self.result_zeroblob = declare("sqlite3_result_zeroblob", None, c_void_p, c_int)
        self.result_error = declare("sqlite3_result_error", None, c_void_p, c_char_p, c_int)


def _load():
    global _api
    if _api is not None:
        return _api
    with _load_lock:
        if _api is not None:
            return _api
        path = _library_override or default_library_path()
        if not os.path.isfile(path):
            raise LibraryError(path, "file not found")
        try:
            dll = ctypes.CDLL(path)
        except OSError as exception:
            raise LibraryError(path, "cannot load the library: %s" % exception)
        try:
            _api = _Api(dll)
        except AttributeError as exception:
            raise LibraryError(path, "not a usable SQLite library: %s" % exception)
        return _api


def load():
    _load()


def _sqlite_version():
    return _load().libversion().decode("ascii")


def __getattr__(name):
    if name == "sqlite_version":
        return _sqlite_version()
    if name == "sqlite_version_info":
        return tuple(int(part) for part in _sqlite_version().split("."))
    raise AttributeError("module %r has no attribute %r" % (__name__, name))


def _make_error(api, db, code, message=None):
    extended = api.extended_errcode(db) if db else 0
    if extended == 0 or (extended & 0xFF) == SQLITE_OK:
        extended = code
    if message is None:
        raw = api.errmsg(db) if db else None
        message = raw.decode("utf-8", "replace") if raw else "unknown error"
    primary = extended & 0xFF
    if primary == _NOMEM:
        return MemoryError()
    exception = _PRIMARY_CLASSES.get(primary, DatabaseError)(message)
    exception.sqlite_errorcode = extended
    exception.sqlite_errorname = _CODE_NAMES.get(extended) or _CODE_NAMES.get(primary, "SQLITE_ERROR")
    return exception


def _skip_blank(raw, index=0):
    size = len(raw)
    while index < size:
        char = raw[index]
        if char in b" \t\r\n\f\v":
            index += 1
        elif raw.startswith(b"--", index):
            end = raw.find(b"\n", index)
            index = size if end == -1 else end + 1
        elif raw.startswith(b"/*", index):
            end = raw.find(b"*/", index + 2)
            index = size if end == -1 else end + 2
        else:
            break
    return index


def _is_dml(raw):
    index = 0
    while index < len(raw) and raw[index] in b" \r\n\t":
        index += 1
    start = raw[index:index + 7].lower()
    return start.startswith((b"insert", b"update", b"delete", b"replace"))


class _Statement:

    def __init__(self, api, handle, is_dml):
        self.api = api
        self.handle = handle
        self.is_dml = is_dml
        self.column_count = api.column_count(handle) if handle else 0

    def finalize(self):
        if self.handle:
            self.api.finalize(self.handle)
            self.handle = None


class Cursor:

    def __init__(self, connection):
        self.connection = connection
        self.arraysize = 1
        self.description = None
        self.rowcount = -1
        self.lastrowid = None
        self._statement = None
        self._has_row = False
        self._dml = False
        self._closed = False
        connection._cursors.add(self)

    def _check(self):
        if self._closed:
            raise ProgrammingError("Cannot operate on a closed cursor.")
        self.connection._check()

    def _finish(self):
        statement, self._statement = self._statement, None
        self._has_row = False
        if statement is not None:
            statement.finalize()

    def _fail(self, code):
        error = _make_error(self.connection._api, self.connection._db, code)
        self._finish()
        return error

    def execute(self, sql, parameters=()):
        self._check()
        if not isinstance(sql, str):
            raise TypeError("execute() argument 1 must be str, not %s" % type(sql).__name__)
        self._finish()
        self.description = None
        statement = self.connection._prepare(sql)
        self._dml = statement.is_dml
        self.rowcount = 0 if statement.is_dml else -1
        if statement.handle is None:
            self.rowcount = -1
            return self
        self._statement = statement
        try:
            self._bind(statement, parameters)
        except BaseException:
            self._finish()
            raise
        api = self.connection._api
        columns = statement.column_count
        if columns > 0:
            self.description = tuple(
                (api.column_name(statement.handle, index).decode("utf-8", "replace"),
                 None, None, None, None, None, None) for index in range(columns))
        code = api.step(statement.handle)
        if code == _ROW:
            self._has_row = True
        elif code == _DONE:
            self._done(statement)
        else:
            raise self._fail(code)
        return self

    def _done(self, statement):
        api = self.connection._api
        if statement.is_dml:
            self.rowcount += api.changes(self.connection._db)
            self.lastrowid = api.last_insert_rowid(self.connection._db)
        self._finish()

    def _bind(self, statement, parameters):
        api = self.connection._api
        handle = statement.handle
        needed = api.bind_parameter_count(handle)
        if isinstance(parameters, dict):
            for index in range(1, needed + 1):
                raw = api.bind_parameter_name(handle, index)
                if raw is None:
                    raise ProgrammingError(
                        "Binding %d has no name, but you supplied a dictionary (which has only names)." % index)
                name = raw[1:].decode("utf-8", "replace")
                try:
                    value = parameters[name]
                except KeyError:
                    raise ProgrammingError("You did not supply a value for binding parameter :%s." % name)
                self._bind_value(handle, index, value)
            return
        if parameters is None:
            parameters = ()
        try:
            supplied = len(parameters)
        except TypeError:
            raise ProgrammingError("parameters are of unsupported type")
        if supplied != needed:
            raise ProgrammingError(
                "Incorrect number of bindings supplied. The current statement uses %d, and there are %d supplied."
                % (needed, supplied))
        for index, value in enumerate(parameters, 1):
            self._bind_value(handle, index, value)

    def _bind_value(self, handle, index, value):
        api = self.connection._api
        transient = ctypes.c_void_p(-1)
        if value is None:
            code = api.bind_null(handle, index)
        elif isinstance(value, int):
            if not (_INT64_MIN <= value <= _INT64_MAX):
                raise OverflowError("Python int too large to convert to SQLite INTEGER")
            code = api.bind_int64(handle, index, int(value))
        elif isinstance(value, float):
            code = api.bind_double(handle, index, float(value))
        elif isinstance(value, str):
            raw = value.encode("utf-8")
            code = api.bind_text64(handle, index, raw, len(raw), transient, 1)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            raw = bytes(value)
            if raw:
                code = api.bind_blob64(handle, index, raw, len(raw), transient)
            else:
                code = api.bind_zeroblob(handle, index, 0)
        else:
            raise ProgrammingError("Error binding parameter %d: type '%s' is not supported"
                                   % (index, type(value).__name__))
        if code != SQLITE_OK:
            raise _make_error(api, self.connection._db, code)

    def _row(self, statement):
        api = self.connection._api
        handle = statement.handle
        row = []
        for index in range(statement.column_count):
            kind = api.column_type(handle, index)
            if kind == _INTEGER:
                row.append(api.column_int64(handle, index))
            elif kind == _FLOAT:
                row.append(api.column_double(handle, index))
            elif kind == _TEXT:
                pointer = api.column_text(handle, index)
                size = api.column_bytes(handle, index)
                raw = ctypes.string_at(pointer, size) if pointer and size else b""
                try:
                    row.append(raw.decode("utf-8"))
                except UnicodeDecodeError:
                    name = api.column_name(handle, index).decode("utf-8", "replace")
                    raise OperationalError("Could not decode to UTF-8 column '%s' with text '%s'"
                                           % (name, raw.decode("utf-8", "replace")))
            elif kind == _BLOB:
                pointer = api.column_blob(handle, index)
                size = api.column_bytes(handle, index)
                row.append(ctypes.string_at(pointer, size) if pointer and size else b"")
            else:
                row.append(None)
        return tuple(row)

    def executemany(self, sql, seq_of_parameters):
        self._check()
        total = 0
        is_dml = False
        for parameters in seq_of_parameters:
            self.execute(sql, parameters)
            is_dml = self._dml
            total += max(self.rowcount, 0)
        if is_dml:
            self.rowcount = total
        return self

    def fetchone(self):
        self._check()
        statement = self._statement
        if statement is None or not self._has_row:
            return None
        try:
            row = self._row(statement)
        except BaseException:
            self._finish()
            raise
        code = self.connection._api.step(statement.handle)
        if code == _DONE:
            self._done(statement)
        elif code != _ROW:
            raise self._fail(code)
        return row

    def fetchmany(self, size=None):
        if size is None:
            size = self.arraysize
        rows = []
        while len(rows) < size:
            row = self.fetchone()
            if row is None:
                break
            rows.append(row)
        return rows

    def fetchall(self):
        rows = []
        while True:
            row = self.fetchone()
            if row is None:
                return rows
            rows.append(row)

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._finish()
        self.connection._cursors.discard(self)

    def __del__(self):
        try:
            self._finish()
        except Exception:
            pass


class Connection:

    def __init__(self, database, timeout=5.0, uri=False):
        self._api = None
        self._db = None
        self._closed = True
        self._cursors = weakref.WeakSet()
        self._authorizer = None
        self._callbacks = []
        api = _load()
        self._api = api
        path = os.fspath(database)
        if isinstance(path, bytes):
            raw = path
        else:
            raw = path.encode("utf-8")
        if b"\0" in raw:
            raise ValueError("embedded null character")
        handle = ctypes.c_void_p()
        flags = _OPEN_READWRITE | _OPEN_CREATE | (_OPEN_URI if uri else 0)
        code = api.open_v2(raw, ctypes.byref(handle), flags, None)
        if code != SQLITE_OK:
            error = _make_error(api, handle.value, code)
            if handle.value:
                api.close_v2(handle)
            raise error
        self._db = handle.value
        self._closed = False
        api.extended_result_codes(self._db, 1)
        api.busy_timeout(self._db, int(float(timeout) * 1000))

    def _check(self):
        if self._closed:
            raise ProgrammingError("Cannot operate on a closed database.")

    def _prepare(self, sql):
        self._check()
        if "\0" in sql:
            raise ProgrammingError("the query contains a null character")
        raw = sql.encode("utf-8")
        buffer = ctypes.create_string_buffer(raw)
        handle = ctypes.c_void_p()
        tail = ctypes.c_void_p()
        code = self._api.prepare_v2(self._db, buffer, -1, ctypes.byref(handle), ctypes.byref(tail))
        if code != SQLITE_OK:
            raise _make_error(self._api, self._db, code)
        offset = (tail.value or ctypes.addressof(buffer)) - ctypes.addressof(buffer)
        if _skip_blank(raw, offset) < len(raw):
            if handle.value:
                self._api.finalize(handle)
            raise ProgrammingError("You can only execute one statement at a time.")
        return _Statement(self._api, handle.value, _is_dml(raw))

    def cursor(self):
        self._check()
        return Cursor(self)

    def execute(self, sql, parameters=()):
        return self.cursor().execute(sql, parameters)

    def executescript(self, script):
        self._check()
        api = self._api
        raw = script.encode("utf-8")
        if b"\0" in raw:
            raise ProgrammingError("the query contains a null character")
        buffer = ctypes.create_string_buffer(raw)
        base = ctypes.addressof(buffer)
        offset = 0
        while True:
            offset = _skip_blank(raw, offset)
            if offset >= len(raw):
                break
            handle = ctypes.c_void_p()
            tail = ctypes.c_void_p()
            code = api.prepare_v2(self._db, base + offset, -1, ctypes.byref(handle), ctypes.byref(tail))
            if code != SQLITE_OK:
                raise _make_error(api, self._db, code)
            following = (tail.value or base) - base
            if handle.value:
                code = api.step(handle)
                while code == _ROW:
                    code = api.step(handle)
                if code != _DONE:
                    error = _make_error(api, self._db, code)
                    api.finalize(handle)
                    raise error
                api.finalize(handle)
            if following <= offset:
                break
            offset = following
        return self.cursor()

    @property
    def in_transaction(self):
        self._check()
        return not self._api.get_autocommit(self._db)

    def commit(self):
        if self.in_transaction:
            self.execute("COMMIT")

    def rollback(self):
        if self.in_transaction:
            self.execute("ROLLBACK")

    def interrupt(self):
        self._check()
        self._api.interrupt(self._db)

    def set_authorizer(self, authorizer_callback):
        self._check()
        api = self._api
        if authorizer_callback is None:
            code = api.set_authorizer(self._db, api.authorizer_type(), None)
            self._authorizer = None
        else:
            def trampoline(_user, action, arg1, arg2, arg3, arg4):
                try:
                    result = authorizer_callback(
                        action, _text(arg1), _text(arg2), _text(arg3), _text(arg4))
                    return result if result in (SQLITE_OK, SQLITE_DENY, SQLITE_IGNORE) else SQLITE_DENY
                except Exception:
                    return SQLITE_DENY
            callback = api.authorizer_type(trampoline)
            code = api.set_authorizer(self._db, callback, None)
            self._authorizer = callback
        if code != SQLITE_OK:
            raise _make_error(api, self._db, code)

    def config(self, option, value):
        self._check()
        result = ctypes.c_int(-1)
        code = self._api.db_config(self._db, option, int(value), ctypes.byref(result))
        return result.value if code == SQLITE_OK else None

    def limit(self, name, value=-1):
        self._check()
        return self._api.limit(self._db, LIMITS[name], int(value))

    def last_insert_rowid(self):
        self._check()
        return self._api.last_insert_rowid(self._db)

    def create_function(self, name, narg, function, deterministic=True):
        self._check()
        api = self._api
        callback = api.function_type(_function_trampoline(api, function))
        flags = _UTF8 | (_DETERMINISTIC | _INNOCUOUS if deterministic else 0)
        code = api.create_function_v2(self._db, name.encode("utf-8"), int(narg), flags, None, callback,
                                      None, None, None)
        if code != SQLITE_OK:
            raise _make_error(api, self._db, code)
        self._callbacks.append(callback)

    def create_collation(self, name, compare):
        self._check()
        api = self._api

        def trampoline(_user, size_a, raw_a, size_b, raw_b):
            try:
                a = ctypes.string_at(raw_a, size_a).decode("utf-8", "replace") if size_a else ""
                b = ctypes.string_at(raw_b, size_b).decode("utf-8", "replace") if size_b else ""
                result = compare(a, b)
                return -1 if result < 0 else (1 if result > 0 else 0)
            except Exception:
                return 0
        callback = api.collation_type(trampoline)
        code = api.create_collation_v2(self._db, name.encode("utf-8"), _UTF8, None, callback, None)
        if code != SQLITE_OK:
            raise _make_error(api, self._db, code)
        self._callbacks.append(callback)

    def close(self):
        if self._closed:
            return
        for cursor in list(self._cursors):
            cursor._finish()
        self._closed = True
        db, self._db = self._db, None
        if db:
            self._api.set_authorizer(db, self._api.authorizer_type(), None)
            self._api.close_v2(db)
        self._authorizer = None
        self._callbacks = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


def _function_trampoline(api, function):
    transient = ctypes.c_void_p(-1)

    def read(value):
        kind = api.value_type(value)
        if kind == _INTEGER:
            return api.value_int64(value)
        if kind == _FLOAT:
            return api.value_double(value)
        if kind == _TEXT:
            pointer = api.value_text(value)
            size = api.value_bytes(value)
            raw = ctypes.string_at(pointer, size) if pointer and size else b""
            return raw.decode("utf-8", "replace")
        if kind == _BLOB:
            pointer = api.value_blob(value)
            size = api.value_bytes(value)
            return ctypes.string_at(pointer, size) if pointer and size else b""
        return None

    def trampoline(context, count, arguments):
        try:
            result = function(*[read(arguments[index]) for index in range(count)])
            if result is None:
                api.result_null(context)
            elif isinstance(result, (bool, int)):
                if not (_INT64_MIN <= int(result) <= _INT64_MAX):
                    raise OverflowError("integer overflow")
                api.result_int64(context, int(result))
            elif isinstance(result, float):
                api.result_double(context, result)
            elif isinstance(result, str):
                raw = result.encode("utf-8")
                api.result_text64(context, raw, len(raw), transient, 1)
            elif isinstance(result, (bytes, bytearray, memoryview)):
                raw = bytes(result)
                if raw:
                    api.result_blob64(context, raw, len(raw), transient)
                else:
                    api.result_zeroblob(context, 0)
            else:
                raise TypeError("unsupported result type: %s" % type(result).__name__)
        except Exception as exception:
            message = str(exception) or type(exception).__name__
            raw = message.encode("utf-8")
            api.result_error(context, raw, len(raw))
    return trampoline


def _text(raw):
    return None if raw is None else raw.decode("utf-8", "replace")


def connect(database, timeout=5.0, detect_types=0, isolation_level=None, check_same_thread=True,
            factory=None, cached_statements=128, uri=False, *, autocommit=True):
    if isolation_level is not None or autocommit is not True and autocommit is not None:
        raise NotSupportedError("this module has no implicit transactions: use isolation_level=None")
    return Connection(database, timeout, uri)


def complete_statement(sql):
    api = _load()
    if "\0" in sql:
        raise ValueError("embedded null character")
    return bool(api.complete(sql.encode("utf-8")))
