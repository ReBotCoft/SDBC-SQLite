# SDBC Driver for SQLite (LibreOffice Base)

A generic driver, written in Python and distributed as an `.oxt` extension, that lets LibreOffice Base use an external SQLite file. The engine is an official SQLite (3.54.1) that ships inside the extension: the driver depends neither on the `sqlite3` module of LibreOffice's Python nor on LibreOffice's `sqlite3.dll`.

> **Notice.** This software is free, experimental and provided "as is", without any warranty. You use it at your own risk, including the risk of data loss or corruption. Always work on a backup copy of your database. To the maximum extent permitted by law, the author is not liable for any damage arising from its use. No support, maintenance or future compatibility is promised.

## Installing the extension

The driver requires **64-bit Windows** with **LibreOffice 26.8 or later**; nothing else needs to be installed (SQLite is already inside the extension, no Java).

1. Close LibreOffice.
2. Double-click the `SDBC-SQLite.oxt` file, or open LibreOffice and choose *Tools → Extensions… → Add*.
3. Accept the license and choose whom to install for.
4. Close and reopen LibreOffice (including the Quickstarter icon, if any).

Then create the connection to a SQLite file as described in "What to enter in the Base wizard". If something does not work, the extension settings (*Edit → Database → PySQLite settings…*) have an "Open the log" button. Before using real data, work on a copy of the database.

## What to enter in the Base wizard

1. *File → New → Database*, choose **Connect to an existing database** and the type **PySQLite SDBC**, then *Next*.
2. In the connection field write **any text after the prefix** (for example `placeholder`): the wizard does not accept it empty, but the real path is chosen afterwards, in the settings.
3. *Finish* and save the `.odb` document.
4. On first opening a guided message appears explaining that the file does not exist yet: this is normal.
5. *Edit → Database → PySQLite settings…*, category **Database access**: enter the address (with **Open…** for an existing file or **New…** to prepare a file; the suggested extension is `.db3`) and choose "yes" in **Create the database if it does not exist**. *OK*.
6. Save, close and reopen the document: the file is created and the message "The new database has been created." appears.

Settings can be defined in the connection address, in the document, in LibreOffice's global options or through the driver's default values. For the precedence between levels and the description of the options, see the manual.

## Optional SQLite protections

The **Security** page in the global and document settings lets you configure three independent protections, all disabled by default:

- **Defensive mode (`DefensiveMode`)**: limits operations that could compromise the database's internal structures, without preventing `DROP TABLE`, `DELETE` or `UPDATE`.
- **Untrusted schema (`UntrustedSchema`)**: limits the functions that can be used in views, triggers, constraints and other schema expressions. It can make schemas that depend on functions not marked as innocuous unusable.
- **Safety limits (`LimitsProfile`)**: profiles `none` (None), `prudent` (Prudent) and `strict` (Strict); individual custom limits are not provided. The Strict profile can prevent operations on particularly large BLOBs or very wide tables.

The protections act **on connections opened through PySQLite**, are not written into the `.db3` file and do not bind other programs that access the same database. They follow the normal priority of settings: a document can also disable protections chosen at global level. They do not replace operating-system permissions or `ReadOnly=true`. If a requested protection cannot be applied, the connection is opened anyway and warning **50.107** is shown. For details, profile values and incompatibilities, see the manual.

The `LIKE` comparison also handles patterns with many `%` characters efficiently.

## Known limitations

- The driver is meant to work on the file with **one program at a time**: several programs can read together, but SQLite allows only one write at a time, and the second one to write may receive a database-busy error.
- If **two people or programs modify the same row**, the last one to save wins, without warning.
- Beyond **50,000 rows** (threshold adjustable in the settings) results are read in blocks: if another program changes the table while it is open, rows may shift or the driver asks you to refresh the list. In forms, press "Refresh" before editing.
- **True read-only** access is obtained only with the `ReadOnly=true` parameter in the address or with the setting in the Options; a read-only request made by a macro is only a hint.
- **Tables without a primary key** are read-only; some HSQLDB functions are not implemented; `ATTACH` is not available from Base's interface.
- Functions and comparisons taught by the driver **do not exist** if the same file is opened with another program.

Usage limitations, diagnostic messages and possible solutions are described in the manual.

## Requirements

**Supported systems:** 64-bit Windows (x64) with LibreOffice 26.8 or later.

**Verified environment:** Windows 11 Pro and LibreOffice 26.8 (Python 3.13). Compatibility with 64-bit Windows 10 and with later versions of LibreOffice has not been verified.

**Not supported:** 32-bit Windows, Windows on ARM processors, Linux and macOS. On these systems the driver does not start and says so with a message.

**SQLite included in the extension.** The package includes SQLite 3.54.1 and does not require installing the SQLite engine or Python separately. The bundled library is for Windows x64; the extension does not use the system SQLite library.

## License

GNU Lesser General Public License, version 3 or later. The text is in `extension/registration/license_en.txt`. The SQLite DLL that ships with the extension is not covered by this license: SQLite is in the public domain (text in `extension/service/pythonpath/sdbc_pysqlite/native/win-x64/LICENSE-SQLite.txt`). The icons were created by the author with the help of an artificial-intelligence image tool, starting from a prompt written by the author. The full notice on licenses and on the origin of the components is in the `NOTICE` file in the root.
