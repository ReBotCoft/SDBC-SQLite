# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

CONFIG_PACKAGE = "dev.rebotcoft.sdbc"
CONFIG_NAME = "pysqlite"
IDENTIFIER = CONFIG_PACKAGE + "." + CONFIG_NAME

IMPLEMENTATION_NAME = IDENTIFIER + ".Driver"
SERVICE_NAMES = (IMPLEMENTATION_NAME, "com.sun.star.sdbc.Driver")

URL_PREFIX = "sdbc:external:pysqlite:"

CONFIG_PATH = "/" + IDENTIFIER

LOG_FILE_NAME = "sdbc-pysqlite.log"
DEFAULT_RETENTION_DAYS = 14
