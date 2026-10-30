# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import URL_PREFIX

PROTOCOL = IDENTIFIER + ":"
COMMAND = PROTOCOL + "Settings"
HANDLER_IMPLEMENTATION = IDENTIFIER + ".SettingsHandler"
HANDLER_SERVICES = ("com.sun.star.frame.ProtocolHandler",)

OPTIONS_HANDLER_IMPLEMENTATION = IDENTIFIER + ".OptionsHandler"
OPTIONS_HANDLER_SERVICES = (OPTIONS_HANDLER_IMPLEMENTATION,)

_SECRET_NAMES = ("password", "pass", "pwd")


def is_our_address(url):
    return isinstance(url, str) and url.strip().startswith(URL_PREFIX)


def info_lines(pairs):
    lines = []
    for name, value in pairs:
        shown = "***" if str(name).lower() in _SECRET_NAMES else repr(value)
        lines.append("%s = %s" % (name, shown))
    return lines
