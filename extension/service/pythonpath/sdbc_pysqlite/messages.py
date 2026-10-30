# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

from collections import namedtuple

from sdbc_pysqlite import errors
from sdbc_pysqlite import parameters

Described = namedtuple("Described", "message sqlstate error_code is_warning")

_PATH_GUIDE_IT = (
    "Il file del database non esiste ancora, oppure il percorso indicato non è corretto.\n\n"
    "Se stai creando il documento per la prima volta, questo messaggio è normale.\n\n"
    "Per proseguire:\n"
    "1. Vai in Modifica → Database → Impostazioni PySQLite.\n"
    "2. Nella categoria «Accesso al database» indica un percorso valido, nome del file compreso "
    "(puoi usare «Sfoglia…»).\n"
    "3. Se il file non esiste ancora, scegli «sì» in «Crea il database se non esiste».\n"
    "4. Se vuoi, scegli anche le altre impostazioni navigando tra le categorie.\n"
    "5. Salva, chiudi e riapri il documento.\n\n"
    "Se hai attivato la creazione, alla riapertura comparirà un avviso che informa della creazione "
    "del nuovo file.\n\n"
    "Dettaglio: ")
_PATH_GUIDE_EN = (
    "The database file does not exist yet, or the given path is not correct.\n\n"
    "If you are creating the document for the first time, this message is normal.\n\n"
    "To continue:\n"
    "1. Go to Edit → Database → PySQLite settings.\n"
    "2. In the \"Database access\" category give a valid path, including the file name "
    "(you can use \"Browse…\").\n"
    "3. If the file does not exist yet, choose \"yes\" in \"Create the database if it does not exist\".\n"
    "4. If you wish, also choose the other settings by browsing the categories.\n"
    "5. Save, close and reopen the document.\n\n"
    "If you turned creation on, a notice about the creation of the new file will appear when the "
    "document is reopened.\n\n"
    "Detail: ")


_CATALOG = {
    errors.FILE_NOT_FOUND: (
        "E", "08001",
        _PATH_GUIDE_IT + "il file non esiste: {percorso}",
        _PATH_GUIDE_EN + "the file does not exist: {percorso}"),
    errors.PATH_IS_FOLDER: (
        "E", "08001",
        _PATH_GUIDE_IT + "il percorso è una cartella, manca il nome del file: {percorso}",
        _PATH_GUIDE_EN + "the path is a folder, the file name is missing: {percorso}"),
    errors.NOT_A_DATABASE: (
        "E", "08001",
        "Il file non è un database SQLite valido: {percorso}. Controlla di aver scelto il file giusto.",
        "The file is not a valid SQLite database: {percorso}. Check that you chose the right file."),
    errors.CANNOT_CREATE: (
        "E", "08001",
        "Impossibile creare il file o le cartelle: {percorso}. Controlla i permessi e lo spazio sul disco.",
        "Cannot create the file or folders: {percorso}. Check the permissions and the free disk space."),
    errors.ADDRESS_INVALID: (
        "E", "08001",
        "L'indirizzo di connessione è vuoto o non valido: «{indirizzo}». Scrivi il percorso del file.",
        "The connection address is empty or invalid: \"{indirizzo}\". Write the file path."),
    errors.FILE_CREATED: (
        "A", "01000",
        "Il nuovo database è stato creato.\n\n"
        "Il file non esisteva e, avendo attivato la creazione automatica, il driver lo ha creato vuoto. "
        "Da ora in poi il documento lo aprirà normalmente e questo avviso non comparirà più.\n\n"
        "Se non ti aspettavi la creazione di un nuovo file, controlla il percorso in Modifica → Database "
        "→ Impostazioni PySQLite.",
        "The new database has been created.\n\n"
        "The file did not exist and, since you turned automatic creation on, the driver created it empty. "
        "From now on the document will open normally and this notice will no longer appear.\n\n"
        "If you did not expect a new file to be created, check the path in Edit → Database → PySQLite "
        "settings."),
    errors.FOLDER_NOT_FOUND: (
        "E", "08001",
        _PATH_GUIDE_IT + "la cartella non esiste: {cartella}",
        _PATH_GUIDE_EN + "the folder does not exist: {cartella}"),
    errors.PATH_BAD_CHARACTERS: (
        "E", "08001",
        "Il percorso contiene caratteri non ammessi da Windows ({caratteri}): {percorso}. Correggi il percorso.",
        "The path contains characters not allowed by Windows ({caratteri}): {percorso}. Correct the path."),
    errors.SQLITE_LIBRARY: (
        "E", "08001",
        "Il componente SQLite incluso nell'estensione non è stato trovato o non si carica ({dettaglio}). "
        "File: {percorso}. Reinstalla l'estensione.",
        "The SQLite component included in the extension was not found or cannot be loaded ({dettaglio}). "
        "File: {percorso}. Reinstall the extension."),
    errors.LOG_NOT_WRITABLE: (
        "E", "HY000",
        "La cartella del registro non è scrivibile: {cartella}. Cambia LogPath o i permessi della cartella.",
        "The log folder is not writable: {cartella}. Change LogPath or the folder permissions."),
    errors.INVALID_VALUE: (
        "E", "HY000",
        "Valore non valido per l'impostazione {nome}: «{valore}». Valori ammessi: {ammessi}.",
        "Invalid value for setting {nome}: \"{valore}\". Allowed values: {ammessi}."),
    errors.UNKNOWN_PARAMETER: (
        "E", "HY000",
        "Parametro sconosciuto nell'indirizzo: «{nome}». Parametri noti: {ammessi}.",
        "Unknown parameter in the address: \"{nome}\". Known parameters: {ammessi}."),
    errors.PARAMETER_NO_EQUALS: (
        "E", "HY000",
        "Parametro senza il segno =: «{gruppo}». Usa il formato ?nome=valore&nome=valore.",
        "Parameter without the = sign: \"{gruppo}\". Use the format ?name=value&name=value."),
    errors.PARAMETER_REPEATED: (
        "E", "HY000",
        "Parametro ripetuto nell'indirizzo: «{nome}». Indicalo una sola volta.",
        "Parameter repeated in the address: \"{nome}\". Give it only once."),
    errors.JOURNAL_MODE_IN_USE: (
        "E", "HYT00",
        "Non è stato possibile impostare il giornale «{richiesto_m}»: il file del database usa il giornale "
        "«{effettivo_m}», impostato da un altro programma o da un'altra connessione, e in questo momento è in "
        "uso e non può essere cambiato.\n\n"
        "Giornale richiesto dalle impostazioni: {richiesto_m}. Giornale trovato nel file: {effettivo_m}.\n\n"
        "Puoi procedere in tre modi:\n"
        "1. Chiudere l'altro programma che usa il file e riaprire il documento: il driver riporterà il "
        "giornale a «{richiesto_m}».\n"
        "2. Solo per questa volta: in «Modifica → Database → Proprietà…» aggiungere in fondo all'indirizzo "
        "JournalMode={effettivo} (preceduto da & se l'indirizzo ha già altri parametri, da ? se non ne ha).\n"
        "3. Per sempre: in «Modifica → Database → Impostazioni PySQLite…», categoria «Integrità e "
        "transazioni», scegliere il «Giornale di protezione delle scritture» «{effettivo_m}».",
        "The \"{richiesto_m}\" journal could not be set: the database file uses the \"{effettivo_m}\" journal, "
        "set by another program or connection, and it is in use right now and cannot be changed.\n\n"
        "Journal requested by the settings: {richiesto_m}. Journal found in the file: {effettivo_m}.\n\n"
        "You can proceed in three ways:\n"
        "1. Close the other program using the file and reopen the document: the driver will set the journal "
        "back to \"{richiesto_m}\".\n"
        "2. Just for this time: in \"Edit → Database → Properties…\" add JournalMode={effettivo} at the end "
        "of the address (preceded by & if the address already has parameters, by ? if it has none).\n"
        "3. For good: in \"Edit → Database → PySQLite settings…\", category \"Integrity and transactions\", "
        "choose the \"Write protection journal\" \"{effettivo_m}\"."),
    errors.JOURNAL_MODE_NOT_OBTAINED: (
        "A", "01000",
        "Modo di giornale richiesto: {richiesto}. SQLite ha adottato: {effettivo}. "
        "L'opzione richiesta non è disponibile per questo database.",
        "Journal mode requested: {richiesto}. SQLite adopted: {effettivo}. "
        "The requested option is not available for this database."),
    errors.PROTECTION_NOT_OBTAINED: (
        "A", "01000",
        "Protezioni richieste e non ottenute: {protezioni}. La libreria SQLite in uso non le supporta o non "
        "ha accettato il valore. La connessione è stata aperta senza.",
        "Protections requested and not obtained: {protezioni}. The SQLite library in use does not support "
        "them or did not accept the value. The connection was opened without them."),
    errors.ISOLATION_IGNORED: (
        "A", "01000",
        "Livello di isolamento richiesto: {livello}. Il driver permette una sola scrittura alla volta "
        "(come SQLite): la richiesta è accettata e ignorata.",
        "Isolation level requested: {livello}. The driver allows only one write at a time "
        "(as SQLite does): the request is accepted and ignored."),
    errors.CONNECTION_CLOSED: (
        "E", "08003",
        "L'operazione richiede una connessione aperta, ma la connessione è stata chiusa.",
        "The operation needs an open connection, but the connection has been closed."),
    errors.UNCOMMITTED_DISCARDED: (
        "A", "01000",
        "Connessione chiusa con modifiche non confermate: sono state scartate.",
        "Connection closed with uncommitted changes: they were discarded."),
    errors.OLD_LIBRARY: (
        "A", "01000",
        "La libreria SQLite è la versione {versione}; il driver è provato con la 3.54.1 o successive. "
        "L'apertura continua, ma alcune funzioni potrebbero non funzionare.",
        "The SQLite library is version {versione}; the driver is tested with 3.54.1 or later. "
        "The connection is opened anyway, but some features may not work."),
    errors.QUERY_NO_ROWS: (
        "A", "01000",
        "Il comando non restituisce righe, ma è stato eseguito con executeQuery: il risultato è vuoto.",
        "The command returns no rows, but it was run with executeQuery: the result is empty."),
    errors.UPDATE_RETURNED_ROWS: (
        "A", "01000",
        "Il comando restituisce righe, ma è stato eseguito con executeUpdate: {n} righe scartate.",
        "The command returns rows, but it was run with executeUpdate: {n} rows discarded."),
    errors.STATEMENT_CLOSED: (
        "E", "08003",
        "L'operazione richiede un comando aperto, ma il comando è stato chiuso.",
        "The operation needs an open statement, but the statement has been closed."),
    errors.RESULT_CLOSED: (
        "E", "24000",
        "L'operazione richiede un risultato aperto, ma il risultato è stato chiuso.",
        "The operation needs an open result, but the result has been closed."),
    errors.INTERRUPTED: (
        "E", "HY008",
        "Operazione interrotta: il comando è stato annullato prima di finire.",
        "Operation interrupted: the statement was cancelled before it finished."),
    errors.BATCH_RETURNED_ROWS: (
        "E", "HY000",
        "Un comando di un blocco restituisce righe ({comando}): in un blocco sono ammessi solo comandi "
        "che non restituiscono righe. I comandi precedenti sono stati eseguiti. Eseguilo da solo.",
        "A command in a batch returns rows ({comando}): only commands that return no rows are allowed "
        "in a batch. The previous commands were executed. Run it on its own."),
    errors.COLUMN_OUT_OF_RANGE: (
        "E", "07009",
        "Colonna {colonna} inesistente: il risultato ha {totale} colonne.",
        "Column {colonna} does not exist: the result has {totale} columns."),
    errors.NO_CURRENT_ROW: (
        "E", "24000",
        "Nessuna riga corrente nel risultato: posizionati su una riga prima di leggere un valore.",
        "No current row in the result: move to a row before reading a value."),
    errors.VALUE_NOT_CONVERTIBLE: (
        "E", "22018",
        "Il valore «{valore}» ({origine}) non si può leggere come {tipo} senza perdere informazione. "
        "Leggilo come un altro tipo o correggi il dato.",
        "The value \"{valore}\" ({origine}) cannot be read as {tipo} without losing information. "
        "Read it as another type or correct the data."),
    errors.VALUE_OUT_OF_RANGE: (
        "E", "22003",
        "Il valore {valore} ({origine}) è fuori dall'intervallo del tipo {tipo}. "
        "Il valore nel file non è stato modificato.",
        "The value {valore} ({origine}) is outside the range of type {tipo}. "
        "The value in the file was not changed."),
    errors.DATE_UNREADABLE: (
        "E", "22007",
        "Il valore «{valore}» ({origine}) non è una data o un'ora leggibile. Correggi il dato nel file.",
        "The value \"{valore}\" ({origine}) is not a readable date or time. Correct the data in the file."),
    errors.RESULT_READ_ONLY: (
        "E", "HY000",
        "Il risultato è in sola lettura: la modifica dei dati da un risultato non è ancora disponibile.",
        "The result is read-only: changing data through a result is not available yet."),
    errors.PARAMETER_NOT_SET: (
        "E", "07002",
        "Il parametro n. {numero} non ha un valore. In un comando preparato imposta tutti i parametri "
        "prima di eseguire; in un comando SQL diretto (per esempio la finestra SQL) il «?» non è "
        "ammesso: scrivi il valore nel testo. Nessun comando è stato eseguito.",
        "Parameter no. {numero} has no value. In a prepared command set all parameters before running; "
        "in a direct SQL command (for example the SQL window) the \"?\" is not allowed: write the value "
        "in the text. No command was run."),
    errors.PARAMETER_OUT_OF_RANGE: (
        "E", "07009",
        "Il parametro n. {numero} non esiste: il comando ha {totale} parametri.",
        "Parameter no. {numero} does not exist: the command has {totale} parameters."),
    errors.BATCH_ROW_FAILED: (
        "E", "HY000",
        "Lotto interrotto alla riga {riga}: {dettaglio}.",
        "Batch stopped at row {riga}: {dettaglio}."),
    errors.PARAMETER_NO_COLUMN: (
        "A", "01000",
        "Il parametro n. {numero} non è abbinato a nessuna colonna: il valore è passato così com'è, "
        "senza conversioni per colonna.",
        "Parameter no. {numero} is not matched to any column: the value was passed as is, without "
        "per-column conversion."),
    errors.DECIMAL_AMBIGUOUS: (
        "E", "42000",
        "Il comando non è stato eseguito: la colonna «{colonna}» esiste in più tabelle ({tabelle}) e almeno una "
        "è di tipo LO_DECIMAL, che non ha lo stesso formato delle altre: il driver non può sapere quale si "
        "intende e il valore sarebbe sbagliato. Scrivi il nome della tabella davanti alla colonna, per esempio "
        "persone.importo.",
        "The command was not run: column \"{colonna}\" exists in more than one table ({tabelle}) and at least "
        "one is of type LO_DECIMAL, which does not have the same format as the others: the driver cannot tell "
        "which one is meant and the value would be wrong. Write the table name in front of the column, for "
        "example persone.importo."),
    errors.DECIMAL_NATURAL_JOIN: (
        "E", "42000",
        "Il comando non è stato eseguito: NATURAL JOIN e USING confrontano i numeri come sono salvati, e la "
        "colonna «{colonna}» è di tipo LO_DECIMAL. Il tipo LO_DECIMAL va usato solo tra colonne dello stesso "
        "tipo e della stessa scala. Usa JOIN ... ON tabella1.colonna = tabella2.colonna.",
        "The command was not run: NATURAL JOIN and USING compare numbers as they are stored, and column "
        "\"{colonna}\" is of type LO_DECIMAL. LO_DECIMAL should only be used between columns of the same type "
        "and the same scale. Use JOIN ... ON table1.column = table2.column."),
    errors.DECIMAL_NOT_UNDERSTOOD: (
        "E", "42000",
        "Il comando non è stato eseguito: nomina una colonna LO_DECIMAL ma il driver non riesce a capire come "
        "tradurlo ({dettaglio}). Riscrivi il comando in una forma più semplice, per esempio con nomi di "
        "colonna preceduti dal nome della tabella.",
        "The command was not run: it names an LO_DECIMAL column but the driver cannot work out how to "
        "translate it ({dettaglio}). Rewrite the command in a simpler form, for example with column names "
        "preceded by the table name."),
    errors.DECIMAL_TRIGGER: (
        "E", "42000",
        "Il trigger non è stato creato: usa la colonna «{colonna}», di tipo LO_DECIMAL. I trigger lavorano sui "
        "numeri come sono salvati, non su quelli con la virgola, e per ora non si traducono. Esegui "
        "l'operazione con un comando o una macro a parte, oppure scrivi il trigger tenendo conto che i valori "
        "sono moltiplicati per la scala.",
        "The trigger was not created: it uses column \"{colonna}\", of type LO_DECIMAL. Triggers work on "
        "numbers as they are stored, not on numbers with decimals, and are not translated for now. Run the "
        "operation with a separate command or macro, or write the trigger taking into account that values "
        "are multiplied by the scale."),
    errors.DECIMAL_NEW_TABLE_PLAIN: (
        "A", "01000",
        "La tabella è stata creata con i valori già con la virgola, ma la colonna nuova è un numero normale, "
        "non LO_DECIMAL. Per averla decimale crea prima la tabella con LO_DECIMAL(p,s) e poi copia con "
        "INSERT ... SELECT.",
        "The table was created with values that already have decimals, but the new column is a plain number, "
        "not LO_DECIMAL. To make it decimal, create the table first with LO_DECIMAL(p,s) and then copy with "
        "INSERT ... SELECT."),
    errors.DECIMAL_VIEW_PLAIN: (
        "A", "01000",
        "La colonna della vista mostra già i numeri con la virgola ed è un numero normale, non LO_DECIMAL.",
        "The view column already shows numbers with decimals and is a plain number, not LO_DECIMAL."),
    errors.TABLE_USED_BY_RELATIONS: (
        "E", "23000",
        "La tabella «{tabella}» non è stata eliminata: è usata dalle relazioni con le tabelle {tabelle}. "
        "Togli prima le relazioni dalla finestra Relazioni.",
        "Table \"{tabella}\" was not dropped: it is used by relations with tables {tabelle}. "
        "Remove the relations from the Relations window first."),
    errors.COLUMN_IN_USE: (
        "E", "23000",
        "La colonna «{colonna}» non è stata eliminata: è usata da {oggetti}. Togli prima ciò che la usa.",
        "Column \"{colonna}\" was not dropped: it is used by {oggetti}. Remove what uses it first."),
    errors.COLUMN_NOT_NULL_NO_DEFAULT: (
        "E", "23000",
        "La colonna «{colonna}» non è stata aggiunta: è obbligatoria, ma la tabella ha già {n} righe. "
        "Aggiungila non obbligatoria, oppure aggiungila con un comando SQL che indichi un valore predefinito.",
        "Column \"{colonna}\" was not added: it is required, but the table already has {n} rows. "
        "Add it as not required, or add it with an SQL command that gives a default value."),
    errors.CONVERSION_IMPOSSIBLE: (
        "E", "22018",
        "La colonna «{colonna}» non è stata modificata: {n} righe non si possono convertire in {tipo}; "
        "la prima è «{valore}» ({chiave}). La tabella non è cambiata.",
        "Column \"{colonna}\" was not changed: {n} rows cannot be converted to {tipo}; the first is "
        "\"{valore}\" ({chiave}). The table was not changed."),
    errors.CONVERSION_NULLS: (
        "E", "23000",
        "La colonna «{colonna}» non è stata resa obbligatoria: {n} righe hanno la cella vuota; la prima è "
        "({chiave}). La tabella non è cambiata.",
        "Column \"{colonna}\" was not made required: {n} rows have an empty cell; the first is "
        "({chiave}). The table was not changed."),
    errors.CONVERSION_TOO_MANY_DIGITS: (
        "E", "22003",
        "La colonna «{colonna}» non è stata modificata: {n} valori hanno troppe cifre per {tipo}; il primo è "
        "{valore} ({chiave}). La tabella non è cambiata.",
        "Column \"{colonna}\" was not changed: {n} values have too many digits for {tipo}; the first is "
        "{valore} ({chiave}). The table was not changed."),
    errors.RELATION_VIOLATED: (
        "E", "23000",
        "La relazione non è stata creata: {n} righe di «{tabella}» si riferiscono a valori che non esistono "
        "in «{tabellaRif}»; la prima ha {colonna} = {valore}.",
        "The relation was not created: {n} rows of \"{tabella}\" refer to values that do not exist in "
        "\"{tabellaRif}\"; the first has {colonna} = {valore}."),
    errors.PRIMARY_KEY_DUPLICATES: (
        "E", "23000",
        "La chiave primaria non è stata creata: {n} valori sono doppi; il primo è {valore}.",
        "The primary key was not created: {n} values are duplicated; the first is {valore}."),
    errors.COLUMN_IN_RELATION: (
        "E", "23000",
        "La colonna «{colonna}» non è stata modificata: è usata dalla relazione «{relazione}» con la tabella "
        "«{tabella}». Togli la relazione dalla finestra Relazioni, modifica la colonna e rimettila.",
        "Column \"{colonna}\" was not changed: it is used by relation \"{relazione}\" with table "
        "\"{tabella}\". Remove the relation from the Relations window, change the column and put the "
        "relation back."),
    errors.PENDING_CHANGES: (
        "E", "25000",
        "La struttura di «{tabella}» non è stata modificata: ci sono modifiche in sospeso. Confermale o "
        "annullale, poi riprova.",
        "The structure of \"{tabella}\" was not changed: there are pending changes. Commit or discard "
        "them, then try again."),
    errors.VIEW_NOT_ALTERED: (
        "E", "HY000",
        "La vista «{vista}» non è stata modificata: {dettaglio}. La vista precedente è rimasta com'era.",
        "View \"{vista}\" was not changed: {dettaglio}. The previous view was left as it was."),
    errors.DEFINITION_NOT_UNDERSTOOD: (
        "E", "HY000",
        "La struttura di «{tabella}» non è stata modificata: il driver non riesce a leggere la definizione "
        "della tabella nel file. Modificala con un comando SQL.",
        "The structure of \"{tabella}\" was not changed: the driver cannot read the table definition in "
        "the file. Change it with an SQL command."),
    errors.AUTO_VALUE_IMPOSSIBLE: (
        "E", "HY000",
        "Il valore automatico non è possibile per la colonna «{colonna}»: deve essere di tipo intero e "
        "l'unica colonna della chiave primaria della tabella.",
        "The automatic value is not possible for column \"{colonna}\": it must be of an integer type and "
        "the only column of the table's primary key."),
    errors.STRICT_TYPE_NOT_ALLOWED: (
        "E", "HY000",
        "La colonna «{colonna}» non è stata salvata: la tabella «{tabella}» è STRICT e non ammette il tipo "
        "«{tipo}». In una tabella STRICT scegli INTEGER_ST, REAL_ST, TEXT_ST, BLOB_ST o ANY_ST. "
        "La tabella non è cambiata.",
        "Column \"{colonna}\" was not saved: table \"{tabella}\" is STRICT and does not allow type "
        "\"{tipo}\". In a STRICT table choose INTEGER_ST, REAL_ST, TEXT_ST, BLOB_ST or ANY_ST. "
        "The table was not changed."),
    errors.RESULT_OUT_OF_DATE: (
        "E", "HY000",
        "ATTENZIONE: un'altra connessione ha modificato il database mentre i dati venivano letti, quindi "
        "l'elenco potrebbe non essere corretto. Premi «Aggiorna» (la freccia circolare che gira in senso "
        "orario: nel formulario la trovi nella barra in basso, nella tabella nella barra in alto), poi riprova.",
        "WARNING: another connection has changed the database while the data was being read, so the list "
        "may be incorrect. Press \"Refresh\" (the circular arrow turning clockwise: in a form it is in the "
        "bar at the bottom, in a table in the bar at the top), then try again."),
    errors.UNEXPECTED: (
        "E", "HY000",
        "Errore imprevisto del driver: {dettaglio}. Segnalalo allegando il registro.",
        "Unexpected driver error: {dettaglio}. Report it, attaching the log."),
}

_FOOTER = {
    "it": "[codice %s · SQLState %s · %s]",
    "en": "[code %s · SQLState %s · %s]",
}


def _footer(code, sqlstate, location, language):
    return "\n\n" + _FOOTER[language] % (code, sqlstate, location)


_ADDRESS_FIRST = (
    errors.INVALID_VALUE, errors.UNKNOWN_PARAMETER, errors.PARAMETER_NO_EQUALS,
    errors.PARAMETER_REPEATED, errors.ADDRESS_INVALID,
)
_ADDRESS_PREFIX = {
    "it": "Indirizzo ricevuto: «{indirizzo}». ",
    "en": "Address received: \"{indirizzo}\". ",
}

_SQLITE = {
    1: ("ERROR", "42000", "ERRORE SQL", "SQL ERROR",
        "Errore di SQL: il motivo indicato da SQLite è tra parentesi.",
        "SQL error: SQLite's reason is given in brackets."),
    2: ("INTERNAL", "HY000", "ERRORE INTERNO SQLITE", "SQLITE INTERNAL ERROR",
        "Errore interno di SQLite (non dovrebbe capitare).",
        "Internal SQLite error (it should not happen)."),
    3: ("PERM", "HY000", "PERMESSO NEGATO", "PERMISSION DENIED",
        "Permesso negato sul file.",
        "Permission denied on the file."),
    4: ("ABORT", "40000", "OPERAZIONE ANNULLATA", "OPERATION ABORTED",
        "L'operazione è stata interrotta e annullata.",
        "The operation was interrupted and rolled back."),
    5: ("BUSY", "HYT00", "TIMEOUT: DATABASE OCCUPATO", "TIMEOUT: DATABASE BUSY",
        "Database attualmente occupato: è consentita una sola scrittura alla volta. "
        "Riprova, oppure aumenta LockTimeoutSeconds.",
        "Database currently busy: only one write at a time is allowed. "
        "Try again, or increase LockTimeoutSeconds."),
    6: ("LOCKED", "HYT00", "TIMEOUT: TABELLA BLOCCATA", "TIMEOUT: TABLE LOCKED",
        "Una tabella è bloccata da un'operazione della stessa connessione.",
        "A table is locked by an operation of the same connection."),
    7: ("NOMEM", "HY001", "MEMORIA ESAURITA", "OUT OF MEMORY",
        "Memoria esaurita.",
        "Out of memory."),
    8: ("READONLY", "25006", "DATABASE IN SOLA LETTURA", "DATABASE READ-ONLY",
        "Si tenta di scrivere in un database di sola lettura.",
        "An attempt was made to write to a read-only database."),
    9: ("INTERRUPT", "HY008", "OPERAZIONE INTERROTTA", "OPERATION INTERRUPTED",
        "L'operazione è stata interrotta su richiesta.",
        "The operation was interrupted on request."),
    10: ("IOERR", "HY000", "ERRORE DI LETTURA/SCRITTURA", "DISK I/O ERROR",
         "Errore di lettura o scrittura su disco.",
         "Error reading from or writing to the disk."),
    11: ("CORRUPT", "HY000", "DATABASE DANNEGGIATO", "DATABASE CORRUPT",
         "Il file del database è danneggiato.",
         "The database file is damaged."),
    12: ("NOTFOUND", "HY000", "ELEMENTO NON TROVATO", "NOT FOUND",
         "Elemento non trovato (codice interno, raro).",
         "Item not found (internal code, rare)."),
    13: ("FULL", "HY000", "DISCO PIENO", "DISK FULL",
         "Disco pieno, la scrittura non è possibile.",
         "The disk is full, writing is not possible."),
    14: ("CANTOPEN", "08001", "IMPOSSIBILE APRIRE IL FILE", "CANNOT OPEN FILE",
         "Il file non si può aprire.",
         "The file cannot be opened."),
    15: ("PROTOCOL", "HY000", "ERRORE DI BLOCCO DEL FILE", "FILE LOCKING ERROR",
         "Errore nel sistema di blocco del file tra programmi.",
         "Error in the file locking system between programs."),
    16: ("EMPTY", "HY000", "RISULTATO VUOTO", "EMPTY RESULT",
         "Codice riservato, non usato.",
         "Reserved code, not used."),
    17: ("SCHEMA", "HY000", "STRUTTURA CAMBIATA", "SCHEMA CHANGED",
         "La struttura del database è cambiata mentre la query era pronta.",
         "The database structure changed while the query was ready."),
    18: ("TOOBIG", "22001", "DATO TROPPO GRANDE", "DATA TOO BIG",
         "Un testo o un dato è troppo grande.",
         "A text or a value is too big."),
    19: ("CONSTRAINT", "23000", "VINCOLO VIOLATO", "CONSTRAINT VIOLATED",
         "Si viola un vincolo (duplicato, campo obbligatorio vuoto, chiave esterna...).",
         "A constraint is violated (duplicate, empty required field, foreign key...)."),
    20: ("MISMATCH", "22005", "TIPO DI DATO NON VALIDO", "DATA TYPE MISMATCH",
         "Tipo di dato incompatibile.",
         "Incompatible data type."),
    21: ("MISUSE", "HY010", "USO SCORRETTO DEL DRIVER", "LIBRARY MISUSE",
         "Funzioni chiamate nell'ordine sbagliato.",
         "Functions called in the wrong order."),
    22: ("NOLFS", "HY000", "FILE TROPPO GRANDE PER IL SISTEMA", "LARGE FILE UNSUPPORTED",
         "Il sistema non supporta file grandi (raro).",
         "The system does not support large files (rare)."),
    23: ("AUTH", "28000", "NON AUTORIZZATO", "NOT AUTHORIZED",
         "Operazione non autorizzata.",
         "Operation not authorized."),
    24: ("FORMAT", "HY000", "FORMATO NON VALIDO", "INVALID FORMAT",
         "Codice riservato, non usato.",
         "Reserved code, not used."),
    25: ("RANGE", "07009", "INDICE FUORI INTERVALLO", "INDEX OUT OF RANGE",
         "Un parametro o una colonna indicata non esiste (numero fuori intervallo).",
         "A parameter or column that was given does not exist (number out of range)."),
    26: ("NOTADB", "08001", "FILE NON È UN DATABASE", "NOT A DATABASE FILE",
         "Il file non è un database SQLite.",
         "The file is not a SQLite database."),
    27: ("NOTICE", "01000", "AVVISO DI SQLITE", "SQLITE NOTICE",
         "Segnalazione di SQLite, non un errore.",
         "A SQLite notice, not an error."),
    28: ("WARNING", "01000", "AVVERTIMENTO DI SQLITE", "SQLITE WARNING",
         "Avvertimento di SQLite, non un errore.",
         "A SQLite warning, not an error."),
}

_CONSTRAINT_LABELS = {
    275: ("CONDIZIONE DI CONTROLLO NON RISPETTATA", "CHECK CONDITION FAILED"),
    787: ("CHIAVE ESTERNA NON VALIDA", "FOREIGN KEY VIOLATED"),
    1299: ("CAMPO OBBLIGATORIO VUOTO", "REQUIRED FIELD EMPTY"),
    1555: ("CHIAVE PRIMARIA DUPLICATA", "PRIMARY KEY DUPLICATE"),
    2067: ("VALORE DUPLICATO", "DUPLICATE VALUE"),
}


class _SafeValues(dict):

    def __missing__(self, key):
        return "{" + key + "}"


def normalize_language(language):
    return "it" if str(language).lower().startswith("it") else "en"


def _describe_sqlite(exception, path, language, location):
    code = getattr(exception, "sqlite_errorcode", None) or 1
    name = getattr(exception, "sqlite_errorname", None)
    principal = code & 0xFF
    entry = _SQLITE.get(principal, _SQLITE[1])
    short_name, sqlstate, label_it, label_en, meaning_it, meaning_en = entry
    if not name:
        name = "SQLITE_" + short_name
    label = label_it if language == "it" else label_en
    if principal == 19 and code in _CONSTRAINT_LABELS:
        label = _CONSTRAINT_LABELS[code][0 if language == "it" else 1]
    meaning = meaning_it if language == "it" else meaning_en
    where = ("File: %s. " % path) if path else ""
    text = "%s (%s %d, SQLState %s). %s%s (%s)" % (
        label, name, code, sqlstate, where, meaning, exception)
    text += _footer(name + " " + str(code), sqlstate, location, language)
    return Described(text, sqlstate, code, principal in (27, 28))


def describe(error, language, location):
    language = normalize_language(language)
    if error.sqlite is not None:
        return _describe_sqlite(error.sqlite, error.values.get("percorso", ""), language, location)
    entry = _CATALOG.get(error.code)
    if entry is None:
        text = "%s %s" % ("Errore del driver" if language == "it" else "Driver error", error.code)
        text += _footer(error.code, "HY000", location, language)
        return Described(text, "HY000", error.code or 0, False)
    kind, sqlstate, text_it, text_en = entry
    template = text_it if language == "it" else text_en
    values = _SafeValues(error.values)
    if error.code == errors.INVALID_VALUE and "ammessi" not in values:
        if values.get("ammessi_chiave") == "pair":
            values["ammessi"] = parameters.pair_text(language)
        else:
            values["ammessi"] = parameters.allowed_text(values.get("nome", ""), language)
    if error.code == errors.JOURNAL_MODE_IN_USE:
        values["richiesto_m"] = str(values.get("richiesto", "")).upper()
        values["effettivo_m"] = str(values.get("effettivo", "")).upper()
    if error.code in _ADDRESS_FIRST and "{indirizzo}" not in template and "indirizzo" in values:
        template = _ADDRESS_PREFIX[language] + template
    message = template.format_map(values) + _footer(error.code, sqlstate, location, language)
    return Described(message, sqlstate, error.code, kind == "A")
