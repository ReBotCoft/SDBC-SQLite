# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import datetime
from collections import namedtuple
from decimal import Decimal

from sdbc_pysqlite import decimals
from sdbc_pysqlite import errors
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite import values
from sdbc_pysqlite.errors import DriverError

Piece = namedtuple("Piece", "text slots warnings", defaults=((),))

_COMPARE = {"=", "==", "<", ">", "<=", ">=", "<>", "!=", "LIKE", "GLOB"}
_TABLE_AFTER = {"INTO", "UPDATE", "FROM", "JOIN"}
_STOP_AFTER_TABLE = {"VALUES", "SELECT", "DEFAULT", "WITH"}


def _name(token):
    return sqltext.unquote(token.text)


def _tables(sig):
    names = []
    for i, token in enumerate(sig):
        if token.kind == "word" and token.text.upper() in _TABLE_AFTER and i + 1 < len(sig):
            nxt = sig[i + 1]
            if nxt.kind in ("word", "quoted", "string") and nxt.text.upper() not in _STOP_AFTER_TABLE:
                name = _name(nxt)
                if i + 3 < len(sig) and sig[i + 2].text == "." and sig[i + 3].kind in ("word", "quoted"):
                    name = _name(sig[i + 3])
                names.append(name)
    return names


def _insert_columns(sig):
    words = [t.text.upper() if t.kind == "word" else None for t in sig]
    if not words or words[0] not in ("INSERT", "REPLACE"):
        return None, None
    try:
        into = words.index("INTO")
    except ValueError:
        return None, None
    i = into + 2
    if i < len(sig) and sig[i].text == ".":
        i += 2
    if i >= len(sig) or sig[i].text != "(":
        return None, None
    columns = []
    i += 1
    while i < len(sig) and sig[i].text != ")":
        if sig[i].kind in ("word", "quoted"):
            columns.append(_name(sig[i]))
        i += 1
    for j in range(i, len(sig)):
        if words[j] == "VALUES":
            return columns, j
    return None, None


def _values_slots(sig, columns, start, pmap):
    mapping = {}
    depth = 0
    item = 0
    i = start + 1
    while i < len(sig):
        text = sig[i].text
        if sig[i].kind == "punct" and text == "(":
            depth += 1
            if depth == 1:
                item = 0
        elif sig[i].kind == "punct" and text == ")":
            depth -= 1
        elif depth == 1 and sig[i].kind == "punct" and text == ",":
            item += 1
        elif depth == 1 and i in pmap and item < len(columns):
            before = sig[i - 1].text
            end = sqltext.parameter_end(sig, i)
            after = sig[end + 1].text if end + 1 < len(sig) else ""
            if before in ("(", ",") and after in (")", ","):
                mapping[i] = columns[item]
        i += 1
    return mapping


def _compare_column(sig, i):
    j = i - 1
    op = ""
    while j >= 0 and ((sig[j].kind == "punct" and sig[j].text in "=<>!")
                      or (sig[j].kind == "word" and sig[j].text.upper() in ("LIKE", "GLOB"))):
        op = sig[j].text.upper() + op
        j -= 1
    if op not in _COMPARE or j < 0 or sig[j].kind not in ("word", "quoted"):
        return None, None
    column = _name(sig[j])
    table = None
    if j >= 2 and sig[j - 1].text == "." and sig[j - 2].kind in ("word", "quoted"):
        table = _name(sig[j - 2])
    return column, table


def _find_type(db, tables, column, qualifier=None):
    found = []
    for table in tables:
        if qualifier is not None and table.lower() != qualifier.lower():
            continue
        try:
            for definition in schema.table_columns(db, table):
                if definition.name.lower() == column.lower():
                    found.append(definition.label)
        except Exception:
            continue
    if qualifier is not None and not found:
        return _find_type(db, tables, column, None)
    if len(found) != 1:
        return None
    return ts.classify(found[0])


def analyze(db, sql):
    pieces = []
    for text in sqltext.split_statements(sql):
        sig = sqltext.significant(text)
        pmap, count = sqltext.parameter_map(sig)
        first = {}
        for token_index, number in sorted(pmap.items()):
            first.setdefault(number, token_index)
        positions = [first[number] for number in range(count)]
        slots = []
        if positions:
            tables = _tables(sig)
            columns, start = _insert_columns(sig)
            inserted = _values_slots(sig, columns, start, pmap) if columns is not None else {}
            for i in positions:
                if i in inserted:
                    slots.append(_find_type(db, tables[:1], inserted[i]))
                    continue
                column, qualifier = _compare_column(sig, i)
                slots.append(_find_type(db, tables, column, qualifier) if column else None)
        warnings = ()
        translation = decimals.translate(db, text)
        if translation.decimal:
            for ordinal, slot in translation.slots.items():
                if ordinal < len(slots):
                    slots[ordinal] = slot
            for ordinal, slot in enumerate(slots):
                if ordinal not in translation.slots and slot is not None and slot.kind == ts.K_DECIMAL:
                    slots[ordinal] = None
            text = translation.text
            warnings = tuple(translation.warnings)
        pieces.append(Piece(text, slots, warnings))
    return pieces


def _origin(number):
    return "parametro %d" % number


def convert(value, ctype, number, options):
    kind, data = value
    origin = _origin(number)
    if isinstance(ctype, decimals.Compare):
        return _compare_value(kind, data, ctype.scale)
    column_kind = ctype.kind if ctype is not None else None
    scale = ctype.scale if ctype is not None else 0
    if kind == "null":
        return None
    if kind == "date":
        return values.encode_date(data.Year, data.Month, data.Day)
    if kind == "time":
        nanos = _nanos(data)
        return values.encode_time(data.Hours, data.Minutes, data.Seconds, nanos,
                                  scale if column_kind == ts.K_TIME else (6 if nanos else 0))
    if kind == "timestamp":
        nanos = _nanos(data)
        use = scale if column_kind == ts.K_TIMESTAMP else (6 if nanos else 0)
        return values.encode_timestamp(data.Year, data.Month, data.Day, data.Hours, data.Minutes,
                                       data.Seconds, nanos, use, options.date_time_format,
                                       options.date_time_zone)
    if column_kind == ts.K_DECIMAL and kind in ("int", "real", "text", "decimal"):
        return values.encode_decimal(data, ctype.scale, origin)
    if kind == "decimal":
        if data == data.to_integral_value():
            return int(data)
        return float(data)
    if kind == "bool":
        return 1 if data else 0
    return data


def _compare_value(kind, data, scale):
    if kind == "null":
        return None
    if kind in ("int", "real", "decimal", "text"):
        try:
            number = Decimal(str(data).strip()) if kind != "decimal" else data
        except Exception:
            return data
        if not number.is_finite():
            return data
        scaled = decimals.shift(number, scale)
        if scaled == scaled.to_integral_value():
            value = int(scaled)
            return value if -2 ** 63 <= value < 2 ** 63 else float(scaled)
        return float(scaled)
    if kind == "bool":
        return (1 if data else 0) * 10 ** scale
    return data


def _nanos(struct):
    nanos = getattr(struct, "NanoSeconds", None)
    if nanos is None:
        nanos = getattr(struct, "HundredthSeconds", 0) * 10000000
    return int(nanos)


def classify_object(x, number):
    if x is None:
        return ("null", None)
    if isinstance(x, bool):
        return ("bool", x)
    if isinstance(x, int):
        return ("int", x)
    if isinstance(x, float):
        return ("real", x)
    if isinstance(x, Decimal):
        return ("decimal", x)
    if isinstance(x, str):
        return ("text", x)
    if isinstance(x, (bytes, bytearray, memoryview)):
        return ("blob", bytes(x))
    if isinstance(x, datetime.datetime):
        return ("timestamp", _Struct(x.year, x.month, x.day, x.hour, x.minute, x.second, x.microsecond * 1000))
    if isinstance(x, datetime.date):
        return ("date", _Struct(x.year, x.month, x.day))
    if isinstance(x, datetime.time):
        return ("time", _Struct(0, 0, 0, x.hour, x.minute, x.second, x.microsecond * 1000))
    if hasattr(x, "Year") and hasattr(x, "Hours"):
        return ("timestamp", x)
    if hasattr(x, "Year"):
        return ("date", x)
    if hasattr(x, "Hours"):
        return ("time", x)
    if hasattr(x, "value") and isinstance(x.value, bytes):
        return ("blob", bytes(x.value))
    raise DriverError(errors.VALUE_NOT_CONVERTIBLE, valore=type(x).__name__, origine=_origin(number),
                      tipo="parametro")


class _Struct:

    def __init__(self, year=0, month=0, day=0, hours=0, minutes=0, seconds=0, nanos=0):
        self.Year, self.Month, self.Day = year, month, day
        self.Hours, self.Minutes, self.Seconds, self.NanoSeconds = hours, minutes, seconds, nanos
