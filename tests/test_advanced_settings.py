# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest

import support

from sdbc_pysqlite import advanced_settings as adv
from sdbc_pysqlite import settings_form as form
from sdbc_pysqlite import settings_model as model


class PlanTests(unittest.TestCase):
    def test_tutto_a_posto(self):
        different, missing = adv.plan(dict(adv.FIXED_VALUES))
        self.assertEqual((different, missing), ([], []))

    def test_valore_diverso(self):
        current = dict(adv.FIXED_VALUES)
        current["BooleanComparisonMode"] = 2
        different, missing = adv.plan(current)
        self.assertEqual(different, [("BooleanComparisonMode", 2, 1)])
        self.assertEqual(missing, [])

    def test_voce_assente(self):
        current = dict(adv.FIXED_VALUES)
        del current["UseCatalog"]
        self.assertEqual(adv.plan(current), ([], ["UseCatalog"]))

    def test_booleano_e_numero_sono_diversi(self):
        current = dict(adv.FIXED_VALUES)
        current["TableTypeFilterMode"] = True
        self.assertEqual(adv.plan(current)[0], [("TableTypeFilterMode", True, 3)])
        current = dict(adv.FIXED_VALUES)
        current["IsAutoRetrievingEnabled"] = 1
        self.assertEqual(adv.plan(current)[0], [("IsAutoRetrievingEnabled", 1, True)])

    def test_voci_mostrate_mai_toccate(self):
        for name in adv.SHOWN:
            self.assertNotIn(name, adv.FIXED_VALUES)


class FakeBag:

    def __init__(self, values, writable=True):
        self.values = dict(values)
        self.writable = writable

    def getPropertyValue(self, name):
        if name not in self.values:
            raise KeyError(name)
        return self.values[name]

    def removeProperty(self, name):
        raise RuntimeError("NotRemoveableException")

    def setPropertyValue(self, name, value):
        if not self.writable:
            raise RuntimeError("cannot set")
        self.values[name] = value


class ResetTests(unittest.TestCase):
    def _old(self):
        values = dict(adv.FIXED_VALUES)
        values["BooleanComparisonMode"] = 2
        values["UseCatalog"] = True
        return values

    def test_riscrive_le_voci_diverse(self):
        bag = FakeBag(self._old())
        counts = adv.reset(bag)
        self.assertEqual(counts, {"written": 2, "same": len(adv.FIXED_VALUES) - 2, "failed": 0})
        self.assertEqual(bag.values["BooleanComparisonMode"], 1)
        self.assertIs(bag.values["UseCatalog"], False)

    def test_non_tenta_di_cancellare(self):
        bag = FakeBag(self._old())
        bag.removeProperty = lambda name: self.fail("non si deve cancellare")
        adv.reset(bag)

    def test_voce_assente_si_aggiunge(self):
        values = dict(adv.FIXED_VALUES)
        del values["UseCatalog"]
        bag = FakeBag(values)
        self.assertEqual(adv.reset(bag)["written"], 1)
        self.assertIs(bag.values["UseCatalog"], False)

    def test_fallimento(self):
        counts = adv.reset(FakeBag(self._old(), writable=False))
        self.assertEqual((counts["written"], counts["failed"]), (0, 2))

    def test_nessuna_modifica_se_tutto_a_posto(self):
        counts = adv.reset(FakeBag(adv.FIXED_VALUES))
        self.assertEqual(counts, {"written": 0, "same": len(adv.FIXED_VALUES), "failed": 0})

    def test_traccia(self):
        lines = []
        adv.reset(FakeBag(self._old()), lines.append)
        self.assertTrue(any("BooleanComparisonMode: written 1 (was 2)" in line for line in lines))


class ButtonLayoutTests(unittest.TestCase):
    def _names(self, mode, language):
        lay = form.layout(mode, language, {}, "", set())
        return [e.name for page in lay.pages for e in page.elements], lay

    def test_pulsante_nella_scheda_sistema_del_documento(self):
        for language in ("it", "en"):
            names, lay = self._names("document", language)
            self.assertIn("btn_reset_advanced", names)
            page = lay.page("system")
            self.assertIn("btn_reset_advanced", [e.name for e in page.elements])
            self.assertLessEqual(page.height, form.CONTENT_HEIGHT)

    def test_pulsante_non_nelle_opzioni(self):
        names, _ = self._names("options", "it")
        self.assertNotIn("btn_reset_advanced", names)

    def test_testi_nelle_due_lingue(self):
        for key in ("btn_reset_advanced", "reset_advanced_hint", "msg_reset_confirm", "msg_reset_nothing"):
            self.assertTrue(model.text(key, "it") and model.text(key, "en"))
        for language in ("it", "en"):
            text = model.text("msg_reset_done", language, changed=2, same=18, extra="")
            self.assertIn("2", text)
            self.assertIn("18", text)
        self.assertEqual(model.text("btn_reset_advanced", "it"), "Reimposta le opzioni avanzate del documento")


if __name__ == "__main__":
    unittest.main()
