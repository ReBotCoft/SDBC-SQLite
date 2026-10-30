# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from sdbc_pysqlite import ddl
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import typesystem as ts

_CLAUSE_START = {"CONSTRAINT", "PRIMARY", "NOT", "NULL", "UNIQUE", "CHECK", "DEFAULT", "COLLATE",
                 "REFERENCES", "GENERATED", "AS", ddl.AUTO_INCREMENT_MARKER}

RULE_WORDS = {0: "CASCADE", 1: "RESTRICT", 2: "SET NULL", 3: "NO ACTION", 4: "SET DEFAULT"}


def _sig(tokens):
    return [t for t in tokens if t.kind not in ("space", "comment")]


def _join(tokens):
    return "".join(t.text for t in tokens).strip()


def _upper(token):
    return token.text.upper() if token.kind == "word" else None


class Clause:

    def __init__(self, kind, text):
        self.kind = kind
        self.text = text


def _clause_kind(tokens):
    words = [_upper(t) for t in _sig(tokens)]
    if words and words[0] == "CONSTRAINT":
        words = words[2:]
    first = words[0] if words else None
    if first == "NOT":
        return "NOTNULL"
    return {"NULL": "NULL", "DEFAULT": "DEFAULT", "PRIMARY": "PK", "UNIQUE": "UNIQUE", "CHECK": "CHECK",
            "COLLATE": "COLLATE", "REFERENCES": "REFERENCES"}.get(first, "OTHER")


def _split_clauses(tokens):
    groups, current, depth = [], [], 0
    for token in tokens:
        if token.kind == "punct" and token.text == "(":
            depth += 1
        elif token.kind == "punct" and token.text == ")":
            depth -= 1
        starts = (depth == 0 and token.kind == "word" and token.text.upper() in _CLAUSE_START)
        if starts:
            sig = _sig(current)
            first = _upper(sig[0]) if sig else None
            word = token.text.upper()
            if first == "NOT" and word == "NULL" and len(sig) == 1:
                starts = False
            elif first == "DEFAULT" and len(sig) == 1:
                starts = False
            elif first == "CONSTRAINT" and len(sig) <= 2:
                starts = False
            elif first == "GENERATED" and word == "AS":
                starts = False
        if starts and current and _sig(current):
            groups.append(current)
            current = []
        current.append(token)
    if _sig(current):
        groups.append(current)
    return [Clause(_clause_kind(g), _join(g)) for g in groups]


class Column:
    def __init__(self, lead, name, label, clauses, raw=None):
        self.lead = lead
        self.name = name
        self.label = label
        self.clauses = clauses
        self._raw = raw
        stripped = raw.rstrip() if raw is not None else ""
        self._trail = raw[len(stripped):] if raw is not None else ""
        self._snapshot = self._state()

    def _state(self):
        return (self.label, tuple((c.kind, c.text) for c in self.clauses))

    @property
    def plain_name(self):
        return sqltext.unquote(self.name)

    def has(self, kind):
        return any(c.kind == kind for c in self.clauses)

    def drop(self, *kinds):
        self.clauses = [c for c in self.clauses if c.kind not in kinds]

    def text(self):
        if self._raw is not None and self._state() == self._snapshot:
            return self._raw
        parts = [self.name]
        if self.label:
            parts.append(self.label)
        parts.extend(c.text for c in self.clauses)
        return self.lead + " ".join(parts) + self._trail


class Constraint:

    def __init__(self, lead, text):
        self.lead = lead
        self.raw = text
        words = [_upper(t) for t in _sig(sqltext.tokens(text))]
        if words[:1] == ["CONSTRAINT"]:
            words = words[2:]
        self.kind = {"PRIMARY": "PK", "UNIQUE": "UNIQUE", "CHECK": "CHECK", "FOREIGN": "FK"}.get(
            words[0] if words else None, "OTHER")

    def text(self):
        return self.lead + self.raw


def new_table(name):
    return TableDef("CREATE TABLE %s (" % sqltext.quote_name(name), [], "\n)", "\n  ")


def _item_lead(tokens):
    lead = ""
    for token in tokens:
        if token.kind in ("space", "comment"):
            lead += token.text
        else:
            break
    return lead


class TableDef:
    def __init__(self, head, items, tail, lead=" "):
        self.head = head
        self.items = items
        self.tail = tail
        self.lead = lead

    @property
    def columns(self):
        return [i for i in self.items if isinstance(i, Column)]

    @property
    def constraints(self):
        return [i for i in self.items if isinstance(i, Constraint)]

    def column(self, name):
        for column in self.columns:
            if column.plain_name.lower() == name.lower():
                return column
        return None

    @property
    def without_rowid(self):
        return "WITHOUT" in self.tail.upper()

    def render(self, name=None):
        head = self.head if name is None else "CREATE TABLE %s (" % sqltext.quote_name(name)
        return head + ",".join(i.text() for i in self.items) + self.tail

    def remove_unique(self, names):
        wanted = [n.lower() for n in names]
        for item in list(self.items):
            if isinstance(item, Constraint) and item.kind == "UNIQUE" \
                    and [n.lower() for n in _paren_names(item.raw)] == wanted:
                self.items.remove(item)
                return True
        if len(wanted) == 1:
            column = self.column(wanted[0])
            if column is not None and column.has("UNIQUE"):
                column.drop("UNIQUE")
                return True
        return False

    def unique_keys(self):
        result = []
        for item in self.items:
            if isinstance(item, Constraint) and item.kind == "UNIQUE":
                result.append(_paren_names(item.raw))
            elif isinstance(item, Column) and item.has("UNIQUE"):
                result.append([item.plain_name])
        return result

    def remove_unique_on(self, name):
        lowered = name.lower()
        self.items = [i for i in self.items
                      if not (isinstance(i, Constraint) and i.kind == "UNIQUE"
                              and lowered in [n.lower() for n in _paren_names(i.raw)])]

    def primary_key(self):
        for constraint in self.constraints:
            if constraint.kind == "PK":
                return _paren_names(constraint.raw)
        return [c.plain_name for c in self.columns if c.has("PK")]

    def set_primary_key(self, names, auto_increment_strict):
        for column in self.columns:
            column.drop("PK")
            column.clauses = [c for c in column.clauses if c.text.upper() != "AUTOINCREMENT"]
        self.items = [i for i in self.items if not (isinstance(i, Constraint) and i.kind == "PK")]
        if not names:
            return None
        if len(names) == 1 and not self.without_rowid:
            column = self.column(names[0])
            if column is not None and ts.classify(column.label).kind == ts.K_INT:
                column.label = "INTEGER"
                column.drop("NOTNULL", "NULL")
                column.clauses.insert(0, Clause("PK", "PRIMARY KEY" + (" AUTOINCREMENT" if auto_increment_strict else "")))
                return column.plain_name
        for name in names:
            column = self.column(name)
            if column is not None and not column.has("NOTNULL"):
                column.drop("NULL")
                column.clauses.append(Clause("NOTNULL", "NOT NULL"))
        self._insert_constraint("PRIMARY KEY (%s)" % ", ".join(sqltext.quote_name(n) for n in names))
        return None

    def _insert_constraint(self, text):
        self.items.append(Constraint(self.lead, text))

    def foreign_keys(self):
        result = []
        for item in self.items:
            if isinstance(item, Constraint) and item.kind == "FK":
                sig = _sig(sqltext.tokens(item.raw))
                words = [_upper(t) for t in sig]
                try:
                    start = words.index("FOREIGN")
                except ValueError:
                    continue
                sources = _names_after(sig, start + 2)
                try:
                    ref = words.index("REFERENCES")
                except ValueError:
                    continue
                result.append((item, sources, sqltext.unquote(sig[ref + 1].text)))
            elif isinstance(item, Column):
                for clause in item.clauses:
                    if clause.kind == "REFERENCES" or clause.text.upper().startswith("CONSTRAINT") and \
                            "REFERENCES" in clause.text.upper().split():
                        sig = _sig(sqltext.tokens(clause.text))
                        words = [_upper(t) for t in sig]
                        if "REFERENCES" not in words:
                            continue
                        ref = words.index("REFERENCES")
                        result.append((clause, [item.plain_name], sqltext.unquote(sig[ref + 1].text)))
        return result

    def remove_foreign_key(self, sources, target):
        wanted = [s.lower() for s in sources]
        for holder, found, found_target in self.foreign_keys():
            if [s.lower() for s in found] == wanted and found_target.lower() == target.lower():
                if isinstance(holder, Constraint):
                    self.items.remove(holder)
                else:
                    for column in self.columns:
                        if holder in column.clauses:
                            column.clauses.remove(holder)
                return True
        return False

    def add_foreign_key(self, sources, target, destinations, update_rule, delete_rule):
        text = "FOREIGN KEY (%s) REFERENCES %s (%s)" % (
            ", ".join(sqltext.quote_name(s) for s in sources), sqltext.quote_name(target),
            ", ".join(sqltext.quote_name(d) for d in destinations))
        if update_rule != 3:
            text += " ON UPDATE " + RULE_WORDS[update_rule]
        if delete_rule != 3:
            text += " ON DELETE " + RULE_WORDS[delete_rule]
        self._insert_constraint(text)

    def add_column(self, name, label, not_null, default_literal):
        clauses = []
        if not_null:
            clauses.append(Clause("NOTNULL", "NOT NULL"))
        if default_literal is not None:
            clauses.append(Clause("DEFAULT", "DEFAULT " + default_literal))
        column = Column(self.lead, sqltext.quote_name(name), label, clauses)
        position = len(self.items)
        for index, item in enumerate(self.items):
            if isinstance(item, Constraint):
                position = index
                break
        self.items.insert(position, column)
        return column

    def remove_column(self, name):
        column = self.column(name)
        if column is not None:
            self.items.remove(column)

    def uses_column(self, name):
        lowered = name.lower()
        for constraint in self.constraints:
            for token in _sig(sqltext.tokens(constraint.raw)):
                if token.kind in ("word", "quoted") and sqltext.unquote(token.text).lower() == lowered:
                    return True
        return False


def _paren_names(text):
    sig = _sig(sqltext.tokens(text))
    for index, token in enumerate(sig):
        if token.text == "(":
            return _names_after(sig, index)
    return []


def _names_after(sig, index):
    names = []
    if index >= len(sig) or sig[index].text != "(":
        return names
    depth = 0
    for token in sig[index:]:
        if token.text == "(":
            depth += 1
        elif token.text == ")":
            depth -= 1
            if depth == 0:
                break
        elif depth == 1 and token.kind in ("word", "quoted", "string"):
            if token.kind == "word" and token.text.upper() in ("ASC", "DESC", "COLLATE"):
                continue
            names.append(sqltext.unquote(token.text))
    return names


def parse(sql):
    parts = ddl._split(sql)
    if parts is None:
        return None
    head, raw_items, tail = parts
    items = []
    for tokens in raw_items:
        if not _sig(tokens):
            return None
        if ddl._is_constraint(tokens):
            items.append(Constraint("", _text_of(tokens)))
            continue
        parts_c = ddl._column_parts(tokens)
        if parts_c is None:
            return None
        lead, name, type_tokens, constraints = parts_c
        items.append(Column(lead, name.text, _type_join(type_tokens), _split_clauses(constraints),
                            raw=_text_of(tokens)))
    if not items:
        return None
    return TableDef(head, items, tail)


def _text_of(tokens):
    return "".join(t.text for t in tokens)


def _type_join(tokens):
    result = ""
    previous = None
    for token in tokens:
        text = token.text
        if previous is not None and text not in ("(", ")", ",") and previous not in ("(", ","):
            result += " "
        result += text
        previous = text
    return result


def default_literal(text, column_type):
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
    if text is None or str(text).strip() == "":
        return None
    value = str(text).strip()
    kind = column_type.kind
    if kind == ts.K_DECIMAL:
        try:
            number = Decimal(value)
        except InvalidOperation:
            return None
        scaled = number.scaleb(column_type.scale).to_integral_value(rounding=ROUND_HALF_UP)
        return str(int(scaled))
    if kind in (ts.K_INT, ts.K_REAL, ts.K_NUMERIC):
        try:
            number = Decimal(value)
        except InvalidOperation:
            return quote_text(value)
        if kind == ts.K_INT and number != number.to_integral_value():
            return str(int(number))
        return value
    if kind == ts.K_BOOL:
        lowered = value.lower()
        if lowered in ("true", "1"):
            return "1"
        if lowered in ("false", "0"):
            return "0"
    return quote_text(value)


def quote_text(value):
    return "'" + value.replace("'", "''") + "'"
