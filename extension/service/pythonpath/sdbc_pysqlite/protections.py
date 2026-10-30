# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from sdbc_pysqlite import parameters
from sdbc_pysqlite import sqlite

_PRUDENT = {
    "EXPR_DEPTH": 200,
    "TRIGGER_DEPTH": 50,
    "COMPOUND_SELECT": 100,
    "LIKE_PATTERN_LENGTH": 5000,
    "ATTACHED": 5,
    "VDBE_OP": 50000000,
}

PROFILES = {
    "none": {},
    "prudent": dict(_PRUDENT),
    "strict": dict(_PRUDENT, LENGTH=100000000, SQL_LENGTH=10000000, COLUMN=500, VARIABLE_NUMBER=32766),
}


def _apply_limits(connection, profile):
    obtained = True
    for name, value in PROFILES[profile].items():
        current = connection.limit(name)
        if current < 0:
            obtained = False
            continue
        if current > value:
            connection.limit(name, value)
        if connection.limit(name) > value:
            obtained = False
    return obtained


def apply(connection, options):
    missing = []
    if options.defensive_mode and connection.config(sqlite.DBCONFIG_DEFENSIVE, 1) != 1:
        missing.append(parameters.DEFENSIVE_MODE)
    if options.untrusted_schema and connection.config(sqlite.DBCONFIG_TRUSTED_SCHEMA, 0) != 0:
        missing.append(parameters.UNTRUSTED_SCHEMA)
    if not _apply_limits(connection, options.limits_profile):
        missing.append(parameters.LIMITS_PROFILE)
    return missing
