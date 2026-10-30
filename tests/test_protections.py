# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest

import support
from test_database import DatabaseTestCase, PREFIX

from sdbc_pysqlite import errors
from sdbc_pysqlite import parameters
from sdbc_pysqlite import protections
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.errors import DriverError

DEFENSIVE = "?DefensiveMode=true"
UNTRUSTED = "?UntrustedSchema=true"


class ParameterTests(unittest.TestCase):

    def test_all_three_are_off_by_default(self):
        self.assertIs(parameters.DEFAULTS[parameters.DEFENSIVE_MODE], False)
        self.assertIs(parameters.DEFAULTS[parameters.UNTRUSTED_SCHEMA], False)
        self.assertEqual(parameters.DEFAULTS[parameters.LIMITS_PROFILE], "none")

    def test_values_are_checked(self):
        self.assertIs(parameters.convert(parameters.DEFENSIVE_MODE, "true"), True)
        self.assertEqual(parameters.convert(parameters.LIMITS_PROFILE, "strict"), "strict")
        for text in ("Strict", "high", ""):
            with self.assertRaises(parameters.InvalidValue):
                parameters.convert(parameters.LIMITS_PROFILE, text)
        with self.assertRaises(parameters.InvalidValue):
            parameters.convert(parameters.UNTRUSTED_SCHEMA, "yes")

    def test_profiles_cover_the_approved_values(self):
        self.assertEqual(protections.PROFILES["none"], {})
        self.assertEqual(protections.PROFILES["prudent"], {
            "EXPR_DEPTH": 200, "TRIGGER_DEPTH": 50, "COMPOUND_SELECT": 100,
            "LIKE_PATTERN_LENGTH": 5000, "ATTACHED": 5, "VDBE_OP": 50000000})
        self.assertEqual(protections.PROFILES["strict"], dict(
            protections.PROFILES["prudent"], LENGTH=100000000, SQL_LENGTH=10000000, COLUMN=500,
            VARIABLE_NUMBER=32766))


class DefensiveModeTests(DatabaseTestCase):

    TAMPER = "UPDATE sqlite_master SET sql = sql WHERE name = 'x'"

    def tamper(self, connection):
        connection.execute("PRAGMA writable_schema = ON")
        connection.execute(self.TAMPER)

    def test_off_by_default_the_schema_table_can_be_written(self):
        opened = self.open(PREFIX + self.make_db("a.db"))
        self.tamper(opened.connection)
        self.assertEqual(self.warning_codes(opened), [])

    def test_on_the_schema_table_cannot_be_written(self):
        opened = self.open(PREFIX + self.make_db("a.db") + DEFENSIVE)
        self.assertEqual(self.warning_codes(opened), [])
        with self.assertRaises(sqlite.Error):
            self.tamper(opened.connection)

    def test_on_the_journal_off_is_not_obtained_and_the_driver_says_so(self):
        opened = self.open(PREFIX + self.make_db("a.db") + DEFENSIVE + "&JournalMode=off")
        self.assertEqual(self.warning_codes(opened), [errors.JOURNAL_MODE_NOT_OBTAINED])
        self.assertEqual(opened.warnings[0].values, {"richiesto": "off", "effettivo": "delete"})

    def test_on_ordinary_work_still_runs(self):
        opened = self.open(PREFIX + self.make_db("a.db") + DEFENSIVE)
        connection = opened.connection
        connection.execute("CREATE TABLE n(a INTEGER PRIMARY KEY, b TEXT)")
        connection.execute("INSERT INTO n(b) VALUES ('x')")
        connection.execute("ALTER TABLE n ADD COLUMN c INTEGER")
        connection.execute("CREATE INDEX i ON n(b)")
        connection.execute("DROP TABLE n")


class UntrustedSchemaTests(DatabaseTestCase):

    def prepare(self, settings=""):
        opened = self.open(PREFIX + self.make_db("a.db") + settings)
        opened.connection.execute("CREATE VIEW v_now AS SELECT now() AS x")
        opened.connection.execute("CREATE VIEW v_year AS SELECT year('2026-10-30') AS x")
        return opened.connection

    def test_off_by_default_every_function_works_in_a_view(self):
        connection = self.prepare()
        self.assertTrue(connection.execute("SELECT x FROM v_now").fetchone()[0])
        self.assertEqual(connection.execute("SELECT x FROM v_year").fetchone()[0], 2026)

    def test_on_deterministic_functions_still_work_in_a_view(self):
        connection = self.prepare(UNTRUSTED)
        self.assertEqual(connection.execute("SELECT x FROM v_year").fetchone()[0], 2026)

    def test_on_functions_that_are_not_deterministic_fail_in_a_view(self):
        connection = self.prepare(UNTRUSTED)
        with self.assertRaises(sqlite.Error):
            connection.execute("SELECT x FROM v_now").fetchone()

    def test_on_the_same_function_works_outside_a_schema_object(self):
        connection = self.prepare(UNTRUSTED)
        self.assertTrue(connection.execute("SELECT now()").fetchone()[0])

    def test_the_non_deterministic_functions_are_the_documented_ones(self):
        connection = self.prepare(UNTRUSTED)
        for call in ("rand()", "rand(5)", "uuid()", "identity()", "curdate()", "today()", "curtime()",
                     "now()", "unix_timestamp()", "unix_millis()"):
            connection.execute("CREATE VIEW IF NOT EXISTS w_%d AS SELECT %s AS x" % (abs(hash(call)), call))
            with self.assertRaises(sqlite.Error, msg=call):
                connection.execute("SELECT x FROM w_%d" % abs(hash(call))).fetchone()


class LimitsTests(DatabaseTestCase):

    count = 0

    def limits(self, profile):
        suffix = "" if profile is None else "?LimitsProfile=" + profile
        self.count += 1
        opened = self.open(PREFIX + self.make_db("a%d.db" % self.count) + suffix)
        self.assertEqual(self.warning_codes(opened), [])
        return opened.connection

    def test_none_leaves_the_library_values(self):
        connection = self.limits("none")
        plain = self.limits(None)
        for name in sqlite.LIMITS:
            self.assertEqual(connection.limit(name), plain.limit(name), name)

    def test_profiles_set_the_approved_values(self):
        for profile in ("prudent", "strict"):
            connection = self.limits(profile)
            for name, value in protections.PROFILES[profile].items():
                self.assertEqual(connection.limit(name), value, (profile, name))

    def test_prudent_does_not_touch_the_strict_only_limits(self):
        prudent = self.limits("prudent")
        plain = self.limits(None)
        for name in ("LENGTH", "SQL_LENGTH", "COLUMN", "VARIABLE_NUMBER", "FUNCTION_ARG"):
            self.assertEqual(prudent.limit(name), plain.limit(name), name)

    def test_untouched_limits_stay_with_strict(self):
        strict = self.limits("strict")
        plain = self.limits(None)
        self.assertEqual(strict.limit("FUNCTION_ARG"), plain.limit("FUNCTION_ARG"))

    def test_a_lower_library_limit_is_never_raised(self):
        connection = self.limits(None)
        connection.limit("COLUMN", 100)

        class Options:
            defensive_mode = False
            untrusted_schema = False
            limits_profile = "strict"

        self.assertEqual(protections.apply(connection, Options), [])
        self.assertEqual(connection.limit("COLUMN"), 100)

    def test_strict_refuses_a_table_with_too_many_columns(self):
        columns = ", ".join("c%d" % i for i in range(501))
        self.limits(None).execute("CREATE TABLE wide(%s)" % columns)
        for profile in ("prudent", "strict"):
            connection = self.limits(profile)
            if profile == "strict":
                with self.assertRaises(sqlite.Error):
                    connection.execute("CREATE TABLE wide(%s)" % columns)
            else:
                connection.execute("CREATE TABLE wide(%s)" % columns)

    def test_prudent_refuses_a_very_long_like_pattern(self):
        pattern = "a" * 5001
        self.assertEqual(self.limits(None).execute("SELECT 'a' LIKE ?", (pattern,)).fetchone()[0], 0)
        with self.assertRaises(sqlite.Error):
            self.limits("prudent").execute("SELECT 'a' LIKE ?", (pattern,)).fetchone()

    def test_the_drivers_own_like_follows_the_limit_with_bytes_not_characters(self):
        connection = self.limits("prudent")
        self.assertEqual(connection.execute("SELECT 'a' LIKE ?", ("a" * 5000,)).fetchone()[0], 0)
        with self.assertRaises(sqlite.Error):
            connection.execute("SELECT 'a' LIKE ?", ("\u00e8" * 2501,)).fetchone()
        self.assertEqual(connection.execute("SELECT 'a' LIKE ?", ("\u00e8" * 2500,)).fetchone()[0], 0)
        self.assertEqual(connection.execute("SELECT 'a' LIKE 'a' ESCAPE '!'").fetchone()[0], 1)

    def test_prudent_refuses_a_long_union(self):
        sql = " UNION ALL ".join("SELECT %d" % i for i in range(101))
        self.assertEqual(len(self.limits(None).execute(sql).fetchall()), 101)
        with self.assertRaises(sqlite.Error):
            self.limits("prudent").execute(sql).fetchall()

    def test_strict_refuses_too_many_parameters(self):
        sql = "SELECT 1 WHERE 0 IN (%s)" % ",".join("?" * 32767)
        values = tuple(range(1, 32768))
        with self.assertRaises(sqlite.Error):
            self.limits("strict").execute(sql, values).fetchall()
        self.assertLessEqual(self.limits("strict").limit("VARIABLE_NUMBER"), 32766)


class AllTogetherTests(DatabaseTestCase):

    def test_all_three_on_give_no_warning_and_ordinary_work_runs(self):
        text = PREFIX + self.make_db("a.db") + "?DefensiveMode=true&UntrustedSchema=true&LimitsProfile=strict"
        opened = self.open(text)
        self.assertEqual(self.warning_codes(opened), [])
        connection = opened.connection
        connection.execute("CREATE TABLE t2(a INTEGER PRIMARY KEY, b TEXT)")
        connection.execute("INSERT INTO t2(b) VALUES (?)", ("x",))
        self.assertEqual(connection.execute("SELECT b FROM t2").fetchone()[0], "x")

    def test_a_wrong_profile_in_the_address_is_an_error(self):
        error = self.fails(PREFIX + self.make_db("a.db") + "?LimitsProfile=high")
        self.assertEqual(error.code, errors.INVALID_VALUE)

    def test_levels_follow_the_usual_chain(self):
        path = self.make_db("a.db")
        from_options = {parameters.LIMITS_PROFILE: "strict"}
        self.assertEqual(self.open(PREFIX + path, from_options).options.limits_profile, "strict")
        document = {parameters.LIMITS_PROFILE: "prudent"}
        opened = database_open(self, PREFIX + path, from_options, document)
        self.assertEqual(opened.options.limits_profile, "prudent")
        self.assertEqual(self.open(PREFIX + path + "?LimitsProfile=none", from_options).options.limits_profile,
                         "none")


def database_open(case, text, settings, document):
    from sdbc_pysqlite import database
    from test_database import file_url_to_path
    opened = database.open_database(text, settings, file_url_to_path, document)
    case.opened.append(opened)
    return opened


class NotObtainedTests(unittest.TestCase):

    class Fake:
        def __init__(self, config_result, limit_current):
            self.config_result = config_result
            self.limit_current = limit_current

        def config(self, option, value):
            return self.config_result

        def limit(self, name, value=-1):
            return self.limit_current

    class Options:
        defensive_mode = True
        untrusted_schema = True
        limits_profile = "prudent"

    def test_everything_refused(self):
        connection = self.Fake(None, -1)
        self.assertEqual(protections.apply(connection, self.Options),
                         ["DefensiveMode", "UntrustedSchema", "LimitsProfile"])

    def test_a_limit_the_library_cannot_lower(self):
        class Stubborn(self.Fake):
            def limit(self, name, value=-1):
                return 10 ** 9
        connection = Stubborn(1, 0)
        connection.config = lambda option, value: 1 if option == sqlite.DBCONFIG_DEFENSIVE else 0
        self.assertEqual(protections.apply(connection, self.Options), ["LimitsProfile"])

    def test_nothing_requested_nothing_asked(self):
        class Off:
            defensive_mode = False
            untrusted_schema = False
            limits_profile = "none"
        self.assertEqual(protections.apply(self.Fake(None, -1), Off), [])

    def test_the_warning_has_both_languages(self):
        from sdbc_pysqlite import messages
        warning = DriverError(errors.PROTECTION_NOT_OBTAINED, protezioni="DefensiveMode, LimitsProfile")
        for language in ("it", "en"):
            described = messages.describe(warning, language, "x")
            self.assertTrue(described.is_warning)
            self.assertIn("DefensiveMode, LimitsProfile", described.message)


if __name__ == "__main__":
    unittest.main()
