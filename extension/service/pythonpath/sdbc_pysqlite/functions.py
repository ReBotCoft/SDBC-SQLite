# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import datetime
import json
import math
import random
import re
import time
import unicodedata
import uuid as uuid_module
from collections import namedtuple
from decimal import Decimal, ROUND_DOWN
from functools import lru_cache


@lru_cache(maxsize=8192)
def _plain_char(char):
    decomposed = unicodedata.normalize("NFD", char)
    base = "".join(c for c in decomposed if not unicodedata.combining(c))
    return base if len(base) == 1 else char


@lru_cache(maxsize=8192)
def _lower_char(char):
    lowered = char.lower()
    return lowered if len(lowered) == 1 else char


def strip_accents(text):
    if text.isascii():
        return text
    return "".join(_plain_char(c) for c in text)


def fold(text):
    plain = strip_accents(text)
    if plain.isascii():
        return plain.lower()
    return "".join(_lower_char(c) for c in plain)


def _as_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode("utf-8", "replace")
    if isinstance(value, float):
        return repr(value)
    return str(value)


def upper(value):
    return None if value is None else _as_text(value).upper()


def lower(value):
    return None if value is None else _as_text(value).lower()


_MANY = object()
_ONE = object()


@lru_cache(maxsize=1024)
def _like_tokens(pattern, escape):
    folded = fold(pattern)
    escape = fold(escape) if escape else None
    tokens = []
    i = 0
    while i < len(folded):
        char = folded[i]
        if escape is not None and char == escape and i + 1 < len(folded):
            i += 1
            tokens.append(folded[i])
        elif char == "%":
            if not tokens or tokens[-1] is not _MANY:
                tokens.append(_MANY)
        elif char == "_":
            tokens.append(_ONE)
        else:
            tokens.append(char)
        i += 1
    return tuple(tokens)


def _like_match(tokens, text):
    size = len(text)
    count = len(tokens)
    t = p = 0
    star = -1
    mark = 0
    while t < size:
        if p < count and tokens[p] is _MANY:
            star = p
            mark = t
            p += 1
        elif p < count and (tokens[p] is _ONE or tokens[p] == text[t]):
            p += 1
            t += 1
        elif star >= 0:
            p = star + 1
            mark += 1
            t = mark
        else:
            return False
    while p < count and tokens[p] is _MANY:
        p += 1
    return p == count


def like(pattern, text, escape=None):
    if pattern is None or text is None:
        return None
    if escape is not None:
        escape = _as_text(escape)
        if len(escape) != 1:
            raise ValueError("ESCAPE expression must be a single character")
    return 1 if _like_match(_like_tokens(_as_text(pattern), escape), fold(_as_text(text))) else 0


def nocase_compare(a, b):
    fa, fb = fold(a), fold(b)
    if fa != fb:
        return -1 if fa < fb else 1
    la, lb = a.lower(), b.lower()
    if la != lb:
        return -1 if la < lb else 1
    return 0


@lru_cache(maxsize=1024)
def _compile(pattern, flags):
    try:
        return re.compile(strip_accents(pattern), re.IGNORECASE | flags)
    except re.error as exception:
        raise ValueError("invalid regular expression: %s" % exception)


def _regex_args(text, pattern, flags=0):
    return strip_accents(_as_text(text)), _compile(_as_text(pattern), flags)


def regexp(pattern, text):
    if pattern is None or text is None:
        return None
    plain, compiled = _regex_args(text, pattern)
    return 1 if compiled.search(plain) else 0


def regexp_matches(text, pattern):
    if pattern is None or text is None:
        return None
    plain, compiled = _regex_args(text, pattern)
    return 1 if compiled.fullmatch(plain) else 0


def regexp_substring(text, pattern):
    if pattern is None or text is None:
        return None
    original = _as_text(text)
    plain, compiled = _regex_args(text, pattern)
    found = compiled.search(plain)
    return original[found.start():found.end()] if found else None


def regexp_substring_array(text, pattern):
    if pattern is None or text is None:
        return None
    original = _as_text(text)
    plain, compiled = _regex_args(text, pattern)
    return json.dumps([original[m.start():m.end()] for m in compiled.finditer(plain)], ensure_ascii=False)


def regexp_count(text, pattern):
    if pattern is None or text is None:
        return None
    plain, compiled = _regex_args(text, pattern)
    return sum(1 for _ in compiled.finditer(plain))


def regexp_instr(text, pattern):
    if pattern is None or text is None:
        return None
    plain, compiled = _regex_args(text, pattern)
    found = compiled.search(plain)
    return found.start() + 1 if found else 0


def _expand(replacement, match, original):
    out = []
    i = 0
    while i < len(replacement):
        char = replacement[i]
        if char == "\\" and i + 1 < len(replacement):
            i += 1
            out.append(replacement[i])
        elif char == "$" and i + 1 < len(replacement) and replacement[i + 1].isdigit():
            number = int(replacement[i + 1])
            if number > (match.re.groups or 0):
                raise ValueError("No group %d" % number)
            span = match.span(number)
            out.append(original[span[0]:span[1]] if span[0] >= 0 else "")
            i += 1
        else:
            out.append(char)
        i += 1
    return "".join(out)


def regexp_replace(text, pattern, replacement="", start=1, count=0, options=""):
    if pattern is None or text is None:
        return None
    if start not in (None, 1):
        raise ValueError("REGEXP_REPLACE: the start position must be 1")
    flags = 0
    for letter in _as_text(options or ""):
        if letter == "n":
            flags |= re.DOTALL
        elif letter == "m":
            flags |= re.MULTILINE
        elif letter not in "ic":
            raise ValueError("REGEXP_REPLACE: unknown option '%s'" % letter)
    original = _as_text(text)
    plain, compiled = _regex_args(text, pattern, flags)
    replacement = "" if replacement is None else _as_text(replacement)
    limit = int(count or 0)
    out = []
    last = 0
    done = 0
    for match in compiled.finditer(plain):
        if limit and done >= limit:
            break
        out.append(original[last:match.start()])
        out.append(_expand(replacement, match, original))
        last = match.end()
        done += 1
    out.append(original[last:])
    return "".join(out)


def left(text, count):
    if text is None or count is None:
        return None
    return "" if int(count) < 1 else _as_text(text)[:int(count)]


def right(text, count):
    if text is None or count is None:
        return None
    count = int(count)
    return "" if count < 1 else _as_text(text)[-count:]


def locate(search, text, start=None):
    if search is None or text is None:
        return None
    begin = 0 if start is None else max(int(start) - 1, 0)
    return _as_text(text).find(_as_text(search), begin) + 1


def instr3(text, search, start):
    return locate(search, text, start)


def _pad(text, length, pad, at_left):
    if text is None or length is None:
        return None
    text = _as_text(text)
    length = int(length)
    pad = " " if pad is None else _as_text(pad)
    if length <= 0:
        return ""
    if len(text) >= length:
        return text[:length]
    if not pad:
        return text
    fill = (pad * (length // len(pad) + 1))[:length - len(text)]
    return fill + text if at_left else text + fill


def lpad(text, length, pad=None):
    return _pad(text, length, pad, True)


def rpad(text, length, pad=None):
    return _pad(text, length, pad, False)


def repeat(text, count):
    if text is None or count is None:
        return None
    return _as_text(text) * max(int(count), 0)


def space(count):
    if count is None or int(count) < 0:
        return None
    return " " * int(count)


def reverse(text):
    return None if text is None else _as_text(text)[::-1]


def replace2(text, search):
    if text is None or search is None:
        return None
    return _as_text(text).replace(_as_text(search), "") if _as_text(search) else _as_text(text)


def translate(text, source, target):
    if text is None or source is None or target is None:
        return None
    source, target = _as_text(source), _as_text(target)
    table = {}
    for index, char in enumerate(source):
        if char not in table:
            table[char] = target[index] if index < len(target) else ""
    return "".join(table.get(c, c) for c in _as_text(text))


def ascii_code(text):
    if text is None:
        return None
    text = _as_text(text)
    return ord(text[0]) if text else None


def bit_length(text):
    return None if text is None else len(_as_text(text).encode("utf-8")) * 8


def char_length(text):
    return None if text is None else len(_as_text(text))


def insert(text, start, length, other):
    if text is None:
        return None if other is None else _as_text(other)
    if other is None:
        return _as_text(text)
    text, other = _as_text(text), _as_text(other)
    start, length = int(start), int(length)
    if start < 1 or length <= 0 or not other or start > len(text):
        return text
    return text[:start - 1] + other + text[start - 1 + length:]


def overlay(text, other, start, length=None):
    if text is None or other is None or start is None:
        return None
    other = _as_text(other)
    count = len(other) if length is None else int(length)
    start = int(start)
    text = _as_text(text)
    return text[:max(start - 1, 0)] + other + text[max(start - 1, 0) + max(count, 0):]


def trim_form(chars, text, mode):
    if text is None or chars is None:
        return None
    text, chars = _as_text(text), _as_text(chars)
    if len(chars) != 1:
        raise ValueError("data exception: trim error")
    if mode in (1, 3):
        text = text.lstrip(chars)
    if mode in (2, 3):
        text = text.rstrip(chars)
    return text


_SOUNDEX = {**dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"), **dict.fromkeys("DT", "3"),
            "L": "4", **dict.fromkeys("MN", "5"), "R": "6"}


def soundex(text):
    if text is None:
        return None
    letters = [c for c in strip_accents(_as_text(text)).upper() if "A" <= c <= "Z"]
    if not letters:
        return ""
    result = letters[0]
    previous = _SOUNDEX.get(letters[0], "")
    for char in letters[1:]:
        code = _SOUNDEX.get(char, "")
        if code and code != previous:
            result += code
        if char not in "HW":
            previous = code
        if len(result) == 4:
            break
    return (result + "000")[:4]


def difference(a, b):
    if a is None or b is None:
        return 0
    sa, sb = soundex(a), soundex(b)
    return sum(1 for x, y in zip(sa, sb) if x == y)


def hex_to_raw(text):
    if text is None:
        return None
    try:
        return bytes.fromhex(_as_text(text))
    except ValueError:
        raise ValueError("invalid hexadecimal string")


def raw_to_hex(value):
    if value is None:
        return None
    raw = bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else _as_text(value).encode("utf-8")
    return raw.hex().upper()


def cot(x):
    if x is None:
        return None
    try:
        return 1.0 / math.tan(float(x))
    except (ValueError, ZeroDivisionError):
        return None


def truncate(x, places=0):
    if x is None or places is None:
        return None
    places = int(places)
    exact = Decimal(repr(x)) if isinstance(x, float) else Decimal(int(x)) if isinstance(x, (int, bool)) \
        else Decimal(_as_text(x))
    if places >= 0:
        cut = exact.quantize(Decimal(1).scaleb(-places), rounding=ROUND_DOWN)
    else:
        cut = exact.scaleb(places).quantize(Decimal(1), rounding=ROUND_DOWN).scaleb(-places)
    return int(cut) if isinstance(x, int) and places >= 0 or (isinstance(x, int) and places < 0) else float(cut)


def _integer(value):
    return None if value is None else int(value)


def bit_and(a, b):
    return None if a is None or b is None else int(a) & int(b)


def bit_or(a, b):
    return None if a is None or b is None else int(a) | int(b)


def bit_xor(a, b):
    return None if a is None or b is None else int(a) ^ int(b)


def bit_not(a):
    return None if a is None else ~int(a)


def bit_and_not(a, b):
    return None if a is None or b is None else int(a) & ~int(b)


def to_number(value, _format=None):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    text = _as_text(value).strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            raise ValueError("data exception: invalid character value for cast")


def width_bucket(value, low, high, count):
    if None in (value, low, high, count):
        return None
    count = int(count)
    if count < 1 or low == high:
        raise ValueError("width_bucket: invalid arguments")
    if low < high:
        if value < low:
            return 0
        if value >= high:
            return count + 1
        return int((value - low) * count / (high - low)) + 1
    if value > low:
        return 0
    if value <= high:
        return count + 1
    return int((low - value) * count / (low - high)) + 1


def nvl(a, b):
    return b if a is None else a


def nvl2(a, b, c):
    return b if a is not None else c


def _truthy(value):
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes", "y")
    return bool(value)


def casewhen(condition, a, b):
    return a if _truthy(condition) else b


def decode(main, *rest):
    pairs = len(rest) // 2
    for index in range(pairs):
        if rest[2 * index] == main:
            return rest[2 * index + 1]
    return rest[-1] if len(rest) % 2 else None


def _order_key(value):
    if isinstance(value, (int, float)):
        return (1, value)
    if isinstance(value, str):
        return (2, value)
    return (3, bytes(value))


def greatest(*values):
    return None if not values or any(v is None for v in values) else max(values, key=_order_key)


def least(*values):
    return None if not values or any(v is None for v in values) else min(values, key=_order_key)


def uuid_new():
    return uuid_module.uuid4().bytes


def uuid_convert(value):
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        if len(raw) != 16:
            raise ValueError("UUID: a binary value must have 16 bytes")
        return str(uuid_module.UUID(bytes=raw))
    return uuid_module.UUID(_as_text(value).strip()).bytes


Names = namedtuple("Names", "days days_short months months_short")

ENGLISH_NAMES = Names(
    ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"),
    ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
     "November", "December"),
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))

_ISO = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?)?"
                  r"\s*(?:Z|[+-]\d{2}(?::?\d{2})?)?\s*$")
_TIME = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2})(?:[.,](\d+))?)?\s*$")
_EPOCH = datetime.datetime(1970, 1, 1)
_JULIAN_EPOCH = 2440587.5


class Moment(namedtuple("Moment", "value kind source")):
    pass


def parse_moment(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if abs(value) < 1e7:
            return Moment(_EPOCH + datetime.timedelta(days=value - _JULIAN_EPOCH), "timestamp", "julian")
        return Moment(_EPOCH + datetime.timedelta(seconds=value), "timestamp", "unix")
    text = _as_text(value)
    found = _ISO.match(text)
    try:
        if found:
            year, month, day, hour, minute, second, fraction = found.groups()
            micro = int((fraction or "0").ljust(6, "0")[:6])
            moment = datetime.datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0),
                                       int(second or 0), micro)
            return Moment(moment, "date" if hour is None else "timestamp", "text")
        found = _TIME.match(text)
        if found:
            hour, minute, second, fraction = found.groups()
            micro = int((fraction or "0").ljust(6, "0")[:6])
            return Moment(datetime.datetime(1970, 1, 1, int(hour), int(minute), int(second or 0), micro),
                          "time", "text")
    except ValueError:
        pass
    raise ValueError("invalid date or time: %s" % text)


def format_moment(moment, kind=None, source=None):
    kind = kind or "timestamp"
    source = source or "text"
    if kind == "time":
        text = moment.strftime("%H:%M:%S")
    elif source == "unix":
        return int((moment - _EPOCH).total_seconds())
    elif source == "julian":
        return _JULIAN_EPOCH + (moment - _EPOCH).total_seconds() / 86400.0
    elif kind == "date":
        return moment.strftime("%Y-%m-%d")
    else:
        text = moment.strftime("%Y-%m-%d %H:%M:%S")
    if kind != "date" and moment.microsecond:
        text += ".%03d" % (moment.microsecond // 1000) if moment.microsecond % 1000 == 0 \
            else ".%06d" % moment.microsecond
    return text


_FIELDS = {
    "yy": "year", "yyyy": "year", "year": "year", "qq": "quarter", "quarter": "quarter", "mm": "month",
    "month": "month", "dd": "day", "day": "day", "hh": "hour", "hour": "hour", "mi": "minute",
    "minute": "minute", "ss": "second", "second": "second", "ms": "millisecond", "millisecond": "millisecond",
    "milli_second": "millisecond", "mcs": "microsecond", "microsecond": "microsecond", "ns": "nanosecond",
    "nanosecond": "nanosecond", "frac_second": "nanosecond", "week": "week", "wk": "week",
}


def _field(name):
    key = _as_text(name).strip().lower()
    if key.startswith("sql_tsi_"):
        key = key[8:]
    if key not in _FIELDS:
        raise ValueError("invalid datetime field: %s" % _as_text(name))
    return _FIELDS[key]


def _add_months(moment, months):
    index = moment.year * 12 + moment.month - 1 + months
    year, month = divmod(index, 12)
    if not 1 <= year <= 9999:
        raise ValueError("date out of range")
    first = datetime.date(year, month + 1, 1)
    last_day = ((first.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
                - datetime.timedelta(days=1)).day
    return moment.replace(year=year, month=month + 1, day=min(moment.day, last_day))


def _last_day_of_month(moment):
    return (moment.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)


def _ordinal_in(moment, field):
    if field == "year":
        return moment.year
    if field == "quarter":
        return moment.year * 4 + (moment.month - 1) // 3
    if field == "month":
        return moment.year * 12 + moment.month - 1
    if field == "week":
        return moment.toordinal() // 7
    days = moment.toordinal()
    if field == "day":
        return days
    seconds = days * 86400 + moment.hour * 3600 + moment.minute * 60 + moment.second
    if field == "hour":
        return days * 24 + moment.hour
    if field == "minute":
        return days * 1440 + moment.hour * 60 + moment.minute
    if field == "second":
        return seconds
    micro = seconds * 1000000 + moment.microsecond
    if field == "millisecond":
        return micro // 1000
    if field == "microsecond":
        return micro
    return micro * 1000


class _Dates:

    def __init__(self, names_provider, zone, date_format):
        self._provider = names_provider
        self._names = None
        self.zone = zone
        self.date_format = date_format

    @property
    def names(self):
        if self._names is None:
            try:
                names = self._provider() if self._provider else None
            except Exception:
                names = None
            self._names = names if names else ENGLISH_NAMES
        return self._names

    def _now(self):
        if self.zone == "utc":
            return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        return datetime.datetime.now()

    def curdate(self):
        return format_moment(self._now().replace(hour=0, minute=0, second=0, microsecond=0), "date",
                             self.date_format)

    def curtime(self):
        return format_moment(self._now().replace(microsecond=0), "time")

    def now(self):
        return format_moment(self._now().replace(microsecond=0), "timestamp", self.date_format)

    @staticmethod
    def _part(value, getter):
        moment = parse_moment(value)
        return None if moment is None else getter(moment.value)

    def year(self, value):
        return self._part(value, lambda d: d.year)

    def month(self, value):
        return self._part(value, lambda d: d.month)

    def day(self, value):
        return self._part(value, lambda d: d.day)

    def hour(self, value):
        return self._part(value, lambda d: d.hour)

    def minute(self, value):
        return self._part(value, lambda d: d.minute)

    def second(self, value):
        return self._part(value, lambda d: d.second)

    def quarter(self, value):
        return self._part(value, lambda d: (d.month - 1) // 3 + 1)

    def dayofweek(self, value):
        return self._part(value, lambda d: (d.weekday() + 1) % 7 + 1)

    def dayofyear(self, value):
        return self._part(value, lambda d: d.timetuple().tm_yday)

    def week(self, value):
        def week_of_year(d):
            january_first = d.replace(month=1, day=1)
            offset = (january_first.weekday() + 1) % 7
            return (d.timetuple().tm_yday - 1 + offset) // 7 + 1
        return self._part(value, week_of_year)

    def days(self, value):
        return self._part(value, lambda d: d.toordinal())

    def seconds_since_midnight(self, value):
        return self._part(value, lambda d: d.hour * 3600 + d.minute * 60 + d.second)

    def dayname(self, value):
        return self._part(value, lambda d: self.names.days[(d.weekday() + 1) % 7])

    def monthname(self, value):
        return self._part(value, lambda d: self.names.months[d.month - 1])

    def extract(self, field, value):
        name = _as_text(field).strip().upper()
        getters = {
            "YEAR": self.year, "MONTH": self.month, "DAY": self.day, "DAY_OF_MONTH": self.day,
            "HOUR": self.hour, "MINUTE": self.minute, "SECOND": self.second, "QUARTER": self.quarter,
            "DAY_OF_WEEK": self.dayofweek, "DAY_OF_YEAR": self.dayofyear, "WEEK_OF_YEAR": self.week,
            "SECONDS_SINCE_MIDNIGHT": self.seconds_since_midnight, "DAY_NAME": self.dayname,
            "MONTH_NAME": self.monthname, "TIMEZONE_HOUR": lambda v: 0, "TIMEZONE_MINUTE": lambda v: 0,
        }
        if name not in getters:
            raise ValueError("invalid EXTRACT field: %s" % name)
        return getters[name](value)

    def _seconds(self, moment):
        if moment.source == "text" and self.zone == "local":
            return time.mktime(moment.value.timetuple()) + moment.value.microsecond / 1e6
        return (moment.value - _EPOCH).total_seconds()

    def unix_timestamp(self, value=None):
        if value is None:
            return int(time.time())
        return int(self._seconds(parse_moment(value)))

    def unix_millis(self, value=None):
        if value is None:
            return int(time.time() * 1000)
        return int(self._seconds(parse_moment(value)) * 1000)

    @staticmethod
    def _shift(moment, field, amount):
        value = moment.value
        if field in ("year", "quarter", "month"):
            value = _add_months(value, amount * {"year": 12, "quarter": 3, "month": 1}[field])
        elif field == "week":
            value += datetime.timedelta(weeks=amount)
        elif field == "nanosecond":
            value += datetime.timedelta(microseconds=int(amount / 1000))
        else:
            unit = {"day": "days", "hour": "hours", "minute": "minutes", "second": "seconds",
                    "millisecond": "milliseconds", "microsecond": "microseconds"}[field]
            value += datetime.timedelta(**{unit: amount})
        return Moment(value, moment.kind, moment.source)

    def dateadd(self, field, amount, value):
        if field is None or amount is None or value is None:
            return None
        moment = parse_moment(value)
        shifted = self._shift(moment, _field(field), int(amount))
        return format_moment(shifted.value, shifted.kind, shifted.source)

    def datediff(self, a, b, c=None):
        if c is None:
            if a is None or b is None:
                return None
            return parse_moment(a).value.toordinal() - parse_moment(b).value.toordinal()
        if a is None or b is None or c is None:
            return None
        field = _field(a)
        return _ordinal_in(parse_moment(c).value, field) - _ordinal_in(parse_moment(b).value, field)

    def last_day(self, value):
        if value is None:
            return None
        moment = parse_moment(value)
        return format_moment(_last_day_of_month(moment.value), moment.kind, moment.source)

    def add_months(self, value, months):
        if value is None or months is None:
            return None
        moment = parse_moment(value)
        source = moment.value
        shifted = _add_months(source, int(months))
        if source.day == _last_day_of_month(source).day:
            shifted = _last_day_of_month(shifted)
        return format_moment(shifted, moment.kind, moment.source)

    def months_between(self, a, b):
        if a is None or b is None:
            return None
        d1, d2 = parse_moment(a).value, parse_moment(b).value
        months = (d1.year - d2.year) * 12 + d1.month - d2.month
        both_last = d1.day == _last_day_of_month(d1).day and d2.day == _last_day_of_month(d2).day
        if d1.day == d2.day or both_last:
            return float(months)
        seconds1 = d1.hour * 3600 + d1.minute * 60 + d1.second + d1.microsecond / 1e6
        seconds2 = d2.hour * 3600 + d2.minute * 60 + d2.second + d2.microsecond / 1e6
        return months + (d1.day - d2.day) / 31.0 + (seconds1 - seconds2) / (31.0 * 86400)

    def next_day(self, value, weekday):
        if value is None or weekday is None:
            return None
        moment = parse_moment(value)
        wanted = _as_text(weekday).strip().lower()
        names = ENGLISH_NAMES
        found = None
        for index in range(7):
            options = {names.days[index].lower(), names.days_short[index].lower(),
                       self.names.days[index].lower(), self.names.days_short[index].lower()}
            if wanted in options:
                found = index
                break
        if found is None:
            raise ValueError("invalid day name: %s" % _as_text(weekday))
        current = (moment.value.weekday() + 1) % 7
        step = (found - current) % 7 or 7
        return format_moment(moment.value + datetime.timedelta(days=step), moment.kind, moment.source)

    def trunc_date(self, value, pattern="DD"):
        if value is None:
            return None
        moment = parse_moment(value)
        d = moment.value
        key = _as_text(pattern or "DD").strip().upper()
        if key in ("YYYY", "YY", "YEAR"):
            d = d.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif key in ("MONTH", "MM"):
            d = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif key in ("DD", "DDD"):
            d = d.replace(hour=0, minute=0, second=0, microsecond=0)
        elif key in ("HH", "HH12", "HH24"):
            d = d.replace(minute=0, second=0, microsecond=0)
        elif key == "MI":
            d = d.replace(second=0, microsecond=0)
        elif key == "SS":
            d = d.replace(microsecond=0)
        else:
            raise ValueError("invalid TRUNC format: %s" % key)
        return format_moment(d, moment.kind, moment.source)

    _ELEMENTS = ("A.M.", "P.M.", "B.C.", "A.D.", "AM", "PM", "BC", "AD", "YYYY", "RRRR", "IYYY", "YY", "IY",
                 "MONTH", "MON", "MM", "IW", "W", "DAY", "DDD", "DD", "DY", "HH12", "HH24", "HH", "MI", "SS",
                 "FF[1-9]?", "TZ")
    _FORMAT = re.compile('"[^"]*"|' + "|".join(re.escape(e).replace(r"\[1\-9\]\?", "[1-9]?")
                                                for e in sorted(_ELEMENTS, key=len, reverse=True)),
                         re.IGNORECASE)

    def to_char(self, value, pattern):
        if value is None or pattern is None:
            return None
        d = parse_moment(value).value
        names = self.names
        iso = d.isocalendar()
        meridian = "pm" if d.hour >= 12 else "am"
        out = []
        last = 0
        text = _as_text(pattern)
        for found in self._FORMAT.finditer(text):
            out.append(text[last:found.start()])
            token = found.group().upper()
            if token.startswith('"'):
                out.append(found.group()[1:-1])
            elif token in ("YYYY", "RRRR"):
                out.append("%04d" % d.year)
            elif token == "IYYY":
                out.append("%04d" % iso[0])
            elif token == "YY":
                out.append("%02d" % (d.year % 100))
            elif token == "IY":
                out.append("%02d" % (iso[0] % 100))
            elif token == "MM":
                out.append("%02d" % d.month)
            elif token == "MON":
                out.append(names.months_short[d.month - 1])
            elif token == "MONTH":
                out.append(names.months[d.month - 1])
            elif token == "IW":
                out.append("%02d" % iso[1])
            elif token == "W":
                out.append(str((d.day - 1) // 7 + 1))
            elif token == "DAY":
                out.append(names.days[(d.weekday() + 1) % 7])
            elif token == "DY":
                out.append(names.days_short[(d.weekday() + 1) % 7])
            elif token == "DD":
                out.append("%02d" % d.day)
            elif token == "DDD":
                out.append(str(d.timetuple().tm_yday))
            elif token == "HH12":
                out.append("%02d" % (d.hour % 12))
            elif token in ("HH", "HH24"):
                out.append("%02d" % d.hour)
            elif token == "MI":
                out.append("%02d" % d.minute)
            elif token == "SS":
                out.append("%02d" % d.second)
            elif token.startswith("FF"):
                digits = int(token[2:]) if len(token) > 2 else 6
                out.append(("%06d" % d.microsecond).ljust(digits, "0")[:digits])
            elif token in ("AM", "PM"):
                out.append(meridian)
            elif token in ("A.M.", "P.M."):
                out.append(meridian[0] + "." + meridian[1] + ".")
            elif token in ("BC", "AD"):
                out.append("AD")
            elif token in ("B.C.", "A.D."):
                out.append("A.D.")
            elif token == "TZ":
                out.append("+00:00")
            last = found.end()
        out.append(text[last:])
        return "".join(out)

    def to_timestamp(self, text, pattern, whole_seconds=False):
        if text is None or pattern is None:
            return None
        pattern = _as_text(pattern)
        if pattern.upper().startswith("JAVA:"):
            raise ValueError("the JAVA: format prefix is not supported")
        names = self.names
        groups = []
        regex = []
        last = 0
        for found in self._FORMAT.finditer(pattern):
            regex.append(re.escape(pattern[last:found.start()]))
            token = found.group().upper()
            if token.startswith('"'):
                regex.append(re.escape(found.group()[1:-1]))
            else:
                groups.append(token)
                if token in ("YYYY", "RRRR", "IYYY"):
                    regex.append(r"(\d{4})")
                elif token in ("YY", "IY"):
                    regex.append(r"(\d{2})")
                elif token in ("MM", "DD", "HH", "HH12", "HH24", "MI", "SS", "IW"):
                    regex.append(r"(\d{1,2})")
                elif token == "DDD":
                    regex.append(r"(\d{1,3})")
                elif token.startswith("FF"):
                    regex.append(r"(\d{1,9})")
                elif token == "MON":
                    regex.append("(" + "|".join(re.escape(n) for n in names.months_short + ENGLISH_NAMES.months_short)
                                 + ")")
                elif token == "MONTH":
                    regex.append("(" + "|".join(re.escape(n) for n in names.months + ENGLISH_NAMES.months) + ")")
                elif token in ("AM", "PM", "A.M.", "P.M."):
                    regex.append(r"([AaPp]\.?[Mm]\.?)")
                elif token in ("DAY", "DY"):
                    regex.append(r"([^\W\d_]+)")
                elif token in ("BC", "AD", "B.C.", "A.D."):
                    regex.append(r"([AaBb]\.?[CcDd]\.?)")
                else:
                    raise ValueError("unsupported format element: %s" % token)
            last = found.end()
        regex.append(re.escape(pattern[last:]))
        match = re.fullmatch("".join(regex), _as_text(text).strip(), re.IGNORECASE)
        if not match:
            raise ValueError("the text does not match the format: %s" % _as_text(text))
        year, month, day, hour, minute, second, micro, pm = 1970, 1, 1, 0, 0, 0, 0, None
        have_date = False
        for token, got in zip(groups, match.groups()):
            if token in ("YYYY", "RRRR", "IYYY"):
                year, have_date = int(got), True
            elif token in ("YY", "IY"):
                year, have_date = (2000 if int(got) <= 68 else 1900) + int(got), True
            elif token == "MM":
                month, have_date = int(got), True
            elif token in ("MON", "MONTH"):
                pool = names.months_short + ENGLISH_NAMES.months_short if token == "MON" \
                    else names.months + ENGLISH_NAMES.months
                lowered = [n.lower() for n in pool]
                month, have_date = lowered.index(got.lower()) % 12 + 1, True
            elif token == "DD":
                day, have_date = int(got), True
            elif token in ("HH", "HH24", "HH12"):
                hour = int(got)
            elif token == "MI":
                minute = int(got)
            elif token == "SS":
                second = int(got)
            elif token.startswith("FF"):
                micro = int(got.ljust(9, "0")[:6])
            elif token in ("AM", "PM", "A.M.", "P.M."):
                pm = got.lower().startswith("p")
        if pm is not None:
            hour = hour % 12 + (12 if pm else 0)
        moment = datetime.datetime(year, month, day, hour, minute, second, 0 if whole_seconds else micro)
        return format_moment(moment, "timestamp", "text")

    def to_date(self, text, pattern):
        return self.to_timestamp(text, pattern, whole_seconds=True)


def install(connection, names=None, zone="local", date_format="text", path="", like_pattern_limit=None):
    dates = _Dates(names, zone, date_format)

    def limited_like(pattern, text, escape=None):
        if pattern is not None and isinstance(pattern, str):
            if len(pattern) > like_pattern_limit // 4 and len(pattern.encode("utf-8")) > like_pattern_limit:
                raise ValueError("LIKE or GLOB pattern too complex")
        return like(pattern, text, escape)

    like_function = like if like_pattern_limit is None else limited_like
    generator = random.Random()

    def rand(seed=None):
        if seed is not None:
            generator.seed(int(seed))
        return generator.random()

    def identity():
        return connection.last_insert_rowid()

    database_name = re.sub(r"\.[^.\\/]*$", "", re.split(r"[\\/]", path)[-1]) if path else ""

    def trunc(value, second=None):
        if isinstance(second, str):
            return dates.trunc_date(value, second)
        return truncate(value, second)

    table = [
        ("upper", 1, upper, True), ("lower", 1, lower, True), ("ucase", 1, upper, True),
        ("lcase", 1, lower, True), ("like", 2, like_function, True), ("like", 3, like_function, True),
        ("regexp", 2, regexp, True), ("regexp_matches", 2, regexp_matches, True),
        ("regexp_like", 2, regexp_matches, True), ("regexp_substring", 2, regexp_substring, True),
        ("regexp_substr", 2, regexp_substring, True), ("regexp_substring_array", 2, regexp_substring_array, True),
        ("regexp_count", 2, regexp_count, True), ("regexp_instr", 2, regexp_instr, True)]
    for count in range(2, 7):
        table.append(("regexp_replace", count, regexp_replace, True))
    table += [
        ("left", 2, left, True), ("right", 2, right, True), ("locate", 2, locate, True),
        ("locate", 3, locate, True), ("instr", 3, instr3, True), ("lpad", 2, lpad, True),
        ("lpad", 3, lpad, True), ("rpad", 2, rpad, True), ("rpad", 3, rpad, True), ("repeat", 2, repeat, True),
        ("space", 1, space, True), ("reverse", 1, reverse, True), ("replace", 2, replace2, True),
        ("translate", 3, translate, True), ("ascii", 1, ascii_code, True), ("bit_length", 1, bit_length, True),
        ("char_length", 1, char_length, True), ("character_length", 1, char_length, True),
        ("insert", 4, insert, True), ("overlay", 3, overlay, True), ("overlay", 4, overlay, True),
        ("sdbc_trim", 3, trim_form, True), ("soundex", 1, soundex, True), ("difference", 2, difference, True),
        ("hextoraw", 1, hex_to_raw, True), ("rawtohex", 1, raw_to_hex, True),
        ("cot", 1, cot, True), ("truncate", 1, truncate, True), ("truncate", 2, truncate, True),
        ("trunc", 2, trunc, True), ("bitand", 2, bit_and, True), ("bitor", 2, bit_or, True),
        ("bitxor", 2, bit_xor, True), ("bitnot", 1, bit_not, True), ("bitandnot", 2, bit_and_not, True),
        ("to_number", 1, to_number, True), ("to_number", 2, to_number, True),
        ("width_bucket", 4, width_bucket, True), ("rand", 0, rand, False), ("rand", 1, rand, False),
        ("nvl", 2, nvl, True), ("ifnull", 2, nvl, True), ("isnull", 2, nvl, True), ("nvl2", 3, nvl2, True),
        ("casewhen", 3, casewhen, True), ("decode", -1, decode, True), ("greatest", -1, greatest, True),
        ("least", -1, least, True), ("uuid", 0, uuid_new, False), ("uuid", 1, uuid_convert, True),
        ("identity", 0, identity, False), ("user", 0, lambda: "", True),
        ("database", 0, lambda: database_name, True),
        ("curdate", 0, dates.curdate, False), ("today", 0, dates.curdate, False),
        ("curtime", 0, dates.curtime, False), ("now", 0, dates.now, False),
        ("year", 1, dates.year, True), ("month", 1, dates.month, True), ("day", 1, dates.day, True),
        ("dayofmonth", 1, dates.day, True), ("hour", 1, dates.hour, True), ("minute", 1, dates.minute, True),
        ("second", 1, dates.second, True), ("quarter", 1, dates.quarter, True),
        ("dayofweek", 1, dates.dayofweek, True), ("dayofyear", 1, dates.dayofyear, True),
        ("week", 1, dates.week, True), ("days", 1, dates.days, True),
        ("seconds_since_midnight", 1, dates.seconds_since_midnight, True),
        ("dayname", 1, dates.dayname, True), ("monthname", 1, dates.monthname, True),
        ("extract", 2, dates.extract, True), ("unix_timestamp", 0, dates.unix_timestamp, False),
        ("unix_timestamp", 1, dates.unix_timestamp, True), ("unix_millis", 0, dates.unix_millis, False),
        ("unix_millis", 1, dates.unix_millis, True), ("dateadd", 3, dates.dateadd, True),
        ("timestampadd", 3, dates.dateadd, True), ("datediff", 2, dates.datediff, True),
        ("datediff", 3, dates.datediff, True), ("timestampdiff", 3, dates.datediff, True),
        ("last_day", 1, dates.last_day, True), ("add_months", 2, dates.add_months, True),
        ("months_between", 2, dates.months_between, True), ("next_day", 2, dates.next_day, True),
        ("to_char", 2, dates.to_char, True), ("to_date", 2, dates.to_date, True),
        ("to_timestamp", 2, dates.to_timestamp, True),
    ]
    for name, count, function, deterministic in table:
        connection.create_function(name, count, function, deterministic)
    connection.create_collation("NOCASE", nocase_compare)
