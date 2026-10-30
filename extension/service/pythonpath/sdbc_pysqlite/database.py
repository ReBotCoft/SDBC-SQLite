# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os
import pathlib
from collections import namedtuple

from sdbc_pysqlite import address
from sdbc_pysqlite import errors
from sdbc_pysqlite import functions
from sdbc_pysqlite import parameters
from sdbc_pysqlite import protections
from sdbc_pysqlite import sqlite
from sdbc_pysqlite.errors import DriverError

ConnectionOptions = namedtuple(
    "ConnectionOptions",
    "create_if_missing lock_timeout_seconds foreign_keys read_only journal_mode "
    "full_load_limit window_size transaction_mode date_time_format date_time_zone names_language "
    "auto_increment_reuse row_id_as_key old_library_warning defensive_mode untrusted_schema limits_profile")

TESTED_SQLITE_VERSION = (3, 54, 1)

OpenedDatabase = namedtuple("OpenedDatabase", "connection path full_path options warnings")


def resolve_options(from_address, from_settings, from_document=None):
    from_document = from_document or {}
    pair = (parameters.DATE_TIME_ZONE, parameters.DATE_TIME_FORMAT)

    def document_value(name):
        try:
            return parameters.convert_setting(name, from_document[name])
        except parameters.InvalidValue:
            raise DriverError(errors.INVALID_VALUE, nome=name, valore=str(from_document[name]))

    def settings_value(name):
        try:
            return parameters.check_typed(name, from_settings[name])
        except parameters.InvalidValue:
            raise DriverError(errors.INVALID_VALUE, nome=name, valore=str(from_settings[name]))

    layers = (
        (lambda name: name in from_address, lambda name: from_address[name]),
        (lambda name: from_document.get(name) is not None, document_value),
        (lambda name: from_settings.get(name) is not None, settings_value),
    )
    pair_layer = None
    for layer in layers:
        if any(layer[0](name) for name in pair):
            pair_layer = layer
            break
    values = {}
    for name in parameters.PARAMETER_NAMES:
        if name in pair:
            has, get = pair_layer if pair_layer else (None, None)
            values[name] = get(name) if has and has(name) else parameters.DEFAULTS[name]
            continue
        values[name] = parameters.DEFAULTS[name]
        for has, get in layers:
            if has(name):
                values[name] = get(name)
                break
    zone = values[parameters.DATE_TIME_ZONE]
    date_format = values[parameters.DATE_TIME_FORMAT]
    if not parameters.check_date_time(zone, date_format):
        raise DriverError(errors.INVALID_VALUE, nome=parameters.DATE_TIME_FORMAT, valore=date_format,
                          ammessi_chiave="pair")
    return ConnectionOptions(
        create_if_missing=values[parameters.CREATE_IF_MISSING],
        lock_timeout_seconds=values[parameters.LOCK_TIMEOUT_SECONDS],
        foreign_keys=values[parameters.FOREIGN_KEYS],
        read_only=values[parameters.READ_ONLY],
        journal_mode=values[parameters.JOURNAL_MODE],
        full_load_limit=values[parameters.FULL_LOAD_LIMIT],
        window_size=values[parameters.WINDOW_SIZE],
        transaction_mode=values[parameters.TRANSACTION_MODE],
        date_time_format=date_format,
        date_time_zone=zone,
        names_language=values[parameters.NAMES_LANGUAGE],
        auto_increment_reuse=values[parameters.AUTO_INCREMENT_REUSE],
        row_id_as_key=values[parameters.ROW_ID_AS_KEY],
        old_library_warning=values[parameters.OLD_LIBRARY_WARNING],
        defensive_mode=values[parameters.DEFENSIVE_MODE],
        untrusted_schema=values[parameters.UNTRUSTED_SCHEMA],
        limits_profile=values[parameters.LIMITS_PROFILE])


def old_library_version():
    if sqlite.sqlite_version_info < TESTED_SQLITE_VERSION:
        return sqlite.sqlite_version
    return ""


def _sqlite_error(exception, path):
    return DriverError(None, sqlite=exception, percorso=path)


def _prepare_file(path, full_path, options):
    create = options.create_if_missing and not options.read_only
    folder = os.path.dirname(full_path)
    if os.path.isdir(full_path):
        raise DriverError(errors.PATH_IS_FOLDER, percorso=path)
    if not os.path.isdir(folder):
        if not create:
            raise DriverError(errors.FOLDER_NOT_FOUND, cartella=folder)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            raise DriverError(errors.CANNOT_CREATE, percorso=path)
    if os.path.exists(full_path):
        return False
    if not create:
        raise DriverError(errors.FILE_NOT_FOUND, percorso=path)
    return True


def _connect(full_path, options):
    timeout = float(options.lock_timeout_seconds)
    if options.read_only:
        uri = pathlib.Path(full_path).as_uri() + "?mode=ro"
        return sqlite.connect(uri, uri=True, timeout=timeout)
    return sqlite.connect(full_path, timeout=timeout)


def _current_journal_mode(connection):
    row = connection.execute("PRAGMA journal_mode").fetchone()
    return str(row[0]).lower() if row else ""


def _apply_journal_mode(connection, options):
    requested = options.journal_mode
    try:
        row = connection.execute("PRAGMA journal_mode = %s" % requested).fetchone()
        return str(row[0]).lower() if row else ""
    except sqlite.Error as exception:
        if not options.read_only:
            if getattr(exception, "sqlite_errorcode", 0) & 0xFF == 5:
                try:
                    found = _current_journal_mode(connection) or "?"
                except sqlite.Error:
                    found = "?"
                raise DriverError(errors.JOURNAL_MODE_IN_USE, richiesto=requested, effettivo=found)
            raise
        return _current_journal_mode(connection)


def open_database(url, from_settings, convert_file_url, from_document=None, names_provider=None):
    try:
        sqlite.load()
    except sqlite.LibraryError as exception:
        raise DriverError(errors.SQLITE_LIBRARY, percorso=exception.path or "-", dettaglio=exception.reason)
    split = address.split_address(url, convert_file_url)
    path = split.path
    address.check_path_text(path, url)
    from_address = address.parse_parameters(split.options, url)
    options = resolve_options(from_address, from_settings, from_document)

    full_path = os.path.abspath(path)
    created = _prepare_file(path, full_path, options)

    try:
        connection = _connect(full_path, options)
    except sqlite.Error as exception:
        raise (DriverError(errors.CANNOT_CREATE, percorso=path) if created
               else _sqlite_error(exception, path))
    warnings = []
    try:
        connection.execute("PRAGMA schema_version").fetchone()
        missing = protections.apply(connection, options)
        connection.execute("PRAGMA foreign_keys = %s" % ("ON" if options.foreign_keys else "OFF"))
        actual = _apply_journal_mode(connection, options)
        names = None
        if names_provider is not None and options.names_language != "en":
            def names():
                return names_provider(options.names_language)
        functions.install(connection, names, options.date_time_zone, options.date_time_format, full_path,
                          protections.PROFILES[options.limits_profile].get("LIKE_PATTERN_LENGTH"))
    except DriverError:
        connection.close()
        raise
    except sqlite.Error as exception:
        connection.close()
        if getattr(exception, "sqlite_errorcode", 0) == 26:
            raise DriverError(errors.NOT_A_DATABASE, percorso=path)
        raise _sqlite_error(exception, path)
    if missing:
        warnings.append(DriverError(errors.PROTECTION_NOT_OBTAINED, protezioni=", ".join(missing)))
    if created:
        warnings.append(DriverError(errors.FILE_CREATED, percorso=path))
    if actual != options.journal_mode:
        warnings.append(DriverError(errors.JOURNAL_MODE_NOT_OBTAINED,
                                    richiesto=options.journal_mode, effettivo=actual))
    return OpenedDatabase(connection, path, full_path, options, warnings)
