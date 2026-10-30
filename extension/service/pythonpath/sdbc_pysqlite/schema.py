# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import re
from collections import namedtuple

from sdbc_pysqlite import sqltext
from sdbc_pysqlite import typesystem as ts

ColumnDef = namedtuple("ColumnDef", "cid name label notnull default pk hidden")

TABLE_TYPES = ("TABLE", "VIEW")
ESCAPE = "\\"

_KEY_RULES = {"CASCADE": 0, "RESTRICT": 1, "SET NULL": 2, "NO ACTION": 3, "SET DEFAULT": 4}
DEFERRABILITY_NONE = 7
INDEX_OTHER = 3
SCOPE_SESSION = 2
NOT_PSEUDO = 1
FUNCTION_NO_TABLE = 1
NAME_PART_LIMIT = 10

S = ts.VARCHAR
I = ts.INTEGER
SI = ts.SMALLINT
B = ts.BOOLEAN


def like_to_regex(pattern, escape=ESCAPE):
    if pattern is None or pattern == "":
        return re.compile(".*", re.DOTALL)
    out = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == escape and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        if char == "%":
            out.append(".*")
        elif char == "_":
            out.append(".")
        else:
            out.append(re.escape(char))
        i += 1
    return re.compile("^" + "".join(out) + "$", re.DOTALL | re.IGNORECASE)


def shadow_tables(db):
    try:
        rows = db.execute("PRAGMA main.table_list").fetchall()
    except Exception:
        return set()
    return {row[1].lower() for row in rows if row[2] == "shadow"}


def list_objects(db):
    rows = db.execute(
        "SELECT name, type FROM main.sqlite_master WHERE type IN ('table', 'view') "
        "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY type, name COLLATE NOCASE").fetchall()
    hidden = shadow_tables(db)
    return [(name, "VIEW" if kind == "view" else "TABLE") for name, kind in rows if name.lower() not in hidden]


def object_kind(db, name):
    row = db.execute(
        "SELECT type FROM main.sqlite_master WHERE name = ? COLLATE NOCASE AND type IN ('table', 'view')",
        (name,)).fetchone()
    return row[0] if row else None


def table_columns(db, table):
    result = []
    for cid, name, label, notnull, default, pk, hidden in db.execute(
            "PRAGMA main.table_xinfo(%s)" % sqltext.quote_name(table)):
        if hidden == 1:
            continue
        result.append(ColumnDef(cid, name, label or "", bool(notnull), default, pk, hidden))
    return result


def is_without_rowid(db, table):
    try:
        row = db.execute("PRAGMA main.table_list(%s)" % sqltext.quote_name(table)).fetchone()
    except Exception:
        return False
    return bool(row and row[4])


def is_strict(db, table):
    try:
        row = db.execute("PRAGMA main.table_list(%s)" % sqltext.quote_name(table)).fetchone()
    except Exception:
        return False
    return bool(row and len(row) > 5 and row[5])


def rowid_alias(db, table, columns=None):
    columns = table_columns(db, table) if columns is None else columns
    keys = [c for c in columns if c.pk]
    if len(keys) != 1 or keys[0].label.strip().upper() != "INTEGER":
        return None
    if object_kind(db, table) != "table" or is_without_rowid(db, table):
        return None
    return keys[0].name


def default_text(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        return text[1:-1].replace("''", "'")
    return text


def _matching_tables(db, table_pattern, types=None):
    regex = like_to_regex(table_pattern)
    wanted = None
    if types is not None:
        wanted = [t.upper() for t in types if t]
        if not wanted:
            wanted = None
    result = []
    for name, kind in list_objects(db):
        if not regex.match(name):
            continue
        if wanted is not None and not any(like_to_regex(w).match(kind) for w in wanted):
            continue
        result.append((name, kind))
    return result


def tables_rows(db, table_pattern, types):
    columns = [("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("TABLE_TYPE", S), ("REMARKS", S)]
    rows = [(None, None, name, kind, None) for name, kind in _matching_tables(db, table_pattern, types)]
    return columns, rows


def table_types_rows():
    return [("TABLE_TYPE", S)], [(kind,) for kind in TABLE_TYPES]


def catalogs_rows():
    return [("TABLE_CAT", S)], []


def schemas_rows():
    return [("TABLE_SCHEM", S), ("TABLE_CATALOG", S)], []


def type_info_rows():
    return list(ts.TYPE_INFO_COLUMNS), ts.type_info_rows()


def columns_rows(db, table_pattern, column_pattern):
    declared = [
        ("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("COLUMN_NAME", S), ("DATA_TYPE", I),
        ("TYPE_NAME", S), ("COLUMN_SIZE", I), ("BUFFER_LENGTH", I), ("DECIMAL_DIGITS", I),
        ("NUM_PREC_RADIX", I), ("NULLABLE", I), ("REMARKS", S), ("COLUMN_DEF", S), ("SQL_DATA_TYPE", I),
        ("SQL_DATETIME_SUB", I), ("CHAR_OCTET_LENGTH", I), ("ORDINAL_POSITION", I), ("IS_NULLABLE", S)]
    column_regex = like_to_regex(column_pattern)
    rows = []
    for table, _kind in _matching_tables(db, table_pattern):
        columns = table_columns(db, table)
        alias = rowid_alias(db, table, columns)
        for position, column in enumerate(columns, 1):
            if not column_regex.match(column.name):
                continue
            ctype = ts.classify(column.label)
            not_null = column.notnull or column.name == alias
            octets = ctype.size if ctype.kind in (ts.K_TEXT, ts.K_VARIANT, ts.K_BINARY) else 0
            rows.append((
                None, None, table, column.name, ctype.code, ctype.name, ctype.size, 0, ctype.scale, 10,
                0 if not_null else 1, None, default_text(column.default), 0, 0, octets, position,
                "NO" if not_null else "YES"))
    return declared, rows


def primary_key_columns(db, table):
    return sorted((c.pk, c.name) for c in table_columns(db, table) if c.pk)


def primary_keys_rows(db, table):
    declared = [("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("COLUMN_NAME", S),
                ("KEY_SEQ", SI), ("PK_NAME", S)]
    if not table or object_kind(db, table) != "table":
        return declared, []
    keys = primary_key_columns(db, table)
    name = "PK_" + table
    rows = [(None, None, table, column, seq, name) for seq, column in sorted(keys, key=lambda k: k[1].lower())]
    return declared, rows


_FK_DECLARED = [
    ("PKTABLE_CAT", S), ("PKTABLE_SCHEM", S), ("PKTABLE_NAME", S), ("PKCOLUMN_NAME", S),
    ("FKTABLE_CAT", S), ("FKTABLE_SCHEM", S), ("FKTABLE_NAME", S), ("FKCOLUMN_NAME", S),
    ("KEY_SEQ", SI), ("UPDATE_RULE", SI), ("DELETE_RULE", SI), ("FK_NAME", S), ("PK_NAME", S),
    ("DEFERRABILITY", SI)]

ForeignKey = namedtuple("ForeignKey", "name table target_table pairs update_rule delete_rule")


def _cut(text):
    return text[:NAME_PART_LIMIT]


def foreign_keys(db, table):
    groups = {}
    order = []
    for fk_id, seq, target, source, destination, on_update, on_delete, _match in db.execute(
            "PRAGMA main.foreign_key_list(%s)" % sqltext.quote_name(table)):
        if fk_id not in groups:
            groups[fk_id] = {"target": target, "pairs": [], "update": on_update, "delete": on_delete}
            order.append(fk_id)
        groups[fk_id]["pairs"].append((seq, source, destination))
    result = []
    used = set()
    for fk_id in order:
        group = groups[fk_id]
        pairs = sorted(group["pairs"])
        if any(destination is None for _s, _src, destination in pairs):
            target_keys = [name for _seq, name in primary_key_columns(db, group["target"])]
            pairs = [(seq, source, destination if destination is not None
                      else (target_keys[i] if i < len(target_keys) else None))
                     for i, (seq, source, destination) in enumerate(pairs)]
        sources = [source for _s, source, _d in pairs]
        destinations = [destination or "" for _s, _src, destination in pairs]
        base = "FK_%s_%s_%s_%s" % (_cut(table), _cut("_".join(sources)), _cut(group["target"]),
                                   _cut("_".join(destinations)))
        name, counter = base, 1
        while name.lower() in used:
            counter += 1
            name = "%s_%d" % (base, counter)
        used.add(name.lower())
        result.append(ForeignKey(
            name, table, group["target"], [(s, d) for _q, s, d in pairs],
            _KEY_RULES.get((group["update"] or "NO ACTION").upper(), 3),
            _KEY_RULES.get((group["delete"] or "NO ACTION").upper(), 3)))
    return result


def _key_rows(fk):
    pk_name = "PK_" + fk.target_table
    return [(None, None, fk.target_table, destination, None, None, fk.table, source, seq, fk.update_rule,
             fk.delete_rule, fk.name, pk_name, DEFERRABILITY_NONE)
            for seq, (source, destination) in enumerate(fk.pairs, 1)]


def imported_keys_rows(db, table):
    if not table or object_kind(db, table) != "table":
        return list(_FK_DECLARED), []
    rows = []
    for fk in foreign_keys(db, table):
        rows.extend(_key_rows(fk))
    return list(_FK_DECLARED), rows


def exported_keys_rows(db, table):
    rows = []
    if table and object_kind(db, table) == "table":
        for name, kind in list_objects(db):
            if kind != "TABLE":
                continue
            for fk in foreign_keys(db, name):
                if fk.target_table.lower() == table.lower():
                    rows.extend(_key_rows(fk))
        rows.sort(key=lambda r: (r[6].lower(), r[11], r[8]))
    return list(_FK_DECLARED), rows


def cross_reference_rows(db, primary_table, foreign_table):
    rows = []
    if foreign_table and primary_table and object_kind(db, foreign_table) == "table":
        for fk in foreign_keys(db, foreign_table):
            if fk.target_table.lower() == primary_table.lower():
                rows.extend(_key_rows(fk))
    return list(_FK_DECLARED), rows


def index_info_rows(db, table, unique_only):
    declared = [
        ("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("NON_UNIQUE", B), ("INDEX_QUALIFIER", S),
        ("INDEX_NAME", S), ("TYPE", SI), ("ORDINAL_POSITION", SI), ("COLUMN_NAME", S),
        ("ASC_OR_DESC", S), ("CARDINALITY", I), ("PAGES", I), ("FILTER_CONDITION", S)]
    rows = []
    if not table or object_kind(db, table) != "table":
        return declared, rows
    for _seq, name, unique, origin, partial in db.execute(
            "PRAGMA main.index_list(%s)" % sqltext.quote_name(table)).fetchall():
        if origin == "pk" or partial:
            continue
        if unique_only and not unique:
            continue
        details = db.execute("PRAGMA main.index_xinfo(%s)" % sqltext.quote_name(name)).fetchall()
        keys = [d for d in details if d[5]]
        if any(d[1] == -2 or d[2] is None for d in keys):
            continue
        for position, (_seqno, _cid, column, desc, _coll, _key) in enumerate(keys, 1):
            rows.append((None, None, table, not unique, None, name, INDEX_OTHER, position, column,
                         "D" if desc else "A", None, None, None))
    rows.sort(key=lambda r: (r[3], r[5].lower(), r[7]))
    return declared, rows


def best_row_identifier_rows(db, table):
    declared = [("SCOPE", SI), ("COLUMN_NAME", S), ("DATA_TYPE", SI), ("TYPE_NAME", S), ("COLUMN_SIZE", I),
                ("BUFFER_LENGTH", I), ("DECIMAL_DIGITS", SI), ("PSEUDO_COLUMN", SI)]
    rows = []
    if table and object_kind(db, table) == "table":
        columns = {c.name: c for c in table_columns(db, table)}
        for _seq, name in primary_key_columns(db, table):
            ctype = ts.classify(columns[name].label)
            rows.append((SCOPE_SESSION, name, ctype.code, ctype.name, ctype.size, 0, ctype.scale, NOT_PSEUDO))
    return declared, rows


TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE")
TABLE_STRUCTURE_PRIVILEGES = ("CREATE", "ALTER", "DROP", "REFERENCE")
VIEW_STRUCTURE_PRIVILEGES = ("DROP",)


def table_privileges_rows(db, table_pattern, user, writable):
    declared = [("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("GRANTOR", S),
                ("GRANTEE", S), ("PRIVILEGE", S), ("IS_GRANTABLE", S)]
    rows = []
    for name, kind in _matching_tables(db, table_pattern):
        if not writable:
            privileges = TABLE_PRIVILEGES[:1]
        elif kind == "TABLE":
            privileges = TABLE_PRIVILEGES + TABLE_STRUCTURE_PRIVILEGES
        else:
            privileges = TABLE_PRIVILEGES[:1] + VIEW_STRUCTURE_PRIVILEGES
        for privilege in privileges:
            rows.append((None, None, name, "", user, privilege, "NO"))
    return declared, rows


def empty_rows(kind):
    layouts = {
        "version_columns": [("SCOPE", SI), ("COLUMN_NAME", S), ("DATA_TYPE", SI), ("TYPE_NAME", S),
                            ("COLUMN_SIZE", I), ("BUFFER_LENGTH", I), ("DECIMAL_DIGITS", SI),
                            ("PSEUDO_COLUMN", SI)],
        "column_privileges": [("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("COLUMN_NAME", S),
                              ("GRANTOR", S), ("GRANTEE", S), ("PRIVILEGE", S), ("IS_GRANTABLE", S)],
        "procedures": [("PROCEDURE_CAT", S), ("PROCEDURE_SCHEM", S), ("PROCEDURE_NAME", S), ("RESERVED1", S),
                       ("RESERVED2", S), ("RESERVED3", S), ("REMARKS", S), ("PROCEDURE_TYPE", SI)],
        "procedure_columns": [("PROCEDURE_CAT", S), ("PROCEDURE_SCHEM", S), ("PROCEDURE_NAME", S),
                              ("COLUMN_NAME", S), ("COLUMN_TYPE", SI), ("DATA_TYPE", SI), ("TYPE_NAME", S),
                              ("PRECISION", I), ("LENGTH", I), ("SCALE", SI), ("RADIX", SI),
                              ("NULLABLE", SI), ("REMARKS", S)],
        "udts": [("TYPE_CAT", S), ("TYPE_SCHEM", S), ("TYPE_NAME", S), ("CLASS_NAME", S),
                 ("DATA_TYPE", I), ("REMARKS", S), ("BASE_TYPE", SI)],
        "function_columns": [("FUNCTION_CAT", S), ("FUNCTION_SCHEM", S), ("FUNCTION_NAME", S),
                             ("COLUMN_NAME", S), ("COLUMN_TYPE", SI), ("DATA_TYPE", I), ("TYPE_NAME", S),
                             ("PRECISION", I), ("LENGTH", I), ("SCALE", SI), ("RADIX", SI),
                             ("NULLABLE", SI), ("REMARKS", S), ("CHAR_OCTET_LENGTH", I),
                             ("ORDINAL_POSITION", I), ("IS_NULLABLE", S), ("SPECIFIC_NAME", S)],
        "pseudo_columns": [("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("COLUMN_NAME", S),
                           ("DATA_TYPE", I), ("COLUMN_SIZE", I), ("DECIMAL_DIGITS", I),
                           ("NUM_PREC_RADIX", I), ("COLUMN_USAGE", S), ("REMARKS", S),
                           ("CHAR_OCTET_LENGTH", I), ("IS_NULLABLE", S)],
        "super_tables": [("TABLE_CAT", S), ("TABLE_SCHEM", S), ("TABLE_NAME", S), ("SUPERTABLE_NAME", S)],
        "super_types": [("TYPE_CAT", S), ("TYPE_SCHEM", S), ("TYPE_NAME", S), ("SUPERTYPE_CAT", S),
                        ("SUPERTYPE_SCHEM", S), ("SUPERTYPE_NAME", S)],
        "attributes": [("TYPE_CAT", S), ("TYPE_SCHEM", S), ("TYPE_NAME", S), ("ATTR_NAME", S),
                       ("DATA_TYPE", I), ("ATTR_TYPE_NAME", S), ("ATTR_SIZE", I), ("DECIMAL_DIGITS", I),
                       ("NUM_PREC_RADIX", I), ("NULLABLE", I), ("REMARKS", S), ("ATTR_DEF", S),
                       ("SQL_DATA_TYPE", I), ("SQL_DATETIME_SUB", I), ("CHAR_OCTET_LENGTH", I),
                       ("ORDINAL_POSITION", I), ("IS_NULLABLE", S), ("SCOPE_CATALOG", S),
                       ("SCOPE_SCHEMA", S), ("SCOPE_TABLE", S), ("SOURCE_DATA_TYPE", SI)],
        "client_info": [("NAME", S), ("MAX_LEN", I), ("DEFAULT_VALUE", S), ("DESCRIPTION", S)],
        "schemas_filtered": [("TABLE_SCHEM", S), ("TABLE_CATALOG", S)],
    }
    return list(layouts[kind]), []


def function_list(db):
    seen = {}
    try:
        for name, _builtin, kind, *_rest in db.execute("PRAGMA function_list"):
            seen.setdefault(name.upper(), set()).add(kind)
    except Exception:
        return []
    return sorted(seen.items())


def functions_rows(db, name_pattern):
    declared = [("FUNCTION_CAT", S), ("FUNCTION_SCHEM", S), ("FUNCTION_NAME", S), ("REMARKS", S),
                ("FUNCTION_TYPE", SI), ("SPECIFIC_NAME", S)]
    regex = like_to_regex(name_pattern)
    rows = [(None, None, name, None, FUNCTION_NO_TABLE, name)
            for name, _kinds in function_list(db) if regex.match(name)]
    return declared, rows


_NUMERIC = ("ABS", "ROUND", "RANDOM", "SIGN", "CEIL", "CEILING", "FLOOR", "MOD", "POWER", "POW", "SQRT", "LN",
            "LOG", "LOG10", "LOG2", "EXP", "SIN", "COS", "TAN", "ASIN", "ACOS", "ATAN", "ATAN2", "SINH", "COSH",
            "TANH", "ASINH", "ACOSH", "ATANH", "DEGREES", "RADIANS", "PI", "TRUNC", "MAX", "MIN")
_STRING = ("LENGTH", "LOWER", "UPPER", "SUBSTR", "SUBSTRING", "REPLACE", "TRIM", "LTRIM", "RTRIM", "INSTR", "HEX",
           "UNHEX", "QUOTE", "PRINTF", "FORMAT", "CHAR", "UNICODE", "CONCAT", "CONCAT_WS", "SOUNDEX", "OCTET_LENGTH",
           "LIKE", "GLOB")
_TIME = ("DATE", "TIME", "DATETIME", "JULIANDAY", "STRFTIME", "UNIXEPOCH", "TIMEDIFF")
_SYSTEM = ("COALESCE", "IFNULL", "IIF", "NULLIF", "TYPEOF", "LAST_INSERT_ROWID", "CHANGES", "TOTAL_CHANGES",
           "SQLITE_VERSION", "SQLITE_SOURCE_ID")
_GROUPS = {"numeric": _NUMERIC, "string": _STRING, "time": _TIME, "system": _SYSTEM}
_ALWAYS = {"time": ("CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP")}


def function_names(db, group):
    available = {name for name, _kinds in function_list(db)}
    names = [n for n in _GROUPS[group] if n in available]
    names.extend(_ALWAYS.get(group, ()))
    return ",".join(names)


SQL_KEYWORDS = (
    "ABORT,ACTION,AFTER,ANALYZE,ATTACH,AUTOINCREMENT,BEFORE,CONFLICT,DATABASE,DETACH,EACH,EXCLUSIVE,"
    "EXPLAIN,FAIL,GLOB,IF,IGNORE,IMMEDIATE,INDEXED,INITIALLY,INSTEAD,ISNULL,NOTNULL,OFFSET,PLAN,PRAGMA,"
    "QUERY,RAISE,REGEXP,REINDEX,RENAME,REPLACE,RESTRICT,ROW,TEMP,TEMPORARY,TRIGGER,VACUUM,VIEW,VIRTUAL,"
    "WITHOUT")
