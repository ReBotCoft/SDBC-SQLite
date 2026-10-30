# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from com.sun.star.container import XNamed
from com.sun.star.sdbcx import XAlterTable
from com.sun.star.sdbcx import XColumnsSupplier
from com.sun.star.sdbcx import XDataDescriptorFactory
from com.sun.star.sdbcx import XIndexesSupplier
from com.sun.star.sdbcx import XKeysSupplier
from com.sun.star.sdbcx import XRename

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import logger
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import structure
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbcx import properties
from sdbc_pysqlite.sdbcx.collection import Collection
from sdbc_pysqlite.sdbcx.collection import DescriptorCollection
from sdbc_pysqlite.sdbcx.column import ColumnContainer
from sdbc_pysqlite.sdbcx.column import ColumnDescriptor
from sdbc_pysqlite.sdbcx.column import column_values
from sdbc_pysqlite.sdbcx.column import spec_of
from sdbc_pysqlite.sdbcx.index import IndexContainer
from sdbc_pysqlite.sdbcx.index import IndexDescriptor
from sdbc_pysqlite.sdbcx.key import KeyContainer
from sdbc_pysqlite.sdbcx.key import KeyDescriptor
from sdbc_pysqlite.sdbcx.properties import KEY_FOREIGN
from sdbc_pysqlite.sdbcx.properties import KEY_PRIMARY
from sdbc_pysqlite.sdbcx.properties import PropertyObject

TABLE_DEFINITIONS = (
    ("Name", "string"), ("CatalogName", "string"), ("SchemaName", "string"), ("Description", "string"),
    ("Type", "string"))


def _plain_name(text):
    return sqltext.unquote((text or "").strip())


@traced
class Table(PropertyObject, XColumnsSupplier, XKeysSupplier, XIndexesSupplier, XRename, XAlterTable,
            XDataDescriptorFactory, XNamed):
    _definitions = TABLE_DEFINITIONS
    _implementation_name = IDENTIFIER + ".Table"
    _service_names = ("com.sun.star.sdbcx.Table",)

    def __init__(self, connection, name, kind):
        super().__init__(connection, {"Name": name, "Type": "VIEW" if kind == "view" else "TABLE"}, False)
        self._columns = ColumnContainer(connection, name)
        self._keys = KeyContainer(connection, name)
        self._indexes = IndexContainer(connection, name)

    def getColumns(self):
        return self._columns

    def getKeys(self):
        return self._keys

    def getIndexes(self):
        return self._indexes

    def getName(self):
        return self.name

    def setName(self, aName):
        self.rename(aName)

    def rename(self, newName):
        old = self.name
        new = _plain_name(newName)
        try:
            structure.rename_table(self._connection._engine, old, new)
        except Exception as error:
            raise _error(self, error, "rename")
        self._values["Name"] = new
        for child in (self._columns, self._keys, self._indexes):
            child._table = new
        logger.info(logger.label_of(self, "rename"), "table <%s> renamed to <%s>" % (old, new),
                    self._connection._log_code)

    def alterColumnByName(self, colName, descriptor):
        spec = spec_of(descriptor)
        try:
            done = structure.alter_column(self._connection._engine, self.name, colName, spec)
        except Exception as error:
            raise _error(self, error, "alterColumnByName")
        if "rename" in done:
            logger.info(logger.label_of(self, "alterColumnByName"),
                        "column <%s> of <%s> renamed to <%s>" % (colName, self.name, spec.name),
                        self._connection._log_code)
        if "rebuild" in done:
            logger.info(logger.label_of(self, "alterColumnByName"),
                        "table <%s> rebuilt to change column <%s>" % (self.name, spec.name),
                        self._connection._log_code)

    def alterColumnByIndex(self, index, descriptor):
        self.alterColumnByName(self._columns.getElementNames()[index], descriptor)

    def createDataDescriptor(self):
        descriptor = TableDescriptor(self._connection, {"Name": self.name, "Type": self._values["Type"]})
        columns = descriptor.getColumns()
        for index in range(self._columns.getCount()):
            source = self._columns.getByIndex(index)
            columns.appendByDescriptor(ColumnDescriptor(self._connection, dict(source._values)))
        return descriptor


def _error(owner, error, method):
    from sdbc_pysqlite import sqlite
    from sdbc_pysqlite.engine import driver_error
    if isinstance(error, DriverError):
        return owner._error(error, method)
    if isinstance(error, sqlite.Error):
        return owner._error(driver_error(error, owner._connection._path), method)
    return error


class TableDescriptor(PropertyObject, XColumnsSupplier, XKeysSupplier, XIndexesSupplier):
    _definitions = TABLE_DEFINITIONS
    _defaults = {"Type": "TABLE"}
    _implementation_name = IDENTIFIER + ".TableDescriptor"
    _service_names = ("com.sun.star.sdbcx.TableDescriptor",)

    def __init__(self, connection, values=None):
        super().__init__(connection, values, True)
        self._columns = DescriptorCollection(connection, ColumnDescriptor)
        self._keys = DescriptorCollection(connection, KeyDescriptor)
        self._indexes = DescriptorCollection(connection, IndexDescriptor)

    def getColumns(self):
        return self._columns

    def getKeys(self):
        return self._keys

    def getIndexes(self):
        return self._indexes


@traced
class TableContainer(Collection):
    _implementation_name = IDENTIFIER + ".Tables"

    def _entries(self):
        db = self._connection._db
        rows = db.execute(
            "SELECT name, type, sql FROM main.sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY type, name COLLATE NOCASE").fetchall()
        hidden = schema.shadow_tables(db)
        return [row for row in rows if row[0].lower() not in hidden]

    def _snapshot(self):
        return [(name, (kind, sql)) for name, kind, sql in self._entries()]

    def _create(self, name):
        for entry, kind, _sql in self._entries():
            if entry == name:
                return Table(self._connection, name, kind)
        raise KeyError(name)

    def _append(self, descriptor):
        engine = self._connection._engine
        name = _plain_name(properties.read(descriptor, "Name")[0])
        columns = []
        suppliers = descriptor.getColumns()
        for index in range(suppliers.getCount()):
            columns.append(spec_of(suppliers.getByIndex(index)))
        primary_key, foreign_keys, extra = [], [], []
        label = logger.label_of(self, "appendByDescriptor")
        code = self._connection._log_code
        keys = descriptor.getKeys() if hasattr(descriptor, "getKeys") else None
        logger.trace(label, "descriptor <%s>: %d columns, keys container %s, %s keys" % (
            name, len(columns), "present" if keys is not None else "absent",
            keys.getCount() if keys is not None else 0), code)
        for index in range(keys.getCount() if keys is not None else 0):
            key = keys.getByIndex(index)
            kind, target, update, delete = properties.read(key, "Type", "ReferencedTable", "UpdateRule", "DeleteRule")
            pairs = []
            key_columns = key.getColumns()
            for position in range(key_columns.getCount()):
                pairs.append(properties.read(key_columns.getByIndex(position), "Name", "RelatedColumn"))
            logger.trace(label, "key %d: type %r, columns %r" % (index, kind, pairs), code)
            if kind == KEY_PRIMARY:
                primary_key = [p[0] for p in pairs]
            elif kind == KEY_FOREIGN:
                target = _plain_name(target)
                destinations = [p[1] or "" for p in pairs]
                if any(not d for d in destinations):
                    destinations = [n for _s, n in schema.primary_key_columns(self._connection._db, target)]
                foreign_keys.append(([p[0] for p in pairs], target, destinations,
                                     3 if update is None else update, 3 if delete is None else delete))
        structure.create_table(engine, name, columns, primary_key, foreign_keys)
        logger.info(logger.label_of(self, "appendByDescriptor"), "table <%s> created" % name,
                    self._connection._log_code)
        indexes = descriptor.getIndexes() if hasattr(descriptor, "getIndexes") else None
        for position in range(indexes.getCount() if indexes is not None else 0):
            index = indexes.getByIndex(position)
            index_name, unique = properties.read(index, "Name", "IsUnique")
            parts = []
            index_columns = index.getColumns()
            for item in range(index_columns.getCount()):
                column_name, ascending = properties.read(index_columns.getByIndex(item), "Name", "IsAscending")
                parts.append((column_name, True if ascending is None else bool(ascending)))
            structure.create_index(engine, name, index_name, bool(unique), parts)
        return name

    def _drop(self, name):
        engine = self._connection._engine
        if schema.object_kind(self._connection._db, name) == "view":
            structure.drop_view(engine, name)
        else:
            structure.drop_table(engine, name)
        logger.info(logger.label_of(self, "dropByName"), "<%s> dropped" % name, self._connection._log_code)

    def _new_descriptor(self):
        return TableDescriptor(self._connection)
