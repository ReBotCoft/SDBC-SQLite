# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from collections import namedtuple
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP

from sdbc_pysqlite import decimals
from sdbc_pysqlite import dialect
from sdbc_pysqlite import errors
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import tabledef
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.engine import driver_error
from sdbc_pysqlite.errors import DriverError

ColumnSpec = namedtuple("ColumnSpec", "name label not_null default auto_value")

Copy = namedtuple("Copy", "name source convert label")

INT64_MIN = -(2 ** 63)
INT64_MAX = 2 ** 63 - 1


def _q(name):
    return sqltext.quote_name(name)


def column_label(type_name, precision, scale):
    native = ts.strict_native(type_name)
    if native is not None:
        return native
    entry = ts.LO_BY_NAME.get((type_name or "").upper())
    name = (type_name or "").upper() if entry is not None else (type_name or "")
    params = entry["params"] if entry is not None else ""
    if params == "PRECISION,SCALE":
        if precision and precision > 0:
            return ts.label_for_creation(name, precision, max(0, scale or 0))
        return name
    if params == "LENGTH":
        if precision and 0 < precision < ts.UNLIMITED:
            return ts.label_for_creation(name, precision)
        return name
    if params == "SCALE":
        if scale and scale > 0:
            return ts.label_for_creation(name, scale)
        return name
    return name


def _check_strict(db, table, column, label):
    if label and schema.is_strict(db, table) and not ts.strict_accepts(label):
        raise DriverError(errors.STRICT_TYPE_NOT_ALLOWED, tabella=table, colonna=column, tipo=label)


def visible_default(raw, column_type):
    text = schema.default_text(raw)
    if text is None or text == "":
        return None
    if column_type.kind == ts.K_DECIMAL and column_type.scale > 0:
        try:
            return decimals.plain(Decimal(text).scaleb(-column_type.scale))
        except InvalidOperation:
            return text
    return text


def same_type(label_a, label_b):
    a, b = ts.classify(label_a), ts.classify(label_b)
    return (a.code, a.name, a.size, a.scale) == (b.code, b.name, b.size, b.scale)


def stored_name(db, name):
    row = db.execute(
        "SELECT name FROM main.sqlite_master WHERE name = ? COLLATE NOCASE AND type IN ('table', 'view')",
        (name,)).fetchone()
    return row[0] if row else None


def load_definition(db, table):
    row = db.execute("SELECT name, sql FROM main.sqlite_master WHERE name = ? COLLATE NOCASE AND type = 'table'",
                     (table,)).fetchone()
    if row is None:
        raise DriverError(errors.DEFINITION_NOT_UNDERSTOOD, tabella=table)
    definition = tabledef.parse(row[1] or "")
    if definition is None:
        raise DriverError(errors.DEFINITION_NOT_UNDERSTOOD, tabella=row[0])
    return row[0], definition


def relations_of(db, table):
    result = []
    for name, kind in schema.list_objects(db):
        if kind != "TABLE":
            continue
        for fk in schema.foreign_keys(db, name):
            if name.lower() == table.lower() or fk.target_table.lower() == table.lower():
                result.append((fk.name, name, fk.target_table, fk.pairs))
    return result


def _mentions(sql, word):
    lowered = word.lower()
    return any(t.kind in ("word", "quoted", "string") and sqltext.unquote(t.text).lower() == lowered
               for t in sqltext.tokens(sql or ""))


def _sequence_exists(db):
    return db.execute("SELECT 1 FROM main.sqlite_master WHERE name = 'sqlite_sequence'").fetchone() is not None


def _key_names(db, table, definition):
    key = definition.primary_key()
    if key:
        return list(key)
    if definition.without_rowid:
        return []
    return ["rowid"]


def _key_text(names, values):
    return ", ".join("%s = %s" % (n, _shown(v)) for n, v in zip(names, values)) or "?"


def _shown(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<%d bytes>" % len(value)
    text = str(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _run(engine, sql):
    return engine.run(sql)


def drop_table(engine, table):
    db = engine.db
    users = []
    for _name, child, parent, _pairs in relations_of(db, table):
        if parent.lower() == table.lower() and child.lower() != table.lower() and child not in users:
            users.append(child)
    if users:
        raise DriverError(errors.TABLE_USED_BY_RELATIONS, tabella=table, tabelle=", ".join(users))
    _run(engine, "DROP TABLE %s" % _q(table))


def drop_view(engine, view):
    _run(engine, "DROP VIEW %s" % _q(view))


def rename_table(engine, old, new):
    _run(engine, "ALTER TABLE %s RENAME TO %s" % (_q(old), _q(new)))


def rename_column(engine, table, old, new):
    _run(engine, "ALTER TABLE %s RENAME COLUMN %s TO %s" % (_q(table), _q(old), _q(new)))


def create_index(engine, table, name, unique, columns):
    parts = ", ".join("%s %s" % (_q(c), "ASC" if asc else "DESC") for c, asc in columns)
    _run(engine, "CREATE %sINDEX %s ON %s (%s)" % ("UNIQUE " if unique else "", _q(name), _q(table), parts))


def drop_index(engine, name):
    _run(engine, "DROP INDEX %s" % _q(name))


def _view_text(db, command):
    command = dialect.translate(command)
    translation = decimals.translate(db, command)
    text = translation.text if translation.decimal else command
    return sqltext.strip_trailing(text), (translation.warnings if translation.decimal else [])


def _create_checked(db, name, text):
    db.execute("CREATE VIEW %s AS %s" % (_q(name), text))
    db.execute("SELECT * FROM %s LIMIT 0" % _q(name)).fetchall()


def create_view(engine, name, command):
    db = engine.db
    text, warnings = _view_text(db, command)
    _ensure_transaction(engine)
    db.execute("SAVEPOINT sdbc_create_view")
    try:
        _create_checked(db, name, text)
    except sqlite.Error as exception:
        db.execute("ROLLBACK TO sdbc_create_view")
        db.execute("RELEASE sdbc_create_view")
        raise driver_error(exception, engine.path)
    db.execute("RELEASE sdbc_create_view")
    return warnings


def alter_view(engine, name, command):
    db = engine.db
    try:
        text, warnings = _view_text(db, command)
    except DriverError as error:
        raise DriverError(errors.VIEW_NOT_ALTERED, vista=name, dettaglio=_detail(error))
    _ensure_transaction(engine)
    db.execute("SAVEPOINT sdbc_alter_view")
    try:
        db.execute("DROP VIEW %s" % _q(name))
        _create_checked(db, name, text)
    except sqlite.Error as exception:
        db.execute("ROLLBACK TO sdbc_alter_view")
        db.execute("RELEASE sdbc_alter_view")
        raise DriverError(errors.VIEW_NOT_ALTERED, vista=name, dettaglio=str(exception))
    db.execute("RELEASE sdbc_alter_view")
    return warnings


def _detail(error):
    if error.sqlite is not None:
        return str(error.sqlite)
    return str(error.values.get("dettaglio") or error)


def _ensure_transaction(engine):
    engine.ensure_transaction()


def create_table(engine, name, columns, primary_key, foreign_keys):
    definition = tabledef.new_table(name)
    auto = None
    for spec in columns:
        literal = tabledef.default_literal(spec.default, ts.classify(spec.label))
        definition.add_column(spec.name, spec.label, spec.not_null, literal)
        if spec.auto_value:
            auto = spec.name
    if primary_key:
        strict = auto is not None and len(primary_key) == 1 and primary_key[0].lower() == auto.lower() \
            and _strict(engine)
        definition.set_primary_key(list(primary_key), strict)
    elif auto is not None:
        raise DriverError(errors.AUTO_VALUE_IMPOSSIBLE, colonna=auto)
    if auto is not None and (len(primary_key) != 1 or primary_key[0].lower() != auto.lower()):
        raise DriverError(errors.AUTO_VALUE_IMPOSSIBLE, colonna=auto)
    for sources, target, destinations, update_rule, delete_rule in foreign_keys:
        definition.add_foreign_key(list(sources), target, list(destinations), update_rule, delete_rule)
    _run(engine, definition.render())


def drop_unique(engine, table, columns):
    db = engine.db
    name, definition = load_definition(db, table)
    if not definition.remove_unique(columns):
        return False
    old_columns = [c for c in schema.table_columns(db, name) if c.hidden not in (2, 3)]
    plan = [Copy(c.name, c.name, None, c.label) for c in old_columns]
    rebuild(engine, name, definition, plan)
    return True


def view_command(sql):
    tokens = sqltext.tokens(sql or "")
    depth = 0
    seen_view = False
    for token in tokens:
        if token.kind == "punct" and token.text == "(":
            depth += 1
        elif token.kind == "punct" and token.text == ")":
            depth -= 1
        elif token.kind == "word" and token.text.upper() == "VIEW":
            seen_view = True
        elif seen_view and depth == 0 and token.kind == "word" and token.text.upper() == "AS":
            return sql[token.start + 2:].strip()
    return (sql or "").strip()


def add_column(engine, table, spec):
    db = engine.db
    name, definition = load_definition(db, table)
    ctype = ts.classify(spec.label)
    _check_strict(db, name, spec.name, spec.label)
    literal = tabledef.default_literal(spec.default, ctype)
    count = db.execute("SELECT COUNT(*) FROM %s" % _q(name)).fetchone()[0]
    if spec.not_null and literal is None and count > 0 and not spec.auto_value:
        raise DriverError(errors.COLUMN_NOT_NULL_NO_DEFAULT, colonna=spec.name, n=count)
    if spec.auto_value:
        if definition.primary_key() or ctype.kind != ts.K_INT:
            raise DriverError(errors.AUTO_VALUE_IMPOSSIBLE, colonna=spec.name)
    needs_rebuild = spec.auto_value or (spec.not_null and literal is None)
    if not needs_rebuild:
        text = "ALTER TABLE %s ADD COLUMN %s" % (_q(name), _q(spec.name))
        if spec.label:
            text += " " + spec.label
        if spec.not_null:
            text += " NOT NULL"
        if literal is not None:
            text += " DEFAULT " + literal
        _run(engine, text)
        return False
    old_columns = [c for c in schema.table_columns(db, name) if c.hidden not in (2, 3)]
    definition.add_column(spec.name, spec.label, spec.not_null and not spec.auto_value, literal)
    if spec.auto_value:
        definition.set_primary_key([spec.name], _strict(engine))
    plan = [Copy(c.name, c.name, None, c.label) for c in old_columns]
    rebuild(engine, name, definition, plan, new_columns=[spec.name])
    return True


def _strict(engine):
    return not bool(engine.options.auto_increment_reuse)


def _users_of_column(db, table, definition, column):
    users = []
    if column.lower() in [k.lower() for k in definition.primary_key()]:
        users.append("PRIMARY KEY")
    for name, child, parent, pairs in relations_of(db, table):
        mine = [c for c, p in pairs] if child.lower() == table.lower() else []
        theirs = [p for c, p in pairs] if parent.lower() == table.lower() else []
        if column.lower() in [x.lower() for x in mine + theirs]:
            users.append('FOREIGN KEY "%s"' % name)
    for constraint in definition.constraints:
        if constraint.kind == "CHECK" and _mentions(constraint.raw, column):
            users.append("CHECK")
    for kind, name, sql in db.execute(
            "SELECT type, name, sql FROM main.sqlite_master WHERE type IN ('view', 'trigger')").fetchall():
        if kind == "view" and _mentions(sql, column) and _mentions(sql, table):
            users.append('VIEW "%s"' % name)
        elif kind == "trigger" and _mentions(sql, column):
            owner = db.execute("SELECT tbl_name FROM main.sqlite_master WHERE name = ?", (name,)).fetchone()
            if (owner and owner[0].lower() == table.lower()) or _mentions(sql, table):
                users.append('TRIGGER "%s"' % name)
    return users


def indexes_using(db, table, column):
    result = []
    for _seq, name, _unique, origin, _partial in db.execute(
            "PRAGMA main.index_list(%s)" % _q(table)).fetchall():
        if origin != "c":
            continue
        row = db.execute("SELECT sql FROM main.sqlite_master WHERE type = 'index' AND name = ?", (name,)).fetchone()
        if row and _mentions(row[0], column):
            result.append(name)
    return result


def drop_column(engine, table, column):
    db = engine.db
    name, definition = load_definition(db, table)
    target = definition.column(column)
    if target is None:
        _run(engine, "ALTER TABLE %s DROP COLUMN %s" % (_q(name), _q(column)))
        return []
    users = _users_of_column(db, name, definition, target.plain_name)
    if users:
        raise DriverError(errors.COLUMN_IN_USE, colonna=target.plain_name, oggetti=", ".join(users))
    indexes = indexes_using(db, name, target.plain_name)
    unique_constraint = target.has("UNIQUE") or any(
        c.kind == "UNIQUE" and target.plain_name.lower() in [n.lower() for n in tabledef._paren_names(c.raw)]
        for c in definition.constraints)
    if unique_constraint:
        definition.remove_unique_on(target.plain_name)
        definition.remove_column(target.plain_name)
        old_columns = [c for c in schema.table_columns(db, name)
                       if c.hidden not in (2, 3) and c.name.lower() != target.plain_name.lower()]
        plan = [Copy(c.name, c.name, None, c.label) for c in old_columns]
        rebuild(engine, name, definition, plan, skip_indexes=indexes)
        return indexes
    _ensure_transaction(engine)
    db.execute("SAVEPOINT sdbc_drop_column")
    try:
        for index in indexes:
            db.execute("DROP INDEX %s" % _q(index))
        db.execute("ALTER TABLE %s DROP COLUMN %s" % (_q(name), _q(target.plain_name)))
    except sqlite.Error as exception:
        db.execute("ROLLBACK TO sdbc_drop_column")
        db.execute("RELEASE sdbc_drop_column")
        raise driver_error(exception, engine.path)
    db.execute("RELEASE sdbc_drop_column")
    return indexes


def alter_column(engine, table, column, spec):
    db = engine.db
    done = []
    name, definition = load_definition(db, table)
    target = definition.column(column)
    if target is None:
        raise DriverError(errors.DEFINITION_NOT_UNDERSTOOD, tabella=name)
    columns = {c.name.lower(): c for c in schema.table_columns(db, name)}
    info = columns.get(target.plain_name.lower())
    old_type = ts.classify(info.label if info else target.label)
    new_type = ts.classify(spec.label)
    alias = schema.rowid_alias(db, name)
    is_alias = alias is not None and alias.lower() == column.lower()
    in_primary_key = column.lower() in [k.lower() for k in definition.primary_key()]
    type_changed = not same_type(info.label if info else target.label, spec.label)
    if is_alias and old_type.kind == ts.K_INT and new_type.kind == ts.K_INT:
        type_changed = False
    old_not_null = bool(info.notnull) or in_primary_key or is_alias
    not_null_changed = bool(spec.not_null) != old_not_null and not in_primary_key
    old_default = visible_default(info.default, old_type) if info is not None else None
    new_default = spec.default if spec.default not in (None, "") else old_default
    default_changed = new_default != old_default
    default_rewritten = default_changed or (type_changed and old_default is not None)
    auto_requested = bool(spec.auto_value) and not is_alias
    if type_changed:
        for relation, child, parent, pairs in relations_of(db, name):
            mine = [c for c, p in pairs] if child.lower() == name.lower() else []
            theirs = [p for c, p in pairs] if parent.lower() == name.lower() else []
            if column.lower() in [x.lower() for x in mine + theirs]:
                other = parent if child.lower() == name.lower() else child
                raise DriverError(errors.COLUMN_IN_RELATION, colonna=column, relazione=relation, tabella=other)
    if type_changed:
        _check_strict(db, name, column, spec.label)
    becomes_key = False
    if auto_requested:
        key = definition.primary_key()
        becomes_key = not key and not in_primary_key
        if definition.without_rowid or new_type.kind != ts.K_INT \
                or not (becomes_key or (in_primary_key and len(key) == 1)):
            raise DriverError(errors.AUTO_VALUE_IMPOSSIBLE, colonna=column)
        if becomes_key:
            not_null_changed = False
    if spec.name != column:
        rename_column(engine, name, column, spec.name)
        done.append("rename")
        name, definition = load_definition(db, name)
        target = definition.column(spec.name)
    if not (type_changed or not_null_changed or default_changed or auto_requested):
        return done
    if type_changed:
        target.label = spec.label
    if not_null_changed:
        target.drop("NOTNULL", "NULL")
        if spec.not_null:
            target.clauses.append(tabledef.Clause("NOTNULL", "NOT NULL"))
    if default_rewritten:
        target.drop("DEFAULT")
        literal = tabledef.default_literal(new_default, new_type)
        if literal is not None:
            target.clauses.append(tabledef.Clause("DEFAULT", "DEFAULT " + literal))
    if auto_requested:
        definition.set_primary_key([target.plain_name], _strict(engine))
    old_columns = [c for c in schema.table_columns(db, name) if c.hidden not in (2, 3)]
    plan = []
    checks = []
    not_null = []
    if becomes_key:
        checks.append(lambda d: _check_auto_key(d, name, column))
    for c in old_columns:
        label = c.label
        convert = None
        if c.name.lower() == target.plain_name.lower():
            label = spec.label if type_changed else c.label
            if type_changed:
                convert = conversion(ts.classify(c.label), new_type, spec.label)
            if not_null_changed and spec.not_null:
                not_null.append(c.name)
        plan.append(Copy(c.name, c.name, convert, label))
    rebuild(engine, name, definition, plan, checks=checks, not_null=not_null)
    done.append("rebuild")
    return done


def set_primary_key(engine, table, columns):
    db = engine.db
    name, definition = load_definition(db, table)
    old_key = definition.primary_key()
    if [c.lower() for c in old_key] == [c.lower() for c in columns]:
        return False
    old_columns = [c for c in schema.table_columns(db, name) if c.hidden not in (2, 3)]
    by_name = {c.name.lower(): c for c in old_columns}
    columns = [by_name[c.lower()].name for c in columns]
    checks = []
    if columns:
        checks.append(lambda d: _check_primary_key(d, name, columns))
    definition.set_primary_key(columns, _strict(engine))
    plan = [Copy(c.name, c.name, None, c.label) for c in old_columns]
    rebuild(engine, name, definition, plan, checks=checks, not_null=list(columns))
    return True


def add_foreign_key(engine, table, sources, target, destinations, update_rule, delete_rule):
    db = engine.db
    name, definition = load_definition(db, table)
    old_columns = [c for c in schema.table_columns(db, name) if c.hidden not in (2, 3)]
    by_name = {c.name.lower(): c for c in old_columns}
    sources = [by_name[s.lower()].name for s in sources]
    parent = stored_name(db, target) or target
    definition.add_foreign_key(sources, parent, destinations, update_rule, delete_rule)
    plan = [Copy(c.name, c.name, None, c.label) for c in old_columns]
    checks = [lambda d: _check_foreign_key(d, name, sources, parent, destinations)]
    rebuild(engine, name, definition, plan, checks=checks)


def drop_foreign_key(engine, table, key_name):
    db = engine.db
    name, definition = load_definition(db, table)
    for fk in schema.foreign_keys(db, name):
        if fk.name == key_name:
            sources = [s for s, _d in fk.pairs]
            if not definition.remove_foreign_key(sources, fk.target_table):
                raise DriverError(errors.DEFINITION_NOT_UNDERSTOOD, tabella=name)
            old_columns = [c for c in schema.table_columns(db, name) if c.hidden not in (2, 3)]
            plan = [Copy(c.name, c.name, None, c.label) for c in old_columns]
            rebuild(engine, name, definition, plan)
            return True
    return False


def _check_auto_key(db, table, column):
    quoted = _q(column)
    rows = db.execute("SELECT %s FROM %s WHERE %s IS NOT NULL GROUP BY %s HAVING COUNT(*) > 1"
                      % (quoted, _q(table), quoted, quoted)).fetchall()
    if rows:
        raise DriverError(errors.PRIMARY_KEY_DUPLICATES, n=len(rows), valore=_shown(rows[0][0]))


def _check_primary_key(db, table, columns):
    quoted = ", ".join(_q(c) for c in columns)
    count = db.execute("SELECT COUNT(*) FROM (SELECT 1 FROM %s GROUP BY %s HAVING COUNT(*) > 1)"
                       % (_q(table), quoted)).fetchone()[0]
    if count:
        first = db.execute("SELECT %s FROM %s GROUP BY %s HAVING COUNT(*) > 1 LIMIT 1"
                           % (quoted, _q(table), quoted)).fetchone()
        raise DriverError(errors.PRIMARY_KEY_DUPLICATES, n=count, valore=", ".join(_shown(v) for v in first))


def _check_foreign_key(db, table, sources, target, destinations):
    present = " AND ".join("c.%s IS NOT NULL" % _q(s) for s in sources)
    match = " AND ".join("p.%s = c.%s" % (_q(d), _q(s)) for s, d in zip(sources, destinations))
    where = "%s AND NOT EXISTS (SELECT 1 FROM %s p WHERE %s)" % (present, _q(target), match)
    count = db.execute("SELECT COUNT(*) FROM %s c WHERE %s" % (_q(table), where)).fetchone()[0]
    if count:
        first = db.execute("SELECT %s FROM %s c WHERE %s LIMIT 1" % (
            ", ".join("c.%s" % _q(s) for s in sources), _q(table), where)).fetchone()
        raise DriverError(errors.RELATION_VIOLATED, n=count, tabella=table, tabellaRif=target,
                          colonna=", ".join(sources), valore=", ".join(_shown(v) for v in first))


class ConvertError(Exception):
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind


_NUMBER_KINDS = (ts.K_INT, ts.K_REAL, ts.K_NUMERIC, ts.K_DECIMAL)
_TEXT_KINDS = (ts.K_TEXT, ts.K_VARIANT)
_OPAQUE_KINDS = (ts.K_DATE, ts.K_TIME, ts.K_TIMESTAMP, ts.K_BINARY)


def _int_range(column_type):
    if column_type.min_value is not None:
        return column_type.min_value, column_type.max_value
    return INT64_MIN, INT64_MAX


def _is_plain(old, new):
    if old.kind == new.kind:
        if old.kind == ts.K_DECIMAL:
            return old.scale == new.scale and old.size <= new.size
        if old.kind == ts.K_INT:
            low_old, high_old = _int_range(old)
            low_new, high_new = _int_range(new)
            return low_new <= low_old and high_old <= high_new
        return True
    if old.kind == ts.K_TEXT and new.kind == ts.K_VARIANT:
        return True
    if old.kind in (ts.K_DATE, ts.K_TIME, ts.K_TIMESTAMP) and new.kind in _TEXT_KINDS:
        return True
    if old.kind in _TEXT_KINDS and new.kind in (ts.K_DATE, ts.K_TIME, ts.K_TIMESTAMP):
        return True
    return False


def _logical(value, old):
    if isinstance(value, bool):
        value = int(value)
    if old.kind == ts.K_DECIMAL:
        if isinstance(value, float) and value == int(value):
            value = int(value)
        if isinstance(value, str):
            try:
                value = int(value.strip())
            except ValueError:
                raise ConvertError("impossible")
        if isinstance(value, int):
            return Decimal(value).scaleb(-old.scale)
        raise ConvertError("impossible")
    return value


def _to_decimal_number(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        number = Decimal(repr(value))
    elif isinstance(value, str):
        try:
            number = Decimal(value.strip())
        except InvalidOperation:
            raise ConvertError("impossible")
    else:
        raise ConvertError("impossible")
    if not number.is_finite():
        raise ConvertError("impossible")
    return number


def _encode_decimal(number, new):
    scaled = number.scaleb(new.scale).to_integral_value(rounding=ROUND_HALF_UP)
    value = int(scaled)
    if abs(value) >= 10 ** new.size or not (INT64_MIN <= value <= INT64_MAX):
        raise ConvertError("digits")
    return value


def _encode_int(number, new):
    value = int(number)
    low, high = _int_range(new)
    if not (low <= value <= high):
        raise ConvertError("digits")
    return value


def _plain_text(number):
    if isinstance(number, Decimal):
        return decimals.plain(number)
    if isinstance(number, float):
        return repr(number)
    return str(number)


def conversion(old, new, label=""):
    if _is_plain(old, new):
        return None

    def convert(value):
        if value is None:
            return None
        logical = _logical(value, old)
        kind = new.kind
        if kind == ts.K_DECIMAL:
            return _encode_decimal(_to_decimal_number(logical), new)
        if kind == ts.K_INT:
            return _encode_int(_to_decimal_number(logical), new)
        if kind == ts.K_REAL:
            number = _to_decimal_number(logical)
            return float(number)
        if kind == ts.K_NUMERIC:
            number = _to_decimal_number(logical)
            return int(number) if number == number.to_integral_value() else float(number)
        if kind in _TEXT_KINDS:
            if isinstance(logical, (bytes, bytearray, memoryview)):
                try:
                    return bytes(logical).decode("utf-8")
                except UnicodeDecodeError:
                    raise ConvertError("impossible")
            return logical if isinstance(logical, str) else _plain_text(logical)
        if kind == ts.K_BOOL:
            if isinstance(logical, str):
                lowered = logical.strip().lower()
                if lowered in ("true", "1"):
                    return 1
                if lowered in ("false", "0"):
                    return 0
                raise ConvertError("impossible")
            number = _to_decimal_number(logical)
            if number in (0, 1):
                return int(number)
            raise ConvertError("impossible")
        raise ConvertError("impossible")
    return convert


def rebuild(engine, table, definition, plan, checks=(), not_null=(), skip_indexes=(), new_columns=()):
    db = engine.db
    if db.in_transaction:
        raise DriverError(errors.PENDING_CHANGES, tabella=table)
    key_names = _key_names(db, table, load_definition(db, table)[1])
    _normalize_auto_value(definition, _strict(engine))
    foreign_keys_before = db.execute("PRAGMA foreign_keys").fetchone()[0]
    try:
        db.execute("PRAGMA foreign_keys=OFF")
        db.execute("BEGIN IMMEDIATE")
        try:
            for column in not_null:
                _check_nulls(db, table, column, key_names)
            for check in checks:
                check(db)
            _rebuild_inside(engine, table, definition, plan, key_names, set(n.lower() for n in skip_indexes))
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                try:
                    db.execute("ROLLBACK")
                except sqlite.Error:
                    pass
            raise
    except sqlite.Error as exception:
        raise driver_error(exception, engine.path)
    finally:
        try:
            db.execute("PRAGMA foreign_keys=%d" % foreign_keys_before)
        except sqlite.Error:
            pass


def _normalize_auto_value(definition, strict):
    key = definition.primary_key()
    if len(key) != 1:
        return
    column = definition.column(key[0])
    if column is None or column.label.upper() != "INTEGER":
        return
    for clause in column.clauses:
        if clause.kind == "PK" and clause.text.upper() in ("PRIMARY KEY", "PRIMARY KEY AUTOINCREMENT"):
            clause.text = "PRIMARY KEY" + (" AUTOINCREMENT" if strict else "")


def _check_nulls(db, table, column, key_names):
    count = db.execute("SELECT COUNT(*) FROM %s WHERE %s IS NULL" % (_q(table), _q(column))).fetchone()[0]
    if count:
        first = db.execute("SELECT %s FROM %s WHERE %s IS NULL LIMIT 1" % (
            ", ".join(_key_expr(k) for k in key_names) or "NULL", _q(table), _q(column))).fetchone()
        raise DriverError(errors.CONVERSION_NULLS, colonna=column, n=count, chiave=_key_text(key_names, first))


def _key_expr(name):
    return name if name == "rowid" else _q(name)


def _temp_name(db, table):
    name, counter = "sdbc_new_" + table, 1
    while db.execute("SELECT 1 FROM main.sqlite_master WHERE name = ? COLLATE NOCASE", (name,)).fetchone():
        counter += 1
        name = "sdbc_new_%d_%s" % (counter, table)
    return name


def _violations(db):
    counts = {}
    for row in db.execute("PRAGMA foreign_key_check").fetchall():
        key = (row[0], row[2])
        counts[key] = counts.get(key, 0) + 1
    return counts


def _rebuild_inside(engine, table, definition, plan, key_names, skip_indexes):
    db = engine.db
    before = _violations(db)
    dependents = db.execute(
        "SELECT type, name, sql FROM main.sqlite_master WHERE tbl_name = ? COLLATE NOCASE "
        "AND type IN ('index', 'trigger') AND sql IS NOT NULL ORDER BY type DESC, rowid", (table,)).fetchall()
    old_sequence = None
    if _sequence_exists(db):
        row = db.execute("SELECT seq FROM main.sqlite_sequence WHERE name = ?", (table,)).fetchone()
        old_sequence = row[0] if row else None
    temp = _temp_name(db, table)
    db.execute(definition.render(temp))
    copied = [p for p in plan if p.source is not None]
    if all(p.convert is None for p in copied):
        db.execute("INSERT INTO %s (%s) SELECT %s FROM %s" % (
            _q(temp), ", ".join(_q(p.name) for p in copied), ", ".join(_q(p.source) for p in copied), _q(table)))
    else:
        _copy_converting(db, table, temp, copied, key_names)
    db.execute("DROP TABLE %s" % _q(table))
    legacy = db.execute("PRAGMA legacy_alter_table").fetchone()[0]
    db.execute("PRAGMA legacy_alter_table=ON")
    try:
        db.execute("ALTER TABLE %s RENAME TO %s" % (_q(temp), _q(table)))
    finally:
        db.execute("PRAGMA legacy_alter_table=%d" % legacy)
    for kind, name, sql in dependents:
        if kind == "index" and name.lower() in skip_indexes:
            continue
        db.execute(sql)
    sql_new = db.execute("SELECT sql FROM main.sqlite_master WHERE name = ? COLLATE NOCASE AND type = 'table'",
                         (table,)).fetchone()[0]
    if old_sequence is not None and "AUTOINCREMENT" in sql_new.upper():
        row = db.execute("SELECT seq FROM main.sqlite_sequence WHERE name = ?", (table,)).fetchone()
        if row is None:
            db.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table, old_sequence))
        elif row[0] < old_sequence:
            db.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (old_sequence, table))
    after = _violations(db)
    for key, number in after.items():
        if number > before.get(key, 0):
            raise DriverError(errors.RELATION_VIOLATED, n=number - before.get(key, 0), tabella=key[0],
                              tabellaRif=key[1], colonna="", valore="")


def _copy_converting(db, table, temp, copied, key_names):
    key_sql = [_key_expr(k) for k in key_names]
    select = ", ".join(key_sql + [_q(p.source) for p in copied])
    offset = len(key_sql)
    rows = []
    problems = {}
    for row in db.execute("SELECT %s FROM %s" % (select, _q(table))):
        out = []
        for index, item in enumerate(copied):
            value = row[offset + index]
            if item.convert is not None and value is not None:
                try:
                    value = item.convert(value)
                except ConvertError as error:
                    entry = problems.setdefault((index, error.kind), [0, row[offset + index], row[:offset]])
                    entry[0] += 1
                    value = None
            out.append(value)
        rows.append(out)
    if problems:
        (index, kind), (count, value, key) = sorted(problems.items())[0]
        item = copied[index]
        values = dict(colonna=item.source, n=count, tipo=item.label, valore=_shown(value),
                      chiave=_key_text(key_names, key))
        raise DriverError(errors.CONVERSION_IMPOSSIBLE if kind == "impossible"
                          else errors.CONVERSION_TOO_MANY_DIGITS, **values)
    marks = ", ".join("?" for _ in copied)
    db.cursor().executemany("INSERT INTO %s (%s) VALUES (%s)" % (
        _q(temp), ", ".join(_q(p.name) for p in copied), marks), rows)
