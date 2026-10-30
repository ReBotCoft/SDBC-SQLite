# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from com.sun.star.sdbcx import XAlterView

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import logger
from sdbc_pysqlite import structure
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbcx import properties
from sdbc_pysqlite.sdbcx.collection import Collection
from sdbc_pysqlite.sdbcx.properties import PropertyObject

VIEW_DEFINITIONS = (
    ("Name", "string"), ("CatalogName", "string"), ("SchemaName", "string"), ("Command", "string"),
    ("CheckOption", "long"))


def views_of(db):
    rows = db.execute("SELECT name, sql FROM main.sqlite_master WHERE type = 'view' "
                      "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name COLLATE NOCASE").fetchall()
    return [(name, structure.view_command(sql)) for name, sql in rows]


@traced
class View(PropertyObject, XAlterView):
    _definitions = VIEW_DEFINITIONS
    _implementation_name = IDENTIFIER + ".View"
    _service_names = ("com.sun.star.sdbcx.View",)

    def __init__(self, connection, name, command):
        super().__init__(connection, {"Name": name, "Command": command}, False)

    def alterCommand(self, NewCommand):
        try:
            structure.alter_view(self._connection._engine, self.name, NewCommand)
        except Exception as error:
            raise _sql_error(self, error, "alterCommand")
        self._values["Command"] = NewCommand
        logger.info(logger.label_of(self, "alterCommand"), "view <%s> replaced" % self.name,
                    self._connection._log_code)


def _sql_error(owner, error, method):
    from sdbc_pysqlite import sqlite
    from sdbc_pysqlite.engine import driver_error
    from sdbc_pysqlite.errors import DriverError
    if isinstance(error, DriverError):
        return owner._error(error, method)
    if isinstance(error, sqlite.Error):
        return owner._error(driver_error(error, owner._connection._path), method)
    return error


class ViewDescriptor(PropertyObject):
    _definitions = VIEW_DEFINITIONS
    _implementation_name = IDENTIFIER + ".ViewDescriptor"
    _service_names = ("com.sun.star.sdbcx.ViewDescriptor",)

    def __init__(self, connection, values=None):
        super().__init__(connection, values, True)


@traced
class ViewContainer(Collection):
    _implementation_name = IDENTIFIER + ".Views"

    def _snapshot(self):
        return views_of(self._connection._db)

    def _create(self, name):
        for view, command in views_of(self._connection._db):
            if view == name:
                return View(self._connection, view, command)
        raise KeyError(name)

    def _append(self, descriptor):
        name, command = properties.read(descriptor, "Name", "Command")
        db = self._connection._db
        existing = dict(views_of(db))
        if name in existing:
            return name
        warnings = structure.create_view(self._connection._engine, name, command)
        for warning in warnings:
            logger.warning(logger.label_of(self, "appendByDescriptor"), str(warning), self._connection._log_code)
        return name

    def _drop(self, name):
        structure.drop_view(self._connection._engine, name)

    def _new_descriptor(self):
        return ViewDescriptor(self._connection)
