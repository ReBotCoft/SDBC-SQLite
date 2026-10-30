# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from sdbc_pysqlite import ddl
from sdbc_pysqlite import dialect
from sdbc_pysqlite import decimals
from sdbc_pysqlite import errors
from sdbc_pysqlite import logger
from sdbc_pysqlite import results
from sdbc_pysqlite import sqltext
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.sdbc.resultset import ResultSet


class CommandBase:

    _pretranslated = False

    def _check_open(self, method):
        if self._closed:
            raise self._error(DriverError(errors.STATEMENT_CLOSED), method)
        self._connection._check_open(method)

    def _limit(self, sql):
        limit = int(self._properties.get("MaxRows") or 0)
        if limit > 0 and sqltext.is_wrappable_query(sql):
            return "SELECT * FROM (\n%s\n) LIMIT %d" % (sqltext.strip_trailing(sql), limit)
        return sql

    def _prepare_command(self, piece, method):
        engine = self._connection._engine
        piece = dialect.translate(piece)
        if not self._pretranslated:
            translation = decimals.translate(self._connection._db, piece)
            if translation.decimal:
                piece = translation.text
                for warning in translation.warnings:
                    self._warn(warning, method)
        command = self._limit(piece)
        if sqltext.first_words(command, 1) == ["CREATE"]:
            rewritten = ddl.rewrite_create_table(command, bool(engine.options.auto_increment_reuse))
            if rewritten != command:
                logger.trace(logger.label_of(self, method), "CREATE TABLE rewritten: <%s>" % rewritten,
                             self._connection._log_code)
                command = rewritten
        return command

    def _run_one(self, piece, params, method):
        try:
            command = self._prepare_command(piece, method)
            return self._connection._engine.run(command, params)
        except DriverError as error:
            raise self._error(error, method)

    def _start(self, method):
        self._check_open(method)
        self._warnings = []
        self._queue = []
        self._position = -1

    def _make_result(self, data):
        result = ResultSet(self, data)
        self._results.append(result)
        return result

    def _warn(self, error, method):
        self._warnings.append(self._warning(error, method))

    def _close_all(self):
        self._closed = True
        for result in self._results:
            result.close()
        self._results = []
        self._queue = []

    def _query_outcome(self, outcomes, method):
        for index, outcome in enumerate(outcomes):
            if outcome.result is not None:
                self._queue = [o.result if o.result is not None else o.count for o in outcomes[index:]]
                self._position = 0
                return self._make_result(outcome.result)
        self._warn(DriverError(errors.QUERY_NO_ROWS), method)
        return self._make_result(results.memory_result([], []))

    def _update_outcome(self, outcomes, method):
        total = 0
        discarded = 0
        for outcome in outcomes:
            if outcome.writes:
                total += outcome.count
            if outcome.result is not None:
                if not outcome.writes:
                    discarded += outcome.result.store.count()
                outcome.result.close()
        if discarded:
            self._warn(DriverError(errors.UPDATE_RETURNED_ROWS, n=discarded), method)
        return total

    def _execute_outcome(self, outcomes):
        self._queue = [o.result if o.result is not None else o.count for o in outcomes]
        self._position = 0 if self._queue else -1
        return bool(self._queue) and isinstance(self._queue[0], results.ResultData)

    def _current_result(self, method):
        self._check_open(method)
        if 0 <= self._position < len(self._queue) and isinstance(self._queue[self._position], results.ResultData):
            return self._make_result(self._queue[self._position])
        return None

    def _current_count(self, method):
        self._check_open(method)
        if 0 <= self._position < len(self._queue) and not isinstance(self._queue[self._position], results.ResultData):
            return self._queue[self._position]
        return -1

    def _advance(self, method):
        self._check_open(method)
        if self._position < len(self._queue):
            self._position += 1
        return 0 <= self._position < len(self._queue) and isinstance(self._queue[self._position], results.ResultData)
