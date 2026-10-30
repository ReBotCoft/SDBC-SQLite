# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import re

CREATE_IF_MISSING = "CreateIfMissing"
LOCK_TIMEOUT_SECONDS = "LockTimeoutSeconds"
FOREIGN_KEYS = "ForeignKeys"
READ_ONLY = "ReadOnly"
JOURNAL_MODE = "JournalMode"
FULL_LOAD_LIMIT = "FullLoadLimit"
WINDOW_SIZE = "WindowSize"
TRANSACTION_MODE = "TransactionMode"
DATE_TIME_FORMAT = "DateTimeFormat"
DATE_TIME_ZONE = "DateTimeZone"
NAMES_LANGUAGE = "NamesLanguage"
AUTO_INCREMENT_REUSE = "AutoIncrementReuse"
ROW_ID_AS_KEY = "RowIdAsKey"
OLD_LIBRARY_WARNING = "OldLibraryWarning"
DEFENSIVE_MODE = "DefensiveMode"
UNTRUSTED_SCHEMA = "UntrustedSchema"
LIMITS_PROFILE = "LimitsProfile"

PARAMETER_NAMES = (
    CREATE_IF_MISSING, LOCK_TIMEOUT_SECONDS, FOREIGN_KEYS, READ_ONLY, JOURNAL_MODE,
    FULL_LOAD_LIMIT, WINDOW_SIZE, TRANSACTION_MODE, DATE_TIME_FORMAT, DATE_TIME_ZONE, NAMES_LANGUAGE,
    AUTO_INCREMENT_REUSE, ROW_ID_AS_KEY, OLD_LIBRARY_WARNING, DEFENSIVE_MODE, UNTRUSTED_SCHEMA, LIMITS_PROFILE)
BOOLEAN_NAMES = (CREATE_IF_MISSING, FOREIGN_KEYS, READ_ONLY, AUTO_INCREMENT_REUSE, ROW_ID_AS_KEY,
                 OLD_LIBRARY_WARNING, DEFENSIVE_MODE, UNTRUSTED_SCHEMA)
POSITIVE_NAMES = (FULL_LOAD_LIMIT, WINDOW_SIZE)

JOURNAL_MODES = ("delete", "truncate", "persist", "memory", "wal", "off")
TRANSACTION_MODES = ("free", "blocking", "exclusive")
DATE_TIME_FORMATS = ("text", "unix", "julian")
DATE_TIME_ZONES = ("local", "utc")
NAMES_LANGUAGES = ("auto", "en", "it", "fr", "de", "es")
LIMITS_PROFILES = ("none", "prudent", "strict")

_CHOICES = {
    JOURNAL_MODE: JOURNAL_MODES,
    TRANSACTION_MODE: TRANSACTION_MODES,
    DATE_TIME_FORMAT: DATE_TIME_FORMATS,
    DATE_TIME_ZONE: DATE_TIME_ZONES,
    NAMES_LANGUAGE: NAMES_LANGUAGES,
    LIMITS_PROFILE: LIMITS_PROFILES,
}

DEFAULTS = {
    CREATE_IF_MISSING: False,
    LOCK_TIMEOUT_SECONDS: 5,
    FOREIGN_KEYS: False,
    READ_ONLY: False,
    JOURNAL_MODE: "delete",
    FULL_LOAD_LIMIT: 50000,
    WINDOW_SIZE: 1000,
    TRANSACTION_MODE: "free",
    DATE_TIME_FORMAT: "text",
    DATE_TIME_ZONE: "local",
    NAMES_LANGUAGE: "auto",
    AUTO_INCREMENT_REUSE: False,
    ROW_ID_AS_KEY: False,
    OLD_LIBRARY_WARNING: True,
    DEFENSIVE_MODE: False,
    UNTRUSTED_SCHEMA: False,
    LIMITS_PROFILE: "none",
}

_ALLOWED_TEXT = {
    "it": {
        LOCK_TIMEOUT_SECONDS: "un numero intero da 0 in su",
        FULL_LOAD_LIMIT: "un numero intero da 1 in su",
        WINDOW_SIZE: "un numero intero da 1 in su",
    },
    "en": {
        LOCK_TIMEOUT_SECONDS: "a whole number, 0 or more",
        FULL_LOAD_LIMIT: "a whole number, 1 or more",
        WINDOW_SIZE: "a whole number, 1 or more",
    },
}

_PAIR_TEXT = {
    "it": "DateTimeZone=local ammette solo DateTimeFormat=text; unix e julian richiedono DateTimeZone=utc",
    "en": "DateTimeZone=local allows only DateTimeFormat=text; unix and julian require DateTimeZone=utc",
}


class InvalidValue(ValueError):
    pass


def allowed_text(name, language="en"):
    if name in BOOLEAN_NAMES:
        return "true, false"
    if name in _CHOICES:
        return ", ".join(_CHOICES[name])
    texts = _ALLOWED_TEXT.get(language, _ALLOWED_TEXT["en"])
    return texts.get(name, "")


def pair_text(language="en"):
    return _PAIR_TEXT.get(language, _PAIR_TEXT["en"])


def convert(name, text):
    if name in BOOLEAN_NAMES:
        if text == "true":
            return True
        if text == "false":
            return False
        raise InvalidValue(text)
    if name == LOCK_TIMEOUT_SECONDS:
        if re.fullmatch(r"[0-9]+", text):
            return int(text)
        raise InvalidValue(text)
    if name in POSITIVE_NAMES:
        if re.fullmatch(r"[0-9]+", text) and int(text) >= 1:
            return int(text)
        raise InvalidValue(text)
    if name in _CHOICES:
        if text in _CHOICES[name]:
            return text
        raise InvalidValue(text)
    raise InvalidValue(text)


def check_typed(name, value):
    if name in BOOLEAN_NAMES:
        if isinstance(value, bool):
            return value
        raise InvalidValue(str(value))
    if name == LOCK_TIMEOUT_SECONDS:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        raise InvalidValue(str(value))
    if name in POSITIVE_NAMES:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
            return value
        raise InvalidValue(str(value))
    if name in _CHOICES:
        if isinstance(value, str) and value in _CHOICES[name]:
            return value
        raise InvalidValue(str(value))
    raise InvalidValue(str(value))


def convert_setting(name, value):
    if isinstance(value, str):
        return convert(name, value)
    return check_typed(name, value)


def check_date_time(zone, date_format):
    return zone == "utc" or date_format == "text"
