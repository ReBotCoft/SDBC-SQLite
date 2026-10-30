# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from sdbc_pysqlite import parameters


def read(pairs):
    found = {}
    for name, value in pairs:
        if name in parameters.PARAMETER_NAMES:
            found[name] = value
    return found


def to_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def merge(pairs, chosen):
    result = []
    written = set()
    for name, value in pairs:
        if name in chosen and name in parameters.PARAMETER_NAMES:
            if chosen[name] is not None and name not in written:
                result.append((name, to_text(chosen[name])))
                written.add(name)
            continue
        result.append((name, value))
    for name, value in chosen.items():
        if value is not None and name in parameters.PARAMETER_NAMES and name not in written:
            result.append((name, to_text(value)))
            written.add(name)
    return result


def changed(old_pairs, new_pairs):
    return [(n, repr(v)) for n, v in old_pairs] != [(n, repr(v)) for n, v in new_pairs]
