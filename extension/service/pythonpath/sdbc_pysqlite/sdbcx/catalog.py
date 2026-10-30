# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unohelper

from com.sun.star.sdbcx import XGroupsSupplier
from com.sun.star.sdbcx import XTablesSupplier
from com.sun.star.sdbcx import XUsersSupplier
from com.sun.star.sdbcx import XViewsSupplier

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite.common import ComponentMixin
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import ServiceInfoMixin
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbcx.group import GroupContainer
from sdbc_pysqlite.sdbcx.table import TableContainer
from sdbc_pysqlite.sdbcx.user import UserContainer
from sdbc_pysqlite.sdbcx.view import ViewContainer


@traced
class Catalog(unohelper.Base, ComponentMixin, ServiceInfoMixin, XTablesSupplier, XViewsSupplier, XUsersSupplier,
              XGroupsSupplier, ErrorMixin):

    _implementation_name = IDENTIFIER + ".Catalog"
    _service_names = ("com.sun.star.sdbcx.Catalog",)

    def __init__(self, connection):
        self._connection = connection
        self._tables = TableContainer(connection)
        self._views = ViewContainer(connection)
        self._users = UserContainer(connection)
        self._groups = GroupContainer(connection)

    def getTables(self):
        return self._tables

    def getViews(self):
        return self._views

    def getUsers(self):
        return self._users

    def getGroups(self):
        return self._groups
