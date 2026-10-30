# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import support

from sdbc_pysqlite import settings_form as form
from sdbc_pysqlite import settings_model as model
from sdbc_pysqlite import settings_ui as ui

_EXTENSION = Path(__file__).resolve().parents[1] / "extension"


class HelpersTests(unittest.TestCase):
    P = "sdbc:external:pysqlite:C:\\dati\\a.db"

    def test_is_our_address(self):
        self.assertTrue(ui.is_our_address(self.P))
        self.assertFalse(ui.is_our_address("sdbc:embedded:hsqldb"))
        self.assertFalse(ui.is_our_address(None))

    def test_password_is_not_shown(self):
        lines = ui.info_lines([("user", "pippo"), ("password", "segreta"), ("x", 1)])
        self.assertEqual(lines, ["user = 'pippo'", "password = ***", "x = 1"])
        self.assertFalse(any("segreta" in line for line in lines))


class RegistrationFilesTests(unittest.TestCase):
    def test_xml_files_parse(self):
        for name in ("Addons.xcu", "ProtocolHandler.xcu", "package.components", "META-INF/manifest.xml",
                     "OptionsDialog.xcu", "Options.xcs", "Options.xcu", "dialogs/OptionsPage_log.xdl"):
            ET.parse(_EXTENSION / name)

    def test_manifest_lists_the_registration_files(self):
        text = (_EXTENSION / "META-INF" / "manifest.xml").read_text(encoding="utf-8")
        for name in ("Addons.xcu", "ProtocolHandler.xcu", "OptionsDialog.xcu"):
            self.assertIn(name, text)

    def test_menu_command_uses_the_handler_protocol(self):
        text = (_EXTENSION / "Addons.xcu").read_text(encoding="utf-8")
        self.assertIn(ui.COMMAND, text)
        self.assertIn('oor:name="OfficeMenuBarMerging"', text)
        self.assertTrue(ui.COMMAND.startswith(ui.PROTOCOL))
        handlers = (_EXTENSION / "ProtocolHandler.xcu").read_text(encoding="utf-8")
        self.assertIn(ui.PROTOCOL + "*", handlers)
        self.assertIn(ui.HANDLER_IMPLEMENTATION, handlers)
        components = (_EXTENSION / "package.components").read_text(encoding="utf-8")
        self.assertIn(ui.HANDLER_IMPLEMENTATION, components)
        self.assertIn(ui.OPTIONS_HANDLER_IMPLEMENTATION, components)

    def test_options_page_registration(self):
        text = (_EXTENSION / "OptionsDialog.xcu").read_text(encoding="utf-8")
        self.assertIn(ui.OPTIONS_HANDLER_IMPLEMENTATION, text)
        for group in model.GROUPS:
            self.assertIn("dialogs/OptionsPage_%s.xdl" % group.key, text)
            self.assertTrue((_EXTENSION / "dialogs" / ("OptionsPage_%s.xdl" % group.key)).exists())
        self.assertEqual(text.count("<value>dev.rebotcoft.sdbc.pysqlite.OptionsHandler</value>"), len(model.GROUPS))
        self.assertTrue((_EXTENSION / "service" / "OptionsHandler.py").exists())

    def test_options_page_sizes_and_markers(self):
        ns = "{http://openoffice.org/2000/dialog}"
        for group in model.GROUPS:
            root = ET.parse(_EXTENSION / "dialogs" / ("OptionsPage_%s.xdl" % group.key)).getroot()
            self.assertEqual(root.get(ns + "width"), str(form.PAGE_WIDTH))
            self.assertEqual(root.get(ns + "height"), str(form.OPTIONS_PAGE_HEIGHT))
            ids = [e.get(ns + "id") for e in root.iter(ns + "text")]
            self.assertIn("cat_" + group.key, ids)
            self.assertIn("lbl_error", ids)

    def test_every_page_fits_the_options_page(self):
        for language in ("it", "en"):
            for page in form.layout("options", language).pages:
                self.assertLessEqual(page.height, form.CONTENT_HEIGHT, (language, page.key))

    def test_row_id_as_key_in_the_schema(self):
        for name in ("Options.xcs", "Options.xcu"):
            self.assertIn("RowIdAsKey", (_EXTENSION / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
