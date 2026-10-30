# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os
import tempfile
import unittest

import support

from sdbc_pysqlite import database
from sdbc_pysqlite import dialect
from sdbc_pysqlite import functions


class DialectTests(unittest.TestCase):
    def test_braces(self):
        self.assertEqual(dialect.translate("SELECT {d '2026-10-24'}"), "SELECT '2026-10-24'")
        self.assertEqual(dialect.translate("SELECT {fn UCASE(a)} FROM t"), "SELECT UCASE(a) FROM t")
        self.assertEqual(dialect.translate("SELECT 'a{d x}'"), "SELECT 'a{d x}'")

    def test_keyword_constructs(self):
        self.assertEqual(dialect.translate("SELECT SUBSTRING(a FROM 2 FOR 3)"), "SELECT SUBSTR(a, 2, 3)")
        self.assertEqual(dialect.translate("SELECT POSITION('a' IN b)"), "SELECT LOCATE('a', b)")
        self.assertEqual(dialect.translate("SELECT TRIM(LEADING 'x' FROM a)"),
                         "SELECT sdbc_trim('x', a, 1)")
        self.assertEqual(dialect.translate("SELECT EXTRACT(YEAR FROM d)"), "SELECT EXTRACT('YEAR', d)")
        self.assertEqual(dialect.translate("SELECT CONVERT(a, SQL_INTEGER)"), "SELECT CAST(a AS INTEGER)")
        self.assertEqual(dialect.translate("SELECT INSERT(a,1,2,'x')"), 'SELECT "INSERT"(a,1,2,\'x\')')

    def test_idempotent_and_untouched(self):
        sql = "SELECT SUBSTRING(a FROM 2 FOR 3), {d '2026-01-01'}, TRIM(BOTH 'x' FROM b) FROM t WHERE c=?"
        once = dialect.translate(sql)
        self.assertEqual(dialect.translate(once), once)
        self.assertEqual(once.count("?"), 1)
        self.assertEqual(dialect.translate("SELECT 1"), "SELECT 1")


class FunctionTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.opened = database.open_database(
            "sdbc:external:pysqlite:" + os.path.join(self._dir.name, "f.db"),
            {"CreateIfMissing": True}, lambda u: u)
        self.addCleanup(self.opened.connection.close)
        self.db = self.opened.connection

    def one(self, sql, *params):
        return self.db.execute(dialect.translate(sql), params).fetchone()[0]

    def test_case_and_accents(self):
        self.assertEqual(self.one("SELECT UPPER('caffè')"), "CAFFÈ")
        self.assertEqual(self.one("SELECT LOWER('ÈÀ')"), "èà")
        self.assertEqual(self.one("SELECT 'Café' LIKE 'cafe%'"), 1)
        self.assertEqual(self.one("SELECT 'Café' = 'cafe'"), 0)

    def test_nocase_order(self):
        self.db.execute("create table w(x)")
        for value in ("Z", "é", "e", "E", "a"):
            self.db.execute("insert into w values (?)", (value,))
        rows = [r[0] for r in self.db.execute("select x from w order by x collate nocase")]
        self.assertEqual(rows[0], "a")
        self.assertEqual(rows[-1], "Z")
        self.assertEqual(rows[-2], "é")

    def test_regexp(self):
        self.assertEqual(self.one("SELECT 'abc123' REGEXP '[a-z]+[0-9]+'"), 1)
        self.assertEqual(self.one("SELECT REGEXP_REPLACE('a1b2', '[0-9]', '#')"), "a#b#")
        self.assertEqual(self.one("SELECT REGEXP_COUNT('a1b2', '[0-9]')"), 2)

    def test_text_and_numbers(self):
        self.assertEqual(self.one("SELECT SUBSTRING('abcdef' FROM 2 FOR 3)"), "bcd")
        self.assertEqual(self.one("SELECT POSITION('c' IN 'abcdef')"), 3)
        self.assertEqual(self.one("SELECT TRIM(BOTH 'x' FROM 'xxaxx')"), "a")
        self.assertEqual(self.one("SELECT INSERT('abcdef',2,3,'X')"), "aXef")
        self.assertEqual(self.one("SELECT LOG(100)"), 2)

    def test_dates(self):
        self.assertEqual(self.one("SELECT EXTRACT(YEAR FROM '2026-10-24')"), 2026)
        self.assertEqual(self.one("SELECT DATEDIFF('day', '2026-10-01', '2026-10-24')"), 23)
        self.assertEqual(self.one("SELECT TO_CHAR('2026-10-24 22:30:00', 'DD/MM/YYYY HH24:MI')"),
                         "24/10/2026 22:30")
        self.assertEqual(self.one("SELECT DAYNAME('2026-10-24')"), "Saturday")
        self.assertEqual(self.one("SELECT {d '2026-10-24'}"), "2026-10-24")

    def test_names_provider(self):
        names = functions.Names(("dom", "lun", "mar", "mer", "gio", "ven", "sab"),
                                ("do", "lu", "ma", "me", "gi", "ve", "sa"),
                                tuple("M%d" % i for i in range(12)), tuple("m%d" % i for i in range(12)))
        path = os.path.join(self._dir.name, "n.db")
        opened = database.open_database("sdbc:external:pysqlite:" + path, {"CreateIfMissing": True},
                                        lambda u: u, None, lambda option: names)
        self.addCleanup(opened.connection.close)
        self.assertEqual(opened.connection.execute("SELECT DAYNAME('2026-10-24')").fetchone()[0], "sab")

    def test_names_language_choices_and_provider_argument(self):
        from sdbc_pysqlite import parameters
        self.assertEqual(parameters.NAMES_LANGUAGES, ("auto", "en", "it", "fr", "de", "es"))
        names = functions.Names(("d1",) * 7, ("d",) * 7, ("m1",) * 12, ("m",) * 12)
        asked = []

        def provider(language):
            asked.append(language)
            return names

        for language, expected in (("it", ["it"]), ("auto", ["auto"]), ("en", [])):
            asked.clear()
            path = os.path.join(self._dir.name, "l-%s.db" % language)
            opened = database.open_database("sdbc:external:pysqlite:%s?NamesLanguage=%s" % (path, language),
                                            {"CreateIfMissing": True}, lambda u: u, None, provider)
            self.addCleanup(opened.connection.close)
            value = opened.connection.execute("SELECT DAYNAME('2026-10-24')").fetchone()[0]
            self.assertEqual(asked, expected)
            self.assertEqual(value, "Saturday" if language == "en" else "d1")


if __name__ == "__main__":
    unittest.main()
