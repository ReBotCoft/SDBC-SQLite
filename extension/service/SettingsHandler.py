# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import traceback

import uno
import unohelper

from com.sun.star.beans import PropertyValue
from com.sun.star.frame import FeatureStateEvent
from com.sun.star.frame import XDispatch
from com.sun.star.frame import XDispatchProvider
from com.sun.star.lang import XInitialization
from com.sun.star.lang import XServiceInfo

from sdbc_pysqlite import address
from sdbc_pysqlite import advanced_settings
from sdbc_pysqlite import configuration
from sdbc_pysqlite import document_settings
from sdbc_pysqlite import logger
from sdbc_pysqlite import parameters
from sdbc_pysqlite import settings_dialogs
from sdbc_pysqlite import settings_model as model
from sdbc_pysqlite import settings_ui
from sdbc_pysqlite.errors import DriverError

_LOCATION = "settings_ui.SettingsHandler"


class SettingsHandler(unohelper.Base, XServiceInfo, XInitialization, XDispatchProvider, XDispatch):

    def __init__(self, ctx):
        self._ctx = ctx
        self._frame = None
        self._language = "en"
        logger.configure(ctx)

    def getImplementationName(self):
        return settings_ui.HANDLER_IMPLEMENTATION

    def supportsService(self, name):
        return name in settings_ui.HANDLER_SERVICES

    def getSupportedServiceNames(self):
        return settings_ui.HANDLER_SERVICES

    def initialize(self, arguments):
        if arguments:
            self._frame = arguments[0]

    def queryDispatch(self, url, target_frame, search_flags):
        if url.Protocol == settings_ui.PROTOCOL:
            return self
        return None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(item.FeatureURL, item.FrameName, item.SearchFlags) for item in requests)

    def addStatusListener(self, listener, url):
        event = FeatureStateEvent()
        event.FeatureURL = url
        event.Source = self
        event.IsEnabled = self._document_source() is not None
        event.Requery = False
        event.State = None
        listener.statusChanged(event)

    def removeStatusListener(self, listener, url):
        pass

    def dispatch(self, url, arguments):
        try:
            self._language = configuration.read_settings(self._ctx).language
            self._run(self._language)
        except Exception:
            logger.error(_LOCATION, traceback.format_exc())
            self._message(model.text("msg_save_failed", self._language))

    def _document_source(self):
        try:
            controller = self._frame.getController() if self._frame is not None else None
            document = controller.getModel() if controller is not None else None
            source = getattr(document, "DataSource", None) if document is not None else None
            if source is not None and settings_ui.is_our_address(source.URL):
                return source
        except Exception:
            logger.trace(_LOCATION, "document lookup failed: " + traceback.format_exc())
        return None

    def _model(self):
        return self._frame.getController().getModel()

    def _address_parameters(self, url):
        try:
            split = address.split_address(url, unohelper.fileUrlToSystemPath)
            return set(address.parse_parameters(split.options, url))
        except DriverError:
            return set()

    def _run(self, language):
        source = self._document_source()
        if source is None:
            self._message(model.text("msg_no_document", language))
            return
        url = source.URL
        settings = configuration.read_settings(self._ctx)
        pairs = [(item.Name, item.Value) for item in source.Info]
        current = {}
        for name, raw in document_settings.read(pairs).items():
            try:
                current[name] = parameters.convert_setting(name, raw)
            except parameters.InvalidValue:
                logger.warning(_LOCATION, "invalid document setting ignored in the window: %s = %r" % (name, raw))
        overridden = self._address_parameters(url)
        logger.info(_LOCATION, "dialog opened: address=<%s> document settings=%s" % (url, current))

        chosen = settings_dialogs.run_document_dialog(
            self._ctx, language, settings.all_values(), current, url, overridden,
            reset_advanced=lambda: self._reset_advanced(source, language))
        if chosen is None:
            logger.info(_LOCATION, "dialog cancelled")
            return
        new_address = chosen.pop("__address__", url)
        new_pairs = document_settings.merge(pairs, chosen)
        settings_changed = document_settings.changed(pairs, new_pairs)
        address_changed = new_address != url.strip()
        if not settings_changed and not address_changed:
            self._message(model.text("msg_no_change", language))
            return
        if address_changed:
            source.setPropertyValue("URL", new_address)
            logger.info(_LOCATION, "database address changed: <%s> -> <%s>" % (url, new_address))
        if settings_changed:
            values = []
            for name, value in new_pairs:
                item = PropertyValue()
                item.Name = name
                item.Value = value
                values.append(item)
            source.setPropertyValue("Info", uno.Any("[]com.sun.star.beans.PropertyValue", tuple(values)))
            logger.info(_LOCATION, "document settings stored: %s" % document_settings.read(new_pairs))
        self._model().setModified(True)
        self._message(model.text("msg_document_saved", language))

    def _reset_advanced(self, source, language):
        try:
            bag = source.Settings
        except Exception:
            logger.error(_LOCATION, "reset advanced: no Settings on the data source: " + traceback.format_exc())
            return model.text("msg_save_failed", language)
        counts = advanced_settings.reset(bag, lambda text: logger.info(_LOCATION, "reset advanced: " + text))
        logger.info(_LOCATION, "reset advanced: %s" % counts)
        changed = counts["written"]
        if changed:
            self._model().setModified(True)
        if not changed and not counts["failed"]:
            return model.text("msg_reset_nothing", language)
        extra = model.text("msg_reset_failed_part", language, count=counts["failed"]) if counts["failed"] else ""
        return model.text("msg_reset_done", language, changed=changed, same=counts["same"], extra=extra)

    def _message(self, text):
        try:
            parent = self._frame.getContainerWindow() if self._frame is not None else None
            settings_dialogs.show_message(self._ctx, parent, model.text("msg_title", self._language), text)
        except Exception:
            logger.error(_LOCATION, traceback.format_exc())


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(SettingsHandler, settings_ui.HANDLER_IMPLEMENTATION,
                                         settings_ui.HANDLER_SERVICES)
