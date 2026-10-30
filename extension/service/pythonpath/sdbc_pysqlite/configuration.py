# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from dataclasses import dataclass

import uno

from sdbc_pysqlite import CONFIG_PATH
from sdbc_pysqlite import DEFAULT_RETENTION_DAYS
from sdbc_pysqlite import parameters

_LANGUAGE_NODE = "/org.openoffice.Setup/L10N"


@dataclass(frozen=True)
class Settings:
    trace: bool = False
    log_path: str = ""
    retention_days: int = DEFAULT_RETENTION_DAYS
    create_if_missing: object = parameters.DEFAULTS[parameters.CREATE_IF_MISSING]
    lock_timeout_seconds: object = parameters.DEFAULTS[parameters.LOCK_TIMEOUT_SECONDS]
    foreign_keys: object = parameters.DEFAULTS[parameters.FOREIGN_KEYS]
    read_only: object = parameters.DEFAULTS[parameters.READ_ONLY]
    journal_mode: object = parameters.DEFAULTS[parameters.JOURNAL_MODE]
    full_load_limit: object = parameters.DEFAULTS[parameters.FULL_LOAD_LIMIT]
    window_size: object = parameters.DEFAULTS[parameters.WINDOW_SIZE]
    transaction_mode: object = parameters.DEFAULTS[parameters.TRANSACTION_MODE]
    date_time_format: object = parameters.DEFAULTS[parameters.DATE_TIME_FORMAT]
    date_time_zone: object = parameters.DEFAULTS[parameters.DATE_TIME_ZONE]
    names_language: object = parameters.DEFAULTS[parameters.NAMES_LANGUAGE]
    auto_increment_reuse: object = parameters.DEFAULTS[parameters.AUTO_INCREMENT_REUSE]
    row_id_as_key: object = parameters.DEFAULTS[parameters.ROW_ID_AS_KEY]
    old_library_warning: object = parameters.DEFAULTS[parameters.OLD_LIBRARY_WARNING]
    defensive_mode: object = parameters.DEFAULTS[parameters.DEFENSIVE_MODE]
    untrusted_schema: object = parameters.DEFAULTS[parameters.UNTRUSTED_SCHEMA]
    limits_profile: object = parameters.DEFAULTS[parameters.LIMITS_PROFILE]
    language: str = "en"
    error: str = ""

    def connection_values(self):
        return {
            parameters.CREATE_IF_MISSING: self.create_if_missing,
            parameters.LOCK_TIMEOUT_SECONDS: self.lock_timeout_seconds,
            parameters.FOREIGN_KEYS: self.foreign_keys,
            parameters.READ_ONLY: self.read_only,
            parameters.JOURNAL_MODE: self.journal_mode,
            parameters.FULL_LOAD_LIMIT: self.full_load_limit,
            parameters.WINDOW_SIZE: self.window_size,
            parameters.TRANSACTION_MODE: self.transaction_mode,
            parameters.DATE_TIME_FORMAT: self.date_time_format,
            parameters.DATE_TIME_ZONE: self.date_time_zone,
            parameters.NAMES_LANGUAGE: self.names_language,
            parameters.AUTO_INCREMENT_REUSE: self.auto_increment_reuse,
            parameters.ROW_ID_AS_KEY: self.row_id_as_key,
            parameters.OLD_LIBRARY_WARNING: self.old_library_warning,
            parameters.DEFENSIVE_MODE: self.defensive_mode,
            parameters.UNTRUSTED_SCHEMA: self.untrusted_schema,
            parameters.LIMITS_PROFILE: self.limits_profile,
        }

    def all_values(self):
        values = {"Trace": self.trace, "LogPath": self.log_path, "LogRetentionDays": self.retention_days}
        values.update(self.connection_values())
        return values


def _open_node(provider, path):
    node = uno.createUnoStruct("com.sun.star.beans.NamedValue")
    node.Name = "nodepath"
    node.Value = path
    return provider.createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationAccess", (node, ))


def _read_language(provider):
    try:
        locale = str(_open_node(provider, _LANGUAGE_NODE).getByName("ooLocale") or "")
    except Exception:
        return "en"
    return "it" if locale.lower().startswith("it") else "en"


def read_settings(ctx):
    try:
        provider = ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.configuration.ConfigurationProvider", ctx)
        access = _open_node(provider, CONFIG_PATH)
    except Exception as exception:
        return Settings(error="reading the settings failed (defaults used): %s: %s" % (
            type(exception).__name__, exception))

    problems = []
    values = {}

    def read(name, convert, key):
        try:
            values[key] = convert(access.getByName(name))
        except Exception as exception:
            problems.append("%s: %s: %s" % (name, type(exception).__name__, exception))

    read("Trace", bool, "trace")
    read("LogPath", lambda v: str(v or ""), "log_path")
    read("LogRetentionDays", lambda v: int(v) if int(v) >= 1 else DEFAULT_RETENTION_DAYS, "retention_days")
    read(parameters.CREATE_IF_MISSING, bool, "create_if_missing")
    read(parameters.LOCK_TIMEOUT_SECONDS, int, "lock_timeout_seconds")
    read(parameters.FOREIGN_KEYS, bool, "foreign_keys")
    read(parameters.READ_ONLY, bool, "read_only")
    read(parameters.JOURNAL_MODE, str, "journal_mode")
    read(parameters.FULL_LOAD_LIMIT, int, "full_load_limit")
    read(parameters.WINDOW_SIZE, int, "window_size")
    read(parameters.TRANSACTION_MODE, str, "transaction_mode")
    read(parameters.DATE_TIME_FORMAT, str, "date_time_format")
    read(parameters.DATE_TIME_ZONE, str, "date_time_zone")
    read(parameters.NAMES_LANGUAGE, str, "names_language")
    read(parameters.AUTO_INCREMENT_REUSE, bool, "auto_increment_reuse")
    read(parameters.ROW_ID_AS_KEY, bool, "row_id_as_key")
    read(parameters.OLD_LIBRARY_WARNING, bool, "old_library_warning")
    read(parameters.DEFENSIVE_MODE, bool, "defensive_mode")
    read(parameters.UNTRUSTED_SCHEMA, bool, "untrusted_schema")
    read(parameters.LIMITS_PROFILE, str, "limits_profile")

    error = ""
    if problems:
        error = "reading some settings failed (defaults used for those): " + "; ".join(problems)
    return Settings(language=_read_language(provider), error=error, **values)


_BOOLEAN_OPTIONS = ("Trace",) + parameters.BOOLEAN_NAMES
_INTEGER_OPTIONS = ("LogRetentionDays", parameters.LOCK_TIMEOUT_SECONDS, parameters.FULL_LOAD_LIMIT,
                    parameters.WINDOW_SIZE)
WRITABLE_NAMES = ("Trace", "LogPath", "LogRetentionDays") + parameters.PARAMETER_NAMES


def _is_direct_value(state):
    return getattr(state, "value", state) == "DIRECT_VALUE"


def _back_to_default(access, name):
    try:
        states = access.queryInterface(uno.getTypeByName("com.sun.star.beans.XPropertyState"))
    except Exception:
        states = None
    if states is not None:
        if _is_direct_value(states.getPropertyState(name)):
            states.setPropertyToDefault(name)
        return
    default = parameters.DEFAULTS.get(name)
    if name == "Trace":
        default = False
    elif name == "LogPath":
        default = ""
    elif name == "LogRetentionDays":
        default = 14
    if default is None:
        return
    if name in _BOOLEAN_OPTIONS:
        access.setPropertyValue(name, bool(default))
    elif name in _INTEGER_OPTIONS:
        access.setPropertyValue(name, uno.Any("long", int(default)))
    else:
        access.setPropertyValue(name, str(default))


def write_settings(ctx, values, reset=()):
    provider = ctx.ServiceManager.createInstanceWithContext(
        "com.sun.star.configuration.ConfigurationProvider", ctx)
    node = uno.createUnoStruct("com.sun.star.beans.NamedValue")
    node.Name = "nodepath"
    node.Value = CONFIG_PATH
    access = provider.createInstanceWithArguments(
        "com.sun.star.configuration.ConfigurationUpdateAccess", (node, ))
    for name, value in values.items():
        if name not in WRITABLE_NAMES:
            continue
        if name in _BOOLEAN_OPTIONS:
            access.setPropertyValue(name, bool(value))
        elif name in _INTEGER_OPTIONS:
            access.setPropertyValue(name, uno.Any("long", int(value)))
        else:
            access.setPropertyValue(name, str(value))
    for name in reset:
        if name in WRITABLE_NAMES:
            _back_to_default(access, name)
    access.commitChanges()
