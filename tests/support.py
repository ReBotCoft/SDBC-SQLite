# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import importlib.abc
import importlib.machinery
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHONPATH = os.path.join(ROOT, "extension", "service", "pythonpath")
if PYTHONPATH not in sys.path:
    sys.path.insert(0, PYTHONPATH)

if os.environ.get("SDBC_SQLITE_LIBRARY"):
    from sdbc_pysqlite import sqlite as _sqlite
    _sqlite.set_library_path(os.environ["SDBC_SQLITE_LIBRARY"])


class _FakeSQLException(Exception):

    def __init__(self, Message="", Context=None, SQLState="", ErrorCode=0, NextException=None):
        super().__init__(Message)
        self.Message = Message
        self.Context = Context
        self.SQLState = SQLState
        self.ErrorCode = ErrorCode
        self.NextException = NextException

    _FIELDS = ("Message", "Context", "SQLState", "ErrorCode", "NextException")

    def __setattr__(self, name, value):
        if name not in self._FIELDS and not name.startswith("__"):
            raise AttributeError(name)
        super().__setattr__(name, value)


class _FakeWarning(_FakeSQLException):
    pass


class _ComSunStarModule(types.ModuleType):

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name == "SQLException":
            value = _FakeSQLException
        elif name == "SQLWarning":
            value = _FakeWarning
        elif name.endswith("Exception"):
            value = type(name, (Exception,), {})
        else:
            value = type(name, (object,), {})
        setattr(self, name, value)
        return value


class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path, target=None):
        if fullname in ("com", "com.sun") or fullname.startswith("com.sun.star"):
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        module = _ComSunStarModule(spec.name)
        module.__path__ = []
        return module

    def exec_module(self, module):
        pass


class _Base:
    pass


def install_uno_stubs():
    if "unohelper" in sys.modules and getattr(sys.modules["unohelper"], "_is_fake", False):
        return
    if not any(isinstance(f, _Finder) for f in sys.meta_path):
        sys.meta_path.insert(0, _Finder())

    unohelper = types.ModuleType("unohelper")
    unohelper._is_fake = True
    unohelper.Base = _Base
    unohelper.fileUrlToSystemPath = lambda url: url[len("file://"):] if url.startswith("file://") else url
    unohelper.systemPathToFileUrl = lambda path: "file://" + path

    class ImplementationHelper:
        def addImplementation(self, *args):
            pass

    unohelper.ImplementationHelper = ImplementationHelper
    sys.modules["unohelper"] = unohelper

    uno = types.ModuleType("uno")

    class _Struct:

        _FIELDS = {
            "com.sun.star.beans.Property": ("Name", "Handle", "Type", "Attributes"),
            "com.sun.star.container.ContainerEvent": ("Source", "Accessor", "Element", "ReplacedElement"),
            "com.sun.star.lang.EventObject": ("Source",),
        }

        def __init__(self, type_name="", *args):
            self.type_name = type_name
            for field, value in zip(self._FIELDS.get(type_name, ()), args):
                setattr(self, field, value)

    uno.createUnoStruct = lambda name, *args: _Struct(name, *args)
    uno.getTypeByName = lambda name: ("type", name)

    class Any:

        def __init__(self, type_name, value):
            self.type_name = type_name
            self.value = value

    uno.Any = Any

    class ByteSequence:
        def __init__(self, value=b""):
            self.value = bytes(value)

    uno.ByteSequence = ByteSequence
    sys.modules["uno"] = uno


class FakeAccess:

    def __init__(self, values):
        self.values = values

    def getByName(self, name):
        return self.values[name]


class FakeContext:

    def __init__(self, nodes):
        self.nodes = nodes
        self.ServiceManager = self

    def createInstanceWithContext(self, name, ctx):
        return self

    def createInstanceWithArguments(self, name, arguments):
        path = arguments[0].Value
        if path not in self.nodes:
            raise RuntimeError("no such node: %s" % path)
        return FakeAccess(self.nodes[path])
