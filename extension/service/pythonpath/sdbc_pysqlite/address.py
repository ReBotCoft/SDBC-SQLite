# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from collections import namedtuple

from sdbc_pysqlite import URL_PREFIX
from sdbc_pysqlite import errors
from sdbc_pysqlite import parameters
from sdbc_pysqlite.errors import DriverError

SplitAddress = namedtuple("SplitAddress", "path options")

_FORBIDDEN = '<>"|?*'


def _strip_quotes(text):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return text


def _inner(url):
    text = url.strip()
    while text.startswith(URL_PREFIX):
        text = text[len(URL_PREFIX):]
    return _strip_quotes(text)


def display_text(url):
    text = url.strip()
    while text.startswith(URL_PREFIX):
        text = text[len(URL_PREFIX):]
    return text


def full_address(text, convert_file_url):
    split = split_address(text, convert_file_url)
    return URL_PREFIX + split.path + ("?" + split.options if "?" in _inner(text) else "")


def split_address(url, convert_file_url):
    text = _inner(url)
    path, _, options = text.partition("?")
    path = _strip_quotes(path)
    if path.startswith("file:"):
        try:
            path = convert_file_url(path)
        except Exception:
            raise DriverError(errors.ADDRESS_INVALID, indirizzo=url)
    return SplitAddress(path, options)


def bad_characters(path):
    found = []
    for index, char in enumerate(path):
        wrong = char in _FORBIDDEN or ord(char) < 32
        if char == ":" and index != 1:
            wrong = True
        if char == ":" and index == 1 and not path[0].isalpha():
            wrong = True
        if wrong:
            shown = char if ord(char) >= 32 else "\\x%02x" % ord(char)
            if shown not in found:
                found.append(shown)
    return found


def check_path_text(path, url):
    if not path.strip():
        raise DriverError(errors.ADDRESS_INVALID, indirizzo=url)
    wrong = bad_characters(path)
    if wrong:
        raise DriverError(errors.PATH_BAD_CHARACTERS, percorso=path, caratteri=" ".join(wrong))


def parse_parameters(options, url):
    found = {}
    for group in options.split("&"):
        if group == "":
            continue
        if "=" not in group:
            raise DriverError(errors.PARAMETER_NO_EQUALS, gruppo=group, indirizzo=url)
        name, _, text = group.partition("=")
        if name not in parameters.PARAMETER_NAMES:
            raise DriverError(errors.UNKNOWN_PARAMETER, nome=name, indirizzo=url,
                              ammessi=", ".join(parameters.PARAMETER_NAMES))
        if name in found:
            raise DriverError(errors.PARAMETER_REPEATED, nome=name, indirizzo=url)
        try:
            found[name] = parameters.convert(name, text)
        except parameters.InvalidValue:
            raise DriverError(errors.INVALID_VALUE, nome=name, valore=text, indirizzo=url)
    return found


def check_address(url, convert_file_url):
    split = split_address(url, convert_file_url)
    check_path_text(split.path, url)
    parse_parameters(split.options, url)


def with_path(url, new_path):
    _, question, options = _inner(url).partition("?")
    return new_path + (question + options if question else "")


DEFAULT_EXTENSION = ".db3"


def with_default_extension(path):
    name = path.replace("/", "\\").rsplit("\\", 1)[-1]
    if not name or "." in name.lstrip("."):
        return path
    return path + DEFAULT_EXTENSION
