# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite.sdbcx.collection import EmptyCollection


class UserContainer(EmptyCollection):
    _implementation_name = IDENTIFIER + ".Users"
