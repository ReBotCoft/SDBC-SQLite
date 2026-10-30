# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import re
from collections import namedtuple

SQLNULL = 0
CHAR = 1
NUMERIC = 2
DECIMAL = 3
INTEGER = 4
SMALLINT = 5
FLOAT = 6
REAL = 7
DOUBLE = 8
VARCHAR = 12
BOOLEAN = 16
LONGVARCHAR = -1
DATE = 91
TIME = 92
TIMESTAMP = 93
BINARY = -2
VARBINARY = -3
LONGVARBINARY = -4
BIGINT = -5
TINYINT = -6

UNLIMITED = 2147483647

K_INT = "int"
K_REAL = "real"
K_NUMERIC = "numeric"
K_DECIMAL = "decimal"
K_TEXT = "text"
K_VARIANT = "variant"
K_BOOL = "bool"
K_DATE = "date"
K_TIME = "time"
K_TIMESTAMP = "timestamp"
K_BINARY = "binary"

ColumnType = namedtuple("ColumnType", "code name size scale kind lo min_value max_value")


def _entry(name, code, kind, precision, params, min_scale, max_scale, lo, **extra):
    data = {"name": name, "code": code, "kind": kind, "precision": precision, "params": params,
            "min_scale": min_scale, "max_scale": max_scale, "lo": lo,
            "min_value": None, "max_value": None, "auto_increment": False}
    data.update(extra)
    return data


_LO = [
    _entry("LO_TINYINT", TINYINT, K_INT, 0, "", 0, 0, True, min_value=-128, max_value=127, auto_increment=True),
    _entry("LO_SMALLINT", SMALLINT, K_INT, 0, "", 0, 0, True, min_value=-32768, max_value=32767, auto_increment=True),
    _entry("LO_INTEGER", INTEGER, K_INT, 0, "", 0, 0, True, min_value=-2147483648, max_value=2147483647, auto_increment=True),
    _entry("LO_BIGINT", BIGINT, K_INT, 0, "", 0, 0, True, auto_increment=True),
    _entry("LO_REAL", REAL, K_REAL, 0, "", 0, 0, True),
    _entry("LO_DOUBLE", DOUBLE, K_REAL, 0, "", 0, 0, True),
    _entry("LO_NUMERIC", NUMERIC, K_NUMERIC, 0, "", 0, 0, True),
    _entry("LO_DECIMAL", DECIMAL, K_DECIMAL, 18, "PRECISION,SCALE", 0, 18, True),
    _entry("LO_CHAR", CHAR, K_TEXT, UNLIMITED, "LENGTH", 0, 0, True),
    _entry("LO_VARCHAR", VARCHAR, K_TEXT, UNLIMITED, "LENGTH", 0, 0, True),
    _entry("LO_LONGVARCHAR", LONGVARCHAR, K_TEXT, UNLIMITED, "", 0, 0, True),
    _entry("LO_VARIANT", VARCHAR, K_VARIANT, UNLIMITED, "", 0, 0, True),
    _entry("LO_BOOLEAN", BOOLEAN, K_BOOL, 0, "", 0, 0, True),
    _entry("LO_DATE", DATE, K_DATE, 10, "", 0, 0, True),
    _entry("LO_TIME", TIME, K_TIME, 15, "SCALE", 0, 6, True),
    _entry("LO_TIMESTAMP", TIMESTAMP, K_TIMESTAMP, 29, "SCALE", 0, 6, True),
    _entry("LO_BINARY", BINARY, K_BINARY, UNLIMITED, "LENGTH", 0, 0, True),
    _entry("LO_VARBINARY", VARBINARY, K_BINARY, UNLIMITED, "LENGTH", 0, 0, True),
    _entry("LO_LONGVARBINARY", LONGVARBINARY, K_BINARY, UNLIMITED, "", 0, 0, True),
]
LO_BY_NAME = {e["name"]: e for e in _LO}

_EXTERNAL_BY_CODE = [
    (BIGINT, K_INT, 0, ["INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT", "MEDIUMINT",
                        "INT2", "INT8", "UNSIGNED BIG INT"]),
    (DOUBLE, K_REAL, 0, ["DOUBLE", "REAL", "FLOAT", "DOUBLE PRECISION"]),
    (VARCHAR, K_TEXT, UNLIMITED, ["TEXT", "VARCHAR", "CHAR", "NCHAR", "NVARCHAR", "CHARACTER",
                                  "NATIVE CHARACTER", "VARYING CHARACTER", "CLOB"]),
    (BOOLEAN, K_BOOL, 0, ["BOOLEAN", "BOOL"]),
    (NUMERIC, K_NUMERIC, 0, ["NUMERIC", "DECIMAL"]),
    (DATE, K_DATE, 10, ["DATE"]),
    (TIME, K_TIME, 15, ["TIME"]),
    (TIMESTAMP, K_TIMESTAMP, 29, ["TIMESTAMP", "DATETIME"]),
    (LONGVARBINARY, K_BINARY, UNLIMITED, ["BLOB"]),
]
_EXTERNAL = []
for _code, _kind, _precision, _names in _EXTERNAL_BY_CODE:
    for _name in _names:
        _EXTERNAL.append(_entry(_name, _code, _kind, _precision, "", 0, 0, False))
EXTERNAL_BY_NAME = {e["name"]: e for e in _EXTERNAL}

STRICT_SUFFIX = "_ST"
STRICT_NATIVE = {"INTEGER_ST": "INTEGER", "REAL_ST": "REAL", "TEXT_ST": "TEXT", "BLOB_ST": "BLOB",
                 "ANY_ST": "ANY"}
STRICT_ACCEPTED = ("INT", "INTEGER", "REAL", "TEXT", "BLOB", "ANY")
_STRICT_ENTRIES = [
    _entry("INTEGER_ST", BIGINT, K_INT, 0, "", 0, 0, False),
    _entry("REAL_ST", DOUBLE, K_REAL, 0, "", 0, 0, False),
    _entry("TEXT_ST", VARCHAR, K_TEXT, UNLIMITED, "", 0, 0, False),
    _entry("ANY_ST", VARCHAR, K_VARIANT, UNLIMITED, "", 0, 0, False),
    _entry("BLOB_ST", LONGVARBINARY, K_BINARY, UNLIMITED, "", 0, 0, False),
]

def _build_entries():
    order = []
    for entry in _LO:
        if entry["code"] not in order:
            order.append(entry["code"])
    result = []
    for code in order:
        result.extend(e for e in _EXTERNAL if e["code"] == code)
        result.extend(e for e in _STRICT_ENTRIES if e["code"] == code)
        result.extend(e for e in _LO if e["code"] == code)
    return result


TYPE_ENTRIES = _build_entries()

_CODE_ALIASES = {FLOAT: DOUBLE, -7: BOOLEAN}
_LO_BY_CODE = {}
for _entry_ in _LO:
    _LO_BY_CODE.setdefault(_entry_["code"], _entry_["name"])


def lo_name_for_code(code):
    try:
        code = int(code)
    except (TypeError, ValueError):
        return ""
    return _LO_BY_CODE.get(_CODE_ALIASES.get(code, code), "")

_LABEL = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_$ ]*?)\s*(?:\(\s*([+-]?\d+)\s*(?:,\s*([+-]?\d+)\s*)?\))?\s*$")
_VARIANT_NAME = "LO_VARIANT"


def parse_label(label):
    text = (label or "").strip()
    if not text:
        return "", None, None
    match = _LABEL.match(text)
    if not match:
        name = text.split("(")[0]
        return " ".join(name.upper().split()), None, None
    name = " ".join(match.group(1).upper().split())
    first = int(match.group(2)) if match.group(2) is not None else None
    second = int(match.group(3)) if match.group(3) is not None else None
    return name, first, second


def _fallback(name):
    if "REAL" in name or "FLOA" in name or "DOUB" in name:
        return EXTERNAL_BY_NAME["DOUBLE"]
    if "INT" in name:
        return EXTERNAL_BY_NAME["BIGINT"]
    if "CHAR" in name or "TEXT" in name or "CLOB" in name:
        return EXTERNAL_BY_NAME["VARCHAR"]
    if "BLOB" in name:
        return EXTERNAL_BY_NAME["BLOB"]
    return EXTERNAL_BY_NAME["NUMERIC"]


def _column_type(entry, name, size, scale):
    return ColumnType(entry["code"], name, size, scale, entry["kind"], entry["lo"],
                      entry["min_value"], entry["max_value"])


def classify(label):
    name, first, second = parse_label(label)
    if name in ("", "ANY"):
        entry = LO_BY_NAME[_VARIANT_NAME]
        return _column_type(entry, _VARIANT_NAME, UNLIMITED, 0)
    entry = LO_BY_NAME.get(name)
    if entry is not None:
        return _column_type(entry, name, *_lo_numbers(entry, first, second))
    entry = EXTERNAL_BY_NAME.get(name)
    if entry is None:
        entry = _fallback(name)
    return _column_type(entry, name, entry["precision"], 0)


def _lo_numbers(entry, first, second):
    name = entry["name"]
    if name in ("LO_CHAR", "LO_VARCHAR", "LO_BINARY", "LO_VARBINARY"):
        return (first if first is not None and first > 0 else entry["precision"]), 0
    if name == "LO_DECIMAL":
        if first is None:
            return entry["precision"], 0
        scale = second if second is not None else 0
        return first, max(0, scale)
    if name in ("LO_TIME", "LO_TIMESTAMP"):
        scale = second if second is not None else (first if first is not None else 0)
        return entry["precision"], max(0, min(6, scale))
    return entry["precision"], entry["min_scale"]


def decimal_scale(label):
    name, first, second = parse_label(label)
    if name != "LO_DECIMAL":
        return None
    return max(0, second) if second is not None else 0


def display_size(column_type):
    kind, code = column_type.kind, column_type.code
    if kind == K_INT:
        return {TINYINT: 4, SMALLINT: 6, INTEGER: 11, BIGINT: 20}.get(code, 20)
    if kind == K_REAL:
        return 25
    if kind == K_NUMERIC:
        return 40
    if kind == K_DECIMAL:
        return column_type.size + 2
    if kind in (K_TEXT, K_VARIANT, K_BINARY):
        return column_type.size
    if kind == K_BOOL:
        return 5
    if kind == K_DATE:
        return 10
    if kind == K_TIME:
        return 8 + (column_type.scale + 1 if column_type.scale else 0)
    if kind == K_TIMESTAMP:
        return 19 + (column_type.scale + 1 if column_type.scale else 0)
    return 40


def is_signed(column_type):
    return column_type.kind in (K_INT, K_REAL, K_NUMERIC, K_DECIMAL)


def is_case_sensitive(column_type):
    return column_type.kind in (K_TEXT, K_VARIANT)


def strict_native(type_name):
    return STRICT_NATIVE.get((type_name or "").strip().upper())


def strict_accepts(label):
    return (label or "").strip().upper() in STRICT_ACCEPTED


def label_for_creation(type_name, first=None, second=None):
    numbers = [n for n in (first, second) if n is not None]
    if not numbers:
        return type_name
    return "%s(%s)" % (type_name, ",".join(str(n) for n in numbers))


TYPE_INFO_COLUMNS = (
    ("TYPE_NAME", VARCHAR), ("DATA_TYPE", INTEGER), ("PRECISION", INTEGER),
    ("LITERAL_PREFIX", VARCHAR), ("LITERAL_SUFFIX", VARCHAR), ("CREATE_PARAMS", VARCHAR),
    ("NULLABLE", INTEGER), ("CASE_SENSITIVE", BOOLEAN), ("SEARCHABLE", INTEGER),
    ("UNSIGNED_ATTRIBUTE", BOOLEAN), ("FIXED_PREC_SCALE", BOOLEAN), ("AUTO_INCREMENT", BOOLEAN),
    ("LOCAL_TYPE_NAME", VARCHAR), ("MINIMUM_SCALE", INTEGER), ("MAXIMUM_SCALE", INTEGER),
    ("SQL_DATA_TYPE", INTEGER), ("SQL_DATETIME_SUB", INTEGER), ("NUM_PREC_RADIX", INTEGER),
)

_QUOTED_KINDS = (K_TEXT, K_VARIANT, K_DATE, K_TIME, K_TIMESTAMP)


def type_info_rows():
    rows = []
    for entry in TYPE_ENTRIES:
        quoted = entry["kind"] in _QUOTED_KINDS
        rows.append((
            entry["name"], entry["code"], entry["precision"],
            "'" if quoted else None, "'" if quoted else None,
            entry["params"] or None,
            1,
            entry["kind"] in (K_TEXT, K_VARIANT),
            3,
            False,
            False,
            entry["auto_increment"],
            entry["name"],
            entry["min_scale"], entry["max_scale"],
            0, 0,
            10 if entry["kind"] in (K_INT, K_REAL, K_NUMERIC, K_DECIMAL) else 0,
        ))
    return rows
