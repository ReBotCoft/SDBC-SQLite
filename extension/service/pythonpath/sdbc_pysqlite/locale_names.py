# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import uno

from sdbc_pysqlite import configuration
from sdbc_pysqlite import functions


def _locale_tag(ctx):
    provider = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.configuration.ConfigurationProvider", ctx)
    node = configuration._open_node(provider, configuration._LANGUAGE_NODE)
    for name in ("ooSetupSystemLocale", "ooLocale"):
        try:
            value = str(node.getByName(name) or "").strip()
        except Exception:
            value = ""
        if value:
            return value
    return ""


def read_names(ctx, language="auto"):
    try:
        tag = _locale_tag(ctx) if language in ("", "auto") else language
        parts = tag.replace("_", "-").split("-")
        locale = uno.createUnoStruct("com.sun.star.lang.Locale")
        locale.Language = parts[0] if parts[0] else "en"
        locale.Country = parts[1] if len(parts) > 1 else ""
        data = ctx.ServiceManager.createInstanceWithContext("com.sun.star.i18n.LocaleData", ctx)
        calendars = data.getAllCalendars2(locale)
        calendar = next((c for c in calendars if c.Default), calendars[0])
        days, months = calendar.Days, calendar.Months
        if len(days) != 7 or len(months) < 12:
            return None
        return functions.Names(tuple(d.FullName for d in days), tuple(d.AbbrevName for d in days),
                               tuple(m.FullName for m in months[:12]), tuple(m.AbbrevName for m in months[:12]))
    except Exception:
        return None
