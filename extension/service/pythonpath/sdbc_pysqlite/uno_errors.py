# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from com.sun.star.sdbc import SQLException
from com.sun.star.sdbc import SQLWarning

from sdbc_pysqlite import logger
from sdbc_pysqlite import messages


def english_text(error, location):
    return " ".join(messages.describe(error, "en", location).message.split())


def to_sql_exception(error, context, language, location, code=""):
    logger.error(location, english_text(error, location), code)
    described = messages.describe(error, language, location)
    return SQLException(described.message, context, described.sqlstate, described.error_code, None)


def to_sql_warning_chain(warnings, context, language):
    chain = None
    for error, location in reversed(warnings):
        described = messages.describe(error, language, location)
        chain = SQLWarning(described.message, context, described.sqlstate, described.error_code, chain)
    return chain
