# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest

import support

support.install_uno_stubs()

from test_sdbc_objects import ObjectsTestCase
from sdbc_pysqlite import errors
from sdbc_pysqlite.sdbcx import properties


def fill(descriptor, **values):
    for name, value in values.items():
        descriptor.setPropertyValue(name, value)
    return descriptor


class Recorder:
    def __init__(self):
        self.events = []

    def elementInserted(self, event):
        self.events.append(("inserted", event.Accessor))

    def elementRemoved(self, event):
        self.events.append(("removed", event.Accessor))

    def elementReplaced(self, event):
        self.events.append(("replaced", event.Accessor))

    def disposing(self, event):
        pass


class SdbcxCase(ObjectsTestCase):
    def setUp(self):
        super().setUp()
        self.catalog = self.driver.getDataDefinitionByConnection(self.connection)
        self.tables = self.catalog.getTables()

    def sql(self, text):
        self.statement.execute(text)

    def rows(self, text):
        result = self.statement.executeQuery(text)
        found = []
        columns = result.getMetaData().getColumnCount()
        while result.next():
            found.append(tuple(result.getObject(i + 1, None) for i in range(columns)))
        return found

    def code(self, function, *args):
        return self.code_of(function, *args)

    def column_descriptor(self, columns, name, type_name, precision=0, scale=0, nullable=True, auto=False,
                          default=""):
        descriptor = columns.createDataDescriptor()
        fill(descriptor, Name=name, TypeName=type_name, Precision=precision, Scale=scale,
             IsNullable=properties.NULLABLE if nullable else properties.NO_NULLS, IsAutoIncrement=auto,
             DefaultValue=default)
        return descriptor


class CatalogTests(SdbcxCase):
    def test_catalog_lists_tables_and_views(self):
        self.sql("CREATE VIEW vv AS SELECT id, n FROM t")
        self.assertEqual(self.tables.getElementNames(), ("t", "vv"))
        self.assertEqual(self.tables.getByName("vv").getPropertyValue("Type"), "VIEW")
        self.assertEqual(self.tables.getByName("t").getPropertyValue("Type"), "TABLE")
        self.assertEqual(self.catalog.getViews().getElementNames(), ("vv",))
        self.assertEqual(self.catalog.getUsers().getElementNames(), ())
        self.assertEqual(self.catalog.getGroups().getCount(), 0)

    def test_connection_returned_as_uno_reference_is_found_again(self):
        url = self.connection.getMetaData().getURL()

        class Proxy:
            def getMetaData(self):
                class Meta:
                    def getURL(self_inner):
                        return url
                return Meta()

        catalog = self.driver.getDataDefinitionByConnection(Proxy())
        self.assertEqual(catalog.getTables().getElementNames(), ("t",))

    def test_get_by_name_ignores_case_and_unknown_raises(self):
        self.assertEqual(self.tables.getByName("T").getPropertyValue("Name"), "t")
        self.assertTrue(self.tables.hasByName("T"))
        with self.assertRaises(Exception):
            self.tables.getByName("nessuna")

    def test_index_access_and_enumeration(self):
        self.sql("CREATE TABLE u(a)")
        self.assertEqual(self.tables.getCount(), 2)
        self.assertEqual(self.tables.getByIndex(1).getPropertyValue("Name"), "u")
        enumeration = self.tables.createEnumeration()
        names = []
        while enumeration.hasMoreElements():
            names.append(enumeration.nextElement().getPropertyValue("Name"))
        self.assertEqual(names, ["t", "u"])
        with self.assertRaises(Exception):
            self.tables.getByIndex(9)

    def test_container_sees_changes_made_by_sql(self):
        self.assertEqual(self.tables.getElementNames(), ("t",))
        self.sql("CREATE TABLE u(a)")
        self.assertEqual(self.tables.getElementNames(), ("t", "u"))
        self.sql("DROP TABLE u")
        self.assertEqual(self.tables.getElementNames(), ("t",))

    def test_element_type(self):
        self.assertEqual(self.tables.getElementType(), ("type", "com.sun.star.beans.XPropertySet"))


class PropertyTests(SdbcxCase):
    def test_existing_objects_are_read_only_and_descriptors_are_not(self):
        table = self.tables.getByName("t")
        info = table.getPropertySetInfo()
        by_name = {p.Name: p for p in info.getProperties()}
        self.assertEqual(sorted(by_name), ["CatalogName", "Description", "Name", "SchemaName", "Type"])
        self.assertTrue(all(p.Attributes & properties.READONLY for p in by_name.values()))
        self.assertTrue(info.hasPropertyByName("Name"))
        descriptor = self.tables.createDataDescriptor()
        infos = {p.Name: p for p in descriptor.getPropertySetInfo().getProperties()}
        self.assertFalse(any(p.Attributes & properties.READONLY for p in infos.values()))
        with self.assertRaises(Exception):
            table.setPropertyValue("Name", "altro")
        with self.assertRaises(Exception):
            table.getPropertyValue("Boh")

    def test_properties_are_sorted_by_name(self):
        names = [p.Name for p in self.tables.getByName("t").getColumns().getByName("id").getPropertySetInfo()
                 .getProperties()]
        self.assertEqual(names, sorted(names))


class ColumnTests(SdbcxCase):
    def test_column_values_as_base_sees_them(self):
        columns = self.tables.getByName("t").getColumns()
        self.assertEqual(columns.getElementNames(), ("id", "n", "d", "p"))
        ident = columns.getByName("id")
        self.assertTrue(ident.getPropertyValue("IsAutoIncrement"))
        self.assertEqual(ident.getPropertyValue("IsNullable"), properties.NO_NULLS)
        decimal = columns.getByName("p")
        self.assertEqual(decimal.getPropertyValue("TypeName"), "LO_DECIMAL")
        self.assertEqual((decimal.getPropertyValue("Precision"), decimal.getPropertyValue("Scale")), (10, 2))
        self.assertEqual(columns.getByName("n").getPropertyValue("IsNullable"), properties.NO_NULLS)
        self.assertEqual(columns.getByName("d").getPropertyValue("IsNullable"), properties.NULLABLE)

    def test_existing_column_has_the_names_base_reads_when_expanding_select_star(self):
        column = self.tables.getByName("t").getColumns().getByName("n")
        for name in ("TypeName", "DefaultValue", "Description", "IsNullable", "Precision", "Scale", "Type",
                     "IsAutoIncrement", "IsCurrency", "CatalogName", "SchemaName", "TableName"):
            self.assertTrue(column.getPropertySetInfo().hasPropertyByName(name), name)
        self.assertEqual(column.getPropertyValue("TableName"), "t")
        self.assertNotIn("TableName", [p.Name for p in column.createDataDescriptor().getPropertySetInfo().getProperties()])

    def test_append_simple_column(self):
        columns = self.tables.getByName("t").getColumns()
        listener = Recorder()
        columns.addContainerListener(listener)
        columns.appendByDescriptor(self.column_descriptor(columns, "eta", "LO_INTEGER", default="18"))
        self.assertEqual(listener.events, [("inserted", "eta")])
        self.assertEqual(columns.getByName("eta").getPropertyValue("DefaultValue"), "18")
        self.assertEqual(self.rows("SELECT eta FROM t"), [(18,), (18,)])

    def test_append_required_column_on_full_table_is_refused_with_code(self):
        columns = self.tables.getByName("t").getColumns()
        descriptor = self.column_descriptor(columns, "x", "LO_INTEGER", nullable=False)
        self.assertEqual(self.code(columns.appendByDescriptor, descriptor), errors.COLUMN_NOT_NULL_NO_DEFAULT)
        self.assertEqual(columns.getElementNames(), ("id", "n", "d", "p"))

    def test_drop_column_and_its_indexes(self):
        self.sql("CREATE INDEX ix ON t(d)")
        columns = self.tables.getByName("t").getColumns()
        listener = Recorder()
        columns.addContainerListener(listener)
        columns.dropByName("d")
        self.assertEqual(listener.events, [("removed", "d")])
        self.assertEqual(columns.getElementNames(), ("id", "n", "p"))
        self.assertEqual(self.tables.getByName("t").getIndexes().getElementNames(), ())

    def test_drop_primary_key_column_is_refused_with_code(self):
        columns = self.tables.getByName("t").getColumns()
        self.assertEqual(self.code(columns.dropByName, "id"), errors.COLUMN_IN_USE)

    def test_alter_column_type_and_decimals(self):
        table = self.tables.getByName("t")
        columns = table.getColumns()
        descriptor = self.column_descriptor(columns, "p", "LO_DECIMAL", 10, 1, default="")
        table.alterColumnByName("p", descriptor)
        self.assertEqual(self.rows("SELECT p FROM t ORDER BY id"), [('12.3',), ('0.1',)])
        self.assertEqual(columns.getByName("p").getPropertyValue("Scale"), 1)

    def test_alter_column_keeps_object_fresh_after_change(self):
        table = self.tables.getByName("t")
        columns = table.getColumns()
        before = columns.getByName("n")
        table.alterColumnByName("n", self.column_descriptor(columns, "n", "LO_VARCHAR", 40, nullable=True))
        after = columns.getByName("n")
        self.assertIsNot(before, after)
        self.assertEqual(after.getPropertyValue("IsNullable"), properties.NULLABLE)
        self.assertEqual(after.getPropertyValue("Precision"), 40)

    def test_alter_by_index_and_rename_column(self):
        table = self.tables.getByName("t")
        columns = table.getColumns()
        table.alterColumnByIndex(1, self.column_descriptor(columns, "nome", "LO_VARCHAR", 40, nullable=False))
        self.assertEqual(columns.getElementNames(), ("id", "nome", "d", "p"))

    def test_alter_with_impossible_conversion_is_refused_with_code(self):
        table = self.tables.getByName("t")
        columns = table.getColumns()
        descriptor = self.column_descriptor(columns, "n", "LO_INTEGER", nullable=False)
        self.assertEqual(self.code(table.alterColumnByName, "n", descriptor), errors.CONVERSION_IMPOSSIBLE)

    def test_unchanged_descriptor_changes_nothing(self):
        table = self.tables.getByName("t")
        before = self.rows("SELECT sql FROM sqlite_master WHERE name = 't'")
        for index in range(table.getColumns().getCount()):
            source = table.getColumns().getByIndex(index)
            table.alterColumnByName(source.getPropertyValue("Name"), source.createDataDescriptor())
        self.assertEqual(self.rows("SELECT sql FROM sqlite_master WHERE name = 't'"), before)


class TableTests(SdbcxCase):
    def new_table(self, name="ordini"):
        descriptor = self.tables.createDataDescriptor()
        fill(descriptor, Name=name)
        columns = descriptor.getColumns()
        columns.appendByDescriptor(self.column_descriptor(columns, "id", "LO_BIGINT", nullable=False, auto=True))
        columns.appendByDescriptor(self.column_descriptor(columns, "cliente", "LO_INTEGER"))
        columns.appendByDescriptor(self.column_descriptor(columns, "importo", "LO_DECIMAL", 10, 2, default="1.5"))
        keys = descriptor.getKeys()
        key = keys.createDataDescriptor()
        fill(key, Type=properties.KEY_PRIMARY)
        key.getColumns().appendByDescriptor(fill(key.getColumns().createDataDescriptor(), Name="id"))
        keys.appendByDescriptor(key)
        return descriptor

    def test_create_table_from_descriptor(self):
        listener = Recorder()
        self.tables.addContainerListener(listener)
        self.tables.appendByDescriptor(self.new_table())
        self.assertEqual(listener.events, [("inserted", "ordini")])
        sql = self.rows("SELECT sql FROM sqlite_master WHERE name = 'ordini'")[0][0]
        self.assertIn('"id" INTEGER PRIMARY KEY AUTOINCREMENT', sql)
        self.assertIn('"importo" LO_DECIMAL(10,2) DEFAULT 150', sql)
        ident = self.tables.getByName("ordini").getColumns().getByName("id")
        self.assertTrue(ident.getPropertyValue("IsAutoIncrement"))

    def test_columns_described_only_by_type_code_get_the_lo_type(self):
        descriptor = self.tables.createDataDescriptor()
        fill(descriptor, Name="per_codice")
        columns = descriptor.getColumns()
        for name, code, precision, scale in (("id", 4, 0, 0), ("testo", 12, 50, 0), ("reale", 8, 0, 0),
                                             ("quando", 93, 0, 0), ("grande", -5, 0, 0), ("piccolo", 5, 0, 0),
                                             ("float", 6, 0, 0), ("bit", -7, 0, 0), ("data", 91, 0, 0),
                                             ("deci", 3, 10, 2)):
            column = columns.createDataDescriptor()
            fill(column, Name=name, Type=code, Precision=precision, Scale=scale)
            columns.appendByDescriptor(column)
        keys = descriptor.getKeys()
        key = keys.createDataDescriptor()
        fill(key, Type=properties.KEY_PRIMARY)
        key.getColumns().appendByDescriptor(fill(key.getColumns().createDataDescriptor(), Name="id"))
        keys.appendByDescriptor(key)
        self.tables.appendByDescriptor(descriptor)
        sql = self.rows("SELECT sql FROM sqlite_master WHERE name = 'per_codice'")[0][0]
        self.assertIn('"id" INTEGER PRIMARY KEY', sql)
        for expected in ('"testo" LO_VARCHAR(50)', '"reale" LO_DOUBLE', '"quando" LO_TIMESTAMP',
                         '"grande" LO_BIGINT', '"piccolo" LO_SMALLINT', '"float" LO_DOUBLE', '"bit" LO_BOOLEAN',
                         '"data" LO_DATE', '"deci" LO_DECIMAL(10,2)'):
            self.assertIn(expected, sql)

    def test_type_name_wins_over_type_code_and_unknown_code_stays_untyped(self):
        descriptor = self.tables.createDataDescriptor()
        fill(descriptor, Name="misto")
        columns = descriptor.getColumns()
        for name, type_name, code in (("a", "LO_TINYINT", 12), ("b", "", 1111), ("c", "", 0)):
            column = columns.createDataDescriptor()
            fill(column, Name=name, TypeName=type_name, Type=code)
            columns.appendByDescriptor(column)
        self.tables.appendByDescriptor(descriptor)
        sql = self.rows("SELECT sql FROM sqlite_master WHERE name = 'misto'")[0][0]
        self.assertIn('"a" LO_TINYINT', sql)
        self.assertNotIn("LO_VARCHAR", sql)
        self.assertEqual(self.rows("SELECT name, type FROM pragma_table_info('misto') ORDER BY cid"),
                         [("a", "LO_TINYINT"), ("b", ""), ("c", "")])

    def test_create_table_with_relation(self):
        descriptor = self.new_table()
        keys = descriptor.getKeys()
        key = keys.createDataDescriptor()
        fill(key, Type=properties.KEY_FOREIGN, ReferencedTable="t", UpdateRule=0, DeleteRule=2)
        columns = key.getColumns()
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="cliente", RelatedColumn="id"))
        keys.appendByDescriptor(key)
        self.tables.appendByDescriptor(descriptor)
        listed = self.tables.getByName("ordini").getKeys()
        self.assertEqual(listed.getElementNames()[0], "PK_ordini")
        foreign = listed.getByIndex(1)
        self.assertEqual(foreign.getPropertyValue("Type"), properties.KEY_FOREIGN)
        self.assertEqual(foreign.getPropertyValue("ReferencedTable"), "t")
        self.assertEqual((foreign.getPropertyValue("UpdateRule"), foreign.getPropertyValue("DeleteRule")), (0, 2))
        related = foreign.getColumns().getByIndex(0)
        self.assertEqual((related.getPropertyValue("Name"), related.getPropertyValue("RelatedColumn")),
                         ("cliente", "id"))

    def test_create_table_in_error_gives_a_message(self):
        descriptor = self.new_table("t")
        self.assertIsNotNone(self.code(self.tables.appendByDescriptor, descriptor))

    def test_drop_table_and_view(self):
        self.sql("CREATE VIEW vv AS SELECT id FROM t")
        self.sql("CREATE TABLE u(a)")
        listener = Recorder()
        self.tables.addContainerListener(listener)
        self.tables.dropByName("u")
        self.tables.dropByName("vv")
        self.assertEqual(listener.events, [("removed", "u"), ("removed", "vv")])
        self.assertEqual(self.tables.getElementNames(), ("t",))

    def test_drop_table_used_by_relation_is_refused_with_code(self):
        self.sql("CREATE TABLE f(x INTEGER REFERENCES t(id))")
        self.assertEqual(self.code(self.tables.dropByName, "t"), errors.TABLE_USED_BY_RELATIONS)
        self.assertEqual(self.tables.getElementNames(), ("f", "t"))

    def test_rename_table(self):
        table = self.tables.getByName("t")
        table.rename('"persone"')
        self.assertEqual(table.getPropertyValue("Name"), "persone")
        self.assertEqual(self.tables.getElementNames(), ("persone",))
        self.assertEqual(table.getName(), "persone")
        self.assertEqual(table.getColumns().getElementNames(), ("id", "n", "d", "p"))

    def test_create_data_descriptor_copies_columns(self):
        copy = self.tables.getByName("t").createDataDescriptor()
        self.assertEqual(copy.getColumns().getElementNames(), ("id", "n", "d", "p"))
        self.assertEqual(copy.getPropertyValue("Name"), "t")


class KeyAndIndexTests(SdbcxCase):
    def setUp(self):
        super().setUp()
        self.sql("CREATE TABLE c(id INTEGER PRIMARY KEY, nome TEXT UNIQUE);"
                 "CREATE TABLE o(id INTEGER PRIMARY KEY, cl INTEGER, v TEXT);"
                 "INSERT INTO c VALUES (1, 'a'), (2, 'b');"
                 "INSERT INTO o VALUES (1, 1, 'x'), (2, 2, 'y')")
        self.o = self.tables.getByName("o")

    def test_key_and_index_descriptors_supply_columns(self):
        from com.sun.star.sdbcx import XColumnsSupplier
        self.assertIsInstance(self.o.getKeys().createDataDescriptor(), XColumnsSupplier)
        self.assertIsInstance(self.o.getIndexes().createDataDescriptor(), XColumnsSupplier)

    def test_append_and_drop_foreign_key(self):
        keys = self.o.getKeys()
        key = keys.createDataDescriptor()
        fill(key, Type=properties.KEY_FOREIGN, ReferencedTable="c", UpdateRule=3, DeleteRule=0)
        columns = key.getColumns()
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="cl", RelatedColumn="id"))
        listener = Recorder()
        keys.addContainerListener(listener)
        keys.appendByDescriptor(key)
        name = keys.getElementNames()[-1]
        self.assertEqual(listener.events, [("inserted", name)])
        self.assertTrue(name.startswith("FK_o_cl_c_id"))
        self.assertEqual(keys.getByName(name).getPropertyValue("DeleteRule"), 0)
        keys.dropByName(name)
        self.assertEqual([n for n in keys.getElementNames() if n.startswith("FK")], [])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM o"), [(2,)])

    def test_foreign_key_violation_is_refused_with_code(self):
        self.sql("INSERT INTO o VALUES (3, 9, 'z')")
        keys = self.o.getKeys()
        key = keys.createDataDescriptor()
        fill(key, Type=properties.KEY_FOREIGN, ReferencedTable="c")
        columns = key.getColumns()
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="cl", RelatedColumn="id"))
        self.assertEqual(self.code(keys.appendByDescriptor, key), errors.RELATION_VIOLATED)

    def test_foreign_key_without_related_column_uses_target_primary_key(self):
        keys = self.o.getKeys()
        key = keys.createDataDescriptor()
        fill(key, Type=properties.KEY_FOREIGN, ReferencedTable='"c"')
        columns = key.getColumns()
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="cl"))
        keys.appendByDescriptor(key)
        self.assertEqual(self.tables.getByName("o").getKeys().getByIndex(1).getColumns().getByIndex(0)
                         .getPropertyValue("RelatedColumn"), "id")

    def test_primary_key_listed_unique_listed_and_drop(self):
        keys = self.tables.getByName("c").getKeys()
        self.assertEqual(keys.getElementNames(), ("PK_c", "UQ_c_nome"))
        self.assertEqual(keys.getByName("UQ_c_nome").getPropertyValue("Type"), properties.KEY_UNIQUE)
        keys.dropByName("UQ_c_nome")
        self.assertEqual(keys.getElementNames(), ("PK_c",))
        keys.dropByIndex(0)
        self.assertEqual(keys.getElementNames(), ())

    def test_append_primary_key(self):
        self.sql("CREATE TABLE p(a TEXT, b TEXT)")
        keys = self.tables.getByName("p").getKeys()
        key = keys.createDataDescriptor()
        fill(key, Type=properties.KEY_PRIMARY)
        columns = key.getColumns()
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="a"))
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="b"))
        keys.appendByDescriptor(key)
        self.assertEqual(keys.getElementNames(), ("PK_p",))
        self.assertEqual([c for c in keys.getByName("PK_p").getColumns().getElementNames()], ["a", "b"])

    def test_key_columns_carry_column_properties(self):
        column = self.tables.getByName("c").getKeys().getByName("PK_c").getColumns().getByName("id")
        self.assertEqual(column.getPropertyValue("TypeName"), "INTEGER")

    def test_indexes_create_list_drop_and_hide_automatic(self):
        indexes = self.tables.getByName("c").getIndexes()
        self.assertEqual(indexes.getElementNames(), ())
        descriptor = indexes.createDataDescriptor()
        fill(descriptor, Name="ix_c", IsUnique=True)
        columns = descriptor.getColumns()
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="nome", IsAscending=False))
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="id", IsAscending=True))
        listener = Recorder()
        indexes.addContainerListener(listener)
        indexes.appendByDescriptor(descriptor)
        self.assertEqual(listener.events, [("inserted", "ix_c")])
        index = indexes.getByName("ix_c")
        self.assertTrue(index.getPropertyValue("IsUnique"))
        self.assertFalse(index.getPropertyValue("IsPrimaryKeyIndex"))
        self.assertEqual([(c.getPropertyValue("Name"), c.getPropertyValue("IsAscending"))
                          for c in (index.getColumns().getByIndex(i) for i in range(2))],
                         [("nome", False), ("id", True)])
        indexes.dropByName("ix_c")
        self.assertEqual(indexes.getElementNames(), ())

    def test_duplicate_values_in_unique_index_are_refused(self):
        self.sql("INSERT INTO o VALUES (3, 1, 'x')")
        indexes = self.o.getIndexes()
        descriptor = indexes.createDataDescriptor()
        fill(descriptor, Name="iu", IsUnique=True)
        columns = descriptor.getColumns()
        columns.appendByDescriptor(fill(columns.createDataDescriptor(), Name="v"))
        self.assertIsNotNone(self.code(indexes.appendByDescriptor, descriptor))
        self.assertEqual(indexes.getElementNames(), ())


class ViewTests(SdbcxCase):
    def test_create_list_alter_drop(self):
        views = self.catalog.getViews()
        descriptor = views.createDataDescriptor()
        fill(descriptor, Name="vv", Command="SELECT id, n FROM t")
        views.appendByDescriptor(descriptor)
        view = views.getByName("vv")
        self.assertEqual(view.getPropertyValue("Command"), "SELECT id, n FROM t")
        view.alterCommand("SELECT id FROM t")
        self.assertEqual(self.rows("SELECT * FROM vv ORDER BY id"), [(1,), (2,)])
        self.assertEqual(view.getPropertyValue("Command"), "SELECT id FROM t")
        views.dropByName("vv")
        self.assertEqual(views.getElementNames(), ())

    def test_alter_with_error_keeps_old_view(self):
        self.sql("CREATE VIEW vv AS SELECT id FROM t")
        view = self.catalog.getViews().getByName("vv")
        self.assertEqual(self.code(view.alterCommand, "SELECT nope FROM t"), errors.VIEW_NOT_ALTERED)
        self.assertEqual(self.rows("SELECT * FROM vv ORDER BY id"), [(1,), (2,)])

    def test_append_of_a_view_already_created_by_sql_is_accepted(self):
        self.sql("CREATE VIEW vv AS SELECT id FROM t")
        views = self.catalog.getViews()
        descriptor = fill(views.createDataDescriptor(), Name="vv", Command="SELECT id FROM t")
        views.appendByDescriptor(descriptor)
        self.assertEqual(views.getElementNames(), ("vv",))

    def test_view_in_tables_list_has_columns(self):
        self.sql("CREATE VIEW vv AS SELECT id, n FROM t")
        self.assertEqual(self.tables.getByName("vv").getColumns().getElementNames(), ("id", "n"))
        self.assertEqual(self.tables.getByName("vv").getKeys().getElementNames(), ())


class RefreshTests(SdbcxCase):
    def test_refresh_notifies_listeners_and_rereads(self):
        seen = []

        class Listener:
            def refreshed(self, event):
                seen.append(event)

            def disposing(self, event):
                pass

        self.tables.addRefreshListener(Listener())
        self.sql("CREATE TABLE u(a)")
        self.tables.refresh()
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.tables.getElementNames(), ("t", "u"))


class SqlLogTests(SdbcxCase):
    def test_rename_column_is_written_to_the_log(self):
        from sdbc_pysqlite import logger
        table = self.tables.getByName("t")
        columns = table.getColumns()
        table.alterColumnByName("n", self.column_descriptor(columns, "nome", "LO_VARCHAR", 40, nullable=False))
        with open(logger._state["file"], encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("INFO", text)
        self.assertIn("column <n> of <t> renamed to <nome>", text)


if __name__ == "__main__":
    unittest.main()
