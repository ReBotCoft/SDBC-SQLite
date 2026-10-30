# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import datetime
import math
import re
from decimal import Decimal
from decimal import InvalidOperation
from decimal import ROUND_HALF_UP

from sdbc_pysqlite import errors
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.errors import DriverError

_UTC = datetime.timezone.utc
_EPOCH = datetime.datetime(1970, 1, 1)
_JULIAN_EPOCH = 2440587.5
JULIAN_MAX = 5373484.5
SECONDS_MAX = 1e11
INT64_MIN, INT64_MAX = -(2 ** 63), 2 ** 63 - 1

_RANGES = {
    "Byte": (-128, 127),
    "Short": (-32768, 32767),
    "Int": (-2147483648, 2147483647),
    "Long": (INT64_MIN, INT64_MAX),
}

_DATE_TEXT = re.compile(
    r"^\s*(?P<y>\d{4})-(?P<mo>\d{2})-(?P<d>\d{2})"
    r"(?:[ T](?P<h>\d{2}):(?P<mi>\d{2})(?::(?P<s>\d{2})(?:[.,](?P<f>\d+))?)?)?"
    r"\s*(?P<z>Z|[+-]\d{2}(?::?\d{2})?)?\s*$", re.IGNORECASE)
_TIME_TEXT = re.compile(
    r"^\s*(?P<h>\d{2}):(?P<mi>\d{2})(?::(?P<s>\d{2})(?:[.,](?P<f>\d+))?)?"
    r"\s*(?P<z>Z|[+-]\d{2}(?::?\d{2})?)?\s*$", re.IGNORECASE)


class Origin:

    def __init__(self, table="", column=""):
        self.table = table
        self.column = column

    def __str__(self):
        if self.table and self.column:
            return "%s.%s" % (self.table, self.column)
        return self.column or self.table or "?"


def _shown(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "<%d bytes>" % len(value)
    text = repr(value) if not isinstance(value, str) else value
    return text if len(text) <= 60 else text[:57] + "..."


def _not_convertible(value, origin, type_name):
    return DriverError(errors.VALUE_NOT_CONVERTIBLE, valore=_shown(value), origine=str(origin), tipo=type_name)


def _out_of_range(value, origin, type_name):
    return DriverError(errors.VALUE_OUT_OF_RANGE, valore=_shown(value), origine=str(origin), tipo=type_name)


def _parse_number(text):
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        number = float(stripped)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def exact_number(value, column_type, origin, type_name):
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, str):
        number = _parse_number(value)
        if number is None:
            raise _not_convertible(value, origin, type_name)
        value = number
    if isinstance(value, (bytes, bytearray, memoryview)) or not isinstance(value, (int, float)):
        raise _not_convertible(value, origin, type_name)
    if column_type.kind == ts.K_DECIMAL:
        if isinstance(value, float):
            if value != int(value):
                raise _not_convertible(value, origin, type_name)
            value = int(value)
        return Decimal(value).scaleb(-column_type.scale)
    return value


def _check_declared_range(number, column_type, origin):
    if column_type.min_value is None or isinstance(number, Decimal):
        return
    if number != int(number) or not (column_type.min_value <= number <= column_type.max_value):
        raise _out_of_range(number, origin, column_type.name)


def to_integer(value, column_type, origin, method):
    type_name = method.lower()
    number = exact_number(value, column_type, origin, type_name)
    if isinstance(number, Decimal):
        if number != number.to_integral_value():
            raise _not_convertible(value, origin, type_name)
        number = int(number)
    elif isinstance(number, float):
        if number != math.floor(number):
            raise _not_convertible(value, origin, type_name)
        number = int(number)
    _check_declared_range(number, column_type, origin)
    low, high = _RANGES[method]
    if not (low <= number <= high):
        raise _out_of_range(number, origin, type_name)
    return number


def to_double(value, column_type, origin, single=False):
    type_name = "float" if single else "double"
    number = exact_number(value, column_type, origin, type_name)
    try:
        result = float(number)
    except OverflowError:
        raise _out_of_range(value, origin, type_name)
    if single and abs(result) > 3.4028234663852886e38:
        raise _out_of_range(value, origin, type_name)
    return result


def to_boolean(value, column_type, origin):
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "t", "yes"):
            return True
        if low in ("false", "f", "no"):
            return False
    number = exact_number(value, column_type, origin, "boolean")
    return number != 0


def decimal_text(number):
    return format(number, "f")


def to_text(value, column_type, origin, options=None):
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    kind = column_type.kind
    if kind == ts.K_DECIMAL and isinstance(value, (int, float)):
        return decimal_text(exact_number(value, column_type, origin, "string"))
    if kind == ts.K_BOOL and isinstance(value, (int, float)):
        return "true" if value != 0 else "false"
    if kind in (ts.K_DATE, ts.K_TIME, ts.K_TIMESTAMP) and isinstance(value, (int, float)):
        parts = read_datetime(value, column_type, origin, options)
        if kind == ts.K_DATE:
            return "%04d-%02d-%02d" % parts[:3]
        if kind == ts.K_TIME:
            return _time_text(parts[3:], column_type.scale)
        return "%04d-%02d-%02d %s" % (parts[0], parts[1], parts[2], _time_text(parts[3:], column_type.scale))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex().upper()
    return str(value)


def to_bytes(value, column_type, origin):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    raise _not_convertible(value, origin, "bytes")


def _time_text(parts, scale):
    hour, minute, second, nanos = parts
    text = "%02d:%02d:%02d" % (hour, minute, second)
    if scale > 0:
        text += "." + ("%09d" % nanos)[:scale]
    return text


def _fraction_nanos(fraction):
    if not fraction:
        return 0
    return int((fraction + "000000000")[:9])


def _from_julian(number):
    return _EPOCH + datetime.timedelta(days=number - _JULIAN_EPOCH)


def _from_number(number):
    magnitude = abs(number)
    if number >= 0 and magnitude <= JULIAN_MAX:
        return _from_julian(float(number))
    if magnitude > SECONDS_MAX:
        number = number / 1000.0
    return _EPOCH + datetime.timedelta(seconds=float(number))


def _offset(zone_text):
    if zone_text.upper() == "Z":
        return 0
    sign = -1 if zone_text[0] == "-" else 1
    digits = zone_text[1:].replace(":", "")
    hours = int(digits[:2])
    minutes = int(digits[2:4]) if len(digits) > 2 else 0
    return sign * (hours * 60 + minutes)


def parse_datetime(value):
    if isinstance(value, bool):
        raise ValueError("bool")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            raise ValueError("number")
        moment = _from_number(value)
        nanos = moment.microsecond * 1000
        return moment.replace(microsecond=0), nanos, "utc"
    if not isinstance(value, str):
        raise ValueError("type")
    match = _DATE_TEXT.match(value)
    if match:
        year, month, day = int(match["y"]), int(match["mo"]), int(match["d"])
        hour = int(match["h"] or 0)
        minute = int(match["mi"] or 0)
        second = int(match["s"] or 0)
        nanos = _fraction_nanos(match["f"])
    else:
        match = _TIME_TEXT.match(value)
        if not match:
            number = _parse_number(value)
            if number is None:
                raise ValueError("text")
            return parse_datetime(number)
        year, month, day = 1970, 1, 1
        hour, minute, second = int(match["h"]), int(match["mi"]), int(match["s"] or 0)
        nanos = _fraction_nanos(match["f"])
    moment = datetime.datetime(year, month, day, hour, minute, second)
    zone_text = match["z"]
    if zone_text:
        moment = moment - datetime.timedelta(minutes=_offset(zone_text))
        return moment, nanos, "utc"
    return moment, nanos, "naive"


def utc_to_local(moment):
    try:
        return moment.replace(tzinfo=_UTC).astimezone().replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return moment


def local_to_utc(moment):
    try:
        return moment.astimezone(_UTC).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        return moment


def read_datetime(value, column_type, origin, options=None):
    try:
        moment, nanos, zone = parse_datetime(value)
    except (ValueError, OverflowError):
        raise DriverError(errors.DATE_UNREADABLE, valore=_shown(value), origine=str(origin))
    if zone == "utc" and column_type.kind != ts.K_DATE:
        moment = utc_to_local(moment)
    return (moment.year, moment.month, moment.day, moment.hour, moment.minute, moment.second, nanos)


def to_date(value, column_type, origin, options=None):
    return read_datetime(value, column_type, origin, options)[:3]


def to_time(value, column_type, origin, options=None):
    parts = read_datetime(value, column_type, origin, options)
    return parts[3:]


def to_timestamp(value, column_type, origin, options=None):
    return read_datetime(value, column_type, origin, options)


def encode_date(year, month, day):
    return "%04d-%02d-%02d" % (year, month, day)


def encode_time(hour, minute, second, nanos, scale):
    return _time_text((hour, minute, second, nanos), max(0, min(6, scale)))


def encode_timestamp(year, month, day, hour, minute, second, nanos, scale, date_format, zone):
    scale = max(0, min(6, scale))
    moment = datetime.datetime(year, month, day, hour, minute, second)
    if zone == "utc":
        converted = local_to_utc(moment)
    else:
        converted = moment
    if date_format == "unix":
        seconds = (converted - _EPOCH).total_seconds() + nanos / 1e9
        return int(seconds) if seconds == int(seconds) else seconds
    if date_format == "julian":
        return _JULIAN_EPOCH + ((converted - _EPOCH).total_seconds() + nanos / 1e9) / 86400.0
    text = "%04d-%02d-%02d %02d:%02d:%02d" % (
        converted.year, converted.month, converted.day, converted.hour, converted.minute, converted.second)
    if scale > 0:
        text += "." + ("%09d" % nanos)[:scale]
    return text + ("Z" if zone == "utc" else "")


def encode_decimal(value, scale, origin=""):
    try:
        number = Decimal(str(value) if not isinstance(value, Decimal) else value)
    except (InvalidOperation, ValueError):
        raise DriverError(errors.VALUE_NOT_CONVERTIBLE, valore=_shown(value), origine=str(origin), tipo="decimal")
    if not number.is_finite():
        raise DriverError(errors.VALUE_NOT_CONVERTIBLE, valore=_shown(value), origine=str(origin), tipo="decimal")
    sign, digits, exponent = number.as_tuple()
    scaled = int(Decimal((sign, digits, exponent + scale)).to_integral_value(rounding=ROUND_HALF_UP))
    if not (INT64_MIN <= scaled <= INT64_MAX):
        raise _out_of_range(value, origin, "LO_DECIMAL(%d)" % scale)
    return scaled
