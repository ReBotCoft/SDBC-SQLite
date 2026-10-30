# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft


import weakref

import unohelper

from com.sun.star.sdbc import XConnection
from com.sun.star.sdbc import XWarningsSupplier

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import dialect
from sdbc_pysqlite import errors
from sdbc_pysqlite.engine import Engine
from sdbc_pysqlite import logger
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import uno_errors
from sdbc_pysqlite.common import ComponentMixin
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbc.databasemetadata import DatabaseMetaData
from sdbc_pysqlite.sdbc.preparedstatement import PreparedStatement
from sdbc_pysqlite.sdbc.statement import Statement

_ISOLATION_SERIALIZABLE = 8
_OPEN = []

_ISOLATION_NAMES = {
    0: "NONE", 1: "READ_UNCOMMITTED", 2: "READ_COMMITTED", 4: "REPEATABLE_READ", 8: "SERIALIZABLE",
}


@traced
class Connection(unohelper.Base, ComponentMixin, ServiceInfoMixin, XConnection, XWarningsSupplier,
                 ErrorMixin):

    _implementation_name = IDENTIFIER + ".Connection"
    _service_names = ("com.sun.star.sdbc.Connection", )

    def __init__(self, ctx, url, opened, language, code, warnings, info=()):
        self._ctx = ctx
        self._url = url
        self._opened = opened
        self._db = opened.connection
        self._path = opened.path
        self._full_path = opened.full_path
        self._info = tuple(info)
        self._options = opened.options
        self._language = language
        self._log_code = code
        self._warnings = list(warnings)
        self._closed = False
        self._engine = Engine(self._db, self._options, self._path)
        _OPEN.append(weakref.ref(self))

    @staticmethod
    def find(url):
        for reference in reversed(_OPEN):
            connection = reference()
            if connection is not None and not connection._closed and connection._url == url:
                return connection
        _OPEN[:] = [r for r in _OPEN if r() is not None]
        return None

    def _check_open(self, method):
        if self._closed:
            raise self._error(DriverError(errors.CONNECTION_CLOSED), method)

    def dispose(self):
        self.close()

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._engine.discard():
            self._warnings.append(self._warning(DriverError(errors.UNCOMMITTED_DISCARDED), "close"))
        try:
            self._db.close()
        except sqlite.Error as exception:
            logger.error("sdbc.connection.Connection.close",
                         "closing the database failed: %s" % exception, self._log_code)

    def createStatement(self):
        self._check_open("createStatement")
        return Statement(self)

    def prepareStatement(self, sql):
        self._check_open("prepareStatement")
        return PreparedStatement(self, sql)

    def prepareCall(self, sql):
        self._check_open("prepareCall")
        return PreparedStatement(self, sql)

    def nativeSQL(self, sql):
        return dialect.translate(sql)

    def setAutoCommit(self, autoCommit):
        self._check_open("setAutoCommit")
        try:
            self._engine.set_autocommit(autoCommit)
        except DriverError as error:
            raise self._error(error, "setAutoCommit")

    def getAutoCommit(self):
        self._check_open("getAutoCommit")
        return self._engine.autocommit

    def commit(self):
        self._check_open("commit")
        try:
            self._engine.commit()
        except DriverError as error:
            raise self._error(error, "commit")

    def rollback(self):
        self._check_open("rollback")
        try:
            self._engine.rollback()
        except DriverError as error:
            raise self._error(error, "rollback")

    def isClosed(self):
        return self._closed

    def getMetaData(self):
        self._check_open("getMetaData")
        return DatabaseMetaData(self)

    def setReadOnly(self, readOnly):
        pass

    def isReadOnly(self):
        return bool(self._options.read_only)

    def setCatalog(self, catalog):
        pass

    def getCatalog(self):
        return ""

    def setTransactionIsolation(self, level):
        if level != _ISOLATION_SERIALIZABLE:
            location = "sdbc.connection.Connection.setTransactionIsolation"
            warning = DriverError(errors.ISOLATION_IGNORED,
                                  livello=_ISOLATION_NAMES.get(level, str(level)))
            logger.warning(location, uno_errors.english_text(warning, location), self._log_code)
            self._warnings.append((warning, location))

    def getTransactionIsolation(self):
        return _ISOLATION_SERIALIZABLE

    def getTypeMap(self):
        return None

    def setTypeMap(self, typeMap):
        pass

    def getWarnings(self):
        if not self._warnings:
            return None
        return uno_errors.to_sql_warning_chain(self._warnings, self, self._language)

    def clearWarnings(self):
        self._warnings = []
