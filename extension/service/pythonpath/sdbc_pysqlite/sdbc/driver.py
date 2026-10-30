# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import traceback

import unohelper

from com.sun.star.sdbc import XDriver
from com.sun.star.sdbcx import XDataDefinitionSupplier

from sdbc_pysqlite import IMPLEMENTATION_NAME
from sdbc_pysqlite import SERVICE_NAMES
from sdbc_pysqlite import URL_PREFIX
from sdbc_pysqlite import errors
from sdbc_pysqlite import logger
from sdbc_pysqlite import document_settings
from sdbc_pysqlite import locale_names
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import uno_errors
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.common import extension_version
from sdbc_pysqlite.common import version_part
from sdbc_pysqlite.database import old_library_version
from sdbc_pysqlite.database import open_database
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbc.connection import Connection
from sdbc_pysqlite.sdbcx.catalog import Catalog

_LOCATION = "sdbc.driver.Driver.connect"


def accepts_url(url):
    return isinstance(url, str) and url.startswith(URL_PREFIX)


@traced
class Driver(unohelper.Base, ServiceInfoMixin, XDriver, XDataDefinitionSupplier):

    _implementation_name = IMPLEMENTATION_NAME
    _service_names = SERVICE_NAMES
    _old_library_warned = False

    def __init__(self, ctx):
        self._ctx = ctx
        logger.configure(ctx)

    def _fail(self, error, language, code):
        return uno_errors.to_sql_exception(error, self, language, _LOCATION, code)

    def connect(self, url, info):
        if not accepts_url(url):
            return None
        code = logger.new_connection_code()
        settings = logger.configure(self._ctx)
        language = settings.language
        try:
            try:
                logger.check_writable()
            except OSError:
                raise DriverError(errors.LOG_NOT_WRITABLE, cartella=logger.log_folder())
            pairs = [(item.Name, item.Value) for item in (info or ())]
            document = document_settings.read(pairs)
            opened = open_database(url, settings.connection_values(), unohelper.fileUrlToSystemPath, document,
                                   lambda language: locale_names.read_names(self._ctx, language))
        except DriverError as error:
            raise self._fail(error, language, code)
        except Exception as exception:
            logger.error(_LOCATION, traceback.format_exc(), code)
            raise self._fail(
                DriverError(errors.UNEXPECTED, dettaglio="%s: %s" % (type(exception).__name__, exception)),
                language, code)
        logger.trace(_LOCATION, "opened: address=<%s> path=<%s> full_path=<%s> options=%s sqlite=%s" % (
            url, opened.path, opened.full_path, dict(opened.options._asdict()), sqlite.sqlite_version), code)
        warnings = [(warning, _LOCATION) for warning in opened.warnings]
        old_version = old_library_version()
        if old_version:
            old_warning = (DriverError(errors.OLD_LIBRARY, versione=old_version), _LOCATION)
            if opened.options.old_library_warning and not Driver._old_library_warned:
                Driver._old_library_warned = True
                warnings.append(old_warning)
            else:
                logger.warning(_LOCATION, uno_errors.english_text(*old_warning), code)
        for warning, location in warnings:
            logger.warning(location, uno_errors.english_text(warning, location), code)
        if document:
            logger.trace(_LOCATION, "document settings: %s" % document, code)
        return Connection(self._ctx, url, opened, language, code, warnings, pairs)

    def getDataDefinitionByConnection(self, connection):
        target = connection
        if not hasattr(target, "_engine"):
            try:
                url = connection.getMetaData().getURL()
            except Exception:
                url = None
            target = Connection.find(url) if url else None
        if target is None:
            raise self._fail(DriverError(errors.UNEXPECTED, dettaglio="connection not opened by this driver"),
                             "en", "")
        return Catalog(target)

    def getDataDefinitionByURL(self, url, info):
        return Catalog(self.connect(url, info))

    def acceptsURL(self, url):
        return accepts_url(url)

    def getPropertyInfo(self, url, info):
        return ()

    def getMajorVersion(self):
        return version_part(extension_version(self._ctx), 0)

    def getMinorVersion(self):
        return version_part(extension_version(self._ctx), 1)
