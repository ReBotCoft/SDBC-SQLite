# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import uno
import unohelper

from com.sun.star.container import NoSuchElementException
from com.sun.star.container import XContainer
from com.sun.star.container import XEnumeration
from com.sun.star.container import XEnumerationAccess
from com.sun.star.container import XIndexAccess
from com.sun.star.container import XNameAccess
from com.sun.star.lang import IndexOutOfBoundsException
from com.sun.star.sdbc import SQLException
from com.sun.star.sdbcx import XAppend
from com.sun.star.sdbcx import XDataDescriptorFactory
from com.sun.star.sdbcx import XDrop
from com.sun.star.util import XRefreshable

from sdbc_pysqlite import sqlite
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.engine import driver_error
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced


class Enumeration(unohelper.Base, XEnumeration):
    def __init__(self, items):
        self._items = list(items)
        self._position = 0

    def hasMoreElements(self):
        return self._position < len(self._items)

    def nextElement(self):
        if self._position >= len(self._items):
            raise NoSuchElementException()
        item = self._items[self._position]
        self._position += 1
        return item


@traced
class Collection(unohelper.Base, ServiceInfoMixin, XNameAccess, XIndexAccess, XEnumerationAccess, XAppend,
                 XDrop, XDataDescriptorFactory, XRefreshable, XContainer, ErrorMixin):

    _element_type = "com.sun.star.beans.XPropertySet"
    _implementation_name = "dev.rebotcoft.sdbc.pysqlite.Container"
    _service_names = ("com.sun.star.sdbcx.Container",)

    def __init__(self, connection):
        self._connection = connection
        self._objects = {}
        self._signatures = {}
        self._order = []
        self._container_listeners = []
        self._refresh_listeners = []

    def _snapshot(self):
        return []

    def _create(self, name):
        raise NotImplementedError

    def _append(self, descriptor):
        raise self._error(DriverError(None, sqlite.NotSupportedError("not supported")), "appendByDescriptor")

    def _drop(self, name):
        raise self._error(DriverError(None, sqlite.NotSupportedError("not supported")), "dropByName")

    def _new_descriptor(self):
        raise self._error(DriverError(None, sqlite.NotSupportedError("not supported")), "createDataDescriptor")

    def _guard(self, method, function, *args):
        try:
            return function(*args)
        except SQLException:
            raise
        except DriverError as error:
            raise self._error(error, method)
        except sqlite.Error as exception:
            raise self._error(driver_error(exception, self._connection._path), method)

    def _sync(self, method="getElementNames"):
        snapshot = self._guard(method, self._snapshot)
        names = [name for name, _signature in snapshot]
        current = dict(snapshot)
        for name in list(self._signatures):
            if name not in current or self._signatures[name] != current[name]:
                self._objects.pop(name, None)
                self._signatures.pop(name, None)
        for name, signature in snapshot:
            self._signatures.setdefault(name, signature)
        self._order = names

    def _find(self, name):
        if name in self._order:
            return name
        lowered = (name or "").lower()
        for candidate in self._order:
            if candidate.lower() == lowered:
                return candidate
        return None

    def _get(self, name, method):
        self._sync(method)
        found = self._find(name)
        if found is None:
            raise NoSuchElementException(name, self)
        if found not in self._objects:
            self._objects[found] = self._guard(method, self._create, found)
        return self._objects[found]

    def getElementType(self):
        return uno.getTypeByName(self._element_type)

    def hasElements(self):
        self._sync("hasElements")
        return bool(self._order)

    def getByName(self, aName):
        return self._get(aName, "getByName")

    def getElementNames(self):
        self._sync("getElementNames")
        return tuple(self._order)

    def hasByName(self, aName):
        self._sync("hasByName")
        return self._find(aName) is not None

    def getCount(self):
        self._sync("getCount")
        return len(self._order)

    def getByIndex(self, Index):
        self._sync("getByIndex")
        if Index < 0 or Index >= len(self._order):
            raise IndexOutOfBoundsException(str(Index), self)
        return self._get(self._order[Index], "getByIndex")

    def createEnumeration(self):
        self._sync("createEnumeration")
        return Enumeration(self._get(name, "createEnumeration") for name in list(self._order))

    def appendByDescriptor(self, descriptor):
        name = self._guard("appendByDescriptor", self._append, descriptor)
        self._sync("appendByDescriptor")
        if name is not None and self._find(name) is not None:
            found = self._find(name)
            element = self._get(found, "appendByDescriptor")
            self._fire("elementInserted", found, element)

    def dropByName(self, elementName):
        self._sync("dropByName")
        found = self._find(elementName)
        if found is None:
            raise NoSuchElementException(elementName, self)
        self._guard("dropByName", self._drop, found)
        element = self._objects.get(found)
        self._objects.pop(found, None)
        self._signatures.pop(found, None)
        self._sync("dropByName")
        self._fire("elementRemoved", found, element)

    def dropByIndex(self, index):
        self._sync("dropByIndex")
        if index < 0 or index >= len(self._order):
            raise IndexOutOfBoundsException(str(index), self)
        self.dropByName(self._order[index])

    def createDataDescriptor(self):
        return self._guard("createDataDescriptor", self._new_descriptor)

    def refresh(self):
        self._objects.clear()
        self._signatures.clear()
        self._sync("refresh")
        event = uno.createUnoStruct("com.sun.star.lang.EventObject", self)
        for listener in list(self._refresh_listeners):
            listener.refreshed(event)

    def addRefreshListener(self, l):
        self._refresh_listeners.append(l)

    def removeRefreshListener(self, l):
        if l in self._refresh_listeners:
            self._refresh_listeners.remove(l)

    def addContainerListener(self, xListener):
        self._container_listeners.append(xListener)

    def removeContainerListener(self, xListener):
        if xListener in self._container_listeners:
            self._container_listeners.remove(xListener)

    def _fire(self, method, name, element):
        event = uno.createUnoStruct("com.sun.star.container.ContainerEvent", self, name, element, None)
        for listener in list(self._container_listeners):
            getattr(listener, method)(event)

    def dispose(self):
        self._container_listeners = []
        self._refresh_listeners = []

    def addEventListener(self, xListener):
        pass

    def removeEventListener(self, aListener):
        pass


class DescriptorCollection(Collection):

    def __init__(self, connection, factory=None):
        super().__init__(connection)
        self._items = []
        self._factory = factory

    def _sync(self, method="getElementNames"):
        pass

    @staticmethod
    def _name_of(item):
        return item.getPropertyValue("Name")

    def _index_of(self, name):
        lowered = (name or "").lower()
        for index, item in enumerate(self._items):
            if self._name_of(item) == name:
                return index
        for index, item in enumerate(self._items):
            if (self._name_of(item) or "").lower() == lowered:
                return index
        return None

    def hasElements(self):
        return bool(self._items)

    def getElementNames(self):
        return tuple(self._name_of(i) for i in self._items)

    def hasByName(self, aName):
        return self._index_of(aName) is not None

    def getByName(self, aName):
        index = self._index_of(aName)
        if index is None:
            raise NoSuchElementException(aName, self)
        return self._items[index]

    def getCount(self):
        return len(self._items)

    def getByIndex(self, Index):
        if Index < 0 or Index >= len(self._items):
            raise IndexOutOfBoundsException(str(Index), self)
        return self._items[Index]

    def createEnumeration(self):
        return Enumeration(self._items)

    def appendByDescriptor(self, descriptor):
        self._items.append(descriptor)
        self._fire("elementInserted", self._name_of(descriptor), descriptor)

    def dropByName(self, elementName):
        index = self._index_of(elementName)
        if index is None:
            raise NoSuchElementException(elementName, self)
        self.dropByIndex(index)

    def dropByIndex(self, index):
        if index < 0 or index >= len(self._items):
            raise IndexOutOfBoundsException(str(index), self)
        item = self._items.pop(index)
        self._fire("elementRemoved", self._name_of(item), item)

    def refresh(self):
        pass

    def _new_descriptor(self):
        return self._factory(self._connection)

    @property
    def items(self):
        return list(self._items)


class StaticCollection(Collection):

    def __init__(self, connection, items):
        super().__init__(connection)
        self._items = list(items)

    def _snapshot(self):
        return [(item.name, id(item)) for item in self._items]

    def _create(self, name):
        for item in self._items:
            if item.name == name:
                return item
        raise NoSuchElementException(name, self)


class EmptyCollection(Collection):
    pass
