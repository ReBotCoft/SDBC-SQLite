# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unohelper

from com.sun.star.sdbc import XBatchExecution
from com.sun.star.sdbc import XCloseable
from com.sun.star.sdbc import XMultipleResults
from com.sun.star.sdbc import XStatement
from com.sun.star.sdbc import XWarningsSupplier
from com.sun.star.util import XCancellable

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import errors
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import uno_errors
from sdbc_pysqlite.common import ComponentMixin
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import PropertySetMixin
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbc.commandbase import CommandBase


@traced
class Statement(unohelper.Base, ComponentMixin, PropertySetMixin, ServiceInfoMixin, XStatement,
                XCloseable, XCancellable, XBatchExecution, XMultipleResults, XWarningsSupplier,
                ErrorMixin, CommandBase):

    _implementation_name = IDENTIFIER + ".Statement"
    _service_names = ("com.sun.star.sdbc.Statement", )
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

    def __init__(self, connection):
        self._connection = connection
        self._init_properties()
        self._closed = False
        self._batch = []
        self._warnings = []
        self._results = []
        self._queue = []
        self._position = -1

    def _run_all(self, sql, method):
        pieces = sqltext.split_statements(sql)
        for piece in pieces:
            if sqltext.count_parameters(piece):
                raise self._error(DriverError(errors.PARAMETER_NOT_SET, numero=1), method)
        return [self._run_one(piece, (), method) for piece in pieces]

    def executeQuery(self, sql):
        self._start("executeQuery")
        return self._query_outcome(self._run_all(sql, "executeQuery"), "executeQuery")

    def executeUpdate(self, sql):
        self._start("executeUpdate")
        return self._update_outcome(self._run_all(sql, "executeUpdate"), "executeUpdate")

    def execute(self, sql):
        self._start("execute")
        return self._execute_outcome(self._run_all(sql, "execute"))

    def getConnection(self):
        return self._connection

    def close(self):
        if self._closed:
            return
        self._close_all()

    def cancel(self):
        if not self._closed:
            self._connection._engine.interrupt()

    def addBatch(self, sql):
        self._check_open("addBatch")
        self._batch.append(sql)

    def clearBatch(self):
        self._check_open("clearBatch")
        self._batch = []

    def executeBatch(self):
        self._start("executeBatch")
        batch, self._batch = self._batch, []
        counts = []
        for sql in batch:
            for outcome in self._run_all(sql, "executeBatch"):
                if outcome.result is not None and not outcome.writes:
                    outcome.result.close()
                    raise self._error(DriverError(errors.BATCH_RETURNED_ROWS, comando=sql[:80]), "executeBatch")
                if outcome.result is not None:
                    outcome.result.close()
                counts.append(outcome.count)
        return tuple(counts)

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
