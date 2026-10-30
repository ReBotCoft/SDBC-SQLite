# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft
import os
import unittest
import xml.etree.ElementTree as ET

NS = {"oor": "http://openoffice.org/2001/registry"}
OOR = "{http://openoffice.org/2001/registry}"
XCU = os.path.join(os.path.dirname(__file__), "..", "extension", "Drivers.xcu")


def _section(name):
    root = ET.parse(XCU).getroot()
    for node in root.iter("node"):
        if node.get(OOR + "name") == name:
            out = {}
            for n in node.findall("node"):
                out[n.get(OOR + "name")] = n.find("prop/value").text or ""
            return out
    return None


class DriversXcuTests(unittest.TestCase):
    def test_features_visibili(self):
        self.assertEqual(set(_section("Features")), {
            "UseKeywordAsBeforeAlias", "AppendTableAliasInSelect"})

    def test_features_rimosse(self):
        f = _section("Features")
        for n in ("GeneratedValues", "EscapeDateTime", "RespectDriverResultSetType",
                  "UseDOSLineEnds", "FormsCheckRequiredFields",
                  "BooleanComparisonMode"):
            self.assertNotIn(n, f)

    def test_valori_fissi(self):
        p = _section("Properties")
        self.assertEqual(p["IsAutoRetrievingEnabled"], "true")
        self.assertEqual(p["AutoIncrementCreation"], "AUTO_INCREMENT")
        self.assertEqual(p["EnableSQL92Check"], "false")
        self.assertEqual(p["EnableOuterJoinEscape"], "true")
        self.assertEqual(p["IgnoreDriverPrivileges"], "true")
        self.assertEqual(p["UseCatalogInSelect"], "false")
        self.assertEqual(p["UseSchemaInSelect"], "false")
        self.assertEqual(p["AddIndexAppendix"], "true")
        self.assertEqual(p["RespectDriverResultSetType"], "true")
        self.assertEqual(p["TableTypeFilterMode"], "3")

    def test_valori_iniziali_voci_visibili(self):
        p = _section("Properties")
        self.assertEqual(p["AppendTableAliasName"], "false")
        self.assertEqual(p["GenerateASBeforeCorrelationName"], "false")
        self.assertEqual(p["FormsCheckRequiredFields"], "true")

    def test_a_capo_fisso_spento(self):
        self.assertEqual(_section("Properties")["PreferDosLikeLineEnds"], "false")

    def test_booleancomparisonmode_fisso_sql(self):
        self.assertEqual(_section("Properties")["BooleanComparisonMode"], "1")

    def test_tabella_dei_valori_fissi_uguale_al_driver(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "extension", "service", "pythonpath"))
        from sdbc_pysqlite import advanced_settings as adv
        p = _section("Properties")
        expected = {}
        for name, text in p.items():
            if name in adv.SHOWN:
                continue
            fixed = adv.FIXED_VALUES[name]
            expected[name] = ("true" if fixed else "false") if isinstance(fixed, bool) else str(fixed)
        self.assertEqual(set(adv.FIXED_VALUES), set(p) - set(adv.SHOWN))
        self.assertEqual({n: p[n] for n in adv.FIXED_VALUES}, expected)

    def test_metadata_invariati(self):
        m = _section("MetaData")
        self.assertEqual(m["AutoIncrementCreation"], "AUTO_INCREMENT")
        self.assertEqual(m["FileSystemBased"], "false")


if __name__ == "__main__":
    unittest.main()
