# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from collections import namedtuple

from com.sun.star.sdbcx import XColumnsSupplier
from com.sun.star.sdbcx import XDataDescriptorFactory

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import structure
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbcx import properties
from sdbc_pysqlite.sdbcx.collection import Collection
from sdbc_pysqlite.sdbcx.collection import DescriptorCollection
from sdbc_pysqlite.sdbcx.collection import StaticCollection
from sdbc_pysqlite.sdbcx.column import COLUMN_DEFINITIONS
from sdbc_pysqlite.sdbcx.column import column_values
from sdbc_pysqlite.sdbcx.properties import PropertyObject

INDEX_DEFINITIONS = (
    ("Name", "string"), ("Catalog", "string"), ("IsUnique", "boolean"), ("IsPrimaryKeyIndex", "boolean"),
    ("IsClustered", "boolean"))
INDEX_COLUMN_DEFINITIONS = COLUMN_DEFINITIONS + (("IsAscending", "boolean"),)

IndexInfo = namedtuple("IndexInfo", "name unique columns")


def indexes_of(db, table):
    if schema.object_kind(db, table) != "table":
        return []
    result = []
    for _seq, name, unique, origin, partial in db.execute(
            "PRAGMA main.index_list(%s)" % sqltext.quote_name(table)).fetchall():
        if origin != "c" or partial:
            continue
        details = db.execute("PRAGMA main.index_xinfo(%s)" % sqltext.quote_name(name)).fetchall()
        keys = [d for d in details if d[5]]
        if any(d[1] == -2 or d[2] is None for d in keys):
            continue
        result.append(IndexInfo(name, bool(unique), [(d[2], not d[3]) for d in keys]))
    result.sort(key=lambda i: i.name.lower())
    return result


@traced
class IndexColumn(PropertyObject):
    _definitions = INDEX_COLUMN_DEFINITIONS
    _implementation_name = IDENTIFIER + ".IndexColumn"
    _service_names = ("com.sun.star.sdbcx.IndexColumn",)


class IndexColumnDescriptor(PropertyObject):
    _definitions = INDEX_COLUMN_DEFINITIONS
    _defaults = {"IsNullable": properties.NULLABLE, "IsAscending": True}
    _implementation_name = IDENTIFIER + ".IndexColumnDescriptor"
    _service_names = ("com.sun.star.sdbcx.IndexColumnDescriptor",)

    def __init__(self, connection, values=None):
        super().__init__(connection, values, True)


@traced
class Index(PropertyObject, XColumnsSupplier, XDataDescriptorFactory):
    _definitions = INDEX_DEFINITIONS
    _implementation_name = IDENTIFIER + ".Index"
    _service_names = ("com.sun.star.sdbcx.Index",)

    def __init__(self, connection, info, table):
        super().__init__(connection, {"Name": info.name, "Catalog": "", "IsUnique": info.unique,
                                      "IsPrimaryKeyIndex": False, "IsClustered": False}, False)
        self._info = info
        self._table = table

    def getColumns(self):
        db = self._connection._db
        columns = {c.name.lower(): c for c in schema.table_columns(db, self._table)}
        alias = schema.rowid_alias(db, self._table)
        items = []
        for name, ascending in self._info.columns:
            column = columns.get(name.lower())
            values = column_values(column, alias) if column is not None else {"Name": name}
            values["IsAscending"] = ascending
            items.append(IndexColumn(self._connection, values, False))
        return StaticCollection(self._connection, items)

    def createDataDescriptor(self):
        return IndexDescriptor(self._connection, dict(self._values))


class IndexDescriptor(PropertyObject, XColumnsSupplier):
    _definitions = INDEX_DEFINITIONS
    _implementation_name = IDENTIFIER + ".IndexDescriptor"
    _service_names = ("com.sun.star.sdbcx.IndexDescriptor",)

    def __init__(self, connection, values=None):
        super().__init__(connection, values, True)
        self._columns = DescriptorCollection(connection, IndexColumnDescriptor)

    def getColumns(self):
        return self._columns


@traced
class IndexContainer(Collection):
    _implementation_name = IDENTIFIER + ".Indexes"

    def __init__(self, connection, table):
        super().__init__(connection)
        self._table = table

    def _infos(self):
        return indexes_of(self._connection._db, self._table)

    def _snapshot(self):
        return [(i.name, (i.unique, tuple(i.columns))) for i in self._infos()]

    def _create(self, name):
        for info in self._infos():
            if info.name == name:
                return Index(self._connection, info, self._table)
        raise KeyError(name)

    def _append(self, descriptor):
        name, unique = properties.read(descriptor, "Name", "IsUnique")
        columns = descriptor.getColumns()
        parts = []
        for index in range(columns.getCount()):
            column_name, ascending = properties.read(columns.getByIndex(index), "Name", "IsAscending")
            parts.append((column_name, True if ascending is None else bool(ascending)))
        structure.create_index(self._connection._engine, self._table, name, bool(unique), parts)
        return name

    def _drop(self, name):
        structure.drop_index(self._connection._engine, name)

    def _new_descriptor(self):
        return IndexDescriptor(self._connection)
