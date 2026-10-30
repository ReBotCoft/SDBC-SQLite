# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import uno
import unohelper

from com.sun.star.beans import PropertyVetoException
from com.sun.star.beans import UnknownPropertyException
from com.sun.star.beans import XPropertySet
from com.sun.star.beans import XPropertySetInfo

from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.logger import traced

READONLY = 16

NO_NULLS = 0
NULLABLE = 1

KEY_PRIMARY = 1
KEY_UNIQUE = 2
KEY_FOREIGN = 3


def make_property(name, handle, type_name, attributes):
    return uno.createUnoStruct("com.sun.star.beans.Property", name, handle, uno.getTypeByName(type_name), attributes)


@traced
class PropertyInfo(unohelper.Base, XPropertySetInfo):

    def __init__(self, definitions, read_only):
        self._properties = [make_property(name, handle, type_name, READONLY if read_only else 0)
                            for handle, (name, type_name) in enumerate(definitions)]
        self._properties.sort(key=lambda p: p.Name)
        self._by_name = {p.Name: p for p in self._properties}

    def getProperties(self):
        return tuple(self._properties)

    def getPropertyByName(self, aName):
        if aName not in self._by_name:
            raise UnknownPropertyException(aName, self)
        return self._by_name[aName]

    def hasPropertyByName(self, Name):
        return Name in self._by_name


@traced
class PropertyObject(unohelper.Base, ServiceInfoMixin, XPropertySet, ErrorMixin):

    _definitions = ()
    _defaults = {}
    _implementation_name = ""
    _service_names = ()

    def __init__(self, connection, values=None, is_new=False):
        self._connection = connection
        self._is_new = is_new
        self._values = {name: self._defaults.get(name, _zero(type_name)) for name, type_name in self._definitions}
        if values:
            self._values.update(values)

    def getPropertySetInfo(self):
        return PropertyInfo(self._definitions, not self._is_new)

    def setPropertyValue(self, aPropertyName, aValue):
        if aPropertyName not in self._values:
            raise UnknownPropertyException(aPropertyName, self)
        if not self._is_new:
            raise PropertyVetoException(aPropertyName, self)
        self._values[aPropertyName] = aValue

    def getPropertyValue(self, PropertyName):
        if PropertyName not in self._values:
            raise UnknownPropertyException(PropertyName, self)
        return self._values[PropertyName]

    def addPropertyChangeListener(self, aPropertyName, xListener):
        pass

    def removePropertyChangeListener(self, aPropertyName, aListener):
        pass

    def addVetoableChangeListener(self, PropertyName, aListener):
        pass

    def removeVetoableChangeListener(self, PropertyName, aListener):
        pass

    @property
    def name(self):
        return self._values.get("Name", "")


def _zero(type_name):
    return {"string": "", "long": 0, "short": 0, "boolean": False}.get(type_name)


def read(source, *names):
    result = []
    for name in names:
        try:
            result.append(source.getPropertyValue(name))
        except Exception:
            result.append(None)
    return result
