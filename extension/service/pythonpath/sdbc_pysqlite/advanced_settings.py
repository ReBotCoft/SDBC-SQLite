# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

SHOWN = ("AppendTableAliasName", "GenerateASBeforeCorrelationName")

FIXED_VALUES = {
    "IsAutoRetrievingEnabled": True,
    "AutoIncrementCreation": "AUTO_INCREMENT",
    "AutoRetrievingStatement": "",
    "EnableSQL92Check": False,
    "EnableOuterJoinEscape": True,
    "IgnoreDriverPrivileges": True,
    "ParameterNameSubstitution": False,
    "DisplayVersionColumns": False,
    "UseCatalogInSelect": False,
    "UseSchemaInSelect": False,
    "AddIndexAppendix": True,
    "PreferDosLikeLineEnds": False,
    "FormsCheckRequiredFields": True,
    "EscapeDateTime": True,
    "PrimaryKeySupport": True,
    "RespectDriverResultSetType": True,
    "ColumnAliasInOrderBy": True,
    "UseCatalog": False,
    "TableTypeFilterMode": 3,
    "BooleanComparisonMode": 1,
}


def same(current, wanted):
    if isinstance(wanted, bool) or isinstance(current, bool):
        return isinstance(wanted, bool) and isinstance(current, bool) and current == wanted
    return current == wanted


def plan(current):
    different = []
    missing = []
    for name, wanted in FIXED_VALUES.items():
        if name not in current:
            missing.append(name)
        elif not same(current[name], wanted):
            different.append((name, current[name], wanted))
    return different, missing


def reset(bag, log=None):
    def note(text):
        if log is not None:
            log(text)

    counts = {"written": 0, "same": 0, "failed": 0}
    for name, wanted in FIXED_VALUES.items():
        try:
            old = bag.getPropertyValue(name)
            readable = True
        except Exception as exception:
            old, readable = None, False
            note("%s: not readable (%s)" % (name, type(exception).__name__))
        if readable and same(old, wanted):
            counts["same"] += 1
            note("%s: already %r" % (name, wanted))
            continue
        try:
            bag.setPropertyValue(name, wanted)
            counts["written"] += 1
            note("%s: written %r (was %r)" % (name, wanted, old))
        except Exception as exception:
            counts["failed"] += 1
            note("%s: cannot write (%s: %s)" % (name, type(exception).__name__, exception))
    return counts
