# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from collections import namedtuple
from decimal import Decimal
from decimal import InvalidOperation

from sdbc_pysqlite import errors
from sdbc_pysqlite import schema as schema_module
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite import values
from sdbc_pysqlite.errors import DriverError

Translation = namedtuple("Translation", "text slots warnings decimal")

Compare = namedtuple("Compare", "scale")

Col = namedtuple("Col", "name label scale")
Table = namedtuple("Table", "name columns")
Schema = namedtuple("Schema", "tables names touch")
Source = namedtuple("Source", "alias display table")
Operand = namedtuple("Operand", "kind first last value")

_COMPARE = {"=", "==", "<", ">", "<=", ">=", "<>", "!="}
_BEFORE = {"WHERE", "AND", "OR", "ON", "WHEN", "HAVING", "THEN", "ELSE", "NOT", "SELECT", "DISTINCT", "ALL",
           "RETURNING"}
_AFTER = {"AND", "OR", "THEN", "ELSE", "END", "WHEN", "ORDER", "GROUP", "LIMIT", "UNION", "INTERSECT",
          "EXCEPT", "WINDOW", "HAVING", "RETURNING", "FROM", "AS", "ESCAPE", "ON", "JOIN", "WHERE", "LEFT",
          "RIGHT", "FULL", "INNER", "CROSS", "NATURAL"}
_CLAUSES = {"WHERE", "GROUP", "HAVING", "WINDOW", "ORDER", "LIMIT", "RETURNING"}
_COMPOUND = {"UNION", "INTERSECT", "EXCEPT"}
_AGGREGATES = {"SUM", "AVG", "MAX", "MIN"}
_NOT_ALIAS = {"ON", "USING", "JOIN", "LEFT", "RIGHT", "FULL", "INNER", "CROSS", "NATURAL", "OUTER", "WHERE",
              "GROUP", "ORDER", "LIMIT", "HAVING", "WINDOW", "UNION", "INTERSECT", "EXCEPT", "INDEXED", "NOT",
              "SET", "RETURNING", "FROM"}
_JOINERS = {"NATURAL", "LEFT", "RIGHT", "FULL", "INNER", "CROSS", "JOIN", "OUTER"}


class _Unclear(Exception):
    pass


def load_schema(db):
    version = db.execute("PRAGMA main.schema_version").fetchone()[0]
    cached = getattr(db, "_decimal_schema", None)
    if cached is not None and cached[0] == version:
        return cached[1]
    tables = {}
    names = set()
    touch = set()
    for name, kind in schema_module.list_objects(db):
        if kind != "TABLE":
            continue
        columns = {}
        for column in schema_module.table_columns(db, name):
            ctype = ts.classify(column.label)
            scale = ctype.scale if ctype.kind == ts.K_DECIMAL and ctype.scale > 0 else None
            if scale:
                names.add(column.name.lower())
                touch.add(name.lower())
            columns[column.name.lower()] = Col(column.name, column.label, scale)
        tables[name.lower()] = Table(name, columns)
    result = Schema(tables, names, names | touch)
    try:
        db._decimal_schema = (version, result)
    except Exception:
        pass
    return result


def shift(number, scale):
    sign, digits, exponent = number.as_tuple()
    return Decimal((sign, digits, exponent + scale))


def plain(number):
    if number == number.to_integral_value():
        return str(int(number))
    return format(number.normalize(), "f")


def _to_decimal(text):
    try:
        number = Decimal(text.strip())
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


class _Scope:
    def __init__(self, parent=None):
        self.parent = parent
        self.sources = []
        self.hidden = []
        self.restricted = False

    def add(self, alias, display, table, hidden=False):
        (self.hidden if hidden else self.sources).append(Source(alias.lower() if alias else None, display, table))


class _Run:
    def __init__(self, text, sig, schema):
        self.text = text
        self.sig = sig
        self.schema = schema
        self.edits = []
        self.slots = {}
        self.warnings = []
        self.ctes = set()
        self.ordinal = sqltext.parameter_map(sig)[0]
        self.match = {}
        stack = []
        for i, token in enumerate(sig):
            if token.kind == "punct" and token.text == "(":
                stack.append(i)
            elif token.kind == "punct" and token.text == ")":
                if not stack:
                    raise _Unclear("parentesi non bilanciate")
                self.match[stack.pop()] = i
        if stack:
            raise _Unclear("parentesi non bilanciate")

    def replace(self, first, last, new):
        self.edits.append((self.sig[first].start, self.end(last), new, 1, 1))

    def insert(self, pos, new, group, order):
        self.edits.append((pos, pos, new, group, order))

    def end(self, i):
        return self.sig[i].start + len(self.sig[i].text)

    def result(self):
        out = []
        cursor = 0
        for start, stop, new, _group, _order in sorted(self.edits, key=lambda e: (e[0], e[3], e[4])):
            if start < cursor:
                raise _Unclear("modifiche sovrapposte")
            out.append(self.text[cursor:start])
            out.append(new)
            cursor = max(cursor, stop)
        out.append(self.text[cursor:])
        return "".join(out)

    def kw(self, i):
        if 0 <= i < len(self.sig) and self.sig[i].kind == "word":
            return self.sig[i].text.upper()
        return None

    def punct(self, i, text):
        return 0 <= i < len(self.sig) and self.sig[i].kind == "punct" and self.sig[i].text == text

    def depth0(self, a, b):
        i = a
        while i < b:
            yield i
            i = self.match[i] + 1 if self.punct(i, "(") else i + 1

    def find(self, a, b, words):
        for i in self.depth0(a, b):
            word = self.kw(i)
            if word in words:
                if word == "FROM" and self.kw(i - 1) == "DISTINCT":
                    continue
                return i
        return None

    def split(self, a, b):
        items = []
        start = a
        for i in self.depth0(a, b):
            if self.punct(i, ","):
                items.append((start, i))
                start = i + 1
        if start < b or items:
            items.append((start, b))
        return items

    def op_at(self, i):
        if i >= len(self.sig) or self.sig[i].kind != "punct" or self.sig[i].text not in "=<>!":
            return None, 0
        one = self.sig[i].text
        if i + 1 < len(self.sig) and self.sig[i + 1].kind == "punct" and \
                self.sig[i + 1].start == self.sig[i].start + 1 and one + self.sig[i + 1].text in _COMPARE:
            return one + self.sig[i + 1].text, 2
        return (one, 1) if one in _COMPARE else (None, 0)

    def operand(self, i, b):
        first = i
        sign = 1
        if i < b and self.sig[i].kind == "punct" and self.sig[i].text in "+-":
            sign = -1 if self.sig[i].text == "-" else 1
            i += 1
        if i >= b:
            return None
        token = self.sig[i]
        if token.kind == "number":
            number = _to_decimal(token.text)
            nxt = self.sig[i + 1] if i + 1 < len(self.sig) else None
            if number is None or (nxt is not None and nxt.kind == "word" and nxt.start == self.end(i)):
                return None
            return Operand("num", first, i, number * sign)
        if token.kind == "string" and first == i:
            number = _to_decimal(sqltext.unquote(token.text))
            return Operand("str", first, i, number) if number is not None else None
        if first == i and i in self.ordinal:
            return Operand("ph", first, sqltext.parameter_end(self.sig, i), self.ordinal[i])
        return None

    def operand_back(self, j, a):
        token = self.sig[j]
        if token.kind == "word" and j - 1 >= a and (j - 1) in self.ordinal and self.sig[j - 1].text != "?":
            op = self.operand(j - 1, j + 1)
            return op if op is not None and op.last == j else None
        if token.kind in ("number", "string") or j in self.ordinal:
            first = j
            if token.kind == "number" and j - 1 >= a and self.sig[j - 1].kind == "punct" \
                    and self.sig[j - 1].text in "+-":
                first = j - 1
            op = self.operand(first, j + 1)
            return op if op is not None and op.last == j else None
        return None

    def boundary_before(self, j, a):
        if j < a:
            return True
        token = self.sig[j]
        if token.kind == "punct":
            return token.text in ("(", ",")
        return self.kw(j) in _BEFORE

    def boundary_after(self, j, b):
        if j >= b:
            return True
        token = self.sig[j]
        if token.kind == "punct":
            return token.text in (")", ",", ";")
        return self.kw(j) in _AFTER

    def apply_operand(self, operand, scale, compare):
        if operand.kind == "ph":
            self.slots[operand.value] = Compare(scale)
        else:
            self.replace(operand.first, operand.last, plain(shift(operand.value, scale)))

    def resolve(self, scope, qualifier, name):
        qualifier = qualifier.lower() if qualifier else None
        name = name.lower()
        current = scope
        while current is not None:
            if qualifier:
                for source in current.sources + current.hidden:
                    if source.alias == qualifier or (source.table is not None and
                                                     source.table.name.lower() == qualifier):
                        return source.table.columns.get(name) if source.table is not None else None
            else:
                found = [(s, s.table.columns[name]) for s in current.sources
                         if s.table is not None and name in s.table.columns]
                if found:
                    if len(found) > 1 and any(c.scale for _s, c in found):
                        tables = ", ".join(sorted({s.table.name for s, _c in found}))
                        raise DriverError(errors.DECIMAL_AMBIGUOUS, colonna=found[0][1].name, tabelle=tables)
                    return found[0][1]
            current = current.parent
        return None

    def parse_ref(self, a, b):
        parts = []
        i = a
        while i < b:
            if self.sig[i].kind not in ("word", "quoted"):
                return None
            parts.append(sqltext.unquote(self.sig[i].text))
            if i + 1 < b:
                if not self.punct(i + 1, "."):
                    return None
                i += 2
                if i >= b:
                    return None
            else:
                i += 1
        if not 1 <= len(parts) <= 3:
            return None
        return (parts[-2] if len(parts) > 1 else None), parts[-1]

    def decimal_col(self, scope, a, b):
        ref = self.parse_ref(a, b)
        if ref is None:
            return None
        col = self.resolve(scope, ref[0], ref[1])
        return col if col is not None and col.scale else None

    def expr(self, a, b, scope, skip=frozenset()):
        sig = self.sig
        i = a
        while i < b:
            token = sig[i]
            if token.kind == "punct" and token.text == "(":
                close = self.match[i]
                if i + 1 < close and self.kw(i + 1) in ("SELECT", "WITH", "VALUES"):
                    self.query(i + 1, close, scope, False)
                else:
                    self.expr(i + 1, close, scope, skip)
                i = close + 1
                continue
            if token.kind == "word" and token.text.upper() == "AS":
                i += 2
                continue
            if i in self.ordinal and token.text != "?":
                i += 2
                continue
            if token.kind in ("word", "quoted"):
                if token.kind == "word" and self.punct(i + 1, "("):
                    nxt = self.aggregate(i, b, scope)
                    i = nxt if nxt is not None else i + 1
                    continue
                last = i
                while last + 2 < b and self.punct(last + 1, ".") and sig[last + 2].kind in ("word", "quoted"):
                    last += 2
                if self.punct(last + 1, ".") and self.punct(last + 2, "*"):
                    i = last + 3
                    continue
                name = sqltext.unquote(sig[last].text)
                qualifier = sqltext.unquote(sig[last - 2].text) if last - 2 >= i else None
                if qualifier is None and name.lower() in skip:
                    i = last + 1
                    continue
                col = self.resolve(scope, qualifier, name)
                if col is not None and col.scale:
                    i = self.decimal_ref(i, last, col.scale, a, b)
                else:
                    i = last + 1
                continue
            i += 1

    def round_model(self, i, scope):
        close = self.match[i + 1]
        parts = self.split(i + 2, close)
        if not 1 <= len(parts) <= 2:
            return None
        x, y = parts[0]
        col = self.decimal_col(scope, x, y)
        if col is None:
            return None
        digits = 0
        if len(parts) == 2:
            x2, y2 = parts[1]
            if y2 != x2 + 1 or self.sig[x2].kind != "number" or not self.sig[x2].text.isdigit():
                return None
            digits = int(self.sig[x2].text)
            if digits >= col.scale:
                return None
        ref = self.text[self.sig[x].start:self.end(y - 1)]
        rounded = "ROUND(%s / %d.0)" % (ref, 10 ** (col.scale - digits))
        self.replace(i, close, rounded if digits == 0 else "(%s / %d.0)" % (rounded, 10 ** digits))
        return close + 1

    def aggregate(self, i, b, scope):
        if self.kw(i) == "ROUND":
            return self.round_model(i, scope)
        if self.kw(i) not in _AGGREGATES:
            return None
        close = self.match[i + 1]
        inner = i + 2
        if self.kw(inner) == "DISTINCT":
            inner += 1
        col = self.decimal_col(scope, inner, close)
        if col is None or self.kw(close + 1) in ("OVER", "FILTER"):
            return None
        self.insert(self.sig[i].start, "(", 1, 1)
        self.insert(self.end(close), " / %d.0)" % 10 ** col.scale, 0, 0)
        return close + 1

    def decimal_ref(self, r0, r1, scale, a, b):
        sig = self.sig
        nxt = r1 + 1
        start_ok = r0 == a or self.boundary_before(r0 - 1, a)
        if start_ok and nxt < b:
            word = self.kw(nxt)
            if word == "IS" or word in ("ISNULL", "NOTNULL") or (word == "NOT" and self.kw(nxt + 1) == "NULL"):
                return r1 + 1
            op, count = self.op_at(nxt)
            if op is not None:
                operand = self.operand(nxt + count, b)
                if operand is not None and self.boundary_after(operand.last + 1, b):
                    self.apply_operand(operand, scale, True)
                    return operand.last + 1
            else:
                k = nxt + 1 if word == "BETWEEN" else (nxt + 2 if word == "NOT" and self.kw(nxt + 1) == "BETWEEN" else None)
                if k is not None:
                    first = self.operand(k, b)
                    if first is not None and self.kw(first.last + 1) == "AND":
                        second = self.operand(first.last + 2, b)
                        if second is not None and self.boundary_after(second.last + 1, b):
                            self.apply_operand(first, scale, True)
                            self.apply_operand(second, scale, True)
                            return second.last + 1
                k = nxt + 1 if word == "IN" else (nxt + 2 if word == "NOT" and self.kw(nxt + 1) == "IN" else None)
                if k is not None and self.punct(k, "(") and self.match[k] < b:
                    close = self.match[k]
                    items = [self.operand(x, y) for x, y in self.split(k + 1, close)]
                    if items and all(o is not None for o in items) and \
                            all(o.last + 1 == y for o, (_x, y) in zip(items, self.split(k + 1, close))) and \
                            self.boundary_after(close + 1, b):
                        for operand in items:
                            self.apply_operand(operand, scale, True)
                        return close + 1
        if self.boundary_after(r1 + 1, b):
            for count in (2, 1):
                opi = r0 - count
                if opi - 1 < a:
                    continue
                op, size = self.op_at(opi)
                if op is None or size != count:
                    continue
                operand = self.operand_back(opi - 1, a)
                if operand is not None and (operand.first == a or self.boundary_before(operand.first - 1, a)):
                    self.apply_operand(operand, scale, True)
                    return r1 + 1
        self.replace(r0, r1, "(%s / %d.0)" % (self.text[sig[r0].start:self.end(r1)], 10 ** scale))
        return r1 + 1

    def by_list(self, a, b, scope, aliases):
        for x, y in self.split(a, b):
            end = y
            while end > x and self.kw(end - 1) in ("ASC", "DESC", "FIRST", "LAST", "NULLS"):
                end -= 1
            if end - x == 1 and sqltext.unquote(self.sig[x].text).lower() in aliases:
                continue
            if self.decimal_col(scope, x, end) is not None:
                continue
            self.expr(x, y, scope, frozenset(aliases))

    def tail(self, a, b, scope, aliases=frozenset()):
        starts = []
        for i in self.depth0(a, b):
            word = self.kw(i)
            if word in _CLAUSES:
                starts.append(i)
        for n, i in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else b
            word = self.kw(i)
            if word in ("WHERE", "HAVING"):
                self.expr(i + 1, end, scope, frozenset(aliases) if word == "HAVING" else frozenset())
            elif word in ("GROUP", "ORDER"):
                self.by_list(i + 2 if self.kw(i + 1) == "BY" else i + 1, end, scope, aliases)
            elif word == "WINDOW":
                self.expr(i + 1, end, scope)
            elif word == "RETURNING":
                self.select_items(i + 1, end, scope, False, None)

    def select_items(self, a, b, scope, bare_ok, targets):
        sig = self.sig
        aliases = set()
        for index, (x, y) in enumerate(self.split(a, b)):
            if x >= y:
                continue
            y2 = y
            alias = None
            if y - x >= 2 and self.kw(y - 2) == "AS":
                alias = sqltext.unquote(sig[y - 1].text)
                y2 = y - 2
            elif y - x >= 2 and sig[y - 1].kind in ("word", "quoted") and \
                    self.kw(y - 1) not in _NOT_ALIAS | {"END", "NULL", "ASC", "DESC"} and \
                    self.parse_ref(x, y - 1) is not None:
                alias = sqltext.unquote(sig[y - 1].text)
                y2 = y - 1
            if alias:
                aliases.add(alias.lower())
            target = targets[index] if targets is not None and index < len(targets) else None
            star = self.punct(x, "*") and y2 == x + 1
            qstar = y2 == x + 3 and self.punct(x + 1, ".") and self.punct(x + 2, "*")
            if star or qstar:
                self.star(x, y2, scope, qstar, bare_ok, targets is not None)
                continue
            if target is not None and target.scale:
                self.assign(x, y2, target, scope)
                continue
            col = self.decimal_col(scope, x, y2)
            if col is not None:
                if bare_ok:
                    continue
                self.replace(x, y2 - 1, "(%s / %d.0)" % (self.text[sig[x].start:self.end(y2 - 1)], 10 ** col.scale))
                if alias is None:
                    self.insert(self.end(y2 - 1), " AS %s" % sqltext.quote_name(col.name), 0, 2)
                continue
            before = len(self.edits)
            self.expr(x, y2, scope)
            if len(self.edits) > before and alias is None:
                self.insert(self.end(y2 - 1), " AS %s" % sqltext.quote_name(self.text[sig[x].start:self.end(y2 - 1)]),
                            0, 2)
        return aliases

    def star(self, x, y, scope, qualified, bare_ok, insert_select):
        if qualified:
            qualifier = sqltext.unquote(self.sig[x].text).lower()
            sources = [s for s in scope.sources if s.alias == qualifier or
                       (s.table is not None and s.table.name.lower() == qualifier)]
        else:
            sources = list(scope.sources)
        if not any(s.table is not None and any(c.scale for c in s.table.columns.values()) for s in sources):
            return
        if bare_ok and not insert_select:
            return
        if insert_select:
            raise _Unclear("INSERT ... SELECT * con colonne decimali")
        if any(s.table is None for s in sources) or scope.restricted:
            raise _Unclear("asterisco con sottointerrogazioni o USING/NATURAL")
        parts = []
        for source in sources:
            prefix = source.display
            for column in source.table.columns.values():
                ref = "%s.%s" % (prefix, sqltext.quote_name(column.name))
                if column.scale:
                    parts.append("(%s / %d.0) AS %s" % (ref, 10 ** column.scale, sqltext.quote_name(column.name)))
                else:
                    parts.append(ref)
        self.replace(x, y - 1, ", ".join(parts))

    def assign(self, x, y, col, scope):
        sig = self.sig
        if y - x == 1 and self.kw(x) == "NULL":
            return
        operand = self.operand(x, y)
        if operand is not None and operand.last + 1 == y:
            if operand.kind == "ph":
                self.slots[operand.value] = ts.classify(col.label)
            else:
                origin = "%s" % col.name
                self.replace(operand.first, operand.last, str(values.encode_decimal(operand.value, col.scale, origin)))
            return
        source = self.decimal_col(scope, x, y)
        if source is not None and source.scale == col.scale:
            return
        self.expr(x, y, scope)
        self.insert(sig[x].start, "CAST(ROUND(%d * (" % 10 ** col.scale, 1, 0)
        self.insert(self.end(y - 1), ")) AS INTEGER)", 0, 1)

    def assignments(self, a, b, scope, target):
        for x, y in self.split(a, b):
            if x >= y:
                continue
            if self.punct(x, "("):
                close = self.match[x]
                for name_x, name_y in self.split(x + 1, close):
                    col = target.columns.get(sqltext.unquote(self.sig[name_x].text).lower()) if target else None
                    if col is not None and col.scale:
                        raise _Unclear("assegnazione a un elenco di colonne con una colonna decimale")
                self.expr(close + 1, y, scope)
                continue
            i = x
            if y - x >= 3 and self.punct(x + 1, ".") and self.sig[x + 2].kind in ("word", "quoted"):
                i = x + 2
            name = sqltext.unquote(self.sig[i].text).lower()
            if not self.punct(i + 1, "="):
                self.expr(x, y, scope)
                continue
            col = target.columns.get(name) if target is not None else None
            if col is not None and col.scale:
                self.assign(i + 2, y, col, scope)
            else:
                self.expr(i + 2, y, scope)

    def table_name(self, i):
        sig = self.sig
        if sig[i].kind not in ("word", "quoted", "string"):
            raise _Unclear("nome di tabella atteso")
        name = sqltext.unquote(sig[i].text)
        display = sig[i].text
        if self.punct(i + 1, ".") and i + 2 < len(sig):
            name = sqltext.unquote(sig[i + 2].text)
            display = sig[i].text + "." + sig[i + 2].text
            i += 2
        i += 1
        alias = None
        if self.kw(i) == "AS" and i + 1 < len(sig):
            alias = sqltext.unquote(sig[i + 1].text)
            display = sig[i + 1].text
            i += 2
        elif i < len(sig) and sig[i].kind in ("word", "quoted") and \
                (sig[i].kind == "quoted" or self.kw(i) not in _NOT_ALIAS | {"DO", "VALUES", "SELECT", "DEFAULT", "WITH"}):
            alias = sqltext.unquote(sig[i].text)
            display = sig[i].text
            i += 1
        table = None if name.lower() in self.ctes else self.schema.tables.get(name.lower())
        return table, name, alias, display, i

    def from_clause(self, a, b, scope, outer):
        sig = self.sig
        ons = []
        usings = []
        natural = False
        i = a
        while i < b:
            word = self.kw(i)
            if word == "ON":
                end = i + 1
                while end < b:
                    if self.punct(end, "("):
                        end = self.match[end] + 1
                        continue
                    if self.punct(end, ",") or self.kw(end) in _JOINERS:
                        break
                    end += 1
                ons.append((i + 1, end))
                i = end
                continue
            if word == "USING":
                close = self.match[i + 1]
                usings.extend(sqltext.unquote(sig[k].text).lower() for k in range(i + 2, close)
                              if sig[k].kind in ("word", "quoted"))
                scope.restricted = True
                i = close + 1
                continue
            if word == "NATURAL":
                natural = True
                scope.restricted = True
                i += 1
                continue
            if self.punct(i, ",") or word in _JOINERS:
                i += 1
                continue
            if self.punct(i, "("):
                close = self.match[i]
                if i + 1 < close and self.kw(i + 1) in ("SELECT", "WITH", "VALUES"):
                    self.query(i + 1, close, outer, False)
                    j = close + 1
                    alias = None
                    display = None
                    if self.kw(j) == "AS":
                        j += 1
                    if j < b and sig[j].kind in ("word", "quoted") and self.kw(j) not in _NOT_ALIAS:
                        alias = sqltext.unquote(sig[j].text)
                        display = sig[j].text
                        j += 1
                    scope.add(alias, display, None)
                    i = j
                else:
                    sub = self.from_clause(i + 1, close, scope, outer)
                    ons.extend(sub)
                    i = close + 1
                continue
            if sig[i].kind in ("word", "quoted", "string"):
                table, name, alias, display, j = self.table_name(i)
                if self.punct(j, "("):
                    j = self.match[j] + 1
                    scope.add(alias or name, display, None)
                else:
                    scope.add(alias or name, display, table)
                while self.kw(j) in ("INDEXED", "NOT"):
                    j += 3 if self.kw(j) == "INDEXED" else 2
                i = j
                continue
            i += 1
        self._check_joins(scope, usings, natural)
        return ons

    def _check_joins(self, scope, usings, natural):
        tables = [s.table for s in scope.sources if s.table is not None]
        for name in usings:
            if any(name in t.columns and t.columns[name].scale for t in tables):
                raise DriverError(errors.DECIMAL_NATURAL_JOIN, colonna=name)
        if natural:
            counts = {}
            for table in tables:
                for key in table.columns:
                    counts.setdefault(key, []).append(table.columns[key])
            for key, cols in counts.items():
                if len(cols) > 1 and any(c.scale for c in cols):
                    raise DriverError(errors.DECIMAL_NATURAL_JOIN, colonna=cols[0].name)

    def query(self, a, b, parent, top, targets=None):
        i = a
        if self.kw(i) == "WITH":
            i = self.with_clause(i, b, parent)
        arms = []
        start = i
        for k in self.depth0(i, b):
            if self.kw(k) in _COMPOUND:
                arms.append((start, k))
                start = k + 2 if self.kw(k + 1) == "ALL" else k + 1
        arms.append((start, b))
        compound = len(arms) > 1
        for n, (x, y) in enumerate(arms):
            if x >= y:
                continue
            if compound and n == len(arms) - 1:
                cut = self.find(x, y, {"ORDER", "LIMIT"})
                if cut is not None:
                    y = cut
            if self.kw(x) == "SELECT":
                self.select(x, y, parent, top and not compound, targets)
            elif self.kw(x) == "VALUES":
                self.expr(x + 1, y, _Scope(parent))
            else:
                raise _Unclear("interrogazione non riconosciuta")

    def with_clause(self, a, b, parent):
        sig = self.sig
        i = a + 1
        if self.kw(i) == "RECURSIVE":
            i += 1
        while True:
            self.ctes.add(sqltext.unquote(sig[i].text).lower())
            i += 1
            if self.punct(i, "("):
                i = self.match[i] + 1
            if self.kw(i) != "AS":
                raise _Unclear("WITH non riconosciuto")
            i += 1
            while self.kw(i) in ("NOT", "MATERIALIZED"):
                i += 1
            if not self.punct(i, "("):
                raise _Unclear("WITH non riconosciuto")
            close = self.match[i]
            self.query(i + 1, close, parent, False)
            i = close + 1
            if self.punct(i, ","):
                i += 1
                continue
            return i

    def select(self, a, b, parent, bare_ok, targets=None):
        i = a + 1
        if self.kw(i) in ("DISTINCT", "ALL"):
            i += 1
        list_end = self.find(i, b, {"FROM"} | _CLAUSES) or b
        scope = _Scope(parent)
        ons = []
        tail_start = list_end
        if self.kw(list_end) == "FROM":
            from_end = self.find(list_end + 1, b, _CLAUSES) or b
            ons = self.from_clause(list_end + 1, from_end, scope, parent)
            tail_start = from_end
        aliases = self.select_items(i, list_end, scope, bare_ok, targets)
        for x, y in ons:
            self.expr(x, y, scope)
        self.tail(tail_start, b, scope, aliases)

    def update(self):
        i = 1
        if self.kw(i) == "OR":
            i += 2
        table, name, alias, display, i = self.table_name(i)
        if self.kw(i) != "SET":
            raise _Unclear("UPDATE senza SET")
        scope = _Scope()
        scope.add(alias or name, display, table)
        end = self.find(i + 1, len(self.sig), {"FROM"} | _CLAUSES) or len(self.sig)
        ons = []
        tail_start = end
        if self.kw(end) == "FROM":
            from_end = self.find(end + 1, len(self.sig), _CLAUSES) or len(self.sig)
            ons = self.from_clause(end + 1, from_end, scope, None)
            tail_start = from_end
        self.assignments(i + 1, end, scope, table)
        for x, y in ons:
            self.expr(x, y, scope)
        self.tail(tail_start, len(self.sig), scope)

    def delete(self):
        if self.kw(1) != "FROM":
            raise _Unclear("DELETE senza FROM")
        table, name, alias, display, i = self.table_name(2)
        scope = _Scope()
        scope.add(alias or name, display, table)
        self.tail(i, len(self.sig), scope)

    def insert_command(self):
        sig = self.sig
        n = len(sig)
        i = 1
        if self.kw(i) == "OR":
            i += 2
        if self.kw(i) != "INTO":
            raise _Unclear("INSERT senza INTO")
        table, name, alias, display, i = self.table_name(i + 1)
        scope = _Scope()
        scope.add(alias or name, display, table)
        scope.add("excluded", "excluded", table, hidden=True)
        columns = None
        if self.punct(i, "(") and self.kw(i + 1) not in ("SELECT", "WITH", "VALUES"):
            close = self.match[i]
            columns = [sqltext.unquote(sig[k].text).lower() for k in range(i + 1, close)
                       if sig[k].kind in ("word", "quoted")]
            i = close + 1
        if table is not None:
            targets = [table.columns.get(c) for c in columns] if columns is not None else list(table.columns.values())
        else:
            targets = []
        any_decimal = any(t is not None and t.scale for t in targets)
        upsert = self.find(i, n, {"ON"})
        while upsert is not None and self.kw(upsert + 1) != "CONFLICT":
            upsert = self.find(upsert + 1, n, {"ON"})
        returning = self.find(i, n, {"RETURNING"})
        source_end = min(x for x in (upsert, returning, n) if x is not None)
        word = self.kw(i)
        if word == "VALUES":
            j = i + 1
            while j < source_end and self.punct(j, "("):
                close = self.match[j]
                items = self.split(j + 1, close)
                if any_decimal and len(items) != len(targets):
                    raise _Unclear("numero di valori diverso dalle colonne")
                for k, (x, y) in enumerate(items):
                    col = targets[k] if k < len(targets) else None
                    if col is not None and col.scale:
                        self.assign(x, y, col, scope)
                    else:
                        self.expr(x, y, scope)
                j = close + 1
                if self.punct(j, ","):
                    j += 1
        elif word in ("SELECT", "WITH"):
            self.query(i, source_end, None, False, targets if any_decimal else None)
        if upsert is not None:
            j = upsert
            while j is not None and j < n:
                do = self.find(j, n, {"DO"})
                if do is None:
                    break
                nxt = self.find(do + 1, n, {"ON", "RETURNING"})
                stop = nxt if nxt is not None else n
                if self.kw(do + 1) == "UPDATE" and self.kw(do + 2) == "SET":
                    where = self.find(do + 3, stop, {"WHERE"})
                    self.assignments(do + 3, where if where is not None else stop, scope, table)
                    if where is not None:
                        self.expr(where + 1, stop, scope)
                j = nxt if nxt is not None and self.kw(nxt) == "ON" else None
        if returning is not None:
            self.select_items(returning + 1, n, scope, False, None)

    def create(self):
        words = [self.kw(i) for i in range(min(4, len(self.sig)))]
        if "TRIGGER" in words[:3]:
            for token in self.sig:
                if token.kind in ("word", "quoted") and sqltext.unquote(token.text).lower() in self.schema.names:
                    raise DriverError(errors.DECIMAL_TRIGGER, colonna=sqltext.unquote(token.text))
            return
        kind = None
        if "VIEW" in words[:3]:
            kind = "view"
        elif "TABLE" in words[:3]:
            kind = "table"
        if kind is None:
            return
        as_at = self.find(1, len(self.sig), {"AS"})
        if as_at is None or self.kw(as_at + 1) not in ("SELECT", "WITH", "VALUES"):
            return
        self.query(as_at + 1, len(self.sig), None, False)
        if self.edits:
            self.warnings.append(DriverError(errors.DECIMAL_VIEW_PLAIN if kind == "view"
                                             else errors.DECIMAL_NEW_TABLE_PLAIN))

    def go(self):
        first = self.kw(0)
        i = 0
        if first == "EXPLAIN":
            i = 3 if self.kw(1) == "QUERY" else 1
            first = self.kw(i)
        if i:
            self.shifted(i)
        if first in ("SELECT", "WITH", "VALUES"):
            self.query(0, len(self.sig), None, True)
        elif first in ("INSERT", "REPLACE"):
            self.insert_command()
        elif first == "UPDATE":
            self.update()
        elif first == "DELETE":
            self.delete()
        elif first == "CREATE":
            self.create()

    def shifted(self, offset):
        self.sig = self.sig[offset:]
        self.ordinal = sqltext.parameter_map(self.sig)[0]
        self.match = {}
        stack = []
        for k, token in enumerate(self.sig):
            if token.kind == "punct" and token.text == "(":
                stack.append(k)
            elif token.kind == "punct" and token.text == ")":
                self.match[stack.pop()] = k


def translate(db, sql):
    unchanged = Translation(sql, {}, [], False)
    schema = load_schema(db)
    if not schema.names:
        return unchanged
    sig = sqltext.significant(sql)
    if not any(t.kind in ("word", "quoted") and sqltext.unquote(t.text).lower() in schema.touch for t in sig):
        return unchanged
    try:
        run = _Run(sql, sig, schema)
        run.go()
        text = run.result()
    except DriverError:
        raise
    except _Unclear as exc:
        raise DriverError(errors.DECIMAL_NOT_UNDERSTOOD, dettaglio=str(exc))
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise DriverError(errors.DECIMAL_NOT_UNDERSTOOD, dettaglio="struttura del comando non riconosciuta (%s)" % exc)
    return Translation(text, run.slots, run.warnings, True)
