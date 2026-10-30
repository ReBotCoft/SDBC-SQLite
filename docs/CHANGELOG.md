# Changelog

This file describes the changes in the versions of **SDBC-SQLite (PySQLite)** that matter to those who use the driver. It does not list the individual technical development revisions.

---

## V1.2.0

### Manuals built into the extension

- Two manuals in HTML format are included in the `.oxt` package and can be read without an Internet connection: the **PySQLite user manual** and the guide to **exact decimals in SQL commands**.
- Added the **"?"** button in the **Diagnostic log** page of the global options and in the settings window of the Base document. The button opens the manuals in the default browser.

### Update check

- Added to the extension metadata the address of the update information file, used by LibreOffice's **Check for Updates** mechanism.

### Testing

- The automated suite now has **663 tests**, including checks for the conversion of the manuals to HTML, for opening them and for the generation of the update metadata.
- Verified in LibreOffice 26.8 on Windows 11 that the manuals open through the "?" button in the global settings and in the document settings.

---

## V1.1.0

### SQLite driver for LibreOffice Base

- Generic SDBC/SDBCX driver that lets LibreOffice Base connect to external SQLite databases, keeping the normal mechanisms of querying, editing data and access through forms.
- Distributed as an `.oxt` extension for **Windows x64**, with the **3.54.1** SQLite library included in the package: it requires neither a separate SQLite installation nor Python's `sqlite3` module.
- SQL operations, the metadata Base needs, transactions, table-structure management and SDBC/SDBCX features described in the manual.
- Multi-level configuration: driver defaults, extension settings, document settings and connection-address parameters.
- Platform declared in the extension: `windows_x86_64`, consistent with the native library distributed.

### Optional SQLite protections

- **Security** page in the extension settings and in the Base document settings, with three independent protections, all disabled by default. Whoever enables none of them notices no difference in behavior.
- **Defensive mode** (`DefensiveMode`): uses `SQLITE_DBCONFIG_DEFENSIVE` to prevent operations that are potentially dangerous for the database's internal integrity, such as direct writes to system tables. It does not prevent normal `DROP TABLE`, `DELETE` or `UPDATE` operations.
- **Untrusted schema** (`UntrustedSchema`): equivalent to `trusted_schema=OFF`, it limits the use of functions not marked as innocuous in views, triggers, constraints and other schema expressions. It can make schemas that call certain driver functions, including `NOW()`, `UUID()` and `RAND()`, unusable.
- **Safety limits** (`LimitsProfile`): profiles **None** (default), **Prudent** and **Strict**, which apply predefined sets of limits through `sqlite3_limit()`. Prudent limits, among other things, the depth of expressions and triggers, compound `SELECT`s, `LIKE` patterns, attached databases and operations per statement; Strict adds restrictions on the size of strings and BLOBs, on SQL length, on the number of columns and on parameters. Individual adjustment of the limits is not provided.
- The protections are applied to **every connection** opened by the driver, including internal connections. They are not written into the SQLite file and do not bind other programs that open the same database.
- The normal precedence of settings applies: the document and the address can also disable protections enabled at extension level. The protections are not an authentication or access-control system; for read-only access, `ReadOnly` and operating-system permissions remain the relevant tools.
- The limit profiles do not impose an overall memory ceiling, do not interrupt slow queries and do not enforce the declared length of `VARCHAR(n)` fields.

### Warnings and diagnostics

- Warning **50.107** for requested protections that the SQLite library could not apply: the connection opens anyway and the user is informed of the protections not obtained.
- Warning **50.106** when the requested journal mode was not obtained; with defensive mode active, for example, the `off` journal is refused and the previous mode remains.
- The manual describes the incompatibilities of the untrusted schema with the non-deterministic functions used in views, triggers, constraints and schema expressions.

### LIKE comparison

- The `LIKE` comparison uses a linear-complexity algorithm: patterns with many `%` characters no longer cause slowdowns of several seconds.
- The maximum length of the `LIKE` pattern (5,000 bytes) is enforced only when a safety profile that provides for it is selected.

### Testing

- **644 automated tests** were run, covering the SQLite protections and the `LIKE` comparison, also with the **Strict** profile active.
- Tests in LibreOffice 26.8 on Windows 11: installation, Security page, configuration of the protections, warnings about the journal mode, expected errors for non-innocuous functions in the schema, and `LIKE` behavior.
- The documented tests do not constitute a security certification nor guarantee compatibility with every possible database or external configuration.
