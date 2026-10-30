# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest

import support

from sdbc_pysqlite import address
from sdbc_pysqlite import errors
from sdbc_pysqlite.errors import DriverError

PREFIX = "sdbc:external:pysqlite:"


def identity(url):
    return url


def fake_file_url(url):
    if not url.startswith("file:///"):
        raise ValueError(url)
    return url[len("file:///"):].replace("/", "\\")


class SplitAddressTests(unittest.TestCase):

    def split(self, text):
        return address.split_address(text, fake_file_url)

    def test_plain_path(self):
        result = self.split(PREFIX + r"C:\dati\prova.db")
        self.assertEqual((result.path, result.options), (r"C:\dati\prova.db", ""))

    def test_without_prefix(self):
        self.assertEqual(self.split(r"C:\dati\prova.db").path, r"C:\dati\prova.db")

    def test_spaces_around_are_removed(self):
        self.assertEqual(self.split("  " + PREFIX + r"C:\x.db  ").path, r"C:\x.db")

    def test_repeated_prefix_is_removed_as_many_times_as_needed(self):
        for times in (2, 3, 5):
            self.assertEqual(self.split(PREFIX * times + r"C:\x.db").path, r"C:\x.db")

    def test_prefix_is_case_sensitive(self):
        text = "sdbc:external:pySQLite:" + r"C:\x.db"
        self.assertEqual(self.split(text).path, text)

    def test_quotes_around_path_only(self):
        result = self.split('"C:\\dati\\prova.db"')
        self.assertEqual((result.path, result.options), (r"C:\dati\prova.db", ""))

    def test_quotes_around_whole_string_with_options(self):
        result = self.split('"C:\\dati\\prova.db?ReadOnly=true"')
        self.assertEqual((result.path, result.options), (r"C:\dati\prova.db", "ReadOnly=true"))

    def test_quotes_around_path_then_options(self):
        result = self.split('"C:\\dati\\prova.db"?ReadOnly=true')
        self.assertEqual((result.path, result.options), (r"C:\dati\prova.db", "ReadOnly=true"))

    def test_quotes_with_prefix(self):
        result = self.split(PREFIX + '"C:\\dati\\prova.db"')
        self.assertEqual(result.path, r"C:\dati\prova.db")

    def test_single_quote_is_part_of_the_name(self):
        self.assertEqual(self.split("C:\\L'archivio\\prova.db").path, "C:\\L'archivio\\prova.db")
        self.assertEqual(self.split("'C:\\x.db'").path, "'C:\\x.db'")

    def test_ampersand_and_equals_in_file_name_are_kept(self):
        self.assertEqual(self.split(r"C:\a&b=c.db").path, r"C:\a&b=c.db")

    def test_trailing_question_mark_is_ignored(self):
        result = self.split(r"C:\x.db?")
        self.assertEqual((result.path, result.options), (r"C:\x.db", ""))

    def test_file_url_is_converted(self):
        self.assertEqual(self.split("file:///C:/dati/prova.db").path, r"C:\dati\prova.db")
        self.assertEqual(self.split(PREFIX + "file:///C:/dati/prova.db?ReadOnly=true").options,
                         "ReadOnly=true")

    def test_file_url_that_cannot_be_converted_is_an_invalid_address(self):
        with self.assertRaises(DriverError) as caught:
            self.split("file:/storto")
        self.assertEqual(caught.exception.code, errors.ADDRESS_INVALID)
        self.assertEqual(caught.exception.values["indirizzo"], "file:/storto")


class CheckPathTests(unittest.TestCase):

    def code(self, path):
        try:
            address.check_path_text(path, "ORIGINALE")
        except DriverError as error:
            return error.code
        return None

    def test_valid_paths(self):
        for path in (r"C:\dati\prova.db", r"\\server\cartella\prova.db", "prova.db",
                     r"C:\L'archivio\è prova #1 (copia).db", "/home/x/prova.db"):
            self.assertIsNone(self.code(path), path)

    def test_empty_path(self):
        self.assertEqual(self.code(""), errors.ADDRESS_INVALID)
        self.assertEqual(self.code("   "), errors.ADDRESS_INVALID)

    def test_forbidden_characters(self):
        for path in ('C:\\a<b.db', 'C:\\a>b.db', 'C:\\a|b.db', 'C:\\a*b.db', 'C:\\a"b.db',
                     'C:\\a\x01b.db', "C:\\dati:prova.db", ":prova.db", "1:\\x.db"):
            self.assertEqual(self.code(path), errors.PATH_BAD_CHARACTERS, repr(path))

    def test_forbidden_characters_are_listed_once_in_order(self):
        with self.assertRaises(DriverError) as caught:
            address.check_path_text("C:\\a<b>c<d.db", "X")
        self.assertEqual(caught.exception.values["caratteri"], "< >")
        self.assertEqual(caught.exception.values["percorso"], "C:\\a<b>c<d.db")


class ParseParametersTests(unittest.TestCase):

    URL = PREFIX + r"C:\x.db?..."

    def parse(self, options):
        return address.parse_parameters(options, self.URL)

    def error(self, options):
        with self.assertRaises(DriverError) as caught:
            self.parse(options)
        return caught.exception

    def test_no_parameters(self):
        self.assertEqual(self.parse(""), {})

    def test_all_five(self):
        found = self.parse("CreateIfMissing=true&LockTimeoutSeconds=0&ForeignKeys=false"
                           "&ReadOnly=true&JournalMode=wal")
        self.assertEqual(found, {"CreateIfMissing": True, "LockTimeoutSeconds": 0,
                                 "ForeignKeys": False, "ReadOnly": True, "JournalMode": "wal"})

    def test_empty_groups_are_ignored(self):
        self.assertEqual(self.parse("ReadOnly=true&&ForeignKeys=true&"),
                         {"ReadOnly": True, "ForeignKeys": True})
        self.assertEqual(self.parse("&&&"), {})

    def test_group_without_equals(self):
        error = self.error("ForeignKeys")
        self.assertEqual(error.code, errors.PARAMETER_NO_EQUALS)
        self.assertEqual(error.values["gruppo"], "ForeignKeys")
        self.assertEqual(error.values["indirizzo"], self.URL)

    def test_unknown_name(self):
        error = self.error("CreateIfMisssing=true")
        self.assertEqual(error.code, errors.UNKNOWN_PARAMETER)
        self.assertEqual(error.values["nome"], "CreateIfMisssing")
        self.assertIn("CreateIfMissing", error.values["ammessi"])

    def test_empty_name_is_unknown(self):
        self.assertEqual(self.error("=true").code, errors.UNKNOWN_PARAMETER)

    def test_names_are_case_sensitive(self):
        self.assertEqual(self.error("readonly=true").code, errors.UNKNOWN_PARAMETER)
        self.assertEqual(self.error("READONLY=true").code, errors.UNKNOWN_PARAMETER)

    def test_values_are_case_sensitive(self):
        for text in ("True", "FALSE", "1", "0", "yes", "on", "si", ""):
            error = self.error("ReadOnly=" + text)
            self.assertEqual(error.code, errors.INVALID_VALUE, text)
            self.assertEqual(error.values["valore"], text)

    def test_repeated_parameter(self):
        error = self.error("ReadOnly=true&ReadOnly=false")
        self.assertEqual(error.code, errors.PARAMETER_REPEATED)
        self.assertEqual(error.values["nome"], "ReadOnly")

    def test_invalid_timeout_values(self):
        for text in ("-1", "1.5", "abc", "", " 5", "+5", "٣", "5s"):
            self.assertEqual(self.error("LockTimeoutSeconds=" + text).code,
                             errors.INVALID_VALUE, repr(text))

    def test_valid_timeout_values(self):
        self.assertEqual(self.parse("LockTimeoutSeconds=0"), {"LockTimeoutSeconds": 0})
        self.assertEqual(self.parse("LockTimeoutSeconds=86400"), {"LockTimeoutSeconds": 86400})

    def test_journal_modes(self):
        for mode in ("delete", "truncate", "persist", "memory", "wal", "off"):
            self.assertEqual(self.parse("JournalMode=" + mode), {"JournalMode": mode})
        self.assertEqual(self.error("JournalMode=WAL").code, errors.INVALID_VALUE)
        self.assertEqual(self.error("JournalMode=foo").code, errors.INVALID_VALUE)

    def test_value_may_contain_equals_but_is_then_invalid(self):
        self.assertEqual(self.error("ReadOnly=true=1").code, errors.INVALID_VALUE)

    def test_stops_at_the_first_error_left_to_right(self):
        self.assertEqual(self.error("ReadOnly=x&Nome=1").code, errors.INVALID_VALUE)
        self.assertEqual(self.error("Nome=1&ReadOnly=x").code, errors.UNKNOWN_PARAMETER)
        self.assertEqual(self.error("ReadOnly&Nome=1").code, errors.PARAMETER_NO_EQUALS)


class EditedAddressTests(unittest.TestCase):

    @staticmethod
    def _convert(path):
        return path

    def test_valid_addresses(self):
        for url in ("sdbc:external:pysqlite:C:\\a\\b.db",
                    "sdbc:external:pysqlite:C:\\a\\b.db?CreateIfMissing=true&LockTimeoutSeconds=9",
                    "  sdbc:external:pysqlite:C:\\a.db  "):
            address.check_address(url, self._convert)

    def test_prefix_is_not_required(self):
        for text in ("C:\\a\\b.db", "C:\\a\\b.db?ReadOnly=true", '"C:\\a b\\c.db"', '"C:\\a.db"?ReadOnly=true'):
            address.check_address(text, self._convert)

    def test_empty_field_is_an_error(self):
        for text in ("", "   ", '""', "?ReadOnly=true"):
            with self.assertRaises(DriverError, msg=text):
                address.check_address(text, self._convert)

    def test_display_text_has_no_prefix(self):
        self.assertEqual(address.display_text("sdbc:external:pysqlite:C:\\a.db?ReadOnly=true"),
                         "C:\\a.db?ReadOnly=true")
        self.assertEqual(address.display_text("  sdbc:external:pysqlite:C:\\a.db "), "C:\\a.db")
        self.assertEqual(address.display_text("C:\\a.db"), "C:\\a.db")

    def test_full_address_adds_the_prefix(self):
        full = address.full_address
        self.assertEqual(full("C:\\a.db", self._convert), "sdbc:external:pysqlite:C:\\a.db")
        self.assertEqual(full('"C:\\a b.db"', self._convert), "sdbc:external:pysqlite:C:\\a b.db")
        self.assertEqual(full("C:\\a.db?CreateIfMissing=true", self._convert),
                         "sdbc:external:pysqlite:C:\\a.db?CreateIfMissing=true")
        self.assertEqual(full("sdbc:external:pysqlite:C:\\a.db?ReadOnly=true", self._convert),
                         "sdbc:external:pysqlite:C:\\a.db?ReadOnly=true")
        self.assertEqual(full("  C:\\a.db  ", self._convert), "sdbc:external:pysqlite:C:\\a.db")

    def test_empty_path_unknown_parameter_and_bad_characters(self):
        for url in ("sdbc:external:pysqlite:", "sdbc:external:pysqlite:?ReadOnly=true",
                    "sdbc:external:pysqlite:C:\\a.db?Nope=1", "sdbc:external:pysqlite:C:\\a.db?ReadOnly=maybe",
                    "sdbc:external:pysqlite:C:\\a*.db"):
            with self.assertRaises(DriverError, msg=url):
                address.check_address(url, self._convert)

    def test_with_path_keeps_the_options(self):
        self.assertEqual(address.with_path("C:\\a.db?ReadOnly=true", "D:\\n.db"), "D:\\n.db?ReadOnly=true")
        self.assertEqual(address.with_path("C:\\a.db", "D:\\n.db"), "D:\\n.db")
        self.assertEqual(address.with_path("sdbc:external:pysqlite:C:\\a.db?ReadOnly=true", "D:\\n.db"),
                         "D:\\n.db?ReadOnly=true")
        self.assertEqual(address.with_path("", "D:\\n.db"), "D:\\n.db")


class DefaultExtensionTests(unittest.TestCase):
    def test_extension_added_only_when_missing(self):
        add = address.with_default_extension
        self.assertEqual(add("C:\\dati\\miodb"), "C:\\dati\\miodb.db3")
        self.assertEqual(add("C:\\dati\\miodb.sqlite"), "C:\\dati\\miodb.sqlite")
        self.assertEqual(add("C:\\dati\\miodb.db"), "C:\\dati\\miodb.db")
        self.assertEqual(add("C:\\dati.v2\\miodb"), "C:\\dati.v2\\miodb.db3")
        self.assertEqual(add("C:\\dati\\.nascosto"), "C:\\dati\\.nascosto.db3")
        self.assertEqual(add("/home/u/miodb"), "/home/u/miodb.db3")
        self.assertEqual(add("C:\\dati\\"), "C:\\dati\\")


if __name__ == "__main__":
    unittest.main()
