# **PySQLite — User Manual for LibreOffice Base**

## **Contents**

**0. Introduction**

**1. Getting started**

**2. Settings**

**3. Using Base together with PySQLite**

**4. Known limitations**

**5. Messages and diagnostic log**

**6. Appendices**

## **0. Introduction**

PySQLite is an extension that integrates the SQLite database engine into LibreOffice Base. It is mainly a *driver*, which acts as a communication interface between the two applications and "translates" the application's requests into the operations needed to read and write data.

The driver is written in Python and runs on the interpreter supplied by default with LibreOffice. It implements the SDBC (StarOffice Database Connectivity) interface, which LibreOffice presents as the communication contract for all database engines; every command to the database arrives from Base through this interface, the driver intercepts it and translates it into SQL, and then passes it to the SQLite engine, which carries out all the access, reading and writing operations.

In fact SQLite does not have a real engine that starts its own server instance; it is essentially a set of libraries, which are supplied embedded in the extension itself, so no additional component needs to be installed.

Using the driver does not require any knowledge of Python: you can start working in the Base+SQLite environment from the very first moment after installation, using the normal commands of the graphical interface to create and manage tables, queries, forms and the other tools, at least in their most ordinary use. For these reasons, knowing the SQL language is not essential either, although it is advisable to study the subject, since Base's own interface allows the use of direct SQL commands both through a dedicated dialog window and inside queries, as well as through macros written in StarBasic.

### **0.1. The Base document and the SQLite database**

It is essential for the user to understand that with this extension the database file remains external to, and distinct from, the Base document file.

In particular, the **Base document**, recognizable by the `.odb` extension, is the file that opens in LibreOffice; it keeps the connection data and the database settings, along with any forms, queries and reports.

The **SQLite file**, on the other hand, contains the tables and the data. Being external to the Base document, it can also be used by other compatible programs. In line with what SQLite's online help says, its extension does not determine the format of the data it contains: names such as `archivio.db3`, `archivio.sqlite` and `archivio.db` are equally accepted by SQLite (and by Base).

This distinction is essential because when you save a document in Base's interface, you are acting only on the .odb file, that is, on settings, forms, queries, reports and macros. Saving data to the database, on the other hand, is entirely separate from Base's interface, and works according to mechanisms managed by the joint action of the driver and the SQLite engine.

On the other hand, the two paths can be managed completely independently: the database can be placed in a location entirely distinct from the Base document, which will keep using it without particular problems, provided that the address given in the document settings window is always up to date (see chapter 2).

## **1. Getting started**

To begin, you need to install the extension and create a Base document linked to a SQLite file. The SQLite file may already exist or be created by the driver. The instructions that follow use two example names: `Archivio.odb` for the Base document and `archivio.db3` for the database. The names and folders can be chosen freely: the two files do not necessarily have to be in the same folder.

### **1.1. Installing the extension**

Installation requires the `SDBC-SQLite.oxt` package. The driver requires 64-bit Windows (x64) and LibreOffice 26.8 or later. It has been verified with Windows 11 Pro and LibreOffice 26.8 (Python 3.13); 64-bit Windows 10 and later versions of LibreOffice have not been verified. 32-bit Windows, ARM processors, Linux and macOS are not supported.

The Python interpreter is supplied with LibreOffice and the SQLite engine is included in the extension: no additional components need to be installed.

Installation can be started by double-clicking the file or, from LibreOffice, by opening **Tools → Extensions…** and pressing **Add**.

Follow the instructions in the installation window. When it finishes, close LibreOffice completely, including the Quickstarter if present, and reopen it.

The extension adds the database type **PySQLite SDBC** to Base's wizard and makes its own settings available, which are covered in depth in chapter 2.

### **1.2. Limits of the wizard for the first creation of the document**

When a new Base document is created, a wizard is shown immediately that helps the user define the document's first settings, above all those concerning the database engine used. Although the list of available engines is substantial, the current LibreOffice implementation (26.8.1) does not allow the wizard itself to be customized when a new engine is to be added. For external engines the wizard presents a generic interface, with limited and in some cases mandatory configuration options, such as the address (path of the database file), without which the wizard does not let you continue.

When creating the Base document, therefore, the user may enter data that is not necessarily true or consistent, and postpone the refinement of the settings until the document has been created, once the wizard is complete. The **PySQLite settings** window allows, among other things, the path of the database file to be specified.

Note: in the wizard's address field it is therefore possible to enter a provisional text, sufficient to enable the next step. It is still possible to enter a complete, valid path right away. The connection settings can also be changed later from the same window.

### **1.3. Creating the Base document**

Open **File → New → Database**. LibreOffice starts the guided creation of the document.

Choose **Connect to an existing database** and select **PySQLite SDBC** in the list of available types.

The wording "existing database" can be misleading: in this case it serves to choose the engine and not the specific file, which may not exist yet.

Continue to the address screen and enter a provisional text. As described in the previous section, the path will be defined after the document is saved. If instead the file already exists, for example:

`C:\Dati\archivio.db3`

you can specify it at this stage too; continue to the last screen, where you can choose whether to register the database in LibreOffice and whether to open the document for editing.

Registration makes the data source available to the other LibreOffice documents as well; it does not create the SQLite file.

Press **Finish**. In the save window choose the name of the Base document, for example `Archivio.odb`.

**This step saves the Base document, not the file that will contain the tables and the data.**

### **1.4. Completing the connection**

When Base requests the first access to the data, the driver tries to connect to the specified file. This can happen at the end of the wizard or, later, by selecting **Tables** in the document window.

If a provisional text was entered or the file does not exist yet, a message appears reporting that the database cannot be opened and indicating how to proceed. In the path just described it is a consequence of the connection still being incomplete.

Close the message and open **Edit → Database → PySQLite settings…**. Select the category **Database access**.

From here you can connect an existing file or prepare the creation of a new one.

### **1.4.1. Connecting an existing SQLite file**

If the database file already exists, pressing **Open…** lets you select its path and enter it in the address bar. The file must contain a valid SQLite database. The file name extension is neither sufficient nor necessary to identify its content: the selector proposes the most common extensions and also lets you display all files. In this specific case the option **Create the database if it does not exist** has no effect.

### **1.4.2. Preparing a new SQLite file**

If, instead, the file does not exist, the driver can create a brand-new one: press **New…** and specify a path including the name, and the extension too if you wish. With the default filter, if no extension is specified, `.db3` is added. This command prepares the address of the new file. The actual creation will take place when the driver tries to connect for the first time. However, creation itself is available only if the **Create the database if it does not exist** setting is enabled. In that case the driver, besides the file, will also try to create any folders of the path that do not exist yet, provided it has the necessary permissions. If the setting is disabled, the subsequent connection will generate an error.

### **1.5. Saving and applying the settings**

After configuring the connection, confirm with **OK**, save the Base document, close it and reopen it. Changes to the document settings require this step to take effect. To make the first connection, select **Tables**. If an existing file was connected, Base shows its available tables. If a new file was prepared and its creation was enabled, the driver creates it and shows a notice that it has been created. Since there are no tables yet, the corresponding area will initially be empty. In all other cases, if an error appears, consult the documentation supplied with the extension.

### **1.6. Setting everything from the wizard**

A quick way to skip steps in creating the document is to enter in the wizard's address bar the path of the database file you want to create, followed by a suitable settings string, for example:

`C:\Dati\archivio.db3?CreateIfMissing=true`

In this case the first connection attempt at the end of the wizard will create the file immediately, with no intermediate steps, and will produce the notice that it has been created. This string introduces the parameters of the connection line, which will be covered in the relevant chapter.

## **2. Settings**

It is essential for the user to understand the logic with which the driver manages settings, above all how the driver presents them to the user. The same settings can appear in several places in Base's interface, giving rise to possible ambiguity. The interface essentially presents two windows: the one for the extension's global settings and the one for the document's settings. The logic, however, is organized into four levels with distinct precedence:

### **2.1. The four priority levels**

The settings are defined according to four levels, numbered from 0 to 3: that is, the same setting is redefined at each of these four levels, and what is set at each level prevails over the previous ones.

### **2.1.1. Level 0 — Driver default values**

These can be likened to the driver's "factory settings", and are hard-coded in its implementation code: they are default values that make up the base configuration, and are used when there is no indication in the following levels. They can also be recalled from both settings windows.

### **2.1.2. Level 1 — Global extension settings**

They can be reached in two ways:

Tools -> Extensions... then select the SQLite (pysqlite) SDBC Driver extension in the window and press the Options button  
Tools -> Options... then expand the SQLite (pysqlite) SDBC node in the navigation tree on the left

At first installation the extension's settings repeat the driver's default values. They can be customized and have global validity: they apply to all Base documents that use PySQLite and that do not have a choice of their own (see level 2). For this reason they are saved in the LibreOffice user profile and not in the individual document. Their value is not copied into the documents: when a document leaves **Extension default**, at each opening it uses the global value in force at that moment. Their nature as a global property will become clearer with the next level.

Among these, the diagnostic log settings stand out: they manage the activity log and cannot be of a higher level because the driver writes a single log file common to all documents.

### **2.1.3. Level 2 — Document settings**

Accessible from the additional menu that the extension installed:

Edit -> Database -> PySQLite settings...

Level 2 consists of the document's personal settings, saved inside its own file and kept across later reopenings; they overwrite all previous levels, although for most of them the interface offers a default value, shown as:

Extension default (<current level 1 value>)

with which the driver is explicitly told to take over the level 1 value.

Among these, the address bar stands out: it cannot belong to a lower level, since every Base document must define its own database address.

### **2.1.4. Level 3 — Parameters in the connection address**

The path entered in the address bar can actually contain additional information to be communicated to the driver through a dedicated syntax; it does not matter from which window that address is entered, in particular:

Edit -> Database -> Properties...  
Edit -> Database -> PySQLite settings...  
Or via macro

the driver recognizes the syntax of that string and can therefore process its content; in particular, the additional information that can be given is precisely the driver's own settings, expressed as name=value pairs. These make up the 3rd priority level and overwrite all previous levels; they are handy, for example, in the wizard to speed up the creation of a new database file, or to introduce a temporary setting without modifying the window's profile.

### **2.1.5. Final considerations**

Precedence is applied separately to each setting. If, for example, database creation is disabled in the global settings but enabled in the document, the document's choice prevails. If `CreateIfMissing=false` is present in the address, creation remains disabled instead, because the parameter in the address has the highest priority. As already mentioned, not all settings are available at every level. Those of the diagnostic log concern only the extension's global configuration; the database address, on the other hand, belongs exclusively to the document.

### **2.2. Accessing the extension's global settings**

The extension's global configuration is accessible from two places in LibreOffice's interface:

- **Tools → Extensions…**: in the window select the PySQLite extension and press the **Options** button.
- **Tools → Options**: in the navigation tree find and expand the **SQLite (pysqlite) SDBC** node, then select the desired category.

The two paths give access to the same global configuration. A change made through one of the two is therefore also available through the other.

### **2.3. Accessing the document settings**

Open the Base document and choose **Edit → Database → PySQLite settings…**.

The window shows again the global settings applicable to the document and allows them to be customized. It also includes the address field, which identifies the SQLite file to use.

For settings that offer the choice **Extension default**, this entry means that no specific value is fixed in the document: the one from the global configuration is used. Selecting an explicit value instead defines a level 2 setting, which prevails over the global level.

In both cases, any corresponding parameter in the address keeps precedence, because it belongs to level 3.

### **2.4. The connection address and its parameters**

The address includes the path and the full name of the SQLite file, including its extension, if any. It can be typed, pasted or selected using the **Open…** and **New…** buttons, described in the previous chapter. After the path, one or more settings can be added in the form `name=value`. The first is preceded by the `?` character; the following ones are separated by the `&` character. For example:

`C:\Dati\archivio.db3?CreateIfMissing=true&ReadOnly=false`

In this address:

- `C:\Dati\archivio.db3` identifies the database file;
- `CreateIfMissing=true` allows the file to be created if it does not exist;
- `ReadOnly=false` disables read-only mode.

The allowed names and values are described in the help available through the **?** button next to the address. The button opens the help in the browser. When the path is changed using **Open…** or **New…**, any parameters already present are kept and associated with the new path. The parameters in the address must also be taken into account when a change made in the window seems not to produce the expected effect: if the same setting is specified in the address, that value prevails over the choice made in the document's controls.

### **2.5. Making changes effective**

**Pressing OK does not make changes to the document settings effective immediately.**

Base loads the settings when the document starts. Confirming the window updates the settings kept in the document, but does not reconfigure the document that is already open. After a change you must therefore:

1. Confirm the window with **OK**.
2. Save the Base document.
3. Close the document.
4. Reopen it.


**The new settings take effect only at the next reopening.** This procedure applies to all document settings, including the database address and the parameters added to the path.

Even after a change to the global settings, documents that are already open must be closed and reopened so that they can use the new values. Settings explicitly defined in the document or in the address nevertheless keep their precedence over the global values. The following sections describe the individual settings, organized according to the categories present in the configuration windows.

### **2.6. The individual settings**

In the configuration windows, settings are grouped into pages, visible and selectable on the left side of the windows themselves. Each setting has a control for selection and a caption that summarizes its particulars, in particular the driver's default value and the effects of the available choices. The three **Diagnostic log** settings are available only in the extension settings window. The settings of the other categories are also available in the document and, except for the limitations indicated, can be specified through parameters in the address.

### **2.6.1. Diagnostic log**

The diagnostic log is a text file in which the driver records errors, warnings and some operations in detail. Its name is `sdbc-pysqlite.log`. The log is common to all Base documents that use the driver. To distinguish the document that generated a specific line, an identifier is assigned to each connection and shown in the lines concerning it. The identifier belongs to the connection: when the same document is reopened and a new connection is established, the code may change. Both configuration windows allow, through the dedicated buttons (**Open the log** and **Open the folder**), both consulting and locating the log itself.

### **2.6.1.1. Enable developer mode**

**Default value: No.**

Normally the driver records errors, warnings and some events concerning the structure of the database, for example the rebuilding of a table. Enabling developer mode also records the calls to the driver's methods, with more detailed information on the operations requested by Base. The log thus makes it possible to reconstruct the steps that preceded a problem. This mode is not needed to use the database. Since even an ordinary operation in the interface can produce numerous calls to the driver, the file grows rapidly. It is therefore advisable to enable it only for the duration of diagnostic activities.

### **2.6.1.2. Diagnostic log folder**

**Default value: empty field.**

Lets you choose the folder in which the log is written. The field requires the path of the folder, not the file name. If the field is left empty, the driver uses the `sdbc-pysqlite` subfolder of the LibreOffice user profile. If it cannot use the profile, it falls back to the system's temporary folder. You do not need to know the profile path to consult the log: the **Open the log** and **Open the folder** buttons take you directly to the file or to the location in use. If a custom folder is specified, the driver must have the permissions needed to create it and write to it.

### **2.6.1.3. Diagnostic log retention (days)**

**Default value: 14 - Values allowed in the window: from 1 to 3650 days.**

The log is rotated daily: when midnight strikes, the log file is given a timestamp and the driver replaces it, continuing to write the log to a new file. The setting establishes how many previous daily copies to keep. With the default value up to 14 copies are kept; the excess ones are deleted during rotation. On days when the driver does not write to the log, no empty copy is produced. This distinction is useful if the driver is used only occasionally: the value indicates the retention of the copies produced by rotation, not a deletion carried out every day regardless of use.

### **2.6.2. Database access**

These settings establish how the SQLite file is opened: whether it can be created, whether it can be modified, and how long to wait when another connection temporarily prevents an operation.

### **2.6.2.1. Create the database if it does not exist**

**Default value: No. Parameter in the address: `CreateIfMissing`.**

If the file given in the address does not exist, the setting **Yes** authorizes the driver to create it on the first connection attempt. Any missing folders of the path are also created, if permissions allow. The file is created empty: it does not yet contain tables or data. The creation is accompanied by a notice. With the setting **No**, the driver instead requires the file to exist already. If it does not find it, it interrupts the connection and presents an error with directions for correcting the configuration.

The option does not delete or recreate an existing file. It can be enabled to prepare a new database and then disabled: in this way, if the path is later changed by mistake, the driver reports the missing file instead of creating another empty one. Creation is not carried out if read-only mode is active.

### **2.6.2.2. Open the database read-only**

**Default value: No. Parameter in the address: `ReadOnly`.**

With the setting **Yes**, the database is opened for consultation. You can read the tables and run queries, but not insert, modify or delete data, nor change the structure of the database. The restriction concerns the SQLite file opened through that connection. The Base document can still be modified, for example by adding a form or changing its own settings. With the setting **No**, the driver opens the database allowing writes as well, provided the permissions on the file and the other conditions of the database allow it. Read-only mode does not prevent another program from opening the same file with write permissions.

### **2.6.2.3. Busy database timeout (seconds)**

**Default value: 5 seconds. Parameter in the address: `LockTimeoutSeconds`.**

An operation can remain temporarily blocked because another connection is using the database. For example, a second program may have started a write that it has not yet finished. This setting indicates for how long the driver must wait for the lock to be released. If the operation can proceed within the established time, it is carried out; otherwise a database-busy error is returned.

The value **0** eliminates the wait: if the database is locked, the error is returned immediately. Increasing the time gives more room to concurrent operations, but does not eliminate the lock and does not resolve a transaction left open by another program. The window accepts values from **0 to 86400 seconds**.

### **2.6.3. Integrity and transactions**

This category concerns the checks on the relationships between tables and the way SQLite manages writes. A *transaction* groups operations that must be either confirmed or cancelled together. In ordinary use of Base, confirmation is generally automatic; macros and specially prepared commands can instead manage it explicitly.

### **2.6.3.1. Enable referential integrity checking**

**Default value: No. Parameter in the address: `ForeignKeys`.**

Foreign keys describe links between records of different tables. For example, an orders table can contain the code of the customer to whom each order belongs. When this setting is enabled, SQLite applies the constraints defined in the database. In the example, an order cannot refer to a nonexistent customer, except in the cases allowed by the definition of the field and of the constraint. Changes and deletions also follow the rules defined in the relationship: they can be prevented or can produce linked updates or deletions, if the constraint provides for these actions.

The setting does not create relationships: it makes the constraints already defined operative. If it is disabled, the definitions remain in the database but are not enforced by the connection. Enabling it does not automatically correct any inconsistent data already present.

### **2.6.3.2. Write protection journal**

**Default value: `delete`. Parameter in the address: `JournalMode`.**

During a write SQLite normally uses a support file so that it can complete or cancel the changes without leaving the database only partly updated. This setting chooses the method used.


| Value      | Behavior                                                                                                                                                                                                |
|------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `delete`   | Before modifying the database, it keeps in the journal the original parts needed for recovery. When the transaction ends, it deletes the journal.                                                       |
| `truncate` | Uses the same mechanism as `delete`, but at the end it empties the journal file instead of deleting it.                                                                                                 |
| `persist`  | Keeps the journal file and invalidates its content when the transaction ends, so that it can be reused.                                                                                                 |
| `memory`   | Keeps the journal in RAM instead of on disk. An interruption of the process or of the system can compromise the database.                                                                              |
| `wal`      | Writes the changes first to a separate file; their transfer to the main database takes place later. In several situations it allows reading while another connection is writing.                         |
| `off`      | Disables the protection journal. An error or an interruption during writes can compromise the database.                                                                                                 |


For ordinary use the default value can be kept. The `memory` and `off` modes reduce data protection and are not recommended for this use. The `wal` mode can create files with the `-wal` and `-shm` suffixes next to the database. They must not be considered stray files or deleted while the database is in use. The mode also requires conditions that are not normally available for a database shared through a network folder.

The write journal is distinct from the diagnostic log: the former is used by SQLite to manage the data, the latter contains the driver's messages.

### **2.6.3.3. Locking mode in manual-commit transactions**

**Default value: `free`. Parameter in the address: `TransactionMode`.**

This setting mainly concerns macros and operations that explicitly manage the confirmation of transactions. It does not normally need to be changed to work with tables and forms in Base's interface.

When the driver starts a write transaction managed in this way, the choice determines which accesses are reserved for the connection and which remain available to other programs.


| Value       | Behavior                                                                                                                                                                                                        |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `free`      | Acquires locks when the operations require them, without reserving the right to write in advance. The presence of another connection can therefore prevent a later write.                                       |
| `blocking`  | When the write transaction starts, it reserves the ability to write. Others can continue to read, but must wait before writing.                                                                               |
| `exclusive` | When the write transaction starts, it also excludes reads by other connections. In `wal` mode it behaves like `blocking`.                                                                                       |


Locks are kept until the transaction ends. A macro that leaves a transaction open can therefore prevent other programs from working on the database for all that time.

### **2.6.4. Reading results**

These settings concern the loading of the rows returned by a table or a query. They do not establish how many rows the database can hold and do not delete data.

### **2.6.4.1. Full-load threshold (rows)**

**Default value: 50000. Parameter in the address: `FullLoadLimit`.**

When a result stays within this threshold, the driver can load it entirely into memory. If it exceeds it, the driver switches to progressive reading in blocks. With the default value, therefore, a result of a few thousand rows is loaded entirely; a result larger than 50000 rows is handled in blocks.

Raising the threshold makes it possible to keep larger results entirely in memory, but requires more memory. Consumption also depends on the content of the columns: rows with long texts or binary data take up more space than rows made up of a few numbers.

The threshold and the block size are independent: you can set a threshold smaller than the block without losing rows, because the result is in any case read in full, in blocks, as needed.

The window accepts values from **1 to 10000000 rows**.

### **2.6.4.2. Read block size (rows)**

**Default value: 1000. Parameter in the address: `WindowSize`.**

Establishes how many rows are loaded for each block when the result exceeds the previous threshold. With the default value the driver uses blocks of 1000 rows. The choice does not limit the total number of rows that can be consulted: the driver loads further blocks when needed. Larger blocks require more memory for each load; smaller blocks mean more frequent loads. For ordinary use the default value can be kept.

The window accepts values from **1 to 100000 rows**.

### **2.6.5. Formats**

These settings concern the way the driver interprets and stores dates and times, and the language of the names returned by some SQL functions. The format stored in the database must be distinguished from the one displayed in Base: a date shown as `28/10/2026` may be kept in the file with a different representation.

### **2.6.5.1. Date and time storage format**

**Default value: `text`. Parameter in the address: `DateTimeFormat`.**

SQLite does not impose a single format for storing dates and times. This setting establishes the representation used by the driver.


| Value    | Representation                                                                                              |
|----------|-------------------------------------------------------------------------------------------------------------|
| `text`   | Text according to the ISO 8601 format, with the date expressed in year-month-day order.                      |
| `unix`   | Numeric value based on the seconds elapsed since 1 January 1970.                                             |
| `julian` | Numeric value expressed in Julian days, with the decimal part used to represent the time of day.             |


For a new database you can keep `text`. For an existing database, especially if it is also used by other programs, the choice must be consistent with the representation of the data already present. The setting acts when the structure of a table is created or modified; changing the setting does not automatically convert the values stored in the tables. To convert the storage format, the column must be recreated and rewritten anew.

### **2.6.5.2. Time reference**

**Default value: `local`. Parameter in the address: `DateTimeZone`.**

Establishes whether the driver must use the local time reference or Coordinated Universal Time.

- **`local`**: uses the system's local time reference.
- **`utc`**: uses Coordinated Universal Time, independent of the local time zone.

The choice must be compatible with the storage format:


| Format   | Allowed references   |
|----------|----------------------|
| `text`   | `local` or `utc`     |
| `unix`   | only `utc`           |
| `julian` | only `utc`           |


For example, choosing `unix` also requires setting `utc`. The combination of `unix` with `local` is rejected.

The two settings are therefore not independent, and they are resolved together: they are taken from the highest level that specifies at least one of them. The one that level does not specify takes the **driver default value** (`text` for the format, `local` for the reference), not the value from the lower level.

For example, if the extension Options define `text` and `local` and the document chooses only `unix`, leaving **Extension default** for the time reference, the reference becomes `local` (the driver's value) and the combination of `unix` with `local` is rejected: the window reports the error. To use `unix` or `julian` you must also explicitly choose `utc`. Likewise, if the Options define `unix` and `utc` and the document chooses only `utc`, the format returns to `text`, the driver's value, and does not remain `unix`.

### **2.6.5.3. Language of day and month names**

**Default value: `auto`. Parameter in the address: `NamesLanguage`.**

This setting chooses the language of the names returned by the SQL functions `DAYNAME`, `MONTHNAME` and `TO_CHAR`, when these produce the name of a day or of a month. It does not change the language of Base's menus and does not translate texts already present in the tables.


| Value  | Language used                                    |
|--------|--------------------------------------------------|
| `auto` | The formats language configured in LibreOffice.  |
| `en`   | English.                                         |
| `it`   | Italian.                                         |
| `fr`   | French.                                          |
| `de`   | German.                                          |
| `es`   | Spanish.                                         |


The `auto` choice follows LibreOffice's format settings, which may differ from the interface language. If you need to always obtain Italian names, regardless of the computer's configuration, select `it`.

### **2.6.6. Primary keys**

A primary key uniquely identifies each record of a table. For example, a customers table can use a numeric column whose value is assigned automatically to each new customer. The following settings concern the management of these identifiers.

### **2.6.6.1. Reuse freed automatic numbers**

**Default value: No. Parameter in the address: `AutoIncrementReuse`.**

This choice concerns the generation of automatic numeric primary keys in tables created through the driver. With **No**, the mechanism that keeps the progression beyond the highest value previously assigned is used. Deleting a record does not make its identifier available for a later automatic assignment.

With **Yes**, the ordinary behavior of SQLite is allowed, which under certain conditions can assign again numbers that belonged to deleted records. This does not mean that all missing numbers are recovered nor that the numbering stays free of gaps. The choice acts in the definition of the automatic column. Changing it does not automatically rewrite the structure of tables that already exist.

### **2.6.6.2. Use an implicit primary key**

**Default value: No. Function not available.**

The control is disabled and cannot be used. The driver does not automatically use SQLite's `ROWID` as the primary key for tables without an explicit key.

### **2.6.7. Security**

The **Security** page is available both in the extension's global settings and in the settings of the individual Base document, between **Primary keys** and **System**. The three settings are independent and, by default, apply no additional restrictions. They are optional tools to be evaluated, in particular when knowingly opening a database of not fully trustworthy origin.

The protections are applied by the driver **to every new SQLite connection**, including internal connections, and are not stored in the `.db3` file. Another program that opens the same database inherits no protection. The settings follow the normal hierarchy described in § 2.1: parameters in the address prevail over those of the document, which may prevail over the global ones. **A document can therefore disable protections enabled globally.** These tools do not replace verifying the origin of the document, `ReadOnly=true` or the operating system's permissions.

If a requested protection cannot be enabled by the library, the connection remains usable and warning **50.107** is issued with the list of the protections not obtained.

### **2.6.7.1. Enable defensive mode**

**Default value: No. Parameter in the address: `DefensiveMode` (`true`/`false`).**

SQLite's defensive mode (`SQLITE_DBCONFIG_DEFENSIVE`) prevents some operations that can directly alter the database's internal structures, for example direct writes to the system tables even after `PRAGMA writable_schema=on`. It cannot be disabled by an SQL statement on the connection.

It **does not prevent** the normal statements that modify or delete data, such as `UPDATE`, `DELETE` and `DROP TABLE`. With this protection active, the request for the `off` journal is refused: the driver reports the problem with warning **50.106** and keeps the previous journal.

### **2.6.7.2. Treat the database schema as untrusted**

**Default value: No. Parameter in the address: `UntrustedSchema` (`true`/`false`).**

If you set **Yes** (`UntrustedSchema=true`), the driver uses `trusted_schema=OFF`: views, triggers, `CHECK` constraints, generated columns and expression indexes can call only functions authorized as innocuous. The `true` value of the parameter therefore means **enabling the protection**, not considering the schema trusted.

This mode can make perfectly legitimate schema objects unusable if they call functions not marked as innocuous. Among the driver functions affected are `RAND` (zero and one argument), `UUID()`, `IDENTITY`, `CURDATE`, `TODAY`, `CURTIME`, `NOW`, `UNIX_TIMESTAMP()` and `UNIX_MILLIS()` (the last two in their no-argument forms). A view can be created without errors, but fail when it is used, with a message such as `unsafe use of NOW()`. Direct calls to the functions are not forbidden by this setting.

### **2.6.7.3. Safety limits**

**Default value: None. Parameter in the address: `LimitsProfile` (`none`, `prudent`, `strict`).**

The choice **None** (`none`) keeps the limits of the SQLite library. **Prudent** (`prudent`) reduces some maximums relating to the complexity of statements; **Strict** (`strict`) adds limits on the size of SQL, values and structures. The profiles do not allow individual limits to be changed. The driver applies the limits to the individual connection through `sqlite3_limit()`; if the library's own limit is already lower, it does not raise it.

| Limited resource | Prudent | Strict |
|---|---:|---:|
| Maximum depth of expressions | 200 | 200 |
| Trigger depth | 50 | 50 |
| Number of `SELECT`s in a compound statement (`UNION`) | 100 | 100 |
| Maximum length of the `LIKE`/`GLOB` pattern | 5,000 bytes | 5,000 bytes |
| Databases attachable with `ATTACH` | 5 | 5 |
| Maximum number of SQLite program operations per statement | 50,000,000 | 50,000,000 |
| Maximum length of strings and BLOBs | SQLite value | 100,000,000 bytes |
| Maximum length of the SQL text | SQLite value | 10,000,000 bytes |
| Maximum number of columns | SQLite value | 500 |
| Maximum number of SQL parameters | SQLite value | 32,766 |

The profiles do not change the maximum number of function arguments or the number of worker threads. **Prudent** applies broad limits, normally compatible with the ordinary commands of Base; **Strict** can prevent the use of individual BLOBs larger than 100,000,000 bytes, of tables with more than 500 columns or of very large SQL statements. The limits do not guarantee an execution timeout, do not set an overall ceiling on memory and do not check the declared length of `VARCHAR(n)` types.

### **2.6.8. System**

### **2.6.8.1. Warn if SQLite is older than the recommended version**

**Default value: Yes. Parameter in the address: `OldLibraryWarning`.**

If the SQLite library in use is older than the version recommended by the driver, a warning is shown. The message appears only once per session and does not prevent you from continuing. The extension includes its own SQLite library: with the complete, unmodified package as distributed, it is normally not necessary to act on this setting. Disabling the warning only removes the notice; it does not update the library and does not change its features.

## **3. Using Base together with PySQLite**

This section illustrates how the driver works; however, it is not a manual on how to use Base or SQLite, for which the respective online guides should be consulted. This chapter describes the driver's choices that affect work with Base. The general procedures for building forms, queries and reports remain those of LibreOffice; the general syntax of SQLite commands remains that of the engine. Here the differences to be taken into account when the two programs communicate through PySQLite are explained.

### **3.1. Creating tables and choosing column types**

When a table is created in design view, Base presents a list of types supplied by the driver. The list may appear long and repetitive because different names can correspond to the same data type.

In ordinary SQLite tables, in fact, the type declared in the column does not impose the same constraints as strictly typed databases. SQLite accepts numerous names, even custom ones, and derives the behavior from them through rules based on the name. The same column can moreover contain values of different kinds.

The driver therefore recognizes numerous names so that **SQLite tables created with other programs** can be used in Base without first having to modify their types.

For new tables created in ordinary use of Base, the types with the **`LO_` prefix** are instead recommended, which tell the driver how to read and write the values. For **`STRICT`** tables (which can be created by a direct SQL command or a macro) the types with the **`_ST` suffix** are available. In both cases the database remains a SQLite file.


| Column content                                            | Driver types                                           |
|-----------------------------------------------------------|--------------------------------------------------------|
| Integers                                                  | `LO_TINYINT`, `LO_SMALLINT`, `LO_INTEGER`, `LO_BIGINT` |
| Floating-point numbers                                    | `LO_REAL`, `LO_DOUBLE`                                 |
| Numbers according to SQLite's numeric representation      | `LO_NUMERIC`                                           |
| Decimals with a set number of digits after the point      | `LO_DECIMAL`                                           |
| Text                                                      | `LO_CHAR`, `LO_VARCHAR`, `LO_LONGVARCHAR`              |
| Values of variable type                                   | `LO_VARIANT`                                           |
| Yes/No                                                    | `LO_BOOLEAN`                                           |
| Dates and times                                           | `LO_DATE`, `LO_TIME`, `LO_TIMESTAMP`                   |
| Binary data                                               | `LO_BINARY`, `LO_VARBINARY`, `LO_LONGVARBINARY`        |


A macro or program that creates a table by describing the columns with only the **numeric type code** (`Type`), without giving the type name (`TypeName`), gets the corresponding `LO_` type: 4 `LO_INTEGER`, 5 `LO_SMALLINT`, -6 `LO_TINYINT`, -5 `LO_BIGINT`, 12 `LO_VARCHAR` (with the length indicated), 1 `LO_CHAR`, -1 `LO_LONGVARCHAR`, 8 and 6 `LO_DOUBLE`, 7 `LO_REAL`, 2 `LO_NUMERIC`, 3 `LO_DECIMAL`, 16 and -7 `LO_BOOLEAN`, 91 `LO_DATE`, 92 `LO_TIME`, 93 `LO_TIMESTAMP`, -2 `LO_BINARY`, -3 `LO_VARBINARY`, -4 `LO_LONGVARBINARY`. If the type name is given, the name prevails; with an unrecognized code the column is left with no declared type.

The differences between these types and their limits are summarized in appendix B. In particular, `LO_DECIMAL` is not equivalent to a SQLite column declared simply as `DECIMAL`.

When opening a database produced by another program, it is not necessary to rename all the types with the `LO_` prefix. The driver recognizes the common names, such as `INTEGER`, `TEXT`, `REAL`, `BLOB`, `DATE` and `BOOLEAN`, and presents them to Base according to its own reading rules. Opening the file does not automatically convert the data and does not rewrite the structure.

SQLite does not automatically enforce the declared length of `VARCHAR(n)` types; the driver keeps this behavior. To impose a maximum length, you can define an SQL constraint such as `CHECK(length(column_name) <= 50)` on the column concerned. The safety limit profiles do not replace a constraint of this kind.

### **3.2. Primary keys and automatic values**

To modify records through Base's grids and forms, the table must have an explicit primary key. It is the datum by which Base identifies the record to update or delete. A table without a primary key remains consultable, but is presented as read-only.

The internal `ROWID` number present in many SQLite tables is not used automatically as a substitute for the primary key. The corresponding control is not available.

To obtain automatic numbering you need an integer column that by itself constitutes the primary key. In the SQLite file the driver defines it as `INTEGER PRIMARY KEY`, with or without `AUTOINCREMENT` according to the **Reuse freed automatic numbers** setting.

For this reason, after the structure is saved, Base may show the automatic key as a long integer even if another integer type was initially selected. The driver keeps the definition SQLite needs to generate the numbers.

The choice about reusing numbers is applied when the table is created and may be applied again when a change requires it to be rebuilt. Changing only the document option does not immediately modify all the tables already present.

### **3.3. Saving the document and confirming the data**

The **Save** button of the Base document saves the `.odb` file: settings, query definitions and other objects of the document. It is not a command to confirm all the changes to the SQLite database together.

In ordinary use of tables and forms, Base sends the driver the change to a record when the entry or the modification of that record is finished. The connection normally uses automatic confirmation, called *autocommit*: completed operations are confirmed without waiting for the `.odb` document to be saved.

A macro can disable automatic confirmation with `setAutoCommit(False)`. From that moment it must manage the conclusion of the work with `commit()` to confirm or `rollback()` to cancel the changes still pending. Re-enabling automatic confirmation confirms the open transaction.

Closing a connection with an unconfirmed transaction cancels its changes; the driver produces the corresponding warning. Whoever writes macros must therefore not leave to the Save button or to the closing of the document the decision about what to keep.

### **3.4. Modifying the structure of a table**

The driver allows you to act on the structure through Base's tools, for example by adding or renaming columns, changing their type and defining keys and relationships.

SQLite does not offer a direct command for every change presented by the interface. In these cases the driver rebuilds the table: it prepares the new definition, transfers the data and carries out the necessary checks. The operation may therefore take time even if only one property was changed in the interface.

Before the conversion, the data are checked. If, for example, a column must become mandatory but contains NULL values, or must become numeric but contains texts that cannot be converted, the change is rejected. The message indicates the problem, the number of rows involved and, when available, a first example. You must correct the data or review the change requested.

Some permitted conversions may round numbers or truncate contents. Information about these adaptations is recorded in the diagnostic log. Before changes of type, length or number of decimals it is therefore advisable to work on a copy and check the result.

A rebuild cannot be started if there are changes awaiting confirmation on the connection: message **50409** asks you to confirm or cancel them before trying again.

Deleting a column may also entail deleting the indexes that use it, including those that include other columns; the names are recorded in the log. If instead the column is used by a relationship, a view, a trigger or a key that prevents the operation, the driver reports the dependency to be resolved.

An SQL command written directly follows SQLite's own rules. It should therefore not be assumed that an `ALTER TABLE` run by hand produces the same ancillary interventions as a change made from Base's structure window.

### **3.5. Base's default value and the database DEFAULT**

The default value set in Base's structure is kept in the `.odb` document and serves to suggest content in the entry row. It is not equivalent to a `DEFAULT` constraint written in the definition of the SQLite table.

If the database must assign a value also to inserts made by other programs or by commands that omit that column, you must define a `DEFAULT` in the database through SQL.

For example, the value suggested by Base is not applied to an insert made by another program that opens the SQLite file. A database `DEFAULT`, on the other hand, is applied by the engine when the insert command omits the column, according to SQLite's rules.

`DEFAULT`s already present in the file are kept when the driver modifies the structure. For `LO_DECIMAL` columns, the value written in the SQL definition must respect the internal representation explained in the document on exact decimals.

### **3.6. STRICT tables, computed columns and indexes**

A SQLite `STRICT` table accepts only a limited set of types. If the table is already `STRICT`, to modify its columns from Base's structure use the entries `INTEGER_ST`, `REAL_ST`, `TEXT_ST`, `BLOB_ST` and `ANY_ST`. The driver removes the `_ST` suffix when it writes the definition into the database.

The suffix serves to distinguish the choices in Base's list: selecting it does not by itself turn an ordinary table into a `STRICT` table. The `LO_` types are not allowed in `STRICT` tables; the attempt is rejected with message **50413**.

Computed columns, defined in the table by an expression, are read like the others but are indicated as not writable. To change their result you must modify the data they depend on or their definition, not insert a value in the computed cell.

Ordinary indexes can be managed from Base's index window. Expression indexes and partial indexes require SQL commands and do not appear in that window. Their absence from the list therefore does not mean that the database has none.

### **3.7. Base queries and direct SQL commands**

A query saved in the `.odb` document is distinct from a view saved in the SQLite database. The former belongs to the Base document; the latter stays in the database file and is also visible to other programs that open it.

Base can process the text of a query before sending it to the driver. For SQLite constructs that Base's processor does not recognize, for example some queries with `WITH RECURSIVE`, it may be necessary to enable **Run SQL command directly**.

This choice avoids Base's processing, but the command still passes through PySQLite. The driver's translations therefore remain active, including those for exact decimals and for sequences in curly braces.

The driver translates the date, time and function sequences produced by Base, such as `{d '2026-10-28'}` and `{fn UCASE('text')}`. It also translates some SQL constructs with keywords, such as `SUBSTRING(text FROM 2 FOR 3)`, `POSITION('a' IN text)` and `EXTRACT(YEAR FROM date)`.

This support makes it easier to reuse queries, but it does not make SQLite identical to HSQLDB. Before transferring a complex query you must check its functions, types and results.

### **3.8. Accented letters, searches and sorting**

The driver extends SQLite's ordinary behavior to handle accented letters in the most common searches as well.


| Expression                     | Result or behavior                                                                                          |
|--------------------------------|-------------------------------------------------------------------------------------------------------------|
| `UPPER('perché')`              | Returns `PERCHÉ`.                                                                                           |
| `'Café' LIKE 'cafe%'`          | The condition is true: LIKE ignores uppercase, lowercase and accents.                                       |
| `ORDER BY name COLLATE NOCASE` | Sorts without distinguishing uppercase and lowercase and places accented letters next to the base letter.   |


The `NOCASE` ordering maintains a distinction between texts that differ by their accents, even though it places them next to each other. It must not be confused with `LIKE`, which deliberately also searches for accented variants.

Ordinary comparison with `=`, groupings and the selection of distinct values are not automatically turned into accent-insensitive searches. A search with `LIKE` can therefore find more variants than an equality.

The conversions can also change the length of the text: for example `UPPER` turns the German letter `ß` into `SS`.

The `LIKE` comparison uses a linear algorithm even with patterns containing many `%` characters, avoiding extreme slowdowns. With the **Prudent** or **Strict** safety profiles, a `LIKE` or `GLOB` pattern cannot exceed **5,000 bytes**; otherwise SQLite reports `LIKE or GLOB pattern too complex`.

The extension of `LIKE`'s behavior can prevent SQLite from applying some index optimizations. A search over many records may therefore take longer: the broader result does not necessarily correspond to a faster search.

### **3.9. Regular expressions**

The driver adds the `REGEXP` operator and the functions listed in appendix C. The syntax of the patterns is that of Python's regular expressions, because the driver uses its engine.

The comparison ignores uppercase, lowercase and accents. However, you must distinguish searching for a match within the text from verifying the entire content:

- `'Café' REGEXP 'afe'` is true: the pattern is found in a part of the text.
- `REGEXP_MATCHES('Café', 'afe')` is false: the pattern does not describe the entire text.
- `REGEXP_MATCHES('Café', 'cafe')` is true.

A pattern copied from Java cannot always be used without changes. For example, classes such as `\p{L}` and named groups in the Java form `(?<name>...)` are not the syntax of the engine used: in Python named groups have the form `(?P<name>...)`.

`REGEXP_SUBSTRING_ARRAY` returns a JSON text with the matches found, not an SDBC array. The result can therefore be read as text or processed with SQLite's JSON functions.

### **3.10. Numeric functions, dates and NULL values**

When a function name already exists in SQLite, the driver keeps its behavior apart from the declared extensions. It is therefore not enough for a function to have the same name as in HSQLDB to assume that every particular case produces the same result.


| Case                         | Behavior to consider                                                                                     |
|------------------------------|----------------------------------------------------------------------------------------------------------|
| `LOG(100)`                   | Returns 2: the logarithm is base 10. For the natural logarithm use `LN`.                                 |
| `ROUND(2.5)` and `ROUND(-2.5)` | Return 3 and -3 respectively: in halfway cases SQLite rounds away from zero.                           |
| `CONCAT` with NULL           | Follows SQLite, which treats NULL arguments as empty strings.                                            |
| `LOCATE` and `INSTR`         | The order of the first two arguments is different: `LOCATE(searched, text)` and `INSTR(text, searched)`. |
| `DAYNAME` and `MONTHNAME`    | The names depend on the **Language of day and month names** setting.                                     |
| `USER()`                     | Returns an empty string: the SQLite file has no users authenticated by the driver.                       |
| `DATABASE()`                 | Returns the file name without extension, not the full path.                                              |


NULL indicates the absence of a value and must be distinguished from an empty string or from the number zero. The driver also provides functions such as `NVL`, `NVL2` and `CASEWHEN`; appendix C summarizes the available groups.

### **3.11. Exact decimals**

The `LO_DECIMAL(p,s)` type stores values as scaled integers. For example, with two decimals the value 12.35 is stored as 1235. The driver presents the number with the decimal separator to Base and applies the necessary conversions in reads and writes.

In SQL commands numbers are written with the point, for example `12.35`. In the cells of Base's grid, on the other hand, the separator provided by the locale settings must be respected, normally the comma in an Italian environment.

Another program that opens the file sees the internal representation. Triggers, `CHECK` constraints, `DEFAULT` values, generated columns and indexes with expressions also require particular attention: the text of the definition is not treated as a normal command for reading or updating decimals.

For examples, roundings, rejections by the translator and the handling of views, see the document "Exact Decimals in SQL Commands" (in the `docs` folder of the extension's source code, downloadable from the project's GitHub repository, "Manual - Exact Decimals in SQL Commands"). The document distinguishes the operations translated by the driver from the expressions that SQLite runs on the stored values.

### **3.12. Forms, data refresh and macros**

A form may continue to show values read earlier even if another program has modified or deleted those records. Before modifying data that other programs are working on, use **Refresh** to reread the current content.

Refreshing the display does not protect against a change made by another program immediately afterwards. If two connections change the same datum, the last write may replace the previous one without a conflict warning. This limit is described in chapter 4.

In macros, to write an update concerning a specific record, use the primary key. It is preferable to pass the values through a prepared command, avoiding building the SQL text by directly concatenating the content of the fields.

Positional `?` parameters are assigned starting from position 1. All the parameters used must receive a value before execution; to send NULL it must be assigned explicitly, rather than leaving the parameter without a value.

The SDBC results returned by the driver are read-only. This does not prevent Base from modifying the tables: for updates the application sends separate commands. A macro must therefore run `INSERT`, `UPDATE` or `DELETE`, without assuming that the methods for modifying the result directly are available.

**Schema number.** A SQLite file keeps in its header a free integer (`user_version`, initially 0) that SQLite does not use. An application can use it to indicate the version of the structure of its tables and compare it on opening. The driver does not manage it and has no settings for it: it is read with `PRAGMA user_version` and written with `PRAGMA user_version = N`, from SQL commands or macros. The command is executed immediately, even when a macro has disabled automatic confirmation and has a transaction open: a later `rollback()` does not cancel it. It is therefore advisable to write the new number after the `commit()` that confirms the change to the structure. The compatibility rules (what to do if the file has a lower or higher number than expected) are up to the application.

### **3.13. Base's advanced settings**

The entry **Edit → Database → Advanced Settings…** belongs to Base and is distinct from **PySQLite settings…**. The driver exposes there only the advanced options provided for the connection; many others are fixed at values consistent with its operation.

An already existing document may keep earlier choices. In the **System** category of the document's PySQLite settings, **Reset the document's advanced options** is available: after confirmation it restores the values provided by the driver for the hidden options. The advanced options that are still visible are not changed.

The command may be useful, for example, if a document keeps an old criterion for comparing Yes/No values. After the reset, save, close and reopen the document. It is not necessary to run it at every opening, nor does it modify the database records.

## **4. Known limitations**

The following limits describe what must be taken into account when using the driver.

### **4.1. Access to the same file from several programs**

The driver is designed to work on the SQLite file from one program at a time. Several connections can read at the same time, but SQLite allows only one write at a time. If the file is busy, the driver waits for the time set by **Busy database timeout** and, if the lock persists, returns an error.

Increasing the waiting time does not introduce conflict management between users. There is no general guarantee on concurrent writes by other programs.

If two connections modify the same cell of a record, the last write overwrites the previous one without warning. The driver does not automatically compare the content initially read with the content present at the time of saving.

In SQL commands or macros designed for the purpose, a check can be introduced with a version column, verifying how many rows were updated. The mere addition of this column does not, however, protect Base's ordinary forms, which do not automatically perform that comparison.

### **4.2. Large results and data modified during reading**

Within the full-load threshold, the result is kept in memory and does not automatically follow later changes to the database. Above the threshold it is read in blocks; the default values are described in chapter 2.

If another connection confirms changes while a result read in blocks is being consulted, the driver may interrupt the loading with message **50322**, which invites you to refresh the list. The rows already loaded remain readable, but to continue the query must be rerun through **Refresh**.

Changes made by the same connection do not trigger this check and can shift the positions of the rows. The check, moreover, concerns the result read in blocks: it is not a system for detecting conflicts when saving an individual record.

In forms, a record deleted elsewhere may also remain visible. Refresh the display before acting on the data.

### **4.3. Read-only mode and access protection**

The option **Open the database read-only**, or `ReadOnly=true` in the address, opens the connection using SQLite's read-only mode. The engine prevents writes through that connection.

The SDBC request `setReadOnly(True)` made on an already open connection does not, however, change the opening mode in the current implementation. Opening the `.odb` document read-only must also not be used as a guarantee about the writability of the external database.

The settings of the **Security** page (§ 2.6.7) concern only the connections opened by PySQLite and do not prevent another program from opening the file. Defensive mode also does not prevent `DROP TABLE` or `DELETE`.

The driver does not introduce users, passwords or permissions of its own on the file. Protection from access by other programs depends on the operating system's permissions and on any protections external to the driver.

### **4.4. Functions available only through PySQLite**

The functions added by the driver and the extended `NOCASE` comparison are installed on every connection. They are not embedded in the SQLite file as executable code.

Another program may therefore receive "function not available" or obtain different comparisons. The problem can also concern views, triggers and indexes that depend on those functions or on the custom comparison. Before using the same file with other programs, check the operations they need to perform.

For `LO_DECIMAL` there is in addition the scaled internal representation described in chapter 3 and in the document on decimals.

### **4.5. SQL compatibility and unavailable features**

PySQLite makes it easier to use some functions familiar to those coming from HSQLDB, but it does not implement full compatibility. In particular it does not add:

- forms with `INTERVAL` and the functions `DATE_ADD` and `DATE_SUB`;
- `ROUND` and `TRUNC` with a single argument applied to dates or times;
- HSQLDB's date and time-zone functions not provided by the driver, including `LOCALTIME`, `LOCALTIMESTAMP`, `SYSDATE`, `SYSTIMESTAMP`, `TIMESTAMP_WITH_ZONE` and `TIMEZONE`;
- an SQL array system equivalent to HSQLDB's;
- the functions that describe users, sessions and the state of an HSQLDB server, except for the forms explicitly present such as `USER()` and `DATABASE()`.

Tables without an explicit primary key remain read-only in the interface. The function **Use an implicit primary key** is not active.

SQLite allows `ATTACH` through SQL, but the driver does not present the attached files as a set of navigable databases in Base's interface. Whoever uses the command must manage the attachment on the connection concerned through SQL or macros; it is not equivalent to adding a second path in the document settings.

The driver does not include an importer that automatically transfers an HSQLDB database into SQLite. Linking a document to a SQLite file does not convert the data of the previous database.

### **4.6. Write journal and closing**

On opening, the driver requests the configured journal mode. If another program keeps the file open with a different mode, it may not be possible to change it: in this case message **50010** is shown. It is not necessarily a problem of timeout duration.

Closing waits for the operations in progress to complete. It must not be interpreted as a command to immediately cancel a long operation. Unconfirmed transactions, on the other hand, are cancelled when the connection is closed, as described in section 3.3.

## **5. Messages and diagnostic log**

### **5.1. Reading a message**

A message may report an error, which prevents the requested operation from being completed, or a warning, which informs about a result or a condition to take into account. The warning about the creation of an empty database, for example, confirms a successful operation.

Messages give an explanation and, where possible, the actions to take. The final line identifies the code, the SQLState and the point in the driver, for example:

`[code 50001 · SQLState 08001 · sdbc.driver.Driver.connect]`

The code identifies the case; the SQLState indicates its category; the point in the driver helps to locate where it was produced. To report a problem, keep the entire message, not only the number.

The driver's own codes start at 50000. Errors produced by the engine may instead carry SQLite names and codes, such as `SQLITE_BUSY` or `SQLITE_CONSTRAINT`. They must not be confused with the numbering of the driver's messages.

Some warnings are not shown by all Base windows. Their absence from a window does not prove that they were not produced: the diagnostic log remains the reference for consulting the recorded events.

### **5.2. Opening and configuration problems**


| Code                      | Meaning                                                                   | Action                                                                                                                          |
|---------------------------|---------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------|
| `50001`, `50002`, `50007` | Missing file, path that indicates a folder, or missing folder.            | Correct the path in the document settings. If a new database must be created, enable the relevant option.                       |
| `50003`                   | The file is not recognized as a valid SQLite database.                    | Check the selected file. Changing the extension of the name does not convert the content.                                       |
| `50004`                   | The file or the folders cannot be created.                                | Check the path, permissions and available space.                                                                                |
| `50005`, `50008`          | Address empty, invalid or with characters that are not allowed.           | Correct the text of the address.                                                                                                |
| `50006`                   | The new database has been created.                                        | Informational warning: check the path if the creation was not expected.                                                         |
| `50009`                   | The bundled SQLite component is not available or does not load.           | Check the system requirements (§ 1.1) and reinstall the complete package.                                                       |
| `50101`                   | The log folder is not writable.                                           | Correct the global log path or the permissions on the folder.                                                                   |
| `50102`–`50105`           | Value not allowed, or parameter unknown, incomplete or repeated.          | Read the detail and compare name and value with the help opened by the **?** button.                                            |


After correcting the document settings, confirm with **OK**, save, close and reopen. Simply confirming the window does not reconfigure the connection that is already open.

### **5.3. Busy database and different journal**

A database-busy error may indicate a write kept open by another connection. Close or finish the operation in the other program, then try again. Increasing the timeout helps only if the lock is temporary.

Message **50010**, on the other hand, indicates that the requested journal cannot be set because the file uses another mode and is in use. The message reports the journal requested and the one found.

You can close the other program and reopen the document, or knowingly choose the mode the file already uses. For example `JournalMode=wal` in the address requests WAL. A parameter saved in the address remains active until it is removed: it is not a choice that expires automatically when closing.

Warning **50.106** also reports a journal mode that was not obtained, for example `JournalMode=off` when defensive mode is active: the connection keeps the previous journal.

Warning **50.107** indicates that one or more **requested security protections were not obtained**. The message identifies the protections concerned; the connection opens anyway, so the user must decide whether to proceed.

### **5.4. Problems in data and structure**


| Code or family            | Meaning                                                                                                              | Action                                                                              |
|---------------------------|----------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| `50308`–`50310`           | Value that cannot be converted, out of range, or unreadable date.                                                    | Check the content and type of the column indicated.                                 |
| `50312`, `50313`          | Command parameter not assigned or invalid position.                                                                  | Correct the macro or the prepared command; positions start from 1.                  |
| `50316`–`50319`           | The decimals translator cannot safely execute the command.                                                           | See the document on decimals and make columns and links explicit.                   |
| `50320`, `50321`          | A new table or view contains decimal values already converted, but the resulting columns are not `LO_DECIMAL`.        | Read the warning and check that the definition obtained is the one wanted.          |
| `50322`                   | Another connection changed the data during a read in blocks.                                                         | Use **Refresh** and repeat the operation.                                           |
| `50400`, `50401`, `50408` | A dependency prevents the deletion or modification of the structure.                                                 | Identify the relationships, views, triggers or keys cited in the message.           |
| `50402`–`50407`           | Data incompatible with a new mandatory column, a conversion, a relationship or a key.                                | Correct the data reported before trying again.                                      |
| `50409`                   | There are unconfirmed changes.                                                                                       | Confirm or cancel the transaction before the structure change.                      |
| `50410`, `50411`          | A view cannot be modified, or a table definition cannot be reprocessed.                                              | Read the detail; it may be necessary to act through SQL.                            |
| `50412`                   | The column does not meet the conditions for the automatic value.                                                     | Use an integer column that is the only column of the primary key.                   |
| `50413`                   | Type not allowed in a STRICT table.                                                                                  | Choose a compatible `_ST` type.                                                     |
| `50901`                   | Unexpected driver error.                                                                                             | Keep the log and prepare a reproducible description.                                |


A SQLite constraint error may concern duplicate keys, NULL values that are not allowed, relationships or `CHECK` conditions. The detail makes it possible to tell the cases apart: it is not advisable to indiscriminately disable the checks to make the operation succeed.

### **5.5. Consulting the log and reproducing a problem**

Open **PySQLite settings…** and press **Open the log**. The lines show date and time, event category, connection identifier, method and message. The main categories are `ERROR`, `WARNING`, `INFO` and `TRACE`.

To analyze a problem, first identify the time at which it occurred and then the lines of the same connection. The log also contains activity of other documents: the last line of the file does not necessarily belong to the document being examined.

If the ordinary data are not enough, enable **Enable developer mode** in the global settings, reopen the document and repeat only the steps needed. Keep the log obtained and disable the mode when finished.

For a useful report, state:

- the extension version, operating system and LibreOffice version;
- the operation requested and the steps that produce the problem;
- the expected behavior and the observed result;
- the full text of the message and the time of the event;
- whether other programs are connected to the same file;
- the log for the test and, if possible, a small demonstration database with non-confidential data.

The trace may contain paths, commands and values passed to the driver. Before sharing it, check that it does not contain confidential information. To reproduce the problem it is preferable to use a copy with sample data.

## **6. Appendices**

### **6.1. Appendix A — Parameters in the address**

Parameter names and text values are case-sensitive. Write, for example, `ReadOnly=true`, not `readonly=True`. The allowed logical values are `true` and `false`.

The first pair follows `?`; the following ones are separated by `&`. The name of the same parameter must not be repeated. The three diagnostic log values are not connection parameters.


| Parameter            | Driver default value          | Allowed values                                          |
|----------------------|-------------------------------|---------------------------------------------------------|
| `CreateIfMissing`    | `false`                       | `true`, `false`                                         |
| `ReadOnly`           | `false`                       | `true`, `false`                                         |
| `LockTimeoutSeconds` | `5`                           | Integer from 0 upward.                                  |
| `ForeignKeys`        | `false`                       | `true`, `false`                                         |
| `JournalMode`        | `delete`                      | `delete`, `truncate`, `persist`, `memory`, `wal`, `off` |
| `TransactionMode`    | `free`                        | `free`, `blocking`, `exclusive`                         |
| `FullLoadLimit`      | `50000`                       | Integer from 1 upward.                                  |
| `WindowSize`         | `1000`                        | Integer from 1 upward.                                  |
| `DateTimeFormat`     | `text`                        | `text`, `unix`, `julian`                                |
| `DateTimeZone`       | `local`                       | `local`, `utc`; `local` only with the `text` format.    |
| `NamesLanguage`      | `auto`                        | `auto`, `en`, `it`, `fr`, `de`, `es`                    |
| `AutoIncrementReuse` | `false`                       | `true`, `false`                                         |
| `RowIdAsKey`         | `false`                       | Recognized parameter, but function not active.          |
| `OldLibraryWarning`  | `true`                        | `true`, `false`                                         |
| `DefensiveMode`      | `false`                       | `true`, `false`                                         |
| `UntrustedSchema`    | `false`                       | `true`, `false`; `true` enables the protection          |
| `LimitsProfile`      | `none`                        | `none`, `prudent`, `strict`                             |


The maximum limits of the window's numeric fields are not limits added by the reader of the parameters in the address. For ordinary use, keep to the ranges given in chapter 2.

Address examples:

- `C:\Dati\archivio.db3?ReadOnly=true`: opening for consultation only.
- `C:\Dati\archivio.db3?DefensiveMode=true&UntrustedSchema=true&LimitsProfile=prudent`: three protections enabled on the connection.
- `C:\Dati\nuovo.db3?CreateIfMissing=true`: creation if the file is missing.
- `C:\Dati\archivio.db3?DateTimeFormat=unix&DateTimeZone=utc`: Unix numeric format with UTC reference.

The parameter remains part of the saved address. To return to the value of the document settings, remove the corresponding pair and fix the separators, then save, close and reopen.

### **6.2. Appendix B — Types and representation of values**


| Type or group                                   | Aspects to consider                                                                                                                   |
|-------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `LO_TINYINT`                                    | Integer from -128 to 127.                                                                                                             |
| `LO_SMALLINT`                                   | Integer from -32768 to 32767.                                                                                                         |
| `LO_INTEGER`                                    | Integer from -2147483648 to 2147483647.                                                                                               |
| `LO_BIGINT`                                     | 64-bit signed integer.                                                                                                                |
| `LO_REAL`, `LO_DOUBLE`                          | Floating-point numbers; they do not guarantee decimal exactness in monetary calculations.                                             |
| `LO_NUMERIC`                                    | Integer or real numeric value according to the SQLite content; it is not a scaled decimal.                                            |
| `LO_DECIMAL(p,s)`                               | Scaled integer, with number of decimals `s` from 0 to 18. Values must fit within the 64-bit integer representation.                   |
| `LO_CHAR`, `LO_VARCHAR`, `LO_LONGVARCHAR`       | Texts; lengths and conversions must be considered in structure changes.                                                               |
| `LO_VARIANT`                                    | Columns without a single type: the content may vary from one record to another.                                                       |
| `LO_BOOLEAN`                                    | Written with 0 and 1; when read, a nonzero number is interpreted as true. NULL remains distinct from false.                           |
| `LO_DATE`, `LO_TIME`, `LO_TIMESTAMP`            | Dates and times according to the configured format and time reference. TIME and TIMESTAMP provide up to six fractional digits of seconds. |
| `LO_BINARY`, `LO_VARBINARY`, `LO_LONGVARBINARY` | Byte sequences, for example binary contents.                                                                                          |


The sizes declared by a type must not be interpreted as a promise that any other SQLite program will apply the same checks. SQLite can keep in an ordinary column contents different from those the driver expects; the error may emerge when PySQLite tries to read or convert them.

The external names `DECIMAL` and `NUMERIC` do not activate the `LO_DECIMAL` representation. A column with no declared type, or declared `ANY`, is presented by the driver as `LO_VARIANT`.

### **6.3. Appendix C — Added functions and conventions**

**Compatibility with the untrusted schema.** If `UntrustedSchema=true` is enabled, some non-deterministic functions listed in this appendix cannot be called from views, triggers, `CHECK` constraints, generated columns or expression indexes: `RAND`, `UUID`, `IDENTITY`, `CURDATE`, `TODAY`, `CURTIME`, `NOW`, `UNIX_TIMESTAMP()` and `UNIX_MILLIS()` (the last two without arguments). The functions remain available in ordinary direct SQL statements. See § 2.6.7.2.


The following list summarizes the functions registered by the driver, including some additional forms of functions already present in SQLite. The engine's native functions remain described in the SQLite documentation. The presence of a name does not imply all the variants and all the formats available in HSQLDB.


| Group                            | Names available through the driver                                                                                                                                                                                                                                        |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Uppercase, lowercase and comparison | `UPPER`, `LOWER`, `UCASE`, `LCASE`, `LIKE`; `NOCASE` comparison.                                                                                                                                                                                                       |
| Text                             | `LEFT`, `RIGHT`, `LOCATE`, `INSTR` with three arguments, `LPAD`, `RPAD`, `REPEAT`, `SPACE`, `REVERSE`, `REPLACE` with two arguments, `TRANSLATE`, `ASCII`, `BIT_LENGTH`, `CHAR_LENGTH`, `CHARACTER_LENGTH`, `INSERT`, `OVERLAY`, `SOUNDEX`, `DIFFERENCE`, `HEXTORAW`, `RAWTOHEX`. |
| Numbers and bits                 | `COT`, `TRUNCATE`, `TRUNC` with two arguments, `BITAND`, `BITOR`, `BITXOR`, `BITNOT`, `BITANDNOT`, `TO_NUMBER`, `WIDTH_BUCKET`, `RAND`.                                                                                                                                   |
| NULL values and choices          | `NVL`, `IFNULL`, `ISNULL`, `NVL2`, `CASEWHEN`, `DECODE`, `GREATEST`, `LEAST`.                                                                                                                                                                                             |
| Identification                   | `UUID`, `IDENTITY`, `USER`, `DATABASE`.                                                                                                                                                                                                                                   |
| Current date and time            | `CURDATE`, `TODAY`, `CURTIME`, `NOW`, `UNIX_TIMESTAMP`, `UNIX_MILLIS`.                                                                                                                                                                                                    |
| Parts of the date and time       | `YEAR`, `MONTH`, `DAY`, `DAYOFMONTH`, `HOUR`, `MINUTE`, `SECOND`, `QUARTER`, `DAYOFWEEK`, `DAYOFYEAR`, `WEEK`, `DAYS`, `SECONDS_SINCE_MIDNIGHT`, `DAYNAME`, `MONTHNAME`, `EXTRACT`.                                                                                       |
| Date calculations and conversions | `DATEADD`, `TIMESTAMPADD`, `DATEDIFF`, `TIMESTAMPDIFF`, `LAST_DAY`, `ADD_MONTHS`, `MONTHS_BETWEEN`, `NEXT_DAY`, `TO_CHAR`, `TO_DATE`, `TO_TIMESTAMP`.                                                                                                                    |


Some constructs require the SQL text to be rewritten by the driver, for example `CONVERT`, the keyword forms of `TRIM`, `POSITION`, `SUBSTRING`, `OVERLAY` and `EXTRACT`, and the sequences in curly braces. Their availability through PySQLite does not mean that the original text can be run unchanged by another SQLite program.

For regular expressions:


| Form                                                                                | Result                                                                           |
|-------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| `text REGEXP pattern`                                                               | True if the pattern is found in a part of the text.                              |
| `REGEXP_MATCHES(text, pattern)`, `REGEXP_LIKE(text, pattern)`                       | True if the pattern matches the entire text.                                     |
| `REGEXP_SUBSTRING(text, pattern)`, `REGEXP_SUBSTR(text, pattern)`                   | First match, keeping the original text; NULL if not found.                       |
| `REGEXP_SUBSTRING_ARRAY(text, pattern)`                                              | JSON text with the matches; `[]` if there are none.                              |
| `REGEXP_COUNT(text, pattern)`                                                        | Number of matches.                                                               |
| `REGEXP_INSTR(text, pattern)`                                                        | Position of the first match, starting from 1; 0 if absent.                       |
| `REGEXP_REPLACE(text, pattern [, replacement [, start [, how_many [, options]]]])`  | Text with the requested replacements.                                            |


In `REGEXP_REPLACE`, `start` must be 1; `how_many=0` means all matches. In the replacement, `$1`, `$2` and so on refer to the captured groups. The `n` option extends the dot to newline characters; `m` enables multi-line anchors. The `i` and `c` options do not change the comparison, which remains insensitive to case and accents.

The pattern syntax remains that of Python even though the `$1` convention is used in the replacement. For complex patterns it is therefore not enough to copy a Java expression without checking it.

### **6.4. Appendix D — Copies of the document and of the database**

To keep the entire work, both the `.odb` document and the SQLite database must be considered. The former may contain forms, queries and macros that are not present in the latter.

A simple copy of the two files should be made after finishing the changes and closing all the connections that use the database, including those of other programs. This avoids copying the file while it is being updated.

If journal files remain, especially a `-wal` file, do not delete them to obtain a single file: they may contain information the database needs. For a copy while the database is in use, a SQLite backup procedure designed for this purpose is needed, not just a copy of the main file. The driver does not provide a dedicated backup command in the interface.

To check a copy, keep the original intact and link a test Base document to the copied database. A copy of the `.odb` in fact still contains the old path until it is modified.

Check opening, a few tables and the functions used by the document before replacing the working files. Copying or moving only the Base document does not transfer the database it is linked to.

### **6.5. Appendix E — Reference documentation**

For decimals, use the document "Exact Decimals in SQL Commands" (in the `docs` folder of the extension's source code, downloadable from the project's GitHub repository, "Manual - Exact Decimals in SQL Commands").

The general instructions for LibreOffice Base and the SQL reference of SQLite remain in their respective guides. This manual describes the integration provided by PySQLite and does not replace those references.

### **6.6. Appendix F — Glossary**


| Term                     | Meaning in the manual                                                                           |
|--------------------------|-------------------------------------------------------------------------------------------------|
| Base document            | `.odb` file with the connection to the database and the document's objects.                     |
| SQLite database          | External file with tables, data and objects defined in the database.                            |
| Connection               | Link opened by the driver to the database; it has its own settings and transactions.            |
| SDBC                     | StarOffice Database Connectivity, the database access interface used by LibreOffice.           |
| Primary key              | One or more columns that uniquely identify each record.                                         |
| Foreign key              | Constraint that links values of one table to a key of another table.                            |
| NULL                     | Absence of a value; distinct from zero and from an empty string.                                |
| Commit                   | Confirmation of the changes included in the transaction.                                        |
| Rollback                 | Cancellation of the unconfirmed changes of the transaction.                                     |
| Autocommit               | Automatic confirmation of operations, without a manual transaction left open.                   |
| Write journal            | Mechanism and support file used by SQLite to manage transactions.                               |
| Diagnostic log           | Text file with events and messages from the driver.                                             |
| Base query               | Command kept in the `.odb` document.                                                            |
| SQLite view              | SQL definition kept in the database and usable as a source for reading.                         |
| Trigger                  | Operation defined in the database and run by SQLite when an event occurs.                       |
