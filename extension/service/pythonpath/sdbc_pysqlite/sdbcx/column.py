# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from com.sun.star.sdbcx import XDataDescriptorFactory

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import logger
from sdbc_pysqlite import schema
from sdbc_pysqlite import structure
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbcx import properties
from sdbc_pysqlite.sdbcx.collection import Collection
from sdbc_pysqlite.sdbcx.collection import DescriptorCollection
from sdbc_pysqlite.sdbcx.properties import PropertyObject

COLUMN_DEFINITIONS = (
    ("Name", "string"), ("Type", "long"), ("TypeName", "string"), ("Precision", "long"), ("Scale", "long"),
    ("IsNullable", "long"), ("IsAutoIncrement", "boolean"), ("IsCurrency", "boolean"),
    ("IsRowVersion", "boolean"), ("Description", "string"), ("DefaultValue", "string"))

EXISTING_COLUMN_DEFINITIONS = COLUMN_DEFINITIONS + (
    ("CatalogName", "string"), ("SchemaName", "string"), ("TableName", "string"))

_COLUMN_DEFAULTS = {"IsNullable": properties.NULLABLE}


def column_values(column, alias):
    ctype = ts.classify(column.label)
    not_null = column.notnull or column.pk > 0 or column.name == alias
    return {"Name": column.name, "Type": ctype.code, "TypeName": ctype.name, "Precision": ctype.size,
            "Scale": ctype.scale, "IsNullable": properties.NO_NULLS if not_null else properties.NULLABLE,
            "IsAutoIncrement": column.name == alias, "IsCurrency": False, "IsRowVersion": False,
            "Description": "", "DefaultValue": structure.visible_default(column.default, ctype) or ""}


def spec_of(descriptor):
    name, type_name, type_code, precision, scale, nullable, auto, default = properties.read(
        descriptor, "Name", "TypeName", "Type", "Precision", "Scale", "IsNullable", "IsAutoIncrement", "DefaultValue")
    if not (type_name or "").strip():
        type_name = ts.lo_name_for_code(type_code)
    label = structure.column_label(type_name or "", precision or 0, scale or 0)
    return structure.ColumnSpec(name, label, nullable == properties.NO_NULLS, default or None, bool(auto))


@traced
class Column(PropertyObject, XDataDescriptorFactory):
    _definitions = EXISTING_COLUMN_DEFINITIONS
    _defaults = _COLUMN_DEFAULTS
    _implementation_name = IDENTIFIER + ".Column"
    _service_names = ("com.sun.star.sdbcx.Column",)

    def __init__(self, connection, values, table=""):
        values = dict(values)
        values.setdefault("CatalogName", "")
        values.setdefault("SchemaName", "")
        values.setdefault("TableName", table)
        super().__init__(connection, values, False)
        self.table = table

    def createDataDescriptor(self):
        values = {name: self._values[name] for name, _ in COLUMN_DEFINITIONS if name in self._values}
        return ColumnDescriptor(self._connection, values)


class ColumnDescriptor(PropertyObject, XDataDescriptorFactory):
    _definitions = COLUMN_DEFINITIONS
    _defaults = _COLUMN_DEFAULTS
    _implementation_name = IDENTIFIER + ".ColumnDescriptor"
    _service_names = ("com.sun.star.sdbcx.ColumnDescriptor",)

    def __init__(self, connection, values=None):
        super().__init__(connection, values, True)

    def createDataDescriptor(self):
        return ColumnDescriptor(self._connection, dict(self._values))


@traced
class ColumnContainer(Collection):
    _implementation_name = IDENTIFIER + ".Columns"
    _service_names = ("com.sun.star.sdbcx.Container",)

    def __init__(self, connection, table):
        super().__init__(connection)
        self._table = table

    def _columns(self):
        db = self._connection._db
        columns = schema.table_columns(db, self._table)
        return columns, schema.rowid_alias(db, self._table, columns)

    def _snapshot(self):
        columns, alias = self._columns()
        return [(c.name, tuple(sorted(column_values(c, alias).items()))) for c in columns]

    def _create(self, name):
        columns, alias = self._columns()
        for column in columns:
            if column.name == name:
                return Column(self._connection, column_values(column, alias), self._table)
        raise KeyError(name)

    def _append(self, descriptor):
        spec = spec_of(descriptor)
        rebuilt = structure.add_column(self._connection._engine, self._table, spec)
        if rebuilt:
            logger.info(logger.label_of(self, "appendByDescriptor"),
                        "table <%s> rebuilt to add column <%s>" % (self._table, spec.name),
                        self._connection._log_code)
        return spec.name

    def _drop(self, name):
        dropped = structure.drop_column(self._connection._engine, self._table, name)
        if dropped:
            logger.info(logger.label_of(self, "dropByName"),
                        "column <%s> of <%s> dropped together with indexes %s" % (
                            name, self._table, ", ".join("<%s>" % d for d in dropped)),
                        self._connection._log_code)

    def _new_descriptor(self):
        return ColumnDescriptor(self._connection)


def descriptor_columns(connection):
    return DescriptorCollection(connection, ColumnDescriptor)
