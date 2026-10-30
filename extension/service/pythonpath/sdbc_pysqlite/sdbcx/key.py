# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from collections import namedtuple

from com.sun.star.sdbcx import XColumnsSupplier
from com.sun.star.sdbcx import XDataDescriptorFactory

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import logger
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
from sdbc_pysqlite.sdbcx.properties import KEY_FOREIGN
from sdbc_pysqlite.sdbcx.properties import KEY_PRIMARY
from sdbc_pysqlite.sdbcx.properties import KEY_UNIQUE
from sdbc_pysqlite.sdbcx.properties import PropertyObject

KEY_DEFINITIONS = (
    ("Name", "string"), ("Type", "long"), ("ReferencedTable", "string"), ("UpdateRule", "long"),
    ("DeleteRule", "long"))
KEY_COLUMN_DEFINITIONS = COLUMN_DEFINITIONS + (("RelatedColumn", "string"),)

KeyInfo = namedtuple("KeyInfo", "name type target update delete columns")


def keys_of(db, table):
    if schema.object_kind(db, table) != "table":
        return []
    result = []
    primary = schema.primary_key_columns(db, table)
    if primary:
        result.append(KeyInfo("PK_" + table, KEY_PRIMARY, "", 3, 3, [(name, "") for _seq, name in primary]))
    for fk in schema.foreign_keys(db, table):
        result.append(KeyInfo(fk.name, KEY_FOREIGN, fk.target_table, fk.update_rule, fk.delete_rule, list(fk.pairs)))
    for _seq, index, unique, origin, _partial in db.execute(
            "PRAGMA main.index_list(%s)" % sqltext.quote_name(table)).fetchall():
        if origin != "u" or not unique:
            continue
        names = [row[2] for row in sorted(db.execute(
            "PRAGMA main.index_info(%s)" % sqltext.quote_name(index)).fetchall()) if row[2] is not None]
        if names:
            result.append(KeyInfo("UQ_%s_%s" % (table, "_".join(names)), KEY_UNIQUE, "", 3, 3,
                                  [(n, "") for n in names]))
    return result


@traced
class KeyColumn(PropertyObject):
    _definitions = KEY_COLUMN_DEFINITIONS
    _implementation_name = IDENTIFIER + ".KeyColumn"
    _service_names = ("com.sun.star.sdbcx.KeyColumn",)


class KeyColumnDescriptor(PropertyObject):
    _definitions = KEY_COLUMN_DEFINITIONS
    _defaults = {"IsNullable": properties.NULLABLE}
    _implementation_name = IDENTIFIER + ".KeyColumnDescriptor"
    _service_names = ("com.sun.star.sdbcx.KeyColumnDescriptor",)

    def __init__(self, connection, values=None):
        super().__init__(connection, values, True)


@traced
class Key(PropertyObject, XColumnsSupplier, XDataDescriptorFactory):
    _definitions = KEY_DEFINITIONS
    _implementation_name = IDENTIFIER + ".Key"
    _service_names = ("com.sun.star.sdbcx.Key",)

    def __init__(self, connection, info, table):
        super().__init__(connection, {"Name": info.name, "Type": info.type, "ReferencedTable": info.target,
                                      "UpdateRule": info.update, "DeleteRule": info.delete}, False)
        self._info = info
        self._table = table

    def getColumns(self):
        db = self._connection._db
        columns = {c.name.lower(): c for c in schema.table_columns(db, self._table)}
        alias = schema.rowid_alias(db, self._table)
        items = []
        for name, related in self._info.columns:
            column = columns.get(name.lower())
            values = column_values(column, alias) if column is not None else {"Name": name}
            values["RelatedColumn"] = related or ""
            items.append(KeyColumn(self._connection, values, False))
        return StaticCollection(self._connection, items)

    def createDataDescriptor(self):
        descriptor = KeyDescriptor(self._connection, dict(self._values))
        return descriptor


class KeyDescriptor(PropertyObject, XColumnsSupplier):
    _definitions = KEY_DEFINITIONS
    _defaults = {"UpdateRule": 3, "DeleteRule": 3}
    _implementation_name = IDENTIFIER + ".KeyDescriptor"
    _service_names = ("com.sun.star.sdbcx.KeyDescriptor",)

    def __init__(self, connection, values=None):
        super().__init__(connection, values, True)
        self._columns = DescriptorCollection(connection, KeyColumnDescriptor)

    def getColumns(self):
        return self._columns


@traced
class KeyContainer(Collection):
    _implementation_name = IDENTIFIER + ".Keys"

    def __init__(self, connection, table):
        super().__init__(connection)
        self._table = table

    def _infos(self):
        return keys_of(self._connection._db, self._table)

    def _snapshot(self):
        return [(k.name, (k.type, k.target, k.update, k.delete, tuple(k.columns))) for k in self._infos()]

    def _create(self, name):
        for info in self._infos():
            if info.name == name:
                return Key(self._connection, info, self._table)
        raise KeyError(name)

    def _append(self, descriptor):
        engine = self._connection._engine
        db = self._connection._db
        kind, target, update, delete = properties.read(
            descriptor, "Type", "ReferencedTable", "UpdateRule", "DeleteRule")
        pairs = []
        columns = descriptor.getColumns()
        for index in range(columns.getCount()):
            name, related = properties.read(columns.getByIndex(index), "Name", "RelatedColumn")
            pairs.append((name, related or ""))
        sources = [p[0] for p in pairs]
        if kind == KEY_PRIMARY:
            structure.set_primary_key(engine, self._table, sources)
            logger.info(logger.label_of(self, "appendByDescriptor"),
                        "primary key of <%s> set to %s" % (self._table, sources), self._connection._log_code)
            return "PK_" + self._table
        if kind == KEY_FOREIGN:
            target = structure.stored_name(db, sqltext.unquote(target or "")) or sqltext.unquote(target or "")
            destinations = [p[1] for p in pairs]
            if any(not d for d in destinations):
                destinations = [name for _seq, name in schema.primary_key_columns(db, target)]
            before = {fk.name for fk in schema.foreign_keys(db, self._table)}
            structure.add_foreign_key(engine, self._table, sources, target, destinations,
                                      3 if update is None else update, 3 if delete is None else delete)
            logger.info(logger.label_of(self, "appendByDescriptor"),
                        "table <%s> rebuilt to add a relation to <%s>" % (self._table, target),
                        self._connection._log_code)
            added = [fk.name for fk in schema.foreign_keys(db, self._table) if fk.name not in before]
            return added[0] if added else None
        name = properties.read(descriptor, "Name")[0] or "UQ_%s_%s" % (self._table, "_".join(sources))
        structure.create_index(engine, self._table, name, True, [(c, True) for c in sources])
        return None

    def _drop(self, name):
        engine = self._connection._engine
        for info in self._infos():
            if info.name == name:
                if info.type == KEY_PRIMARY:
                    structure.set_primary_key(engine, self._table, [])
                elif info.type == KEY_FOREIGN:
                    structure.drop_foreign_key(engine, self._table, name)
                else:
                    structure.drop_unique(engine, self._table, [c for c, _r in info.columns])
                logger.info(logger.label_of(self, "dropByName"),
                            "table <%s> rebuilt to drop key <%s>" % (self._table, name), self._connection._log_code)
                return

    def _new_descriptor(self):
        return KeyDescriptor(self._connection)
