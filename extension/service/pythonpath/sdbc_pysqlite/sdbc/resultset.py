# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import uno
import unohelper

from com.sun.star.sdbc import XCloseable
from com.sun.star.sdbc import XColumnLocate
from com.sun.star.sdbc import XResultSet
from com.sun.star.sdbc import XResultSetMetaDataSupplier
from com.sun.star.sdbc import XResultSetUpdate
from com.sun.star.sdbc import XRow
from com.sun.star.sdbc import XRowUpdate
from com.sun.star.sdbc import XWarningsSupplier
from com.sun.star.sdbcx import XDeleteRows
from com.sun.star.sdbcx import XRowLocate
from com.sun.star.util import Date
from com.sun.star.util import DateTime
from com.sun.star.util import Time
from com.sun.star.util import XCancellable

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import errors
from sdbc_pysqlite import results
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite import values
from sdbc_pysqlite.common import ComponentMixin
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import PropertySetMixin
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.engine import driver_error
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbc.resultsetmetadata import ResultSetMetaData


def _truncate(nanos, scale):
    scale = max(0, min(9, scale))
    unit = 10 ** (9 - scale)
    return nanos // unit * unit


@traced
class ResultSet(unohelper.Base, ComponentMixin, PropertySetMixin, ServiceInfoMixin, XResultSet, XRow,
                XResultSetUpdate, XRowUpdate, XRowLocate, XDeleteRows, XColumnLocate,
                XResultSetMetaDataSupplier, XCloseable, XCancellable, XWarningsSupplier, ErrorMixin):

    _implementation_name = IDENTIFIER + ".ResultSet"
    _service_names = ("com.sun.star.sdbc.ResultSet", )
    _default_properties = {
        "CursorName": "",
        "ResultSetConcurrency": 1007,
        "ResultSetType": 1004,
        "FetchDirection": 1000,
        "FetchSize": 0,
    }

    def __init__(self, statement=None, data=None, connection=None):
        self._statement = statement
        self._connection = connection
        self._data = data if data is not None else results.memory_result([], [])
        self._was_null = False
        self._init_properties()

    def _open(self, method):
        if self._data.closed:
            raise self._error(DriverError(errors.RESULT_CLOSED), method)
        return self._data

    def _move(self, method, action):
        data = self._open(method)
        try:
            return action(data)
        except DriverError as error:
            raise self._error(error, method)
        except sqlite.Error as exception:
            raise self._error(driver_error(exception), method)

    def _read_only(self, method):
        raise self._error(DriverError(errors.RESULT_READ_ONLY), method)

    def _cell(self, index, method):
        data = self._open(method)
        row = self._move(method, lambda d: d.row())
        if row is None:
            raise self._error(DriverError(errors.NO_CURRENT_ROW), method)
        if not 1 <= index <= len(data.columns):
            raise self._error(DriverError(errors.COLUMN_OUT_OF_RANGE, colonna=index,
                                          totale=len(data.columns)), method)
        value = row[index - 1]
        self._was_null = value is None
        return value, data.columns[index - 1]

    def _convert(self, index, method, function, empty):
        value, column = self._cell(index, method)
        if value is None:
            return empty
        try:
            return function(value, column, values.Origin(column.table, column.label))
        except DriverError as error:
            raise self._error(error, method)

    def _options(self):
        owner = self._owner_connection()
        return owner._engine.options if owner is not None else None

    def next(self):
        return self._move("next", lambda d: d.next())

    def isBeforeFirst(self):
        return self._move("isBeforeFirst", lambda d: d.is_before_first())

    def isAfterLast(self):
        return self._move("isAfterLast", lambda d: d.is_after_last())

    def isFirst(self):
        return self._move("isFirst", lambda d: d.is_first())

    def isLast(self):
        return self._move("isLast", lambda d: d.is_last())

    def beforeFirst(self):
        self._open("beforeFirst").before_first()

    def afterLast(self):
        self._open("afterLast").after_last()

    def first(self):
        return self._move("first", lambda d: d.first())

    def last(self):
        return self._move("last", lambda d: d.last())

    def getRow(self):
        return self._move("getRow", lambda d: d.get_row())

    def absolute(self, row):
        return self._move("absolute", lambda d: d.absolute(row))

    def relative(self, rows):
        return self._move("relative", lambda d: d.relative(rows))

    def previous(self):
        return self._move("previous", lambda d: d.previous())

    def refreshRow(self):
        self._open("refreshRow")

    def rowUpdated(self):
        self._open("rowUpdated")
        return False

    def rowInserted(self):
        self._open("rowInserted")
        return False

    def rowDeleted(self):
        self._open("rowDeleted")
        return False

    def getStatement(self):
        return self._statement

    def wasNull(self):
        return self._was_null

    def getString(self, columnIndex):
        options = self._options()
        return self._convert(columnIndex, "getString",
                             lambda v, c, o: values.to_text(v, c.ctype, o, options), "")

    def getBoolean(self, columnIndex):
        return self._convert(columnIndex, "getBoolean",
                             lambda v, c, o: values.to_boolean(v, c.ctype, o), False)

    def getByte(self, columnIndex):
        return self._convert(columnIndex, "getByte",
                             lambda v, c, o: values.to_integer(v, c.ctype, o, "Byte"), 0)

    def getShort(self, columnIndex):
        return self._convert(columnIndex, "getShort",
                             lambda v, c, o: values.to_integer(v, c.ctype, o, "Short"), 0)

    def getInt(self, columnIndex):
        return self._convert(columnIndex, "getInt",
                             lambda v, c, o: values.to_integer(v, c.ctype, o, "Int"), 0)

    def getLong(self, columnIndex):
        return self._convert(columnIndex, "getLong",
                             lambda v, c, o: values.to_integer(v, c.ctype, o, "Long"), 0)

    def getFloat(self, columnIndex):
        return self._convert(columnIndex, "getFloat",
                             lambda v, c, o: values.to_double(v, c.ctype, o, single=True), 0.0)

    def getDouble(self, columnIndex):
        return self._convert(columnIndex, "getDouble",
                             lambda v, c, o: values.to_double(v, c.ctype, o), 0.0)

    def getBytes(self, columnIndex):
        return self._convert(columnIndex, "getBytes",
                             lambda v, c, o: uno.ByteSequence(values.to_bytes(v, c.ctype, o)),
                             uno.ByteSequence(b""))

    def getDate(self, columnIndex):
        options = self._options()

        def build(value, column, origin):
            year, month, day = values.to_date(value, column.ctype, origin, options)
            result = Date()
            result.Day, result.Month, result.Year = day, month, year
            return result
        return self._convert(columnIndex, "getDate", build, Date())

    def getTime(self, columnIndex):
        options = self._options()

        def build(value, column, origin):
            hour, minute, second, nanos = values.to_time(value, column.ctype, origin, options)
            result = Time()
            result.Hours, result.Minutes, result.Seconds = hour, minute, second
            result.NanoSeconds = _truncate(nanos, column.ctype.scale)
            result.IsUTC = False
            return result
        return self._convert(columnIndex, "getTime", build, Time())

    def getTimestamp(self, columnIndex):
        options = self._options()

        def build(value, column, origin):
            year, month, day, hour, minute, second, nanos = values.to_timestamp(
                value, column.ctype, origin, options)
            result = DateTime()
            result.Year, result.Month, result.Day = year, month, day
            result.Hours, result.Minutes, result.Seconds = hour, minute, second
            result.NanoSeconds = _truncate(nanos, column.ctype.scale)
            result.IsUTC = False
            return result
        return self._convert(columnIndex, "getTimestamp", build, DateTime())

    def getBinaryStream(self, columnIndex):
        self._cell(columnIndex, "getBinaryStream")
        return None

    def getCharacterStream(self, columnIndex):
        self._cell(columnIndex, "getCharacterStream")
        return None

    def getObject(self, columnIndex, typeMap):
        value, column = self._cell(columnIndex, "getObject")
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray, memoryview)):
            return uno.ByteSequence(bytes(value))
        if column.ctype.kind in (ts.K_DECIMAL, ts.K_DATE, ts.K_TIME, ts.K_TIMESTAMP, ts.K_BOOL):
            return self.getString(columnIndex)
        return value

    def getRef(self, columnIndex):
        self._cell(columnIndex, "getRef")
        return None

    def getBlob(self, columnIndex):
        self._cell(columnIndex, "getBlob")
        return None

    def getClob(self, columnIndex):
        self._cell(columnIndex, "getClob")
        return None

    def getArray(self, columnIndex):
        self._cell(columnIndex, "getArray")
        return None

    def insertRow(self):
        self._read_only("insertRow")

    def updateRow(self):
        self._read_only("updateRow")

    def deleteRow(self):
        self._read_only("deleteRow")

    def cancelRowUpdates(self):
        self._read_only("cancelRowUpdates")

    def moveToInsertRow(self):
        self._read_only("moveToInsertRow")

    def moveToCurrentRow(self):
        self._read_only("moveToCurrentRow")

    def updateNull(self, columnIndex):
        self._read_only("updateNull")

    def updateBoolean(self, columnIndex, x):
        self._read_only("updateBoolean")

    def updateByte(self, columnIndex, x):
        self._read_only("updateByte")

    def updateShort(self, columnIndex, x):
        self._read_only("updateShort")

    def updateInt(self, columnIndex, x):
        self._read_only("updateInt")

    def updateLong(self, columnIndex, x):
        self._read_only("updateLong")

    def updateFloat(self, columnIndex, x):
        self._read_only("updateFloat")

    def updateDouble(self, columnIndex, x):
        self._read_only("updateDouble")

    def updateString(self, columnIndex, x):
        self._read_only("updateString")

    def updateBytes(self, columnIndex, x):
        self._read_only("updateBytes")

    def updateDate(self, columnIndex, x):
        self._read_only("updateDate")

    def updateTime(self, columnIndex, x):
        self._read_only("updateTime")

    def updateTimestamp(self, columnIndex, x):
        self._read_only("updateTimestamp")

    def updateBinaryStream(self, columnIndex, x, length):
        self._read_only("updateBinaryStream")

    def updateCharacterStream(self, columnIndex, x, length):
        self._read_only("updateCharacterStream")

    def updateObject(self, columnIndex, x):
        self._read_only("updateObject")

    def updateNumericObject(self, columnIndex, x, scale):
        self._read_only("updateNumericObject")

    def getBookmark(self):
        data = self._open("getBookmark")
        if self._move("getBookmark", lambda d: d.row()) is None:
            raise self._error(DriverError(errors.NO_CURRENT_ROW), "getBookmark")
        return data.pos

    def moveToBookmark(self, bookmark):
        return self._move("moveToBookmark", lambda d: d.absolute(int(bookmark)))

    def moveRelativeToBookmark(self, bookmark, rows):
        return self._move("moveRelativeToBookmark", lambda d: d.absolute(int(bookmark) + rows))

    def compareBookmarks(self, first, second):
        return (int(first) > int(second)) - (int(first) < int(second))

    def hasOrderedBookmarks(self):
        return True

    def hashBookmark(self, bookmark):
        return int(bookmark)

    def deleteRows(self, rows):
        self._read_only("deleteRows")

    def findColumn(self, columnName):
        data = self._open("findColumn")
        wanted = str(columnName).lower()
        for index, column in enumerate(data.columns, 1):
            if column.label.lower() == wanted:
                return index
        raise self._error(DriverError(errors.COLUMN_OUT_OF_RANGE, colonna=columnName,
                                      totale=len(data.columns)), "findColumn")

    def getMetaData(self):
        return ResultSetMetaData(self._open("getMetaData").columns, self)

    def close(self):
        self._data.close()

    def cancel(self):
        owner = self._owner_connection()
        if owner is not None:
            owner._engine.interrupt()

    def getWarnings(self):
        return None

    def clearWarnings(self):
        pass
