# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unohelper

from com.sun.star.sdbc import XResultSetMetaData

from sdbc_pysqlite import errors
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced


@traced
class ResultSetMetaData(unohelper.Base, XResultSetMetaData, ErrorMixin):

    def __init__(self, columns=(), owner=None):
        self._columns = list(columns)
        self._connection = owner

    def _column(self, index):
        if not 1 <= index <= len(self._columns):
            raise self._error(DriverError(errors.COLUMN_OUT_OF_RANGE, colonna=index,
                                          totale=len(self._columns)), "column")
        return self._columns[index - 1]

    def getColumnCount(self):
        return len(self._columns)

    def isAutoIncrement(self, column):
        return bool(self._column(column).auto_increment)

    def isCaseSensitive(self, column):
        return ts.is_case_sensitive(self._column(column).ctype)

    def isSearchable(self, column):
        self._column(column)
        return True

    def isCurrency(self, column):
        self._column(column)
        return False

    def isNullable(self, column):
        return self._column(column).nullable

    def isSigned(self, column):
        return ts.is_signed(self._column(column).ctype)

    def getColumnDisplaySize(self, column):
        return ts.display_size(self._column(column).ctype)

    def getColumnLabel(self, column):
        return self._column(column).label

    def getColumnName(self, column):
        return self._column(column).label

    def getSchemaName(self, column):
        self._column(column)
        return ""

    def getPrecision(self, column):
        return self._column(column).ctype.size

    def getScale(self, column):
        return self._column(column).ctype.scale

    def getTableName(self, column):
        return self._column(column).table

    def getCatalogName(self, column):
        self._column(column)
        return ""

    def getColumnType(self, column):
        return self._column(column).ctype.code

    def getColumnTypeName(self, column):
        return self._column(column).ctype.name

    def isReadOnly(self, column):
        return bool(self._column(column).read_only)

    def isWritable(self, column):
        return bool(self._column(column).writable)

    def isDefinitelyWritable(self, column):
        return bool(self._column(column).writable)

    def getColumnServiceName(self, column):
        self._column(column)
        return ""
