# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest
from collections import namedtuple

import support

from sdbc_pysqlite import engine
from sdbc_pysqlite import errors
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import structure
from sdbc_pysqlite import tabledef
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.structure import ColumnSpec

Options = namedtuple("Options", "full_load_limit window_size transaction_mode auto_increment_reuse")

ORDERS = '''CREATE TABLE "Ordini" (
  "ID" INTEGER PRIMARY KEY AUTOINCREMENT,
  "Cliente" LO_VARCHAR(50) NOT NULL DEFAULT 'x' COLLATE NOCASE,
  "Importo" LO_DECIMAL(10,2) DEFAULT 0 CHECK("Importo">=0),
  "Rif" INT REFERENCES Clienti(id) ON DELETE CASCADE,
  g INT GENERATED ALWAYS AS (Importo*2) STORED,
  UNIQUE ("Cliente"),
  FOREIGN KEY ("Cliente") REFERENCES Altro ("n")
) WITHOUT ROWID'''


class TableDefTests(unittest.TestCase):
    def test_round_trip_is_exact(self):
        self.assertEqual(tabledef.parse(ORDERS).render(), ORDERS)

    def test_columns_and_clauses(self):
        definition = tabledef.parse(ORDERS)
        names = [c.plain_name for c in definition.columns]
        self.assertEqual(names, ["ID", "Cliente", "Importo", "Rif", "g"])
        client = definition.column("cliente")
        self.assertEqual(client.label, "LO_VARCHAR(50)")
        self.assertEqual([c.kind for c in client.clauses], ["NOTNULL", "DEFAULT", "COLLATE"])
        self.assertEqual([c.kind for c in definition.column("g").clauses], ["OTHER"])
        self.assertTrue(definition.without_rowid)

    def test_primary_key_and_foreign_keys(self):
        definition = tabledef.parse(ORDERS)
        self.assertEqual(definition.primary_key(), ["ID"])
        found = [(sources, target) for _item, sources, target in definition.foreign_keys()]
        self.assertEqual(found, [(["Rif"], "Clienti"), (["Cliente"], "Altro")])

    def test_set_primary_key_single_integer_becomes_alias(self):
        definition = tabledef.parse('CREATE TABLE t (a LO_BIGINT NOT NULL, b TEXT)')
        alias = definition.set_primary_key(["a"], True)
        self.assertEqual(alias, "a")
        self.assertEqual(definition.render(), 'CREATE TABLE t (a INTEGER PRIMARY KEY AUTOINCREMENT, b TEXT)')

    def test_set_primary_key_composite_is_a_constraint(self):
        definition = tabledef.parse('CREATE TABLE t (a INT, b TEXT)')
        self.assertIsNone(definition.set_primary_key(["a", "b"], True))
        self.assertIn('PRIMARY KEY ("a", "b")', definition.render())
        self.assertEqual(definition.primary_key(), ["a", "b"])

    def test_remove_primary_key(self):
        definition = tabledef.parse('CREATE TABLE t (a INTEGER PRIMARY KEY AUTOINCREMENT, b TEXT)')
        definition.set_primary_key([], True)
        self.assertEqual(definition.primary_key(), [])
        self.assertNotIn("PRIMARY", definition.render())
        self.assertNotIn("AUTOINCREMENT", definition.render())

    def test_untouched_columns_keep_their_text(self):
        definition = tabledef.parse('CREATE TABLE t (\n  a   INT   NOT NULL,\n  b TEXT\n)')
        definition.column("b").label = "LO_VARCHAR(3)"
        self.assertEqual(definition.render(), 'CREATE TABLE t (\n  a   INT   NOT NULL,\n  b LO_VARCHAR(3)\n)')

    def test_unreadable_text(self):
        self.assertIsNone(tabledef.parse("CREATE VIEW v AS SELECT 1"))
        self.assertIsNone(tabledef.parse("CREATE TABLE t AS SELECT 1"))

    def test_default_literal(self):
        decimal = tabledef.ts.classify("LO_DECIMAL(10,2)")
        self.assertEqual(tabledef.default_literal("1.5", decimal), "150")
        self.assertEqual(tabledef.default_literal("abc", tabledef.ts.classify("LO_VARCHAR(5)")), "'abc'")
        self.assertEqual(tabledef.default_literal("it's", tabledef.ts.classify("LO_VARCHAR(5)")), "'it''s'")
        self.assertEqual(tabledef.default_literal("true", tabledef.ts.classify("LO_BOOLEAN")), "1")
        self.assertEqual(tabledef.default_literal("7", tabledef.ts.classify("LO_INTEGER")), "7")
        self.assertIsNone(tabledef.default_literal("", tabledef.ts.classify("LO_INTEGER")))


class StructureCase(unittest.TestCase):
    reuse = False

    def setUp(self):
        self.db = sqlite.connect(":memory:", isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.engine = engine.Engine(self.db, Options(100, 50, "free", self.reuse))

    def sql(self, text, params=()):
        return self.db.execute(text, params)

    def all(self, text, params=()):
        return self.db.execute(text, params).fetchall()

    def master(self, name):
        return self.db.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]

    def expect(self, code, action, **values):
        with self.assertRaises(DriverError) as caught:
            action()
        self.assertEqual(caught.exception.code, code)
        for key, value in values.items():
            self.assertEqual(caught.exception.values[key], value, key)
        return caught.exception

    def columns(self, table):
        return [(c.name, c.label, c.notnull) for c in schema.table_columns(self.db, table)]


class DirectOperationTests(StructureCase):
    def setUp(self):
        super().setUp()
        self.sql('CREATE TABLE "Clienti" ("id" INTEGER PRIMARY KEY, "nome" LO_VARCHAR(20))')
        self.sql('CREATE TABLE "Ordini" ("id" INTEGER PRIMARY KEY, "cliente" INTEGER REFERENCES "Clienti"("id"), '
                 '"nota" TEXT)')
        self.sql("INSERT INTO Clienti VALUES (1, 'a'), (2, 'b')")
        self.sql("INSERT INTO Ordini VALUES (1, 1, 'x')")

    def test_drop_table_used_by_relations_is_refused(self):
        self.expect(errors.TABLE_USED_BY_RELATIONS, lambda: structure.drop_table(self.engine, "Clienti"),
                    tabelle="Ordini")
        self.assertTrue(self.all("SELECT * FROM Clienti"))

    def test_drop_table_free_and_self_reference(self):
        structure.drop_table(self.engine, "Ordini")
        self.sql('CREATE TABLE "Albero" ("id" INTEGER PRIMARY KEY, "padre" INTEGER REFERENCES "Albero"("id"))')
        structure.drop_table(self.engine, "Albero")
        structure.drop_table(self.engine, "Clienti")
        self.assertEqual(schema.list_objects(self.db), [])

    def test_rename_table_keeps_relations_and_views(self):
        self.sql('CREATE VIEW "v" AS SELECT * FROM "Clienti"')
        structure.rename_table(self.engine, "Clienti", "Persone")
        self.assertEqual(self.all("SELECT * FROM v ORDER BY 1"), [(1, "a"), (2, "b")])
        self.assertEqual(schema.foreign_keys(self.db, "Ordini")[0].target_table, "Persone")

    def test_rename_column(self):
        self.sql('CREATE VIEW "v" AS SELECT "nome" FROM "Clienti"')
        structure.rename_column(self.engine, "Clienti", "nome", "etichetta")
        self.assertEqual(self.all("SELECT * FROM v ORDER BY 1"), [("a",), ("b",)])

    def test_add_simple_column(self):
        rebuilt = structure.add_column(self.engine, "Clienti", ColumnSpec("eta", "LO_INTEGER", False, "18", False))
        self.assertFalse(rebuilt)
        self.assertEqual(self.all('SELECT "eta" FROM Clienti'), [(18,), (18,)])

    def test_add_required_column_on_full_table_is_refused(self):
        self.expect(errors.COLUMN_NOT_NULL_NO_DEFAULT,
                    lambda: structure.add_column(self.engine, "Clienti", ColumnSpec("x", "LO_INTEGER", True, None, False)),
                    n=2)

    def test_add_required_column_on_empty_table_rebuilds(self):
        self.sql("DELETE FROM Ordini")
        rebuilt = structure.add_column(self.engine, "Ordini", ColumnSpec("x", "LO_INTEGER", True, None, False))
        self.assertTrue(rebuilt)
        self.assertIn(("x", "LO_INTEGER", True), self.columns("Ordini"))

    def test_add_auto_value_column_numbers_the_rows(self):
        self.sql('CREATE TABLE "Righe" ("t" TEXT)')
        self.sql("INSERT INTO Righe VALUES ('a'), ('b'), ('c')")
        structure.add_column(self.engine, "Righe", ColumnSpec("n", "LO_BIGINT", True, None, True))
        self.assertEqual(self.all('SELECT "n", "t" FROM Righe ORDER BY 1'), [(1, "a"), (2, "b"), (3, "c")])
        self.assertIn("AUTOINCREMENT", self.master("Righe"))

    def test_add_auto_value_when_table_has_key_is_refused(self):
        self.expect(errors.AUTO_VALUE_IMPOSSIBLE,
                    lambda: structure.add_column(self.engine, "Clienti", ColumnSpec("n", "LO_BIGINT", True, None, True)))

    def test_create_and_drop_index(self):
        structure.create_index(self.engine, "Clienti", "ix", True, [("nome", True), ("id", False)])
        self.assertIn('UNIQUE INDEX "ix"', self.master("ix"))
        structure.drop_index(self.engine, "ix")
        self.assertEqual(self.all("SELECT name FROM sqlite_master WHERE name = 'ix'"), [])

    def test_direct_operations_join_the_open_transaction(self):
        self.engine.set_autocommit(False)
        structure.rename_column(self.engine, "Clienti", "nome", "n2")
        self.assertTrue(self.db.in_transaction)
        self.engine.rollback()
        self.assertEqual([c[0] for c in self.columns("Clienti")], ["id", "nome"])


class DropColumnTests(StructureCase):
    def setUp(self):
        super().setUp()
        self.sql('CREATE TABLE "t" ("id" INTEGER PRIMARY KEY, "a" TEXT, "b" TEXT, "c" TEXT UNIQUE, "d" TEXT, '
                 '"e" TEXT, UNIQUE ("d", "e"))')
        self.sql("INSERT INTO t VALUES (1, 'a', 'b', 'c', 'd', 'e')")

    def test_free_column(self):
        self.assertEqual(structure.drop_column(self.engine, "t", "a"), [])
        self.assertNotIn("a", [c[0] for c in self.columns("t")])

    def test_indexes_go_with_the_column(self):
        self.sql('CREATE INDEX "i1" ON t ("a")')
        self.sql('CREATE INDEX "i2" ON t ("a", "b")')
        self.sql('CREATE UNIQUE INDEX "i3" ON t ("a")')
        dropped = structure.drop_column(self.engine, "t", "a")
        self.assertEqual(sorted(dropped), ["i1", "i2", "i3"])
        self.assertEqual(self.all("SELECT name FROM sqlite_master WHERE name LIKE 'i%'"), [])
        self.assertEqual(self.all('SELECT "b" FROM t'), [("b",)])

    def test_unique_column_rebuilds(self):
        structure.drop_column(self.engine, "t", "c")
        self.assertEqual([c[0] for c in self.columns("t")], ["id", "a", "b", "d", "e"])
        self.assertEqual(self.all("SELECT * FROM t"), [(1, "a", "b", "d", "e")])

    def test_table_unique_constraint_is_removed_whole(self):
        structure.drop_column(self.engine, "t", "d")
        self.assertEqual([c[0] for c in self.columns("t")], ["id", "a", "b", "c", "e"])
        self.assertNotIn("UNIQUE (\"d\"", self.master("t"))
        self.sql("INSERT INTO t VALUES (2, 'a', 'b', 'c2', 'e')")
        self.sql("INSERT INTO t VALUES (3, 'a', 'b', 'c3', 'e')")

    def test_primary_key_is_refused(self):
        self.expect(errors.COLUMN_IN_USE, lambda: structure.drop_column(self.engine, "t", "id"), colonna="id")

    def test_relation_view_trigger_are_refused(self):
        self.sql('CREATE TABLE "f" ("x" INTEGER REFERENCES t("id"), "y" TEXT)')
        self.expect(errors.COLUMN_IN_USE, lambda: structure.drop_column(self.engine, "f", "x"))
        self.sql('CREATE VIEW "v" AS SELECT "a" FROM t')
        error = self.expect(errors.COLUMN_IN_USE, lambda: structure.drop_column(self.engine, "t", "a"))
        self.assertIn('VIEW "v"', error.values["oggetti"])
        self.sql('CREATE TRIGGER "tr" AFTER INSERT ON t BEGIN UPDATE t SET "b" = 1 WHERE id = new.id; END')
        error = self.expect(errors.COLUMN_IN_USE, lambda: structure.drop_column(self.engine, "t", "b"))
        self.assertIn('TRIGGER "tr"', error.values["oggetti"])
        self.assertIn("a", [c[0] for c in self.columns("t")])


class RebuildTests(StructureCase):
    def setUp(self):
        super().setUp()
        self.sql('CREATE TABLE "Clienti" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "nome" LO_VARCHAR(20))')
        self.sql('CREATE TABLE "Ordini" ("id" INTEGER PRIMARY KEY AUTOINCREMENT, "cliente" INTEGER NOT NULL '
                 'REFERENCES "Clienti"("id") ON DELETE CASCADE, "importo" LO_DECIMAL(10,2) DEFAULT 150, '
                 '"nota" LO_VARCHAR(30), "peso" LO_DOUBLE, "codice" LO_VARCHAR(10))')
        self.sql("INSERT INTO Clienti (nome) VALUES ('a'), ('b')")
        self.sql("INSERT INTO Ordini (cliente, importo, nota, peso, codice) VALUES "
                 "(1, 1235, 'n1', 0.30000000000000004, '12'), (1, 99999, 'n2', 12.9, '7'), (2, NULL, NULL, NULL, NULL)")
        self.sql('CREATE INDEX "ix_nota" ON Ordini ("nota")')
        self.sql('CREATE VIEW "v" AS SELECT "id", "nota" FROM Ordini')
        self.sql('CREATE TRIGGER "tr" AFTER INSERT ON Ordini BEGIN UPDATE Ordini SET "nota" = coalesce(new."nota", \'t\') '
                 'WHERE id = new.id; END')

    def alter(self, name, label=None, not_null=None, default="KEEP", auto=False, new_name=None):
        info = {c.name: c for c in schema.table_columns(self.db, "Ordini")}[name]
        old_default = structure.visible_default(info.default, structure.ts.classify(info.label))
        spec = ColumnSpec(new_name or name, label or info.label, info.notnull if not_null is None else not_null,
                          old_default if default == "KEEP" else default, auto)
        return structure.alter_column(self.engine, "Ordini", name, spec)

    def test_everything_unmodified_is_kept(self):
        self.alter("nota", "LO_VARCHAR(40)")
        self.assertEqual(self.all("SELECT cliente, nota FROM Ordini ORDER BY id"), [(1, "n1"), (1, "n2"), (2, None)])
        self.assertEqual(self.all("SELECT name FROM sqlite_master WHERE type IN ('index','trigger','view') "
                                  "AND name NOT LIKE 'sqlite_%' ORDER BY name"), [("ix_nota",), ("tr",), ("v",)])
        self.assertEqual(self.all("SELECT * FROM v ORDER BY id")[0], (1, "n1"))
        self.assertEqual(self.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertIn("LO_VARCHAR(40)", self.master("Ordini"))
        self.assertIn('DEFAULT 150', self.master("Ordini"))

    def test_relation_cascade_does_not_delete_rows(self):
        self.alter("nota", "LO_VARCHAR(40)")
        structure.alter_column(self.engine, "Clienti", "nome", ColumnSpec("nome", "LO_VARCHAR(30)", False, None, False))
        self.assertEqual(self.all("SELECT COUNT(*) FROM Ordini"), [(3,)])
        self.assertEqual(self.all("SELECT COUNT(*) FROM Clienti"), [(2,)])

    def test_less_decimals_rounds_half_up(self):
        self.alter("importo", "LO_DECIMAL(10,1)")
        self.assertEqual(self.all("SELECT importo FROM Ordini ORDER BY id"), [(124,), (10000,), (None,)])

    def test_more_decimals_scales_up(self):
        self.alter("importo", "LO_DECIMAL(12,3)")
        self.assertEqual(self.all("SELECT importo FROM Ordini ORDER BY id"), [(12350,), (999990,), (None,)])

    def test_decimal_to_integer_truncates(self):
        self.alter("importo", "LO_INTEGER", default=None)
        self.assertEqual(self.all("SELECT importo FROM Ordini ORDER BY id"), [(12,), (999,), (None,)])

    def test_double_to_decimal_goes_through_text(self):
        self.alter("peso", "LO_DECIMAL(10,2)")
        self.assertEqual(self.all("SELECT peso FROM Ordini ORDER BY id"), [(30,), (1290,), (None,)])

    def test_double_to_integer_truncates(self):
        self.alter("peso", "LO_INTEGER")
        self.assertEqual(self.all("SELECT peso FROM Ordini ORDER BY id"), [(0,), (12,), (None,)])

    def test_text_to_integer(self):
        self.alter("codice", "LO_INTEGER")
        self.assertEqual(self.all("SELECT codice FROM Ordini ORDER BY id"), [(12,), (7,), (None,)])

    def test_text_that_is_not_a_number_is_refused_with_count_and_example(self):
        error = self.expect(errors.CONVERSION_IMPOSSIBLE, lambda: self.alter("nota", "LO_INTEGER"),
                            colonna="nota", n=2, valore="n1")
        self.assertEqual(error.values["chiave"], "id = 1")
        self.assertEqual(self.all("SELECT nota FROM Ordini WHERE id < 3 ORDER BY id"), [("n1",), ("n2",)])
        self.assertIn("LO_VARCHAR(30)", self.master("Ordini"))

    def test_too_many_digits_is_refused(self):
        self.expect(errors.CONVERSION_TOO_MANY_DIGITS, lambda: self.alter("importo", "LO_DECIMAL(4,1)"),
                    colonna="importo", n=1)
        self.assertEqual(self.all("SELECT importo FROM Ordini WHERE id = 2"), [(99999,)])

    def test_integer_range_is_checked(self):
        self.sql("UPDATE Ordini SET codice = '70000' WHERE id = 1")
        self.expect(errors.CONVERSION_TOO_MANY_DIGITS, lambda: self.alter("codice", "LO_SMALLINT"), n=1)

    def test_required_with_empty_cells_is_refused(self):
        self.expect(errors.CONVERSION_NULLS, lambda: self.alter("nota", not_null=True), colonna="nota", n=1,
                    chiave="id = 3")
        self.sql("UPDATE Ordini SET nota = 'z' WHERE nota IS NULL")
        self.alter("nota", not_null=True)
        self.assertIn('"nota" LO_VARCHAR(30) NOT NULL', self.master("Ordini"))

    def test_default_value_change_and_empty_default_keeps_it(self):
        self.alter("importo", default="2.5")
        self.assertIn("DEFAULT 250", self.master("Ordini"))
        self.alter("importo", "LO_DECIMAL(12,2)", default=None)
        self.assertIn("DEFAULT 250", self.master("Ordini"))

    def test_default_survives_other_changes_made_by_base(self):
        self.sql("CREATE TABLE T (id INTEGER PRIMARY KEY, a LO_VARCHAR(10) DEFAULT 'x', "
                 "b LO_DECIMAL(10,2) DEFAULT 150, c LO_INTEGER)")
        spec = lambda name, label, nn: ColumnSpec(name, label, nn, None, False)
        structure.alter_column(self.engine, "T", "a", spec("a", "LO_VARCHAR(20)", False))
        structure.alter_column(self.engine, "T", "c", spec("c", "LO_INTEGER", True))
        text = self.master("T")
        self.assertIn("LO_VARCHAR(20) DEFAULT 'x'", text)
        self.assertIn("LO_DECIMAL(10,2) DEFAULT 150", text)

    def test_default_is_rewritten_when_type_or_decimals_change(self):
        spec = lambda label: ColumnSpec("importo", label, False, None, False)
        structure.alter_column(self.engine, "Ordini", "importo", spec("LO_DECIMAL(10,1)"))
        self.assertIn("LO_DECIMAL(10,1) DEFAULT 15", self.master("Ordini"))
        structure.alter_column(self.engine, "Ordini", "importo", spec("LO_DECIMAL(10,3)"))
        self.assertIn("LO_DECIMAL(10,3) DEFAULT 1500", self.master("Ordini"))
        structure.alter_column(self.engine, "Ordini", "importo", spec("LO_BIGINT"))
        self.assertIn("LO_BIGINT DEFAULT 1", self.master("Ordini"))

    def test_unchanged_default_text_is_not_a_change(self):
        before = self.master("Ordini")
        self.alter("importo")
        self.assertEqual(self.master("Ordini"), before)

    def test_column_in_relation_cannot_change_type(self):
        info = {c.name: c for c in schema.table_columns(self.db, "Ordini")}["cliente"]
        error = self.expect(errors.COLUMN_IN_RELATION,
                            lambda: structure.alter_column(self.engine, "Ordini", "cliente",
                                                           ColumnSpec("cliente", "LO_VARCHAR(5)", True, None, False)),
                            colonna="cliente", tabella="Clienti")
        self.assertTrue(error.values["relazione"].startswith("FK_Ordini_cliente_Clienti_id"))
        self.assertEqual(info.label, "INTEGER")

    def test_rename_and_change_together(self):
        done = self.alter("nota", "LO_VARCHAR(40)", new_name="annotazione")
        self.assertEqual(done, ["rename", "rebuild"])
        self.assertIn("annotazione", [c[0] for c in self.columns("Ordini")])
        self.assertEqual(self.all("SELECT annotazione FROM v ORDER BY id")[0], ("n1",))

    def test_pending_changes_refuse_the_rebuild(self):
        self.engine.set_autocommit(False)
        self.engine.run("INSERT INTO Clienti (nome) VALUES ('c')")
        self.expect(errors.PENDING_CHANGES, lambda: self.alter("nota", "LO_VARCHAR(40)"), tabella="Ordini")
        self.assertTrue(self.db.in_transaction)
        self.engine.rollback()

    def test_auto_value_counter_is_carried_on(self):
        self.sql("DELETE FROM Ordini WHERE id = 3")
        self.alter("nota", "LO_VARCHAR(40)")
        self.sql("INSERT INTO Ordini (cliente) VALUES (1)")
        self.assertEqual(self.all("SELECT MAX(id) FROM Ordini"), [(4,)])

    def test_reuse_setting_drives_the_rewritten_table(self):
        self.engine.options = Options(100, 50, "free", True)
        self.alter("nota", "LO_VARCHAR(40)")
        self.assertNotIn("AUTOINCREMENT", self.master("Ordini"))
        self.engine.options = Options(100, 50, "free", False)
        self.alter("nota", "LO_VARCHAR(41)")
        self.assertIn("AUTOINCREMENT", self.master("Ordini"))

    def test_set_primary_key_with_duplicates_is_refused(self):
        self.sql('CREATE TABLE "p" ("a" TEXT, "b" TEXT)')
        self.sql("INSERT INTO p VALUES ('x', '1'), ('x', '2'), ('y', '3')")
        self.expect(errors.PRIMARY_KEY_DUPLICATES, lambda: structure.set_primary_key(self.engine, "p", ["a"]),
                    n=1, valore="x")
        self.assertEqual(self.db.execute("PRAGMA table_info(p)").fetchall()[0][5], 0)
        structure.set_primary_key(self.engine, "p", ["a", "b"])
        self.assertEqual(schema.primary_key_columns(self.db, "p"), [(1, "a"), (2, "b")])
        self.assertEqual(len(self.all("SELECT * FROM p")), 3)

    def test_set_primary_key_with_empty_cells_is_refused(self):
        self.sql('CREATE TABLE "p" ("a" TEXT)')
        self.sql("INSERT INTO p VALUES ('x'), (NULL)")
        self.expect(errors.CONVERSION_NULLS, lambda: structure.set_primary_key(self.engine, "p", ["a"]), n=1)

    def test_remove_primary_key(self):
        self.sql('CREATE TABLE "p" ("a" INTEGER PRIMARY KEY, "b" TEXT)')
        self.sql("INSERT INTO p VALUES (1, 'x')")
        structure.set_primary_key(self.engine, "p", [])
        self.assertEqual(schema.primary_key_columns(self.db, "p"), [])
        self.assertEqual(self.all("SELECT * FROM p"), [(1, "x")])

    def test_add_foreign_key_checks_the_data(self):
        self.sql('CREATE TABLE "r" ("id" INTEGER PRIMARY KEY, "cl" INTEGER)')
        self.sql("INSERT INTO r VALUES (1, 1), (2, 9), (3, 8), (4, NULL)")
        self.expect(errors.RELATION_VIOLATED,
                    lambda: structure.add_foreign_key(self.engine, "r", ["cl"], "Clienti", ["id"], 3, 3),
                    n=2, tabella="r", tabellaRif="Clienti", colonna="cl", valore="9")
        self.sql("DELETE FROM r WHERE cl IN (8, 9)")
        structure.add_foreign_key(self.engine, "r", ["cl"], "Clienti", ["id"], 0, 2)
        keys = schema.foreign_keys(self.db, "r")
        self.assertEqual([(k.target_table, k.pairs, k.update_rule, k.delete_rule) for k in keys],
                         [("Clienti", [("cl", "id")], 0, 2)])
        self.assertEqual(len(self.all("SELECT * FROM r")), 2)

    def test_drop_foreign_key(self):
        name = schema.foreign_keys(self.db, "Ordini")[0].name
        self.assertTrue(structure.drop_foreign_key(self.engine, "Ordini", name))
        self.assertEqual(schema.foreign_keys(self.db, "Ordini"), [])
        self.assertFalse(structure.drop_foreign_key(self.engine, "Ordini", name))
        self.assertEqual(self.all("SELECT COUNT(*) FROM Ordini"), [(3,)])

    def test_auto_key_column_keeps_integer_when_base_resends_big_integer(self):
        before = self.master("Ordini")
        done = self.alter("id", label="LO_BIGINT", not_null=True, auto=True)
        self.assertEqual(done, [])
        self.assertEqual(self.master("Ordini"), before)
        self.assertIn("INTEGER PRIMARY KEY AUTOINCREMENT", before)

    def test_existing_column_becomes_automatic_key_when_table_has_no_key(self):
        self.sql('CREATE TABLE "k2" ("t" TEXT, "n" INTEGER)')
        self.sql("INSERT INTO k2 VALUES ('a', NULL), ('b', 5), ('c', NULL)")
        done = structure.alter_column(self.engine, "k2", "n", ColumnSpec("n", "LO_BIGINT", True, None, True))
        self.assertEqual(done, ["rebuild"])
        self.assertIn('"n" INTEGER PRIMARY KEY AUTOINCREMENT', self.master("k2"))
        self.assertEqual(self.all("SELECT t, n FROM k2 ORDER BY n"), [("a", 1), ("b", 5), ("c", 6)])
        self.assertFalse(structure.set_primary_key(self.engine, "k2", ["n"]))

    def test_automatic_key_refused_for_duplicates_or_other_key(self):
        self.sql('CREATE TABLE "k3" ("t" TEXT, "n" INTEGER)')
        self.sql("INSERT INTO k3 VALUES ('a', 1), ('b', 1)")
        self.expect(errors.PRIMARY_KEY_DUPLICATES,
                    lambda: structure.alter_column(self.engine, "k3", "n", ColumnSpec("n", "LO_BIGINT", True, None, True)))
        self.sql('CREATE TABLE "k4" ("t" TEXT PRIMARY KEY, "n" INTEGER)')
        self.expect(errors.AUTO_VALUE_IMPOSSIBLE,
                    lambda: structure.alter_column(self.engine, "k4", "n", ColumnSpec("n", "LO_BIGINT", True, None, True)))

    def test_make_column_auto_value(self):
        self.sql('CREATE TABLE "k" ("n" LO_BIGINT PRIMARY KEY, "t" TEXT)')
        self.sql("INSERT INTO k VALUES (5, 'a'), (9, 'b')")
        structure.alter_column(self.engine, "k", "n", ColumnSpec("n", "LO_BIGINT", True, None, True))
        self.assertIn("INTEGER PRIMARY KEY AUTOINCREMENT", self.master("k"))
        self.assertEqual(self.all("SELECT n FROM k ORDER BY n"), [(5,), (9,)])
        self.expect(errors.AUTO_VALUE_IMPOSSIBLE,
                    lambda: structure.alter_column(self.engine, "Ordini", "nota",
                                                   ColumnSpec("nota", "LO_BIGINT", True, None, True)))

    def test_unreadable_definition(self):
        self.expect(errors.DEFINITION_NOT_UNDERSTOOD, lambda: structure.load_definition(self.db, "nessuna"))


class ViewTests(StructureCase):
    def setUp(self):
        super().setUp()
        self.sql('CREATE TABLE "t" ("a" INTEGER, "d" LO_DECIMAL(10,2))')
        self.sql("INSERT INTO t VALUES (1, 150)")

    def test_create_view_translates_decimals(self):
        structure.create_view(self.engine, "v", 'SELECT "d" + 1 AS x FROM "t"')
        self.assertEqual(self.all("SELECT x FROM v"), [(2.5,)])

    def test_alter_view_is_atomic(self):
        structure.create_view(self.engine, "v", 'SELECT "a" FROM "t"')
        structure.alter_view(self.engine, "v", 'SELECT "a" + 1 AS b FROM "t"')
        self.assertEqual(self.all("SELECT b FROM v"), [(2,)])
        self.expect(errors.VIEW_NOT_ALTERED, lambda: structure.alter_view(self.engine, "v", "SELECT nope FROM t"),
                    vista="v")
        self.assertEqual(self.all("SELECT b FROM v"), [(2,)])
        self.assertFalse(self.db.in_transaction)

    def test_drop_view(self):
        structure.create_view(self.engine, "v", 'SELECT "a" FROM "t"')
        structure.drop_view(self.engine, "v")
        self.assertEqual(self.all("SELECT name FROM sqlite_master WHERE type = 'view'"), [])


class CreateTableTests(StructureCase):
    def test_create_with_primary_key_and_relation(self):
        self.sql('CREATE TABLE "p" ("id" INTEGER PRIMARY KEY)')
        columns = [ColumnSpec("id", "INTEGER", True, None, True), ColumnSpec("rif", "INTEGER", False, None, False),
                   ColumnSpec("nota", "LO_VARCHAR(20)", False, "x", False)]
        structure.create_table(self.engine, "c", columns, ["id"], [(["rif"], "p", ["id"], 3, 0)])
        self.assertEqual([c[0] for c in self.columns("c")], ["id", "rif", "nota"])
        self.assertEqual(schema.primary_key_columns(self.db, "c"), [(1, "id")])
        self.assertEqual(len(schema.foreign_keys(self.db, "c")), 1)

    def test_auto_value_needs_the_single_primary_key(self):
        columns = [ColumnSpec("a", "INTEGER", True, None, True), ColumnSpec("b", "INTEGER", True, None, False)]
        self.expect(errors.AUTO_VALUE_IMPOSSIBLE, lambda: structure.create_table(self.engine, "x", columns, ["a", "b"], []),
                    colonna="a")
        self.expect(errors.AUTO_VALUE_IMPOSSIBLE, lambda: structure.create_table(self.engine, "x", columns, [], []),
                    colonna="a")


class DropUniqueTests(StructureCase):
    def test_drop_unique_rebuilds_without_constraint(self):
        self.sql('CREATE TABLE "u" ("a" INTEGER, "b" TEXT, UNIQUE ("b"))')
        self.sql("INSERT INTO u VALUES (1, 'x')")
        self.assertTrue(structure.drop_unique(self.engine, "u", ["b"]))
        self.sql("INSERT INTO u VALUES (2, 'x')")
        self.assertEqual(self.all("SELECT count(*) FROM u"), [(2,)])

    def test_drop_unique_missing_returns_false(self):
        self.sql('CREATE TABLE "u" ("a" INTEGER)')
        self.assertFalse(structure.drop_unique(self.engine, "u", ["a"]))


class ViewCommandTests(unittest.TestCase):
    def test_extracts_select(self):
        self.assertEqual(structure.view_command('CREATE VIEW "v" AS SELECT a FROM t'), "SELECT a FROM t")

    def test_as_inside_column_list_is_ignored(self):
        self.assertEqual(structure.view_command('CREATE VIEW v(x) AS SELECT a AS x FROM t'), "SELECT a AS x FROM t")

    def test_plain_text_is_returned(self):
        self.assertEqual(structure.view_command(" SELECT 1 "), "SELECT 1")


class LabelTests(unittest.TestCase):
    def test_column_label(self):
        self.assertEqual(structure.column_label("LO_DECIMAL", 10, 2), "LO_DECIMAL(10,2)")
        self.assertEqual(structure.column_label("LO_VARCHAR", 50, 0), "LO_VARCHAR(50)")
        self.assertEqual(structure.column_label("LO_VARCHAR", 0, 0), "LO_VARCHAR")
        self.assertEqual(structure.column_label("LO_TIMESTAMP", 29, 3), "LO_TIMESTAMP(3)")
        self.assertEqual(structure.column_label("LO_INTEGER", 10, 0), "LO_INTEGER")
        self.assertEqual(structure.column_label("INTEGER", 0, 0), "INTEGER")
        self.assertEqual(structure.column_label("VARCHAR", 50, 0), "VARCHAR")

    def test_same_type(self):
        self.assertTrue(structure.same_type("", "LO_VARIANT"))
        self.assertTrue(structure.same_type("VARCHAR(50)", "VARCHAR"))
        self.assertFalse(structure.same_type("LO_DECIMAL(10,2)", "LO_DECIMAL(10,3)"))


if __name__ == "__main__":
    unittest.main()
