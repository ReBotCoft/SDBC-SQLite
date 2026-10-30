# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os

import uno
import unohelper

from com.sun.star.sdbc import XDatabaseMetaData

from sdbc_pysqlite import IDENTIFIER
from sdbc_pysqlite import errors
from sdbc_pysqlite import results
from sdbc_pysqlite import schema
from sdbc_pysqlite import sqlite
from sdbc_pysqlite import sqltext
from sdbc_pysqlite import typesystem as ts
from sdbc_pysqlite.common import ErrorMixin
from sdbc_pysqlite.common import extension_version
from sdbc_pysqlite.common import version_part
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite.logger import traced
from sdbc_pysqlite.sdbc.resultset import ResultSet



def _optional_interface(name):
    try:
        module = __import__("com.sun.star.sdbc", fromlist=[name])
        return getattr(module, name)
    except (ImportError, AttributeError):
        return object


_INTERFACE = next((i for i in (_optional_interface("XDatabaseMetaData3"),
                               _optional_interface("XDatabaseMetaData2")) if i is not object),
                  XDatabaseMetaData)

_NUMBERS = {-6, 5, 4, -5, 6, 7, 8, 2, 3}
_TEXTS = {1, 12, -1}
_MOMENTS = {91, 92, 93}
_BINARIES = {-2, -3, -4}
_BOOLEAN = {16}


def _sensible(from_type, to_type):
    if from_type == to_type:
        return True
    pairs = ((_NUMBERS, _NUMBERS), (_NUMBERS, _TEXTS), (_TEXTS, _NUMBERS), (_MOMENTS, _TEXTS),
             (_TEXTS, _MOMENTS), (_MOMENTS, _MOMENTS), (_BINARIES, _BINARIES), (_BOOLEAN, _NUMBERS),
             (_NUMBERS, _BOOLEAN), (_BOOLEAN, _TEXTS), (_TEXTS, _BOOLEAN), (_TEXTS, _TEXTS),
             (_TEXTS, _BINARIES), (_BINARIES, _TEXTS))
    return any(from_type in a and to_type in b for a, b in pairs)


@traced
class DatabaseMetaData(unohelper.Base, _INTERFACE, ErrorMixin):

    def __init__(self, connection):
        self._connection = connection

    def _list(self, layout_and_rows):
        declared, rows = layout_and_rows
        return ResultSet(None, results.memory_result(declared, rows), self._connection)

    @property
    def _db(self):
        return self._connection._db

    def getURL(self):
        return self._connection._url

    def isReadOnly(self):
        path = self._connection._full_path
        return bool(self._connection._options.read_only) or (
            bool(path) and os.path.exists(path) and not os.access(path, os.W_OK))

    def getDatabaseProductVersion(self):
        return sqlite.sqlite_version

    def getDriverVersion(self):
        return extension_version(self._connection._ctx)

    def getDriverMajorVersion(self):
        return version_part(self.getDriverVersion(), 0)

    def getDriverMinorVersion(self):
        return version_part(self.getDriverVersion(), 1)

    def getDatabaseMajorVersion(self):
        return sqlite.sqlite_version_info[0]

    def getDatabaseMinorVersion(self):
        return sqlite.sqlite_version_info[1]

    def getSQLKeywords(self):
        return schema.SQL_KEYWORDS

    def getNumericFunctions(self):
        return schema.function_names(self._db, "numeric")

    def getStringFunctions(self):
        return schema.function_names(self._db, "string")

    def getSystemFunctions(self):
        return schema.function_names(self._db, "system")

    def getTimeDateFunctions(self):
        return schema.function_names(self._db, "time")

    def supportsConvert(self, fromType, toType):
        return _sensible(fromType, toType)

    def supportsTransactionIsolationLevel(self, level):
        return level == 8

    def supportsResultSetType(self, setType):
        return setType in (1003, 1004)

    def supportsResultSetConcurrency(self, setType, concurrency):
        return setType in (1003, 1004) and concurrency == 1007

    def ownUpdatesAreVisible(self, setType):
        return False

    def ownDeletesAreVisible(self, setType):
        return False

    def ownInsertsAreVisible(self, setType):
        return False

    def othersUpdatesAreVisible(self, setType):
        return False

    def othersDeletesAreVisible(self, setType):
        return False

    def othersInsertsAreVisible(self, setType):
        return False

    def updatesAreDetected(self, setType):
        return False

    def deletesAreDetected(self, setType):
        return False

    def insertsAreDetected(self, setType):
        return False

    def getConnection(self):
        return self._connection

    def getConnectionInfo(self):
        properties = []
        for name, value in self._connection._info:
            item = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            item.Name = name
            item.Value = value
            properties.append(item)
        return tuple(properties)

    def getTables(self, catalog, schemaPattern, tableNamePattern, types):
        return self._list(schema.tables_rows(self._db, tableNamePattern, types))

    def getTableTypes(self):
        return self._list(schema.table_types_rows())

    def getCatalogs(self):
        return self._list(schema.catalogs_rows())

    def getSchemas(self):
        return self._list(schema.schemas_rows())

    def getColumns(self, catalog, schemaPattern, tableNamePattern, columnNamePattern):
        return self._list(schema.columns_rows(self._db, tableNamePattern, columnNamePattern))

    def getTypeInfo(self):
        return self._list(schema.type_info_rows())

    def getPrimaryKeys(self, catalog, schema_name, table):
        return self._list(schema.primary_keys_rows(self._db, table))

    def getImportedKeys(self, catalog, schema_name, table):
        return self._list(schema.imported_keys_rows(self._db, table))

    def getExportedKeys(self, catalog, schema_name, table):
        return self._list(schema.exported_keys_rows(self._db, table))

    def getCrossReference(self, primaryCatalog, primarySchema, primaryTable,
                          foreignCatalog, foreignSchema, foreignTable):
        return self._list(schema.cross_reference_rows(self._db, primaryTable, foreignTable))

    def getIndexInfo(self, catalog, schema_name, table, unique, approximate):
        return self._list(schema.index_info_rows(self._db, table, unique))

    def getBestRowIdentifier(self, catalog, schema_name, table, scope, nullable):
        return self._list(schema.best_row_identifier_rows(self._db, table))

    def getFunctions(self, catalog, schemaPattern, functionNamePattern):
        return self._list(schema.functions_rows(self._db, functionNamePattern))

    def getTablePrivileges(self, catalog, schemaPattern, tableNamePattern):
        return self._list(schema.table_privileges_rows(
            self._db, tableNamePattern, self.getUserName(), not self.isReadOnly()))

    def getVersionColumns(self, catalog, schema_name, table):
        return self._list(schema.empty_rows("version_columns"))

    def getColumnPrivileges(self, catalog, schema_name, table, columnNamePattern):
        return self._list(schema.empty_rows("column_privileges"))

    def getProcedures(self, catalog, schemaPattern, procedureNamePattern):
        return self._list(schema.empty_rows("procedures"))

    def getProcedureColumns(self, catalog, schemaPattern, procedureNamePattern, columnNamePattern):
        return self._list(schema.empty_rows("procedure_columns"))

    def getUDTs(self, catalog, schemaPattern, typeNamePattern, types):
        return self._list(schema.empty_rows("udts"))

    def getFunctionColumns(self, *arguments):
        return self._list(schema.empty_rows("function_columns"))

    def getPseudoColumns(self, *arguments):
        return self._list(schema.empty_rows("pseudo_columns"))

    def getSchemasFiltered(self, *arguments):
        return self._list(schema.empty_rows("schemas_filtered"))

    def getSuperTables(self, *arguments):
        return self._list(schema.empty_rows("super_tables"))

    def getSuperTypes(self, *arguments):
        return self._list(schema.empty_rows("super_types"))

    def getAttributes(self, *arguments):
        return self._list(schema.empty_rows("attributes"))

    def getClientInfoProperties(self):
        return self._list(schema.empty_rows("client_info"))

    def allProceduresAreCallable(self):
        return False

    def allTablesAreSelectable(self):
        return True

    def nullsAreSortedHigh(self):
        return False

    def nullsAreSortedLow(self):
        return True

    def nullsAreSortedAtStart(self):
        return False

    def nullsAreSortedAtEnd(self):
        return False

    def getDatabaseProductName(self):
        return 'SQLite'

    def getDriverName(self):
        return 'SDBC SQLite (pysqlite)'

    def usesLocalFiles(self):
        return True

    def usesLocalFilePerTable(self):
        return False

    def supportsMixedCaseIdentifiers(self):
        return False

    def storesUpperCaseIdentifiers(self):
        return False

    def storesLowerCaseIdentifiers(self):
        return False

    def storesMixedCaseIdentifiers(self):
        return True

    def supportsMixedCaseQuotedIdentifiers(self):
        return False

    def storesUpperCaseQuotedIdentifiers(self):
        return False

    def storesLowerCaseQuotedIdentifiers(self):
        return False

    def storesMixedCaseQuotedIdentifiers(self):
        return True

    def getIdentifierQuoteString(self):
        return '"'

    def getSearchStringEscape(self):
        return '\\'

    def getExtraNameCharacters(self):
        return '$'

    def supportsAlterTableWithAddColumn(self):
        return True

    def supportsAlterTableWithDropColumn(self):
        return True

    def supportsColumnAliasing(self):
        return True

    def nullPlusNonNullIsNull(self):
        return True

    def supportsTypeConversion(self):
        return True

    def supportsTableCorrelationNames(self):
        return True

    def supportsDifferentTableCorrelationNames(self):
        return False

    def supportsExpressionsInOrderBy(self):
        return True

    def supportsOrderByUnrelated(self):
        return True

    def supportsGroupBy(self):
        return True

    def supportsGroupByUnrelated(self):
        return True

    def supportsGroupByBeyondSelect(self):
        return True

    def supportsLikeEscapeClause(self):
        return True

    def supportsMultipleResultSets(self):
        return True

    def supportsNonNullableColumns(self):
        return True

    def supportsIntegrityEnhancementFacility(self):
        return True

    def supportsSelectForUpdate(self):
        return False

    def supportsStoredProcedures(self):
        return False

    def supportsPositionedDelete(self):
        return False

    def supportsPositionedUpdate(self):
        return False

    def supportsMinimumSQLGrammar(self):
        return True

    def supportsCoreSQLGrammar(self):
        return True

    def supportsExtendedSQLGrammar(self):
        return False

    def supportsANSI92EntryLevelSQL(self):
        return True

    def supportsANSI92IntermediateSQL(self):
        return False

    def supportsANSI92FullSQL(self):
        return False

    def supportsOuterJoins(self):
        return True

    def supportsFullOuterJoins(self):
        return True

    def supportsLimitedOuterJoins(self):
        return True

    def supportsSubqueriesInComparisons(self):
        return True

    def supportsSubqueriesInExists(self):
        return True

    def supportsSubqueriesInIns(self):
        return True

    def supportsSubqueriesInQuantifieds(self):
        return False

    def supportsCorrelatedSubqueries(self):
        return True

    def supportsUnion(self):
        return True

    def supportsUnionAll(self):
        return True

    def getSchemaTerm(self):
        return ''

    def getProcedureTerm(self):
        return ''

    def getCatalogTerm(self):
        return ''

    def isCatalogAtStart(self):
        return False

    def getCatalogSeparator(self):
        return ''

    def supportsSchemasInDataManipulation(self):
        return False

    def supportsSchemasInProcedureCalls(self):
        return False

    def supportsSchemasInTableDefinitions(self):
        return False

    def supportsSchemasInIndexDefinitions(self):
        return False

    def supportsSchemasInPrivilegeDefinitions(self):
        return False

    def supportsCatalogsInDataManipulation(self):
        return False

    def supportsCatalogsInProcedureCalls(self):
        return False

    def supportsCatalogsInTableDefinitions(self):
        return False

    def supportsCatalogsInIndexDefinitions(self):
        return False

    def supportsCatalogsInPrivilegeDefinitions(self):
        return False

    def getMaxBinaryLiteralLength(self):
        return 1000000000

    def getMaxCharLiteralLength(self):
        return 1000000000

    def getMaxColumnNameLength(self):
        return 0

    def getMaxColumnsInGroupBy(self):
        return 2000

    def getMaxColumnsInIndex(self):
        return 2000

    def getMaxColumnsInOrderBy(self):
        return 2000

    def getMaxColumnsInSelect(self):
        return 2000

    def getMaxColumnsInTable(self):
        return 2000

    def getMaxConnections(self):
        return 0

    def getMaxCursorNameLength(self):
        return 0

    def getMaxIndexLength(self):
        return 0

    def getMaxSchemaNameLength(self):
        return 0

    def getMaxProcedureNameLength(self):
        return 0

    def getMaxCatalogNameLength(self):
        return 0

    def getMaxRowSize(self):
        return 1000000000

    def doesMaxRowSizeIncludeBlobs(self):
        return True

    def getMaxStatementLength(self):
        return 1000000000

    def getMaxStatements(self):
        return 0

    def getMaxTableNameLength(self):
        return 0

    def getMaxTablesInSelect(self):
        return 64

    def getMaxUserNameLength(self):
        return 0

    def getDefaultTransactionIsolation(self):
        return 8

    def supportsTransactions(self):
        return True

    def supportsMultipleTransactions(self):
        return True

    def supportsDataDefinitionAndDataManipulationTransactions(self):
        return True

    def supportsDataManipulationTransactionsOnly(self):
        return False

    def dataDefinitionCausesTransactionCommit(self):
        return False

    def dataDefinitionIgnoredInTransactions(self):
        return False

    def supportsOpenCursorsAcrossCommit(self):
        return True

    def supportsOpenCursorsAcrossRollback(self):
        return True

    def supportsOpenStatementsAcrossCommit(self):
        return True

    def supportsOpenStatementsAcrossRollback(self):
        return True

    def supportsBatchUpdates(self):
        return True

    def getUserName(self):
        return ''

    def autoCommitFailureClosesAllResultSets(self):
        return False

    def generatedKeyAlwaysReturned(self):
        return False

    def locatorsUpdateCopy(self):
        return False

    def supportsConvertInGeneral(self):
        return True

    def supportsGetGeneratedKeys(self):
        return True

    def supportsMultipleOpenResults(self):
        return False

    def supportsNamedParameters(self):
        return False

    def supportsRefCursors(self):
        return False

    def supportsSavepoints(self):
        return True

    def supportsSharding(self):
        return False

    def supportsStatementPooling(self):
        return False

    def supportsStoredFunctionsUsingCallSyntax(self):
        return False

    def getMaxLogicalLobSize(self):
        return 1000000000

    def getResultSetHoldability(self):
        return 1

    def getRowIdLifetime(self):
        return 0

    def getSQLStateType(self):
        return 2
