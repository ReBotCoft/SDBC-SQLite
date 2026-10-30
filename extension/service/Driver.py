# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import unohelper

from sdbc_pysqlite import IMPLEMENTATION_NAME
from sdbc_pysqlite import SERVICE_NAMES
from sdbc_pysqlite.sdbc.driver import Driver

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(Driver,
                                         IMPLEMENTATION_NAME,
                                         SERVICE_NAMES)
