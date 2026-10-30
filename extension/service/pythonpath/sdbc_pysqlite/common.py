# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unohelper

from com.sun.star.beans import UnknownPropertyException
from com.sun.star.beans import XPropertySet
from com.sun.star.beans import XPropertySetInfo
from com.sun.star.lang import XComponent
from com.sun.star.lang import XServiceInfo

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import logger
from sdbc_pysqlite import uno_errors
from sdbc_pysqlite.logger import traced


def extension_version(ctx):
    try:
        provider = ctx.getValueByName("/singletons/com.sun.star.deployment.PackageInformationProvider")
        return str(provider.getExtensionVersion(IDENTIFIER) or "")
    except Exception:
        return ""


def version_part(version, index):
    try:
        return int(version.split(".")[index])
    except (ValueError, IndexError):
        return 0


class ErrorMixin:

    def _owner_connection(self):
        obj = self
        for _ in range(4):
            if hasattr(obj, "_language") and hasattr(obj, "_engine"):
                return obj
            obj = getattr(obj, "_connection", None) or getattr(obj, "_statement", None)
            if obj is None:
                break
        return None

    def _error(self, error, method):
        owner = self._owner_connection()
        language = owner._language if owner is not None else "en"
        code = owner._log_code if owner is not None else ""
        location = logger.label_of(self, method)
        return uno_errors.to_sql_exception(error, self, language, location, code)

    def _warning(self, error, method):
        owner = self._owner_connection()
        code = owner._log_code if owner is not None else ""
        location = logger.label_of(self, method)
        logger.warning(location, uno_errors.english_text(error, location), code)
        return (error, location)


@traced
class ServiceInfoMixin(XServiceInfo):

    _implementation_name = ""
    _service_names = ()

    def getImplementationName(self):
        return self._implementation_name

    def supportsService(self, serviceName):
        return serviceName in self._service_names

    def getSupportedServiceNames(self):
        return self._service_names


@traced
class ComponentMixin(XComponent):

    def dispose(self):
        pass

    def addEventListener(self, xListener):
        pass

    def removeEventListener(self, aListener):
        pass


@traced
class PropertySetInfo(unohelper.Base, XPropertySetInfo):

    def __init__(self, properties):
        self._properties = properties

    def getProperties(self):
        return ()

    def getPropertyByName(self, aName):
        raise UnknownPropertyException(aName, self)

    def hasPropertyByName(self, Name):
        return Name in self._properties


@traced
class PropertySetMixin(XPropertySet):

    _default_properties = {}

    def _init_properties(self):
        self._properties = dict(self._default_properties)

    def getPropertySetInfo(self):
        return PropertySetInfo(self._properties)

    def setPropertyValue(self, aPropertyName, aValue):
        if aPropertyName not in self._properties:
            raise UnknownPropertyException(aPropertyName, self)
        self._properties[aPropertyName] = aValue

    def getPropertyValue(self, PropertyName):
        if PropertyName not in self._properties:
            raise UnknownPropertyException(PropertyName, self)
        return self._properties[PropertyName]

    def addPropertyChangeListener(self, aPropertyName, xListener):
        pass

    def removePropertyChangeListener(self, aPropertyName, aListener):
        pass

    def addVetoableChangeListener(self, PropertyName, aListener):
        pass

    def removeVetoableChangeListener(self, PropertyName, aListener):
        pass
