# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unohelper

from com.sun.star.sdbc import XCloseable
from com.sun.star.sdbc import XGeneratedResultSet
from com.sun.star.sdbc import XMultipleResults
from com.sun.star.sdbc import XParameters
from com.sun.star.sdbc import XPreparedBatchExecution
from com.sun.star.sdbc import XPreparedStatement
from com.sun.star.sdbc import XResultSetMetaDataSupplier
from com.sun.star.sdbc import XWarningsSupplier
from com.sun.star.util import XCancellable

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import binding
from sdbc_pysqlite import dialect
from sdbc_pysqlite import errors
from sdbc_pysqlite import results
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite import uno_errors
from sdbc_pysqlite.common import ComponentMixin
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import PropertySetMixin
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbc.commandbase import CommandBase
from sdbc_pysqlite.sdbc.resultsetmetadata import ResultSetMetaData


def _read_stream(stream, length):
    data = b""
    if length and length > 0:
        count, chunk = stream.readBytes((), length)
        return bytes(chunk[:count]) if count else b""
    while True:
        count, chunk = stream.readBytes((), 65536)
        if not count:
            return data
        data += bytes(chunk[:count])


@traced
class PreparedStatement(unohelper.Base, ComponentMixin, PropertySetMixin, ServiceInfoMixin,
                        XPreparedStatement, XParameters, XPreparedBatchExecution,
                        XResultSetMetaDataSupplier, XCloseable, XCancellable,
                        XMultipleResults, XWarningsSupplier, XGeneratedResultSet, ErrorMixin, CommandBase):

    _pretranslated = True
    _implementation_name = IDENTIFIER + ".PreparedStatement"
    _service_names = ("com.sun.star.sdbc.PreparedStatement", )
    _default_properties = {
        "QueryTimeOut": 0,
        "MaxFieldSize": 0,
        "MaxRows": 0,
        "CursorName": "",
        "ResultSetConcurrency": 1007,
        "ResultSetType": 1004,
        "FetchDirection": 1000,
        "FetchSize": 0,
        "EscapeProcessing": True,
    }

    def __init__(self, connection, sql):
        self._connection = connection
        self._sql = sql
        self._init_properties()
        self._closed = False
        self._warnings = []
        self._results = []
        self._queue = []
        self._position = -1
        self._values = {}
        self._batch = []
        self._generated = None
        try:
            self._pieces = binding.analyze(connection._db, sql)
        except DriverError as error:
            raise self._error(error, "prepareStatement")
        except Exception:
            self._pieces = [binding.Piece(text, []) for text in sqltext.split_statements(sql)]
        self._slots = [slot for piece in self._pieces for slot in piece.slots]

    def _set(self, index, value, method):
        self._check_open(method)
        if not 1 <= index <= len(self._slots):
            raise self._error(DriverError(errors.PARAMETER_OUT_OF_RANGE, numero=index, totale=len(self._slots)),
                              method)
        self._values[index] = value

    def _set_object(self, index, x, method):
        try:
            value = binding.classify_object(x, index)
        except DriverError as error:
            raise self._error(error, method)
        self._set(index, value, method)

    def _missing(self, values, method):
        for number in range(1, len(self._slots) + 1):
            if number not in values:
                raise self._error(DriverError(errors.PARAMETER_NOT_SET, numero=number), method)

    def _converted(self, values, method):
        options = self._connection._engine.options
        converted = []
        for number, ctype in enumerate(self._slots, 1):
            try:
                converted.append(binding.convert(values[number], ctype, number, options))
            except DriverError as error:
                raise self._error(error, method)
        return converted

    def _warn_unmatched(self, method):
        for number, ctype in enumerate(self._slots, 1):
            if ctype is None:
                self._warn(DriverError(errors.PARAMETER_NO_COLUMN, numero=number), method)

    def _run_with(self, values, method):
        self._missing(values, method)
        converted = self._converted(values, method)
        outcomes = []
        position = 0
        self._generated = None
        for piece in self._pieces:
            for warning in piece.warnings:
                self._warn(warning, method)
            params = tuple(converted[position:position + len(piece.slots)])
            position += len(piece.slots)
            outcome = self._run_one(piece.text, params, method)
            outcomes.append(outcome)
            self._generated = (self._connection._engine.generated_key(piece.text)
                               if outcome.writes and outcome.count > 0 else None)
        return outcomes

    def executeQuery(self):
        self._start("executeQuery")
        self._warn_unmatched("executeQuery")
        return self._query_outcome(self._run_with(self._values, "executeQuery"), "executeQuery")

    def executeUpdate(self):
        self._start("executeUpdate")
        self._warn_unmatched("executeUpdate")
        return self._update_outcome(self._run_with(self._values, "executeUpdate"), "executeUpdate")

    def execute(self):
        self._start("execute")
        self._warn_unmatched("execute")
        return self._execute_outcome(self._run_with(self._values, "execute"))

    def getConnection(self):
        return self._connection

    def setNull(self, parameterIndex, sqlType):
        self._set(parameterIndex, ("null", None), "setNull")

    def setObjectNull(self, parameterIndex, sqlType, typeName):
        self._set(parameterIndex, ("null", None), "setObjectNull")

    def setBoolean(self, parameterIndex, x):
        self._set(parameterIndex, ("bool", bool(x)), "setBoolean")

    def setByte(self, parameterIndex, x):
        self._set(parameterIndex, ("int", int(x)), "setByte")

    def setShort(self, parameterIndex, x):
        self._set(parameterIndex, ("int", int(x)), "setShort")

    def setInt(self, parameterIndex, x):
        self._set(parameterIndex, ("int", int(x)), "setInt")

    def setLong(self, parameterIndex, x):
        self._set(parameterIndex, ("int", int(x)), "setLong")

    def setFloat(self, parameterIndex, x):
        self._set(parameterIndex, ("real", float(x)), "setFloat")

    def setDouble(self, parameterIndex, x):
        self._set(parameterIndex, ("real", float(x)), "setDouble")

    def setString(self, parameterIndex, x):
        self._set(parameterIndex, ("text", x), "setString")

    def setBytes(self, parameterIndex, x):
        self._set_object(parameterIndex, x, "setBytes")

    def setDate(self, parameterIndex, x):
        self._set(parameterIndex, ("date", x), "setDate")

    def setTime(self, parameterIndex, x):
        self._set(parameterIndex, ("time", x), "setTime")

    def setTimestamp(self, parameterIndex, x):
        self._set(parameterIndex, ("timestamp", x), "setTimestamp")

    def setBinaryStream(self, parameterIndex, x, length):
        self._set(parameterIndex, ("blob", _read_stream(x, length)), "setBinaryStream")

    def setCharacterStream(self, parameterIndex, x, length):
        text = _read_stream(x, length).decode("utf-8", "replace")
        self._set(parameterIndex, ("text", text), "setCharacterStream")

    def setObject(self, parameterIndex, x):
        self._set_object(parameterIndex, x, "setObject")

    def setObjectWithInfo(self, parameterIndex, x, targetSqlType, scale):
        self._set_object(parameterIndex, x, "setObjectWithInfo")

    def setRef(self, parameterIndex, x):
        self._set_object(parameterIndex, None if x is None else object(), "setRef")

    def setBlob(self, parameterIndex, x):
        self._set_object(parameterIndex, None if x is None else object(), "setBlob")

    def setClob(self, parameterIndex, x):
        self._set_object(parameterIndex, None if x is None else object(), "setClob")

    def setArray(self, parameterIndex, x):
        self._set_object(parameterIndex, None if x is None else object(), "setArray")

    def clearParameters(self):
        self._check_open("clearParameters")
        self._values = {}

    def addBatch(self):
        self._check_open("addBatch")
        self._missing(self._values, "addBatch")
        self._batch.append(dict(self._values))

    def clearBatch(self):
        self._check_open("clearBatch")
        self._batch = []

    def executeBatch(self):
        self._start("executeBatch")
        batch, self._batch = self._batch, []
        engine = self._connection._engine
        opened = engine.begin_atomic()
        counts = []
        success = False
        try:
            for row, values in enumerate(batch, 1):
                try:
                    total = 0
                    for outcome in self._run_with(values, "executeBatch"):
                        if outcome.result is not None:
                            outcome.result.close()
                            if not outcome.writes:
                                raise self._error(
                                    DriverError(errors.BATCH_RETURNED_ROWS, comando=self._sql[:80]), "executeBatch")
                        total += outcome.count
                    counts.append(total)
                except Exception as exception:
                    if getattr(exception, "ErrorCode", None) == errors.BATCH_RETURNED_ROWS:
                        raise
                    raise self._error(DriverError(
                        errors.BATCH_ROW_FAILED, riga=row, dettaglio=getattr(exception, "Message", str(exception))),
                        "executeBatch")
            success = True
        finally:
            engine.end_atomic(opened, success)
        return tuple(counts)

    def getGeneratedValues(self):
        self._check_open("getGeneratedValues")
        if self._generated is None:
            return self._make_result(results.memory_result([], []))
        name, number = self._generated
        return self._make_result(results.memory_result([(name, ts.BIGINT)], [(number,)]))

    def getMetaData(self):
        self._check_open("getMetaData")
        for piece in self._pieces:
            try:
                columns = self._connection._engine.columns_of(dialect.translate(piece.text))
            except DriverError as error:
                raise self._error(error, "getMetaData")
            if columns is not None:
                return ResultSetMetaData(columns, self)
        return ResultSetMetaData((), self)

    def close(self):
        if self._closed:
            return
        self._close_all()
        self._values = {}
        self._batch = []

    def cancel(self):
        if not self._closed:
            self._connection._engine.interrupt()

    def getResultSet(self):
        return self._current_result("getResultSet")

    def getUpdateCount(self):
        return self._current_count("getUpdateCount")

    def getMoreResults(self):
        return self._advance("getMoreResults")

    def getWarnings(self):
        if not self._warnings:
            return None
        return uno_errors.to_sql_warning_chain(self._warnings, self, self._connection._language)

    def clearWarnings(self):
        self._warnings = []
