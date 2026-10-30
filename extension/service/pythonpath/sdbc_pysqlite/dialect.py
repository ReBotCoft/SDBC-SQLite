# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import re

from sdbc_pysqlite import sqltext

_MAYBE = re.compile(r"\{|\b(?:trim|substring|position|overlay|extract|convert|insert|timestampadd|"
                    r"timestampdiff|dateadd|datediff|current_date|current_time|current_timestamp)\s*\(",
                    re.IGNORECASE)

_BLANK = ("space", "comment")

_TYPES = {}
for _names, _target in (
        (("INTEGER", "INT", "BIGINT", "SMALLINT", "TINYINT", "BOOLEAN", "BIT"), "INTEGER"),
        (("VARCHAR", "CHAR", "CHARACTER", "LONGVARCHAR", "VARCHAR_IGNORECASE", "CLOB", "DATE", "TIME",
          "TIMESTAMP"), "TEXT"),
        (("DOUBLE", "FLOAT", "REAL"), "REAL"),
        (("DECIMAL", "NUMERIC"), "NUMERIC"),
        (("BINARY", "VARBINARY", "LONGVARBINARY", "BLOB"), "BLOB")):
    for _name in _names:
        _TYPES[_name] = _target
        _TYPES["SQL_" + _name] = _target

_DATE_FIELDS = {"YY", "YYYY", "YEAR", "QQ", "QUARTER", "MM", "MONTH", "DD", "DAY", "HH", "HOUR", "MI", "MINUTE",
                "SS", "SECOND", "MS", "MILLISECOND", "MCS", "MICROSECOND", "NS", "NANOSECOND", "WEEK", "WK"}


def _significant(tokens):
    return [t for t in tokens if t.kind not in _BLANK]


def _match(tokens, start, opener, closer):
    depth = 0
    for index in range(start, len(tokens)):
        token = tokens[index]
        if token.kind == "punct":
            if token.text == opener:
                depth += 1
            elif token.text == closer:
                depth -= 1
                if depth == 0:
                    return index
    return -1


def _split_top(tokens, separator):
    parts = [[]]
    depth = 0
    for token in tokens:
        if token.kind == "punct" and token.text in "({":
            depth += 1
        elif token.kind == "punct" and token.text in ")}":
            depth -= 1
        if depth == 0 and token.kind == "punct" and token.text == separator:
            parts.append([])
        else:
            parts[-1].append(token)
    return parts


def _find_top_word(tokens, word):
    depth = 0
    for index, token in enumerate(tokens):
        if token.kind == "punct" and token.text in "({":
            depth += 1
        elif token.kind == "punct" and token.text in ")}":
            depth -= 1
        elif depth == 0 and token.kind == "word" and token.text.upper() == word:
            return index
    return None


def _text(tokens):
    return "".join(_rewrite(tokens)).strip()


def _trim(args):
    at = _find_top_word(args, "FROM")
    if at is None:
        return None
    head, tail = args[:at], args[at + 1:]
    sig = _significant(head)
    mode = 3
    if sig and sig[0].kind == "word" and sig[0].text.upper() in ("LEADING", "TRAILING", "BOTH"):
        mode = {"LEADING": 1, "TRAILING": 2, "BOTH": 3}[sig[0].text.upper()]
        head = head[head.index(sig[0]) + 1:]
    chars = _text(head)
    target = _text(tail)
    if not chars:
        return {1: "LTRIM(%s)", 2: "RTRIM(%s)", 3: "TRIM(%s)"}[mode] % target
    return "sdbc_trim(%s, %s, %d)" % (chars, target, mode)


def _substring(args):
    at = _find_top_word(args, "FROM")
    if at is None:
        return None
    head, tail = args[:at], args[at + 1:]
    stop = _find_top_word(tail, "FOR")
    if stop is None:
        return "SUBSTR(%s, %s)" % (_text(head), _text(tail))
    return "SUBSTR(%s, %s, %s)" % (_text(head), _text(tail[:stop]), _text(tail[stop + 1:]))


def _position(args):
    at = _find_top_word(args, "IN")
    if at is None:
        return None
    return "LOCATE(%s, %s)" % (_text(args[:at]), _text(args[at + 1:]))


def _overlay(args):
    placing = _find_top_word(args, "PLACING")
    if placing is None:
        return None
    rest = args[placing + 1:]
    start = _find_top_word(rest, "FROM")
    if start is None:
        return None
    after = rest[start + 1:]
    stop = _find_top_word(after, "FOR")
    parts = [_text(args[:placing]), _text(rest[:start])]
    if stop is None:
        parts.append(_text(after))
    else:
        parts += [_text(after[:stop]), _text(after[stop + 1:])]
    return "OVERLAY(%s)" % ", ".join(parts)


def _extract(args):
    at = _find_top_word(args, "FROM")
    if at is None:
        return None
    field = _significant(args[:at])
    if len(field) != 1 or field[0].kind != "word":
        return None
    return "EXTRACT('%s', %s)" % (field[0].text.upper(), _text(args[at + 1:]))


def _convert(args):
    parts = _split_top(args, ",")
    if len(parts) != 2:
        return None
    sig = _significant(parts[1])
    if not sig or sig[0].kind != "word" or sig[0].text.upper() not in _TYPES:
        return None
    return "CAST(%s AS %s)" % (_text(parts[0]), _TYPES[sig[0].text.upper()])


def _date_function(name):
    def handler(args):
        parts = _split_top(args, ",")
        sig = _significant(parts[0])
        if len(parts) < 2 or len(sig) != 1 or sig[0].kind != "word":
            return None
        word = sig[0].text.upper()
        if word not in _DATE_FIELDS and not word.startswith("SQL_TSI_"):
            return None
        return "%s('%s', %s)" % (name, sig[0].text, ", ".join(_text(p) for p in parts[1:]))
    return handler


def _insert(args):
    return '"INSERT"(%s)' % "".join(_rewrite(args))


def _bare_keyword(name):
    def handler(args):
        return name if not _significant(args) else None
    return handler


_HANDLERS = {
    "TRIM": _trim, "SUBSTRING": _substring, "POSITION": _position, "OVERLAY": _overlay,
    "EXTRACT": _extract, "CONVERT": _convert, "INSERT": _insert,
    "DATEADD": _date_function("DATEADD"), "DATEDIFF": _date_function("DATEDIFF"),
    "TIMESTAMPADD": _date_function("TIMESTAMPADD"), "TIMESTAMPDIFF": _date_function("TIMESTAMPDIFF"),
    "CURRENT_DATE": _bare_keyword("CURRENT_DATE"), "CURRENT_TIME": _bare_keyword("CURRENT_TIME"),
    "CURRENT_TIMESTAMP": _bare_keyword("CURRENT_TIMESTAMP"),
}


def _escape(inner):
    sig = _significant(inner)
    if not sig or sig[0].kind != "word":
        return None
    key = sig[0].text.upper()
    rest = inner[inner.index(sig[0]) + 1:]
    if key in ("D", "T", "TS", "FN", "OJ"):
        return _text(rest)
    if key == "ESCAPE":
        return "ESCAPE " + _text(rest)
    return None


def _rewrite(tokens):
    out = []
    i = 0
    size = len(tokens)
    while i < size:
        token = tokens[i]
        if token.kind == "punct" and token.text == "{":
            end = _match(tokens, i, "{", "}")
            if end > 0:
                replaced = _escape(tokens[i + 1:end])
                if replaced is not None:
                    out.append(replaced)
                    i = end + 1
                    continue
        elif token.kind == "word" and token.text.upper() in _HANDLERS:
            k = i + 1
            while k < size and tokens[k].kind in _BLANK:
                k += 1
            if k < size and tokens[k].kind == "punct" and tokens[k].text == "(":
                end = _match(tokens, k, "(", ")")
                if end > 0:
                    replaced = _HANDLERS[token.text.upper()](tokens[k + 1:end])
                    if replaced is not None:
                        out.append(replaced)
                        i = end + 1
                        continue
        out.append(token.text)
        i += 1
    return out


def translate(sql):
    if not _MAYBE.search(sql):
        return sql
    return "".join(_rewrite(sqltext.tokens(sql)))
