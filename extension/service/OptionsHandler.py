# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import traceback

import unohelper

from com.sun.star.awt import XContainerWindowEventHandler
from com.sun.star.lang import XServiceInfo

from sdbc_pysqlite import configuration
from sdbc_pysqlite import logger
from sdbc_pysqlite import settings_dialogs
from sdbc_pysqlite import settings_form as form
from sdbc_pysqlite import settings_model as model
from sdbc_pysqlite import settings_ui

_LOCATION = "settings_ui.OptionsHandler"
_EVENT_METHOD = "external_event"


class OptionsHandler(unohelper.Base, XServiceInfo, XContainerWindowEventHandler):

    def __init__(self, ctx):
        self._ctx = ctx
        self._layout = None
        self._language = "en"
        self._pages = {}
        logger.configure(ctx)

    def getImplementationName(self):
        return settings_ui.OPTIONS_HANDLER_IMPLEMENTATION

    def supportsService(self, name):
        return name in settings_ui.OPTIONS_HANDLER_SERVICES

    def getSupportedServiceNames(self):
        return settings_ui.OPTIONS_HANDLER_SERVICES

    def getSupportedMethodNames(self):
        return (_EVENT_METHOD, )

    def callHandlerMethod(self, window, event_object, method_name):
        if method_name != _EVENT_METHOD:
            return False
        try:
            if event_object == "initialize":
                self._initialize(window)
            elif event_object == "ok":
                self._ok(window)
            elif event_object == "back":
                self._back(window)
            else:
                return False
        except Exception:
            logger.error(_LOCATION, "%s: %s" % (event_object, traceback.format_exc()))
            if event_object == "initialize":
                self._show_error(window)
            return event_object != "initialize"
        return True

    def _key(self, window):
        dialog_model = window.getModel()
        for group in model.GROUPS:
            if dialog_model.hasByName("cat_" + group.key):
                return group.key
        return None

    def _initialize(self, window):
        key = self._key(window)
        if key is None:
            return
        settings = configuration.read_settings(self._ctx)
        self._language = settings.language
        self._layout = form.layout("options", self._language)
        dialog_model = window.getModel()
        form.build(dialog_model, self._layout, key)
        settings_dialogs.add_options_buttons(dialog_model, self._layout, key == "log")
        listeners = form.connect_controls(window, dialog_model, self._layout, key)
        listeners.append(form.on_click(window, "btn_driver", lambda: self._driver_defaults(window, key)))
        if key == "log":
            listeners.append(form.on_click(window, "btn_log", lambda: self._open_log(window)))
            listeners.append(form.on_click(window, "btn_folder", lambda: self._open_folder(window)))
            listeners.append(form.on_click(window, "btn_manuals", lambda: self._open_manuals(window)))
            listeners.append(form.on_click(window, "btn_browse", lambda: self._browse(window)))
        self._pages[key] = listeners
        form.apply_values(window, self._layout, settings.all_values(), key)
        logger.info(_LOCATION, "options page opened: %s" % key)

    def _driver_defaults(self, window, key):
        enabled = {field.name for field in self._layout.page(key).fields if field.enabled}
        form.apply_values(window, self._layout,
                          {name: value for name, value in model.driver_defaults().items() if name in enabled},
                          key)

    def _peer(self, window):
        try:
            return window.getPeer()
        except Exception:
            return None

    def _open_folder(self, window):
        settings_dialogs.open_log_folder(self._ctx, self._peer(window), self._language)

    def _open_log(self, window):
        settings_dialogs.open_log(self._ctx, self._peer(window), self._language)

    def _open_manuals(self, window):
        settings_dialogs.open_manuals(self._ctx, self._peer(window), self._language)

    def _browse(self, window):
        edit = window.getControl("ctl_LogPath")
        chosen = settings_dialogs.pick_folder(self._ctx, self._peer(window), self._language, edit.getText().strip())
        if chosen:
            edit.setText(chosen)

    def _back(self, window):
        key = self._key(window)
        if self._layout is not None and key in self._pages:
            form.apply_values(window, self._layout, configuration.read_settings(self._ctx).all_values(), key)

    def _ok(self, window):
        key = self._key(window)
        if self._layout is None or key not in self._pages:
            return
        values, errors = form.read_values(window, self._layout, key)
        if errors:
            self._message(window, model.text("msg_options_invalid", self._language, list="\n".join(errors)),
                          error=True)
            return
        saved = configuration.read_settings(self._ctx).all_values()
        defaults = model.driver_defaults()
        resets = [name for name, value in values.items() if value == defaults.get(name)]
        changes = {name: value for name, value in values.items()
                   if saved.get(name) != value and value != defaults.get(name)}
        if not changes and not resets:
            return
        try:
            configuration.write_settings(self._ctx, changes, resets)
        except Exception:
            logger.error(_LOCATION, traceback.format_exc())
            self._message(window, model.text("msg_save_failed", self._language), error=True)
            return
        logger.info(_LOCATION, "extension settings stored (%s): %s; back to default: %s" % (key, changes, resets))

    def _message(self, window, text, error=False):
        parent = self._peer(window)
        try:
            settings_dialogs.show_message(self._ctx, parent, model.text("msg_title", self._language), text, error)
        except Exception:
            logger.error(_LOCATION, traceback.format_exc())

    def _show_error(self, window):
        try:
            window.getModel().getByName("lbl_error").Label = (
                "Errore nella costruzione della pagina (vedi il registro). / "
                "Error building the page (see the log).")
        except Exception:
            pass


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(OptionsHandler, settings_ui.OPTIONS_HANDLER_IMPLEMENTATION,
                                         settings_ui.OPTIONS_HANDLER_SERVICES)
