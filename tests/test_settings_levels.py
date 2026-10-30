# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unittest

import support

from sdbc_pysqlite import database
from sdbc_pysqlite import document_settings as ds
from sdbc_pysqlite import errors
from sdbc_pysqlite import parameters
from sdbc_pysqlite import settings_form as form
from sdbc_pysqlite import settings_model as model
from sdbc_pysqlite.errors import DriverError


class DocumentSettingsTests(unittest.TestCase):
    def test_read_keeps_only_known_parameters(self):
        self.assertEqual(ds.read([("Type", "x"), ("ReadOnly", "true"), ("Foo", "1")]), {"ReadOnly": "true"})

    def test_to_text(self):
        self.assertEqual((ds.to_text(True), ds.to_text(False), ds.to_text(9), ds.to_text("wal")),
                         ("true", "false", "9", "wal"))

    def test_merge_sets_removes_and_keeps_unknown(self):
        pairs = [("Type", "x"), ("ReadOnly", "true"), ("LockTimeoutSeconds", "3")]
        merged = ds.merge(pairs, {"ReadOnly": None, "LockTimeoutSeconds": 9, "ForeignKeys": True})
        self.assertEqual(merged, [("Type", "x"), ("LockTimeoutSeconds", "9"), ("ForeignKeys", "true")])
        self.assertTrue(ds.changed(pairs, merged))
        self.assertFalse(ds.changed(pairs, list(pairs)))


class ResolveLevelsTests(unittest.TestCase):
    def settings(self, **over):
        values = dict(parameters.DEFAULTS)
        values.update(over)
        return values

    def resolve(self, address=None, settings=None, document=None):
        return database.resolve_options(address or {}, settings or self.settings(), document)

    def test_row_id_as_key_default_false(self):
        self.assertFalse(self.resolve().row_id_as_key)

    def test_priority_address_document_extension(self):
        settings = self.settings(LockTimeoutSeconds=1)
        self.assertEqual(self.resolve(settings=settings).lock_timeout_seconds, 1)
        self.assertEqual(self.resolve(settings=settings, document={"LockTimeoutSeconds": "2"})
                         .lock_timeout_seconds, 2)
        self.assertEqual(self.resolve({"LockTimeoutSeconds": 3}, settings, {"LockTimeoutSeconds": "2"})
                         .lock_timeout_seconds, 3)

    def test_document_text_values_are_converted(self):
        options = self.resolve(document={"ReadOnly": "true", "RowIdAsKey": "true"})
        self.assertTrue(options.read_only)
        self.assertTrue(options.row_id_as_key)

    def test_invalid_document_value(self):
        with self.assertRaises(DriverError) as raised:
            self.resolve(document={"LockTimeoutSeconds": "abc"})
        self.assertEqual(raised.exception.code, errors.INVALID_VALUE)

    def test_pair_comes_from_the_highest_layer_naming_one(self):
        settings = self.settings(DateTimeZone="utc", DateTimeFormat="text")
        options = self.resolve(settings=settings, document={"DateTimeFormat": "text"})
        self.assertEqual(options.date_time_zone, parameters.DEFAULTS["DateTimeZone"])


class ModelTests(unittest.TestCase):
    def field(self, name):
        return next(f for f in model.FIELDS if f.name == name)

    def test_field_counts(self):
        self.assertEqual(len(model.fields_for("document")), 17)
        self.assertEqual(len(model.fields_for("options")), 20)

    def test_row_id_as_key_is_present_but_disabled(self):
        self.assertFalse(self.field("RowIdAsKey").enabled)

    def test_driver_defaults_cover_every_field(self):
        defaults = model.driver_defaults()
        for f in model.FIELDS:
            self.assertIn(f.name, defaults)
        self.assertEqual(defaults["LogRetentionDays"], 14)
        self.assertFalse(defaults["Trace"])

    def test_parse_number(self):
        f = self.field("LockTimeoutSeconds")
        self.assertEqual(model.parse_number(f, " 7 "), 7)
        for bad in ("", "-1", "1.5", "a", "1 2"):
            with self.assertRaises(ValueError):
                model.parse_number(f, bad)

    def test_check_pair(self):
        self.assertTrue(model.check_pair({}))
        self.assertTrue(model.check_pair({"DateTimeZone": None, "DateTimeFormat": None}))


class FormLayoutTests(unittest.TestCase):
    def test_every_page_fits(self):
        for mode in ("document", "options"):
            lay = form.layout(mode, "it", {}, "sdbc:external:pysqlite:C:\\a.db" if mode == "document" else None,
                              {"ReadOnly"})
            self.assertTrue(lay.pages)
            for page in lay.pages:
                self.assertLessEqual(page.height, form.CONTENT_HEIGHT, page.title)

    def test_every_field_has_one_element(self):
        for mode in ("document", "options"):
            lay = form.layout(mode, "en", {})
            names = [e.field.name for page in lay.pages for e in page.elements if e.field is not None]
            self.assertEqual(sorted(names), sorted(f.name for f in model.fields_for(mode)))

    def test_page_counts_and_navigation(self):
        for mode, expected in (("document", 7), ("options", 8)):
            for language in ("it", "en"):
                lay = form.layout(mode, language, {}, "x" if mode == "document" else None)
                self.assertEqual(len(lay.pages), expected)
                navs = [e for e in lay.header if e.kind == "nav"]
                self.assertEqual(len(navs), 1 if mode == "document" else 0)
                if navs:
                    self.assertEqual(len(navs[0].items), expected)
                    for title in navs[0].items:
                        self.assertLessEqual(len(title) * form.CHAR_NORMAL, form.NAV_WIDTH - 6, title)

    def test_options_page_height(self):
        self.assertEqual(form.OPTIONS_PAGE_HEIGHT, form.CONTENT_HEIGHT + form.OPTIONS_BUTTONS + 2 * form.MARGIN)

    def test_every_page_has_title_separators_and_notes(self):
        for mode in ("document", "options"):
            lay = form.layout(mode, "it", {}, "x" if mode == "document" else None)
            for page in lay.pages:
                kinds = [e.kind for e in page.elements]
                self.assertEqual(kinds[0], "title")
                self.assertEqual(kinds.count("line"), len(page.fields))
                self.assertEqual(sum(1 for e in page.elements if e.kind == "note" and e.name.startswith("note_")
                                     and not e.name.startswith("note_group")), len(page.fields))

    def test_choice_fields_have_a_description_for_every_value(self):
        for field in model.FIELDS:
            if field.kind == "choice":
                self.assertEqual(set(field.choice_notes), set(field.choices), field.name)
                for value in field.choices:
                    for language in ("it", "en"):
                        self.assertTrue(form.description(field, value, language))
                lay = form.layout("options", "it")
                self.assertTrue(any(e.name == "desc_" + field.name for p in lay.pages for e in p.elements))

    def test_element_names_are_unique_in_the_document_window(self):
        lay = form.layout("document", "it", {}, "x", {"ReadOnly"})
        names = [e.name for e in lay.header] + [e.name for page in lay.pages for e in page.elements]
        self.assertEqual(len(names), len(set(names)))

    def test_document_booleans_are_dropdowns_with_the_extension_value(self):
        lay = form.layout("document", "it", {"ForeignKeys": True, "ReadOnly": False})
        found = 0
        for page in lay.pages:
            for e in page.elements:
                if e.field is not None and e.field.kind == "bool":
                    found += 1
                    self.assertEqual(e.kind, "list", e.name)
                    self.assertEqual(len(e.items), 3)
                    if e.field.name == "ForeignKeys":
                        self.assertIn("sì", e.items[0])
                    if e.field.name == "ReadOnly":
                        self.assertIn("no", e.items[0])
        self.assertGreater(found, 0)
        self.assertFalse(any(e.name == "note_legend" for e in lay.header))
        lay = form.layout("options", "it")
        self.assertTrue(all(e.kind == "check" for p in lay.pages for e in p.elements
                            if e.field is not None and e.field.kind == "bool"))

    def test_options_pages_are_narrower_than_the_document_pages(self):
        self.assertLessEqual(form.PAGE_WIDTH, 300)
        self.assertLess(form.OPTIONS_CONTENT_WIDTH, form.CONTENT_WIDTH)
        for mode in ("document", "options"):
            lay = form.layout(mode, "it", {}, "x" if mode == "document" else None)
            limit = form.CONTENT_WIDTH if mode == "document" else form.OPTIONS_CONTENT_WIDTH
            for page in lay.pages:
                for e in page.elements:
                    self.assertLessEqual(e.x + e.width, limit, e.name)
                self.assertLessEqual(page.height, form.CONTENT_HEIGHT, page.key)

    def test_access_page_has_the_editable_address_line(self):
        lay = form.layout("document", "it", {}, "x")
        names = [e.name for e in lay.page("access").elements]
        for name in ("edit_address", "btn_help_db", "btn_open_db", "btn_new_db", "hint_address"):
            self.assertIn(name, names)
        self.assertLess(names.index("edit_address"), names.index("ctl_CreateIfMissing"))
        elements = {e.name: e for e in lay.page("access").elements}
        field = elements["edit_address"]
        self.assertEqual(field.width, form.CONTENT_WIDTH)
        opening, new = elements["btn_open_db"], elements["btn_new_db"]
        self.assertGreater(opening.y, field.y)
        self.assertEqual(opening.y, new.y)
        self.assertLess(opening.x, new.x)
        self.assertEqual(new.x + new.width, form.CONTENT_WIDTH)
        hint = elements["hint_address"]
        helper = elements["btn_help_db"]
        self.assertEqual(helper.y, opening.y)
        self.assertLess(helper.x + helper.width, opening.x)
        self.assertLess(helper.width, opening.width)
        self.assertGreaterEqual(hint.y, opening.y + opening.height)
        self.assertEqual((hint.x, hint.width), (0, form.CONTENT_WIDTH))
        options = form.layout("options", "it")
        self.assertFalse(any(e.name == "edit_address" for p in options.pages for e in p.elements))

    def test_address_is_a_bold_label(self):
        lay = form.layout("document", "it", {}, "sdbc:external:pysqlite:C:\\a.db")
        address = [e for e in lay.header if e.name == "lbl_address"][0]
        self.assertEqual(address.kind, "address")
        self.assertFalse(any(e.kind == "readonly" for e in lay.header))

    def test_browse_only_in_the_log_page_of_options(self):
        lay = form.layout("options", "it")
        for page in lay.pages:
            has = any(e.kind == "browse" for e in page.elements)
            self.assertEqual(has, page.key == "log")

    def test_log_group_only_in_options(self):
        self.assertIn("log", [g.key for g in model.groups_for("options")])
        self.assertNotIn("log", [g.key for g in model.groups_for("document")])


class NumericFieldTests(unittest.TestCase):

    def _int_fields(self):
        return [f for f in model.fields_for("options") if f.kind == "int"]

    def test_every_number_has_limits(self):
        fields = self._int_fields()
        self.assertEqual(len(fields), 4)
        for field in fields:
            self.assertIsNotNone(field.maximum, field.name)
            self.assertGreater(field.maximum, field.minimum)

    def test_agreed_limits(self):
        limits = {f.name: (f.minimum, f.maximum) for f in self._int_fields()}
        self.assertEqual(limits, {"LogRetentionDays": (1, 3650), "LockTimeoutSeconds": (0, 86400),
                                  "FullLoadLimit": (1, 10000000), "WindowSize": (1, 100000)})

    def test_parse_number_respects_the_maximum(self):
        field = next(f for f in self._int_fields() if f.name == "WindowSize")
        self.assertEqual(model.parse_number(field, "100000"), 100000)
        for bad in ("100001", "0", "-1", "", "1e3", "٣"):
            with self.assertRaises(ValueError, msg=bad):
                model.parse_number(field, bad)
        self.assertIn("100000", model.error_text(field, "it"))
        self.assertIn("100000", model.error_text(field, "en"))

    def test_clamp_number(self):
        field = next(f for f in self._int_fields() if f.name == "LogRetentionDays")
        self.assertEqual(form.clamp_number(field, ""), "")
        self.assertEqual(form.clamp_number(field, "0"), "1")
        self.assertEqual(form.clamp_number(field, "7"), "7")
        self.assertEqual(form.clamp_number(field, "99999"), "3650")
        timeout = next(f for f in self._int_fields() if f.name == "LockTimeoutSeconds")
        self.assertEqual(form.clamp_number(timeout, "0"), "0")

    def test_each_number_has_its_spin_buttons_next_to_the_box(self):
        for mode in ("document", "options"):
            lay = form.layout(mode, "it", {}, "x" if mode == "document" else None)
            for page in lay.pages:
                elements = {e.name: e for e in page.elements}
                for field in page.fields:
                    if field.kind != "int":
                        continue
                    box, spin = elements["ctl_" + field.name], elements["spin_" + field.name]
                    self.assertEqual(spin.kind, "spin")
                    self.assertEqual(spin.y, box.y)
                    self.assertGreaterEqual(spin.x, box.x + box.width)


class HighlightedLinesTests(unittest.TestCase):

    def test_description_is_split_in_value_and_text(self):
        field = next(f for f in model.FIELDS if f.name == "JournalMode")
        name, text = form.description_parts(field, "wal", "it")
        self.assertEqual(name, "wal")
        self.assertFalse(text.startswith("wal"))
        self.assertEqual(form.description_parts(field, None, "it"), ("", ""))

    def test_choice_pages_have_a_bold_value_column(self):
        lay = form.layout("document", "it", {}, "x")
        elements = {e.name: e for e in lay.page("integrity").elements}
        name, text = elements["descname_JournalMode"], elements["desc_JournalMode"]
        self.assertEqual(name.kind, "descname")
        self.assertEqual(name.y, text.y)
        self.assertLessEqual(name.x + name.width, text.x)

    def test_empty_means_default_is_its_own_line_with_a_bold_value(self):
        extension = {"FullLoadLimit": 50000, "WindowSize": 1000}
        lay = form.layout("document", "it", extension, "x")
        elements = {e.name: e for e in lay.page("results").elements}
        label, value = elements["dflt_WindowSize"], elements["dfltv_WindowSize"]
        self.assertEqual(value.kind, "notevalue")
        self.assertEqual(value.text, "1000")
        self.assertEqual(label.y, value.y)
        self.assertGreaterEqual(value.x, label.x + label.width)
        self.assertNotIn("Vuoto", elements["note_WindowSize"].text)
        options = form.layout("options", "it")
        self.assertFalse(any(e.name.startswith("dflt") for p in options.pages for e in p.elements))


class AddressHelpTests(unittest.TestCase):

    def test_every_parameter_is_explained_in_both_languages(self):
        from sdbc_pysqlite import parameters
        for language in model.LANGUAGES:
            help_text = model.address_help(language)
            for name in parameters.PARAMETER_NAMES:
                self.assertIn(name + " — ", help_text, (language, name))
            for value in parameters.JOURNAL_MODES + parameters.TRANSACTION_MODES:
                self.assertIn(value + ": ", help_text, (language, value))
            self.assertIn("sdbc:external:pysqlite:", help_text)
            self.assertIn("&", help_text)

    def test_html_page_has_names_and_values_in_bold(self):
        from sdbc_pysqlite import parameters
        for language in model.LANGUAGES:
            page = model.address_help_html(language)
            self.assertTrue(page.startswith("<!DOCTYPE html>"))
            self.assertIn('<meta charset="utf-8">', page)
            for name in parameters.PARAMETER_NAMES:
                self.assertIn("<code>%s</code>" % name, page, (language, name))
            for value in parameters.JOURNAL_MODES + parameters.TRANSACTION_MODES:
                self.assertIn("<b>%s</b>" % value, page, (language, value))
            self.assertIn("&amp;", page)

    def test_defaults_are_shown(self):
        help_text = model.address_help("it")
        self.assertIn("Predefinito del driver: 5.", help_text)
        self.assertIn("Predefinito del driver: delete.", help_text)


class WriteAndResetTests(unittest.TestCase):

    class _Update:
        def __init__(self):
            self.values = {"LogRetentionDays": 7, "ForeignKeys": True}
            self.direct = {"LogRetentionDays", "ForeignKeys"}
            self.committed = False
            self.states = self

        def setPropertyValue(self, name, value):
            self.values[name] = getattr(value, "value", value)
            self.direct.add(name)

        def queryInterface(self, type_):
            return self.states

        def getPropertyState(self, name):
            return "DIRECT_VALUE" if name in self.direct else "DEFAULT_VALUE"

        def setPropertyToDefault(self, name):
            self.direct.discard(name)
            self.values.pop(name, None)

        def commitChanges(self):
            self.committed = True

    def _context(self, update):
        ctx = support.FakeContext({})
        ctx.createInstanceWithArguments = lambda name, arguments: update
        return ctx

    def test_reset_removes_only_direct_values(self):
        from sdbc_pysqlite import configuration
        update = self._Update()
        configuration.write_settings(self._context(update), {"LockTimeoutSeconds": 9},
                                     ["LogRetentionDays", "ReadOnly", "NoSuchName"])
        self.assertEqual(update.values.get("LockTimeoutSeconds"), 9)
        self.assertNotIn("LogRetentionDays", update.values)
        self.assertIn("ForeignKeys", update.values)
        self.assertNotIn("ReadOnly", update.direct)
        self.assertTrue(update.committed)

    def test_reset_without_property_state_writes_the_driver_default(self):
        from sdbc_pysqlite import configuration
        update = self._Update()
        update.states = None
        configuration.write_settings(self._context(update), {}, ["LogRetentionDays", "Trace"])
        self.assertEqual(update.values["LogRetentionDays"], 14)
        self.assertIs(update.values["Trace"], False)
        self.assertTrue(update.committed)


if __name__ == "__main__":
    unittest.main()


class LogFolderTests(unittest.TestCase):

    class Manager:
        def __init__(self, services):
            self.services = services

        def createInstanceWithContext(self, name, ctx):
            if name not in self.services:
                raise RuntimeError(name)
            return self.services[name]

    class Context:
        def __init__(self, services):
            self.ServiceManager = LogFolderTests.Manager(services)

    class Substitution:
        def __init__(self, url):
            self.url = url

        def getSubstituteVariableValue(self, name):
            assert name == "$(user)"
            return self.url

    def test_default_folder_is_in_the_user_profile(self):
        import os
        import tempfile
        from sdbc_pysqlite import logger
        with tempfile.TemporaryDirectory() as profile:
            ctx = self.Context({"com.sun.star.util.PathSubstitution": self.Substitution("file://" + profile)})
            folder = logger.default_folder(ctx)
            self.assertEqual(folder, os.path.join(profile, "sdbc-pysqlite"))
            self.assertTrue(os.path.isdir(folder))

    def test_default_folder_falls_back_to_temp(self):
        import tempfile
        from sdbc_pysqlite import logger
        self.assertEqual(logger.default_folder(self.Context({})), tempfile.gettempdir())

    def test_open_log_missing_and_present(self):
        import os
        import tempfile
        from sdbc_pysqlite import LOG_FILE_NAME, logger, settings_dialogs

        class Shell:
            opened = []

            def execute(self, url, arguments, flags):
                self.opened.append(url)

        shown = []
        original_show = settings_dialogs.show_message
        original_folder = logger.log_folder
        settings_dialogs.show_message = lambda ctx, parent, title, text, error=False: shown.append((text, error))
        try:
            with tempfile.TemporaryDirectory() as folder:
                logger.log_folder = lambda: folder
                ctx = self.Context({"com.sun.star.system.SystemShellExecute": Shell()})
                settings_dialogs.open_log(ctx, None, "it")
                self.assertEqual(len(shown), 1)
                self.assertIn(folder, shown[0][0])
                self.assertEqual(Shell.opened, [])
                open(os.path.join(folder, LOG_FILE_NAME), "w").close()
                settings_dialogs.open_log(ctx, None, "it")
                self.assertEqual(len(shown), 1)
                self.assertEqual(len(Shell.opened), 1)
        finally:
            settings_dialogs.show_message = original_show
            logger.log_folder = original_folder
