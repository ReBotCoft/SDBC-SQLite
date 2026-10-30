# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support

support.install_uno_stubs()

ROOT = Path(__file__).resolve().parents[1]
TOOLS = str(ROOT / "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import build_oxt
import manuals_html

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import manuals
from sdbc_pysqlite import settings_dialogs as dialogs
from sdbc_pysqlite import settings_form as form

XLINK = "{http://www.w3.org/1999/xlink}href"


class ConverterTests(unittest.TestCase):
    def body(self, text):
        return manuals_html.to_html_body(text)[0]

    def test_headings_paragraphs_and_title(self):
        body, title = manuals_html.to_html_body("# Titolo *uno*\n\nPrima riga\nseconda riga.\n\n## Sezione\n")
        self.assertEqual(title, "Titolo uno")
        self.assertIn("<h1>Titolo <em>uno</em></h1>", body)
        self.assertIn("<p>Prima riga seconda riga.</p>", body)
        self.assertIn("<h2>Sezione</h2>", body)

    def test_bold_can_contain_code(self):
        body = self.body("Il tipo **`LO_DECIMAL`: nel file** resta intero.")
        self.assertIn("<strong><code>LO_DECIMAL</code>: nel file</strong>", body)
        self.assertNotIn("**", body)

    def test_html_characters_are_protected(self):
        body = self.body("Un valore <valore attuale> & `a < b`.")
        self.assertIn("&lt;valore attuale&gt; &amp;", body)
        self.assertIn("<code>a &lt; b</code>", body)
        self.assertNotIn("<valore", body)

    def test_table(self):
        body = self.body("| A | B |\n|---|---|\n| `x|y` | **si** |\n| 1 | 2 |\n")
        self.assertEqual(body.count("<tr>"), 3)
        self.assertIn("<th>A</th>", body)
        self.assertIn("<td><code>x|y</code></td><td><strong>si</strong></td>", body)

    def test_code_block_is_not_interpreted(self):
        body = self.body("```sql\nSELECT * FROM t WHERE a < 2 AND **b**;\n```\n")
        self.assertIn('<pre><code class="language-sql">SELECT * FROM t WHERE a &lt; 2 AND **b**;</code></pre>', body)

    def test_lists(self):
        body = self.body("- uno\n- due\n  continua\n\n1. primo\n2. secondo\n")
        self.assertIn("<ul>\n<li>uno</li>\n<li>due continua</li>\n</ul>", body)
        self.assertIn("<ol>\n<li>primo</li>\n<li>secondo</li>\n</ol>", body)

    def test_rule_and_asterisk_in_text(self):
        body = self.body("a * b e c * d\n\n---\n\nfine")
        self.assertIn("<p>a * b e c * d</p>", body)
        self.assertIn("<hr>", body)

    def test_manual_files_and_names(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("2026-10-30 - Manual - PySQLite User Manual.md", "2026-10-28 - Manual - Exact Decimals in SQL Commands.md",
                         "CHANGELOG.md", "README.docs.md", "2026-10-30 - Project - Altro.md"):
                (Path(folder) / name).write_text("# T\n", encoding="utf-8")
            found = [name for _, name in manuals_html.manual_files(folder)]
        self.assertEqual(found, ["exact-decimals-in-sql-commands.html", "pysqlite-user-manual.html"])

    def test_the_real_manuals_convert_completely(self):
        pages = dict(manuals_html.build_pages(ROOT / "docs"))
        self.assertEqual(sorted(pages), ["exact-decimals-in-sql-commands.html", "pysqlite-user-manual.html"])
        for page in pages.values():
            self.assertTrue(page.startswith("<!DOCTYPE html>"))
            self.assertNotIn("**", page)
            self.assertNotIn("`", page)
            self.assertNotIn("\n|", page)
        for path, name in manuals_html.manual_files(ROOT / "docs"):
            lines = path.read_text(encoding="utf-8").split("\n")
            fences = False
            headings = 0
            for line in lines:
                if line.startswith("```"):
                    fences = not fences
                elif not fences and line.startswith("#"):
                    headings += 1
            self.assertEqual(sum(pages[name].count("<h%d>" % level) for level in range(1, 7)), headings, name)


class ManualPagesTests(unittest.TestCase):
    def test_pages_are_found_in_name_order(self):
        with tempfile.TemporaryDirectory() as package:
            folder = Path(package) / manuals.MANUALS_FOLDER
            folder.mkdir()
            for name in ("b.html", "a.html", "nota.txt"):
                (folder / name).write_text("x", encoding="utf-8")
            pages = manuals.manual_pages(package)
        self.assertEqual([os.path.basename(page) for page in pages], ["a.html", "b.html"])

    def test_missing_folder_gives_an_empty_list(self):
        with tempfile.TemporaryDirectory() as package:
            self.assertEqual(manuals.manual_pages(package), [])


class FakeShell:
    def __init__(self, fail=False):
        self.opened = []
        self.fail = fail

    def execute(self, url, parameters, flags):
        if self.fail:
            raise RuntimeError("nessun browser")
        self.opened.append(url)


class FakeToolkit:
    def __init__(self, boxes):
        self.boxes = boxes

    def createMessageBox(self, parent, kind, buttons, title, text):
        self.boxes.append(text)
        return SimpleNamespace(execute=lambda: 1, dispose=lambda: None)


def make_context(location, shell, boxes):
    provider = SimpleNamespace(getPackageLocation=lambda identifier: location if identifier == IDENTIFIER else "")
    manager = SimpleNamespace(createInstanceWithContext=lambda name, ctx: (
        shell if name == "com.sun.star.system.SystemShellExecute" else FakeToolkit(boxes)))
    values = {"/singletons/com.sun.star.deployment.PackageInformationProvider": provider}
    return SimpleNamespace(ServiceManager=manager, getValueByName=lambda name: values[name])


class OpenManualsTests(unittest.TestCase):
    def package(self, names):
        package = tempfile.TemporaryDirectory()
        self.addCleanup(package.cleanup)
        folder = Path(package.name) / manuals.MANUALS_FOLDER
        folder.mkdir()
        for name in names:
            (folder / name).write_text("x", encoding="utf-8")
        return package.name

    def test_every_page_is_opened(self):
        package = self.package(["decimali.html", "manuale.html"])
        shell, boxes = FakeShell(), []
        dialogs.open_manuals(make_context("file://" + package, shell, boxes), None, "en")
        self.assertEqual([url.replace("\\", "/").rsplit("/", 1)[1] for url in shell.opened], ["decimali.html", "manuale.html"])
        self.assertEqual(boxes, [])

    def test_missing_manuals_are_reported(self):
        package = self.package([])
        shell, boxes = FakeShell(), []
        dialogs.open_manuals(make_context("file://" + package, shell, boxes), None, "en")
        self.assertEqual(shell.opened, [])
        self.assertEqual(len(boxes), 1)
        self.assertIn("not in the extension", boxes[0])

    def test_a_browser_that_does_not_open_is_reported(self):
        package = self.package(["manuale.html"])
        shell, boxes = FakeShell(fail=True), []
        dialogs.open_manuals(make_context("file://" + package, shell, boxes), None, "it")
        self.assertEqual(len(boxes), 1)
        self.assertIn("Non riesco ad aprire i manuali", boxes[0])


class FakeDialogModel:
    def __init__(self):
        self.controls = {}

    def createInstance(self, name):
        return SimpleNamespace()

    def insertByName(self, name, control):
        self.controls[name] = control


class ButtonLayoutTests(unittest.TestCase):
    def test_options_log_page_has_four_buttons_that_do_not_overlap(self):
        model = FakeDialogModel()
        dialogs.add_options_buttons(model, SimpleNamespace(language="en"), True)
        row = [model.controls[name] for name in ("btn_driver", "btn_log", "btn_folder", "btn_manuals")]
        for left, right in zip(row, row[1:]):
            self.assertLess(left.PositionX + left.Width, right.PositionX)
        self.assertLessEqual(row[-1].PositionX + row[-1].Width, form.PAGE_WIDTH - form.MARGIN)
        self.assertEqual(row[-1].Label, "?")
        self.assertEqual(row[-1].HelpText, "Open the manuals")
        self.assertEqual({button.PositionY for button in row}, {row[0].PositionY})

    def test_other_options_pages_have_no_manuals_button(self):
        model = FakeDialogModel()
        dialogs.add_options_buttons(model, SimpleNamespace(language="en"), False)
        self.assertEqual(list(model.controls), ["btn_driver"])

    def test_document_window_fits_the_button_between_folder_and_ok(self):
        x = 3 * form.MARGIN + 200
        self.assertGreater(x, 2 * form.MARGIN + 100 + 100)
        self.assertLess(x + form.MANUALS_BUTTON_WIDTH, form.DOC_WIDTH - 2 * 54 - 2 * form.MARGIN)


class UpdateInformationTests(unittest.TestCase):
    def test_description_points_to_the_update_file(self):
        root = ET.parse(ROOT / "extension" / "description.xml").getroot()
        url = build_oxt.read_update_url(root)
        self.assertTrue(url.startswith("https://github.com/ReBotCoft/SDBC-SQLite/releases/latest/download/"))
        self.assertTrue(url.endswith(".update.xml"))

    def test_update_file_matches_the_description(self):
        root = ET.parse(ROOT / "extension" / "description.xml").getroot()
        with tempfile.TemporaryDirectory() as folder:
            with mock.patch.object(build_oxt, "DIST_DIR", Path(folder)):
                path = build_oxt.write_update_file(root)
            update = ET.parse(path).getroot()
        self.assertEqual(path.name, build_oxt.read_update_url(root).rsplit("/", 1)[1])
        values = {element.tag.split("}")[-1]: element for element in update.iter()}
        self.assertEqual(values["identifier"].get("value"), build_oxt.read_value(root, "identifier"))
        self.assertEqual(values["version"].get("value"), build_oxt.read_value(root, "version"))
        self.assertEqual(values["src"].get(XLINK),
                         build_oxt.read_update_url(root).rsplit("/", 1)[0] + "/" + build_oxt.OXT_PATH.name)
        self.assertTrue(update.tag.startswith("{http://openoffice.org/extensions/update/2006}"))


if __name__ == "__main__":
    unittest.main()
