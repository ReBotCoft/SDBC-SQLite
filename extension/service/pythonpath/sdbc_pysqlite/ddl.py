# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from sdbc_pysqlite import sqltext

AUTO_INCREMENT_MARKER = "AUTO_INCREMENT"
INTEGER_TYPES = ("LO_TINYINT", "LO_SMALLINT", "LO_INTEGER", "LO_BIGINT")

_CONSTRAINT_STARTS = ("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN")
_COLUMN_CONSTRAINT_WORDS = ("CONSTRAINT", "PRIMARY", "NOT", "NULL", "UNIQUE", "CHECK", "DEFAULT", "COLLATE",
                            "REFERENCES", "GENERATED", "AS", AUTO_INCREMENT_MARKER)


def _words(tokens):
    return [t for t in tokens if t.kind not in ("space", "comment")]


def _split(text):
    tokens = sqltext.tokens(text)
    sig = _words(tokens)
    words = [t.text.upper() if t.kind == "word" else None for t in sig]
    index = 0
    if words[:1] != ["CREATE"]:
        return None
    index = 1
    if index < len(words) and words[index] in ("TEMP", "TEMPORARY"):
        index += 1
    if words[index:index + 1] != ["TABLE"]:
        return None
    opener = next((t for t in tokens if t.kind == "punct" and t.text == "("), None)
    if opener is None:
        return None
    head = text[:opener.start + 1]
    items, current, depth = [], [], 0
    tail_start = None
    for token in tokens:
        if token.start <= opener.start:
            continue
        if token.kind == "punct" and token.text == "(":
            depth += 1
        elif token.kind == "punct" and token.text == ")":
            if depth == 0:
                items.append(current)
                tail_start = token.start
                break
            depth -= 1
        elif token.kind == "punct" and token.text == "," and depth == 0:
            items.append(current)
            current = []
            continue
        current.append(token)
    if tail_start is None:
        return None
    return head, items, text[tail_start:]


def _text(tokens):
    return "".join(t.text for t in tokens)


def _single_key(item):
    sig = _words(item)
    upper = [t.text.upper() for t in sig]
    start = 0
    if upper[:1] == ["CONSTRAINT"]:
        start = 2
    if upper[start:start + 2] != ["PRIMARY", "KEY"]:
        return None
    rest = sig[start + 2:]
    if len(rest) != 3 or rest[0].text != "(" or rest[2].text != ")":
        return None
    return sqltext.unquote(rest[1].text)


def _is_constraint(item):
    sig = _words(item)
    return bool(sig) and sig[0].kind == "word" and sig[0].text.upper() in _CONSTRAINT_STARTS


def _column_parts(item):
    lead = ""
    index = 0
    while index < len(item) and item[index].kind in ("space", "comment"):
        lead += item[index].text
        index += 1
    if index >= len(item):
        return None
    name = item[index]
    index += 1
    type_tokens, depth = [], 0
    while index < len(item):
        token = item[index]
        if token.kind == "punct" and token.text == "(":
            depth += 1
        elif token.kind == "punct" and token.text == ")":
            depth -= 1
        elif depth == 0 and token.kind == "word" and token.text.upper() in _COLUMN_CONSTRAINT_WORDS:
            break
        type_tokens.append(token)
        index += 1
    return lead, name, _words(type_tokens), item[index:]


def _has_primary_key(item):
    upper = [t.text.upper() for t in _words(item)][:4]
    return "PRIMARY" in upper and upper[upper.index("PRIMARY") + 1:upper.index("PRIMARY") + 2] == ["KEY"]


def _integer_column(items, name):
    for item in items:
        if _is_constraint(item):
            continue
        parts = _column_parts(item)
        if parts and sqltext.unquote(parts[1].text).lower() == name.lower():
            return bool(parts[2]) and parts[2][0].text.upper() in INTEGER_TYPES
    return False


def _without_marker(tokens):
    result = [t for t in tokens if not (t.kind == "word" and t.text.upper() == AUTO_INCREMENT_MARKER)]
    text = _text(result).strip()
    return (" " + text) if text else ""


def rewrite_create_table(text, reuse=False):
    parts = _split(text)
    if parts is None:
        return text
    head, items, tail = parts
    if "WITHOUT" in tail.upper():
        return text
    key_item = None
    key_name = None
    primaries = [item for item in items if _is_constraint(item) and _has_primary_key(item)]
    if len(primaries) == 1:
        name = _single_key(primaries[0])
        if name is not None and _integer_column(items, name):
            key_item, key_name = primaries[0], name
    out = []
    for item in items:
        if item is key_item:
            continue
        if _is_constraint(item):
            out.append(_text(item))
            continue
        parts_c = _column_parts(item)
        if parts_c is None:
            out.append(_text(item))
            continue
        lead, name, type_words, constraints = parts_c
        marker = any(t.kind == "word" and t.text.upper() == AUTO_INCREMENT_MARKER for t in constraints)
        is_key = (key_name is not None and sqltext.unquote(name.text).lower() == key_name.lower()
                  and type_words and type_words[0].text.upper() in INTEGER_TYPES)
        if is_key:
            extra = " AUTOINCREMENT" if marker and not reuse else ""
            out.append("%s%s INTEGER PRIMARY KEY%s%s" % (lead, name.text, extra, _without_marker(constraints)))
        elif marker:
            out.append(lead + name.text + " " + " ".join(t.text for t in type_words) + _without_marker(constraints))
        else:
            out.append(_text(item))
    return head + ",".join(out) + tail
