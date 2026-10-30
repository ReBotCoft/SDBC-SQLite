# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import functools
import logging
import logging.handlers
import os
import secrets
import tempfile
import threading

import unohelper

from sdbc_pysqlite import LOG_FILE_NAME
from sdbc_pysqlite.configuration import read_settings

TRACE = 5
logging.addLevelName(TRACE, "TRACE")
INFO = 25
logging.addLevelName(INFO, "INFO")

_PACKAGE_PREFIX = "sdbc_pysqlite."
_MAX_ARGUMENT_LENGTH = 10000

_logger = logging.getLogger("sdbc_pysqlite")
_logger.propagate = False
_logger.addHandler(logging.NullHandler())
_logger.setLevel(logging.ERROR)

_lock = threading.Lock()
_state = {"trace": False, "file": None, "days": None, "handler": None}


class _Handler(logging.handlers.TimedRotatingFileHandler):

    def handleError(self, record):
        pass


def new_connection_code():
    return secrets.token_hex(3)


DEFAULT_SUBFOLDER = "sdbc-pysqlite"


def default_folder(ctx):
    try:
        substitution = ctx.ServiceManager.createInstanceWithContext("com.sun.star.util.PathSubstitution", ctx)
        profile = unohelper.fileUrlToSystemPath(substitution.getSubstituteVariableValue("$(user)"))
        folder = os.path.join(profile, DEFAULT_SUBFOLDER)
        os.makedirs(folder, exist_ok=True)
        return folder
    except Exception:
        return tempfile.gettempdir()


def _log_file(log_path, ctx):
    folder = log_path.strip() if log_path else default_folder(ctx)
    return os.path.join(folder, LOG_FILE_NAME)


def log_folder():
    log_file = _state["file"]
    return os.path.dirname(log_file) if log_file else tempfile.gettempdir()


def configure(ctx):
    settings = read_settings(ctx)
    log_file = _log_file(settings.log_path, ctx)
    with _lock:
        if (log_file, settings.retention_days) != (_state["file"], _state["days"]):
            old = _state["handler"]
            if old is not None:
                _logger.removeHandler(old)
                old.close()
            handler = _Handler(log_file, when="midnight", backupCount=settings.retention_days,
                               encoding="utf-8", delay=True)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(code)s | %(label)s | %(message)s"))
            _logger.addHandler(handler)
            _state.update(file=log_file, days=settings.retention_days, handler=handler)
        _state["trace"] = settings.trace
        _logger.setLevel(TRACE if settings.trace else INFO)
    if settings.error:
        error("logger.configure", settings.error)
    return settings


def check_writable():
    log_file = _state["file"]
    if log_file is None:
        raise OSError("registro non configurato")
    folder = os.path.dirname(log_file)
    os.makedirs(folder, exist_ok=True)
    with open(log_file, "a", encoding="utf-8"):
        pass


def trace(label, message, code=""):
    if _state["trace"]:
        _logger.log(TRACE, message, extra={"label": label, "code": code})


def error(label, message, code=""):
    _logger.error(message, extra={"label": label, "code": code})


def warning(label, message, code=""):
    _logger.warning(message, extra={"label": label, "code": code})


def info(label, message, code=""):
    _logger.log(INFO, message, extra={"label": label, "code": code})


def _label(obj, method):
    module = type(obj).__module__
    if module.startswith(_PACKAGE_PREFIX):
        module = module[len(_PACKAGE_PREFIX):]
    return "%s.%s.%s" % (module, type(obj).__name__, method)


def label_of(obj, method):
    return _label(obj, method)


def _connection_code(obj):
    for _ in range(4):
        code = getattr(obj, "_log_code", None)
        if code:
            return code
        obj = getattr(obj, "_connection", None) or getattr(obj, "_statement", None)
        if obj is None:
            break
    return ""


def _short(value):
    text = repr(value)
    if len(text) > _MAX_ARGUMENT_LENGTH:
        text = text[:_MAX_ARGUMENT_LENGTH] + "..."
    return text


def _exception_text(exception):
    message = getattr(exception, "Message", None)
    return "%s: %s" % (type(exception).__name__, message if message else exception)


def _is_sql_exception(exception):
    try:
        from com.sun.star.sdbc import SQLException
    except ImportError:
        return False
    return isinstance(exception, SQLException)


def _wrap(name, function):
    @functools.wraps(function)
    def wrapper(self, *args, **kwargs):
        label = _label(self, name)
        code = _connection_code(self)
        if _state["trace"]:
            _logger.log(TRACE, "(%s)" % ", ".join(_short(a) for a in args),
                        extra={"label": label, "code": code})
        try:
            return function(self, *args, **kwargs)
        except Exception as exception:
            if not _is_sql_exception(exception):
                error(label, _exception_text(exception), code)
            raise
    return wrapper


def traced(cls):
    for name, member in list(vars(cls).items()):
        if not name.startswith("_") and callable(member):
            setattr(cls, name, _wrap(name, member))
    return cls
