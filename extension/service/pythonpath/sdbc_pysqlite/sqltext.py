# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import re
from collections import namedtuple

from sdbc_pysqlite import sqlite

Token = namedtuple("Token", "kind text start")

_TOKEN = re.compile(
    r"""(?P<space>\s+)
      | (?P<comment>--[^\n]*|/\*.*?(?:\*/|\Z))
      | (?P<string>'(?:[^']|'')*'?)
      | (?P<quoted>"(?:[^"]|"")*"?|`(?:[^`]|``)*`?|\[[^\]]*\]?)
      | (?P<number>\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+)
      | (?P<word>[^\W\d][\w$]*)
      | (?P<punct>.)""", re.VERBOSE | re.DOTALL)


def tokens(text):
    result = []
    for match in _TOKEN.finditer(text):
        result.append(Token(match.lastgroup, match.group(), match.start()))
    return result


def significant(text):
    return [t for t in tokens(text) if t.kind not in ("space", "comment")]


def unquote(name):
    if len(name) >= 2:
        if name[0] == '"' and name[-1] == '"':
            return name[1:-1].replace('""', '"')
        if name[0] == "`" and name[-1] == "`":
            return name[1:-1].replace("``", "`")
        if name[0] == "[" and name[-1] == "]":
            return name[1:-1]
        if name[0] == "'" and name[-1] == "'":
            return name[1:-1].replace("''", "'")
    return name


def quote_name(name):
    return '"' + name.replace('"', '""') + '"'


def _has_content(text):
    return any(t.kind not in ("space", "comment") and t.text != ";" for t in tokens(text))


def split_statements(text):
    pieces = []
    start = 0
    index = text.find(";", start)
    while index != -1:
        candidate = text[start:index + 1]
        if sqlite.complete_statement(candidate):
            if _has_content(candidate):
                pieces.append(candidate.strip().rstrip(";").rstrip())
            start = index + 1
        index = text.find(";", index + 1)
    rest = text[start:]
    if _has_content(rest):
        pieces.append(rest.strip().rstrip(";").rstrip())
    return pieces


def first_words(text, count=2):
    words = []
    for token in tokens(text):
        if token.kind in ("space", "comment") or token.text == "(":
            continue
        if token.kind != "word":
            break
        words.append(token.text.upper())
        if len(words) == count:
            break
    return words


def insert_target(text):
    sig = significant(text)
    words = [t.text.upper() if t.kind == "word" else None for t in sig]
    if not words or words[0] not in ("INSERT", "REPLACE"):
        return None
    try:
        into = words.index("INTO")
    except ValueError:
        return None
    i = into + 1
    if i >= len(sig) or sig[i].kind not in ("word", "quoted", "string"):
        return None
    name = unquote(sig[i].text)
    if i + 2 < len(sig) and sig[i + 1].text == "." and sig[i + 2].kind in ("word", "quoted", "string"):
        name = unquote(sig[i + 2].text)
    return name


def parameter_map(sig):
    result = {}
    names = {}
    count = 0
    for i, token in enumerate(sig):
        if token.kind != "punct":
            continue
        nxt = sig[i + 1] if i + 1 < len(sig) else None
        if token.text == "?":
            if nxt is not None and nxt.kind == "number" and nxt.start == token.start + 1:
                continue
            result[i] = count
            count += 1
        elif token.text in (":", "@", "$") and nxt is not None and nxt.kind == "word" and nxt.start == token.start + 1:
            key = token.text + nxt.text
            if key not in names:
                names[key] = count
                count += 1
            result[i] = names[key]
    return result, count


def parameter_end(sig, i):
    return i if sig[i].text == "?" else i + 1


def count_parameters(text):
    count = 0
    for token in tokens(text):
        if token.kind == "punct" and token.text in ("?", ":", "@", "$"):
            count += 1
    return count


def is_wrappable_query(text):
    words = first_words(text, 1)
    return bool(words) and words[0] in ("SELECT", "WITH", "VALUES")


def strip_trailing(text):
    return text.rstrip().rstrip(";").rstrip()
