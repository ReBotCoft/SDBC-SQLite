# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest
from decimal import Decimal

import support

from sdbc_pysqlite import errors
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite import values
from sdbc_pysqlite.errors import DriverError

ORIGIN = values.Origin("t", "c")


def kind(label):
    return ts.classify(label)


class TypeTests(unittest.TestCase):
    def test_entries_count(self):
        self.assertEqual(len(ts.TYPE_ENTRIES), 55)
        self.assertEqual(sum(1 for e in ts.TYPE_ENTRIES if e["lo"]), 19)
        self.assertEqual(len(ts.type_info_rows()), 55)
        self.assertTrue(all(len(r) == 18 for r in ts.type_info_rows()))

    def test_all_integer_types_are_auto_increment(self):
        auto = [e["name"] for e in ts.TYPE_ENTRIES if e["auto_increment"]]
        self.assertEqual(auto, ["LO_TINYINT", "LO_SMALLINT", "LO_INTEGER", "LO_BIGINT"])
        rows = {r[0]: r[11] for r in ts.type_info_rows()}
        self.assertTrue(all(rows[n] for n in auto))
        self.assertEqual(sum(1 for v in rows.values() if v), 4)

    def test_untyped_is_variant(self):
        for label in ("", "ANY", None):
            self.assertEqual(kind(label or "").name, "LO_VARIANT")

    def test_lo_numbers(self):
        decimal = kind("LO_DECIMAL(10,2)")
        self.assertEqual((decimal.size, decimal.scale, decimal.kind), (10, 2, ts.K_DECIMAL))
        self.assertEqual(kind("LO_VARCHAR(30)").size, 30)
        self.assertEqual(kind("LO_TIMESTAMP(3)").scale, 3)

    def test_external_names(self):
        self.assertEqual(kind("INTEGER").code, ts.BIGINT)
        self.assertEqual(kind("TEXT").kind, ts.K_TEXT)
        self.assertEqual(kind("varchar(20)").code, ts.VARCHAR)
        self.assertEqual(kind("FLOAT").kind, ts.K_REAL)

    def test_unknown_name_follows_sqlite_rules(self):
        self.assertEqual(kind("MYINTEGERTYPE").kind, ts.K_INT)
        self.assertEqual(kind("SOMETEXT").kind, ts.K_TEXT)
        self.assertEqual(kind("XYZ").kind, ts.K_NUMERIC)

    def test_display_sizes_are_fixed_per_type(self):
        self.assertEqual(ts.display_size(kind("LO_TINYINT")), 4)
        self.assertEqual(ts.display_size(kind("LO_BIGINT")), 20)
        self.assertEqual(ts.display_size(kind("LO_DATE")), 10)
        self.assertEqual(ts.display_size(kind("LO_BOOLEAN")), 5)


class CodeToNameTests(unittest.TestCase):
    def test_every_lo_type_is_found_from_its_code(self):
        expected = {4: "LO_INTEGER", 5: "LO_SMALLINT", -6: "LO_TINYINT", -5: "LO_BIGINT", 12: "LO_VARCHAR",
                    1: "LO_CHAR", -1: "LO_LONGVARCHAR", 8: "LO_DOUBLE", 7: "LO_REAL", 2: "LO_NUMERIC",
                    3: "LO_DECIMAL", 16: "LO_BOOLEAN", 91: "LO_DATE", 92: "LO_TIME", 93: "LO_TIMESTAMP",
                    -2: "LO_BINARY", -3: "LO_VARBINARY", -4: "LO_LONGVARBINARY", 6: "LO_DOUBLE", -7: "LO_BOOLEAN"}
        for code, name in expected.items():
            with self.subTest(code=code):
                self.assertEqual(ts.lo_name_for_code(code), name)
                self.assertIn(name, ts.LO_BY_NAME)

    def test_unknown_or_missing_code_gives_no_name(self):
        for code in (0, 1111, None, "x", 9999):
            self.assertEqual(ts.lo_name_for_code(code), "")


class ReadTests(unittest.TestCase):
    def test_integer_conversions(self):
        t = kind("LO_BIGINT")
        self.assertEqual(values.to_integer(5, t, ORIGIN, "Int"), 5)
        self.assertEqual(values.to_integer("12", t, ORIGIN, "Int"), 12)
        self.assertEqual(values.to_integer(3.0, t, ORIGIN, "Long"), 3)

    def test_information_loss_is_an_error(self):
        t = kind("LO_BIGINT")
        with self.assertRaises(DriverError) as raised:
            values.to_integer(2.5, t, ORIGIN, "Int")
        self.assertEqual(raised.exception.code, errors.VALUE_NOT_CONVERTIBLE)
        with self.assertRaises(DriverError) as raised:
            values.to_integer("abc", t, ORIGIN, "Int")
        self.assertEqual(raised.exception.code, errors.VALUE_NOT_CONVERTIBLE)

    def test_out_of_range(self):
        t = kind("LO_BIGINT")
        with self.assertRaises(DriverError) as raised:
            values.to_integer(300, t, ORIGIN, "Byte")
        self.assertEqual(raised.exception.code, errors.VALUE_OUT_OF_RANGE)
        with self.assertRaises(DriverError):
            values.to_integer(2 ** 31, t, ORIGIN, "Int")

    def test_declared_small_type_range(self):
        t = kind("LO_TINYINT")
        with self.assertRaises(DriverError) as raised:
            values.to_integer(200, t, ORIGIN, "Int")
        self.assertEqual(raised.exception.code, errors.VALUE_OUT_OF_RANGE)

    def test_double_and_boolean(self):
        self.assertEqual(values.to_double("1.5", kind("LO_DOUBLE"), ORIGIN), 1.5)
        self.assertTrue(values.to_boolean(1, kind("LO_BOOLEAN"), ORIGIN))
        self.assertFalse(values.to_boolean(0, kind("LO_BOOLEAN"), ORIGIN))
        self.assertTrue(values.to_boolean("true", kind("LO_BOOLEAN"), ORIGIN))

    def test_decimal_is_scaled_integer(self):
        t = kind("LO_DECIMAL(10,2)")
        self.assertEqual(values.to_text(12345, t, ORIGIN), "123.45")
        self.assertEqual(values.to_text(5, t, ORIGIN), "0.05")
        self.assertEqual(values.to_double(12345, t, ORIGIN), 123.45)
        with self.assertRaises(DriverError):
            values.to_integer(12345, t, ORIGIN, "Int")
        self.assertEqual(values.to_integer(12300, t, ORIGIN, "Int"), 123)

    def test_text_forms(self):
        self.assertEqual(values.to_text(7, kind("LO_INTEGER"), ORIGIN), "7")
        self.assertEqual(values.to_text("x", kind("LO_VARCHAR"), ORIGIN), "x")
        self.assertEqual(values.to_text(b"\x01\xff", kind("LO_VARBINARY"), ORIGIN), "01FF")
        self.assertEqual(values.to_text(1, kind("LO_BOOLEAN"), ORIGIN), "true")

    def test_bytes(self):
        self.assertEqual(values.to_bytes(b"ab", kind("LO_VARBINARY"), ORIGIN), b"ab")
        self.assertEqual(values.to_bytes("ab", kind("LO_VARBINARY"), ORIGIN), b"ab")

    def test_date_texts(self):
        t = kind("LO_DATE")
        self.assertEqual(values.to_date("2026-10-17", t, ORIGIN), (2026, 10, 17))
        self.assertEqual(values.to_date("2026-10-17 23:59:59", t, ORIGIN), (2026, 10, 17))
        ts_type = kind("LO_TIMESTAMP(3)")
        parts = values.to_timestamp("2026-10-17 01:02:03.456", ts_type, ORIGIN)
        self.assertEqual(parts[:6], (2026, 10, 17, 1, 2, 3))
        self.assertEqual(parts[6], 456000000)

    def test_unreadable_date(self):
        with self.assertRaises(DriverError) as raised:
            values.to_date("domani", kind("LO_DATE"), ORIGIN)
        self.assertEqual(raised.exception.code, errors.DATE_UNREADABLE)

    def test_numeric_dates(self):
        t = kind("LO_TIMESTAMP")
        parts = values.to_timestamp(86400 * 365, t, ORIGIN)
        self.assertIn(parts[0], (1970, 1971))
        julian = values.to_timestamp(2440587.5 + 100, t, ORIGIN)
        self.assertEqual(julian[0], 1970)

    def test_encode_helpers(self):
        self.assertEqual(values.encode_date(2026, 1, 2), "2026-01-02")
        self.assertEqual(values.encode_timestamp(2026, 1, 2, 3, 4, 5, 123456789, 3, "text", "local"),
                         "2026-01-02 03:04:05.123")
        self.assertEqual(values.encode_decimal(Decimal("1.234"), 2), 123)
        with self.assertRaises(DriverError):
            values.encode_decimal(10 ** 30, 2)


if __name__ == "__main__":
    unittest.main()
