# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import html
import re
from dataclasses import dataclass

from sdbc_pysqlite import DEFAULT_RETENTION_DAYS
from sdbc_pysqlite import parameters

LANGUAGES = ("it", "en")


def pick(texts, language):
    return texts.get(language) or texts.get("en") or ""


@dataclass(frozen=True)
class Group:
    key: str
    title: dict
    options_only: bool = False
    connection: bool = False


@dataclass
class Field:
    name: str
    group: str
    kind: str
    label: dict
    note: dict
    choices: tuple = ()
    minimum: int = 0
    maximum: int = None
    enabled: bool = True
    choice_notes: dict = None

    @property
    def options_only(self):
        return self.name in LOG_NAMES


LOG_NAMES = ("Trace", "LogPath", "LogRetentionDays")

GROUPS = (
    Group("log", {"it": "Registro diagnostico", "en": "Diagnostic log"}, options_only=True),
    Group("access", {"it": "Accesso al database", "en": "Database access"}, connection=True),
    Group("integrity", {"it": "Integrità e transazioni", "en": "Integrity and transactions"}, connection=True),
    Group("results", {"it": "Consultazione risultati", "en": "Reading results"}, connection=True),
    Group("formats", {"it": "Formati", "en": "Formats"}, connection=True),
    Group("keys", {"it": "Chiavi primarie", "en": "Primary keys"}, connection=True),
    Group("security", {"it": "Sicurezza", "en": "Security"}, connection=True),
    Group("system", {"it": "Sistema", "en": "System"}, connection=True),
)

FIELDS = (
    Field("Trace", "log", "bool",
          {"it": "Abilita modalità sviluppatore", "en": "Enable developer mode"},
          {"it": "Oltre ai messaggi di errore, vengono registrate anche le operazioni eseguite dal driver. "
                 "Questa modalità permette di ottenere informazioni più dettagliate nel registro diagnostico, "
                 "utili per individuare e analizzare eventuali problemi di funzionamento. Il file del registro "
                 "può diventare molto grande: conviene attivarla solo per individuare un problema e "
                 "disattivarla poi.",
           "en": "Besides error messages, the operations performed by the driver are logged too. This gives "
                 "more detailed information in the diagnostic log, useful to find and analyze problems. The "
                 "log file can become very large: turn this on only to track down a problem, then turn it off."}),
    Field("LogPath", "log", "text",
          {"it": "Cartella del registro diagnostico", "en": "Diagnostic log folder"},
          {"it": "Se non viene specificata una cartella, il registro diagnostico viene salvato nella cartella "
                 "«sdbc-pysqlite» del profilo utente di LibreOffice.",
           "en": "If no folder is given, the diagnostic log is saved in the «sdbc-pysqlite» folder of the "
                 "LibreOffice user profile."}),
    Field("LogRetentionDays", "log", "int",
          {"it": "Periodo di conservazione del registro diagnostico (giorni)",
           "en": "Diagnostic log retention (days)"},
          {"it": "Stabilisce per quanti giorni vengono conservati i file del registro diagnostico. I file che "
                 "superano il periodo di conservazione vengono eliminati automaticamente.",
           "en": "Sets how many days the diagnostic log files are kept. Files older than that are deleted "
                 "automatically."}, minimum=1, maximum=3650),
    Field(parameters.CREATE_IF_MISSING, "access", "bool",
          {"it": "Crea il database se non esiste", "en": "Create the database if it does not exist"},
          {"it": "Se il file del database specificato non esiste, il driver ne crea automaticamente uno "
                 "nuovo. Se questa opzione è disattivata, il tentativo di connessione a un database "
                 "inesistente restituisce un errore.",
           "en": "If the specified database file does not exist, the driver creates a new one. If this "
                 "option is off, trying to connect to a missing database returns an error."}),
    Field(parameters.READ_ONLY, "access", "bool",
          {"it": "Apri il database in sola lettura", "en": "Open the database read-only"},
          {"it": "Apre il database in modalità di sola lettura, consentendo la consultazione dei dati ma "
                 "impedendo qualsiasi operazione che ne modifichi il contenuto.",
           "en": "Opens the database read-only: data can be consulted but nothing that changes its content "
                 "is allowed."}),
    Field(parameters.LOCK_TIMEOUT_SECONDS, "access", "int",
          {"it": "Timeout per database occupato (secondi)", "en": "Busy database timeout (seconds)"},
          {"it": "Stabilisce il tempo massimo di attesa quando un'operazione non può essere eseguita a causa "
                 "di un blocco imposto da un'altra connessione al database. Durante questo intervallo il "
                 "driver attende che il blocco venga rilasciato; se il tempo massimo viene raggiunto senza "
                 "che l'operazione possa proseguire, viene restituito un errore. Il valore 0 disabilita "
                 "l'attesa.",
           "en": "Sets the maximum wait when an operation cannot run because another connection holds a lock "
                 "on the database. During this time the driver waits for the lock to be released; if the "
                 "limit is reached before the operation can go on, an error is returned. 0 disables the "
                 "wait."}, minimum=0, maximum=86400),
    Field(parameters.FOREIGN_KEYS, "integrity", "bool",
          {"it": "Attiva il controllo dell'integrità referenziale",
           "en": "Enable referential integrity checking"},
          {"it": "Verifica che i valori delle chiavi esterne corrispondano a record esistenti nelle tabelle "
                 "a cui fanno riferimento. Il controllo viene effettuato durante l'inserimento, la modifica "
                 "e l'eliminazione dei record e le operazioni che violano le regole vengono impedite. "
                 "Quando l'opzione è disattivata le relazioni restano definite, ma i vincoli non vengono "
                 "applicati.",
           "en": "Checks that foreign key values match existing records in the tables they refer to. The "
                 "check is done when records are inserted, changed or deleted, and operations that break "
                 "the rules are refused. When the option is off the relationships stay defined, but the "
                 "constraints are not enforced."}),
    Field(parameters.JOURNAL_MODE, "integrity", "choice",
          {"it": "Giornale di protezione delle scritture", "en": "Write protection journal"},
          {"it": "Stabilisce il metodo utilizzato da SQLite per scrivere e aggiornare i dati contenuti nel "
                 "database, garantendone la coerenza anche in caso di interruzioni impreviste. Le modalità "
                 "differiscono per il modo in cui le scritture vengono gestite e rese definitive, per le "
                 "prestazioni e per la gestione degli accessi contemporanei.",
           "en": "Sets the method SQLite uses to write and update the data in the database, keeping it "
                 "consistent even after unexpected interruptions. The modes differ in how writes are handled "
                 "and made final, in performance and in how simultaneous access is managed."},
          choices=parameters.JOURNAL_MODES,
          choice_notes={
              "delete": {"it": "delete: scrive sul database, conserva i dati originali nel giornale e lo elimina "
                               "al termine della transazione.",
                         "en": "delete: writes to the database, keeps the original data in the journal and "
                               "deletes it when the transaction ends."},
              "truncate": {"it": "truncate: come delete, ma svuota il giornale senza eliminarlo.",
                           "en": "truncate: like delete, but empties the journal without deleting it."},
              "persist": {"it": "persist: come delete, ma mantiene il giornale, invalidandone il contenuto per "
                                "riutilizzarlo.",
                          "en": "persist: like delete, but keeps the journal, invalidating its content to reuse "
                                "it."},
              "memory": {"it": "memory: come delete, ma conserva il giornale nella memoria RAM anziché sul disco. "
                               "Riduce le garanzie di protezione: sconsigliata per l'uso ordinario.",
                         "en": "memory: like delete, but keeps the journal in RAM instead of on disk. It lowers "
                               "the protection guarantees: not advised for ordinary use."},
              "wal": {"it": "wal: scrive prima le modifiche in un file separato e poi le trasferisce nel database "
                            "principale. Crea due file in più accanto al database (-wal e -shm) e di solito non è "
                            "adatta alle cartelle di rete.",
                      "en": "wal: writes changes to a separate file first and then moves them into the main "
                            "database. It creates two more files next to the database (-wal and -shm) and is "
                            "usually not suited to network folders."},
              "off": {"it": "off: scrive direttamente sul database senza giornale di protezione. Riduce le "
                            "garanzie di protezione: sconsigliata per l'uso ordinario.",
                      "en": "off: writes directly to the database with no protection journal. It lowers the "
                            "protection guarantees: not advised for ordinary use."},
          }),
    Field(parameters.TRANSACTION_MODE, "integrity", "choice",
          {"it": "Modalità di blocco nelle transazioni con commit manuale",
           "en": "Locking mode in manual-commit transactions"},
          {"it": "Stabilisce quando vengono acquisiti i blocchi di accesso al database durante le transazioni "
                 "con commit manuale. Può avere effetto negli accessi in scrittura fatti con macro o comandi "
                 "SQL diretti. Nell'uso ordinario di LibreOffice Base non interviene, perché si usa il commit "
                 "immediato (autocommit).",
           "en": "Sets when the database access locks are taken during manual-commit transactions. It can "
                 "matter for writes done by macros or direct SQL commands. In ordinary use of LibreOffice Base "
                 "it does nothing, because immediate commit (autocommit) is used."},
          choices=parameters.TRANSACTION_MODES,
          choice_notes={
              "free": {"it": "free: acquisisce i blocchi soltanto al momento dell'accesso al database, in "
                             "lettura o in scrittura.",
                       "en": "free: takes the locks only when the database is actually accessed, for reading "
                             "or writing."},
              "blocking": {"it": "blocking: riserva il blocco di scrittura dal primo comando di scrittura della transazione, "
                                 "senza impedire le letture degli altri.",
                           "en": "blocking: reserves the write lock from the first write command of the transaction, without "
                                 "stopping others from reading."},
              "exclusive": {"it": "exclusive: acquisisce un blocco esclusivo dal primo comando di scrittura della transazione, impedendo agli "
                                  "altri sia le letture sia le scritture. Con la modalità wal si comporta come "
                                  "blocking.",
                            "en": "exclusive: takes an exclusive lock from the first write command of the transaction, stopping others from both "
                                  "reading and writing. With wal mode it behaves like blocking."},
          }),
    Field(parameters.FULL_LOAD_LIMIT, "results", "int",
          {"it": "Soglia di caricamento dei risultati (righe)", "en": "Full-load threshold (rows)"},
          {"it": "Stabilisce il numero massimo di righe di un risultato che possono essere caricate "
                 "interamente in memoria. Quando il risultato supera questa soglia, le righe vengono "
                 "caricate progressivamente a blocchi, riducendo l'utilizzo della memoria.",
           "en": "Sets the maximum number of rows of a result that can be loaded entirely into memory. When "
                 "a result is larger, rows are loaded gradually in blocks, which reduces memory use."},
          minimum=1, maximum=10000000),
    Field(parameters.WINDOW_SIZE, "results", "int",
          {"it": "Dimensione dei blocchi di lettura (righe)", "en": "Read block size (rows)"},
          {"it": "Stabilisce il numero di righe caricate per ciascun blocco quando il risultato supera la "
                 "soglia di caricamento completo indicata sopra.",
           "en": "Sets how many rows are loaded per block when a result is larger than the full-load "
                 "threshold above."}, minimum=1, maximum=100000),
    Field(parameters.DATE_TIME_FORMAT, "formats", "choice",
          {"it": "Formato di memorizzazione di date e orari", "en": "Date and time storage format"},
          {"it": "Stabilisce il formato utilizzato per memorizzare i valori di data e ora nel database. Si "
                 "possono rappresentare come testo oppure come valori numerici, secondo diverse convenzioni.",
           "en": "Sets the format used to store date and time values in the database. They can be stored as "
                 "text or as numbers, following different conventions."},
          choices=parameters.DATE_TIME_FORMATS,
          choice_notes={
              "text": {"it": "text: memorizza date e orari come testo, nel formato ISO 8601.",
                       "en": "text: stores dates and times as text, in ISO 8601 format."},
              "unix": {"it": "unix: memorizza date e orari come numero di secondi trascorsi dal 1° gennaio 1970.",
                       "en": "unix: stores dates and times as the number of seconds since 1 January 1970."},
              "julian": {"it": "julian: memorizza date e orari come numero di giorni giuliani, con la parte "
                                "decimale per l'ora.",
                         "en": "julian: stores dates and times as a Julian day number, with the decimal part "
                               "for the time of day."},
          }),
    Field(parameters.DATE_TIME_ZONE, "formats", "choice",
          {"it": "Riferimento orario", "en": "Time reference"},
          {"it": "Stabilisce il riferimento orario utilizzato per interpretare e memorizzare data e ora: ora "
                 "locale oppure tempo universale coordinato (UTC). L'ora locale è ammessa soltanto con il "
                 "formato text.",
           "en": "Sets the time reference used to interpret and store date and time: local time or "
                 "Coordinated Universal Time (UTC). Local time is allowed only with the text format."},
          choices=parameters.DATE_TIME_ZONES,
          choice_notes={
              "local": {"it": "local: utilizza l'ora locale del sistema, tenendo conto del fuso orario "
                              "configurato.",
                        "en": "local: uses the system's local time, taking the configured time zone into "
                              "account."},
              "utc": {"it": "utc: utilizza il tempo universale coordinato, indipendentemente dal fuso orario "
                            "locale.",
                      "en": "utc: uses Coordinated Universal Time, whatever the local time zone."},
          }),
    Field(parameters.NAMES_LANGUAGE, "formats", "choice",
          {"it": "Lingua dei nomi di giorni e mesi", "en": "Language of day and month names"},
          {"it": "Stabilisce la lingua dei nomi dei giorni e dei mesi restituiti dalle funzioni DAYNAME, "
                 "MONTHNAME e TO_CHAR.",
           "en": "Sets the language of the day and month names returned by the functions DAYNAME, "
                 "MONTHNAME and TO_CHAR."},
          choices=parameters.NAMES_LANGUAGES,
          choice_notes={
              "auto": {"it": "auto: usa la lingua dei formati impostata in LibreOffice.",
                       "en": "auto: uses the formats language set in LibreOffice."},
              "en": {"it": "en: usa sempre i nomi inglesi, come HSQLDB.",
                     "en": "en: always uses English names, as HSQLDB does."},
              "it": {"it": "it: usa sempre i nomi italiani.",
                     "en": "it: always uses Italian names."},
              "fr": {"it": "fr: usa sempre i nomi francesi.",
                     "en": "fr: always uses French names."},
              "de": {"it": "de: usa sempre i nomi tedeschi.",
                     "en": "de: always uses German names."},
              "es": {"it": "es: usa sempre i nomi spagnoli.",
                     "en": "es: always uses Spanish names."},
          }),
    Field(parameters.AUTO_INCREMENT_REUSE, "keys", "bool",
          {"it": "Riutilizza i numeri automatici liberati", "en": "Reuse freed automatic numbers"},
          {"it": "Stabilisce se i numeri delle chiavi primarie a generazione automatica possono riprendere "
                 "valori già usati e poi liberati dall'eliminazione dei record corrispondenti. Quando "
                 "l'opzione è disattivata, i valori generati seguono una progressione sempre crescente, a "
                 "partire dal valore più alto mai assegnato.",
           "en": "Sets whether automatically generated primary key numbers can take values that were used "
                 "before and freed by deleting the matching records. When the option is off, generated "
                 "values keep increasing, starting from the highest value ever assigned."}),
    Field(parameters.ROW_ID_AS_KEY, "keys", "bool",
          {"it": "Utilizza una chiave primaria implicita", "en": "Use an implicit primary key"},
          {"it": "Funzione non ancora disponibile. Abilita l'uso di una chiave primaria implicita gestita dal "
                 "driver, utilizzando l'identificativo interno ROWID di SQLite per le tabelle senza chiave "
                 "primaria esplicita. Gli identificativi ROWID possono cambiare dopo la compattazione del "
                 "database (VACUUM), rendendo potenzialmente inaffidabile l'identificazione dei record.",
           "en": "Not available yet. Enables an implicit primary key managed by the driver, using SQLite's "
                 "internal ROWID for tables without an explicit primary key. ROWID values can change after "
                 "the database is compacted (VACUUM), which can make identifying records unreliable."},
          enabled=False),
    Field(parameters.DEFENSIVE_MODE, "security", "bool",
          {"it": "Attiva la modalità difensiva", "en": "Enable defensive mode"},
          {"it": "Impedisce a SQLite di eseguire le operazioni che manomettono direttamente la struttura "
                 "interna del database, per esempio la scrittura diretta della tabella dello schema. Non "
                 "impedisce di cancellare tabelle o dati. Il giornale «off» non è più ammesso. È utile quando si apre "
                 "un file ricevuto da altri.",
           "en": "Stops SQLite from running operations that tamper directly with the internal structure of "
                 "the database, for example writing straight into the schema table. It does not stop "
                 "tables or data from being deleted. The \"off\" journal is no longer allowed. It is useful when "
                 "opening a file received from others."}),
    Field(parameters.UNTRUSTED_SCHEMA, "security", "bool",
          {"it": "Considera non fidato lo schema del database",
           "en": "Treat the database schema as untrusted"},
          {"it": "Viste, trigger, vincoli, colonne generate e indici su espressione possono chiamare soltanto "
                 "funzioni sicure. RAND, UUID, IDENTITY, CURDATE, TODAY, CURTIME, NOW, UNIX_TIMESTAMP e "
                 "UNIX_MILLIS (senza argomenti) non lo sono: in uno schema danno errore. Gli schemi di altri "
                 "programmi possono smettere di funzionare. Utile per file ricevuti da altri.",
           "en": "Views, triggers, constraints, generated columns and expression indexes can only call safe "
                 "functions. RAND, UUID, IDENTITY, CURDATE, TODAY, CURTIME, NOW, UNIX_TIMESTAMP and "
                 "UNIX_MILLIS (without arguments) are not: in a schema they cause an error. Schemas from other "
                 "programs may stop working. Useful for files received from others."}),
    Field(parameters.LIMITS_PROFILE, "security", "choice",
          {"it": "Limiti di sicurezza", "en": "Safety limits"},
          {"it": "Abbassa alcuni limiti di SQLite su istruzioni e dati, per ridurre il rischio che un file o "
                 "un'istruzione costruiti ad arte consumino memoria o tempo senza fine. Non limita il tempo "
                 "di esecuzione né la memoria in generale.",
           "en": "Lowers some SQLite limits on statements and data, to reduce the risk that a crafted file or "
                 "statement uses up memory or time without end. It does not limit running time or memory in "
                 "general."},
          choices=parameters.LIMITS_PROFILES,
          choice_notes={
              "none": {"it": "none: nessun cambiamento, valgono i limiti di SQLite.",
                       "en": "none: no change, the SQLite limits apply."},
              "prudent": {"it": "prudent: abbassa i limiti che Base non raggiunge mai (profondità di espressioni "
                                "e trigger, SELECT in UNION, lunghezza dei pattern LIKE, tabelle collegate, "
                                "operazioni per istruzione).",
                          "en": "prudent: lowers the limits Base never reaches (depth of expressions and "
                                "triggers, SELECTs in a UNION, LIKE pattern length, attached databases, "
                                "operations per statement)."},
              "strict": {"it": "strict: come prudent, più stringhe e BLOB fino a 100 MB, istruzioni SQL fino a "
                               "10 MB, tabelle fino a 500 colonne e fino a 32.766 parametri. Tabelle con dati "
                               "o colonne oltre questi valori smettono di funzionare.",
                         "en": "strict: like prudent, plus strings and BLOBs up to 100 MB, SQL statements up "
                               "to 10 MB, tables up to 500 columns and up to 32,766 parameters. Tables with "
                               "data or columns beyond these values stop working."},
          }),
    Field(parameters.OLD_LIBRARY_WARNING, "system", "bool",
          {"it": "Avvisa se SQLite è precedente alla versione raccomandata",
           "en": "Warn if SQLite is older than the recommended version"},
          {"it": "Mostra un avviso quando la versione di SQLite in uso è precedente a quella raccomandata per "
                 "il driver. L'avviso compare una sola volta per sessione e non impedisce di proseguire.",
           "en": "Shows a warning when the SQLite version in use is older than the one recommended for the "
                 "driver. The warning shows once per session and does not stop you from going on."}),
)

CONNECTION_NOTE_OPTIONS = {
    "it": "Valgono per tutti i documenti, salvo che l'indirizzo del documento indichi un valore diverso.",
    "en": "They apply to all documents unless the document's address gives a different value.",
}
CONNECTION_NOTE_DOCUMENT = {
    "it": "Valgono solo per questo documento. Dove è scelto «Predefinito dell'estensione» si usa il valore "
          "delle Opzioni.",
    "en": "They apply to this document only. Where \"Extension default\" is chosen, the value from the "
          "Options is used.",
}

STRINGS = {
    "btn_log": {"it": "Apri il registro", "en": "Open the log"},
    "btn_folder": {"it": "Apri la cartella", "en": "Open the folder"},
    "msg_folder_failed": {"it": "Non riesco ad aprire la cartella:\n{path}", "en": "Cannot open the folder:\n{path}"},
    "msg_log_missing": {"it": "Il registro non esiste ancora.\nCartella: {folder}",
                        "en": "The log does not exist yet.\nFolder: {folder}"},
    "msg_log_failed": {"it": "Non riesco ad aprire il registro:\n{path}",
                       "en": "Cannot open the log:\n{path}"},
    "doc_title": {"it": "Impostazioni PySQLite del documento", "en": "PySQLite document settings"},
    "options_title": {"it": "Impostazioni dell'estensione", "en": "Extension settings"},
    "address_hint": {"it": "Indirizzo del documento (si cambia da Modifica → Database → Proprietà):",
                     "en": "Document address (change it from Edit → Database → Properties):"},
    "address": {"it": "Indirizzo del documento (si cambia da Modifica → Database → Proprietà):",
                "en": "Document address (change it from Edit → Database → Properties):"},
    "address_overrides": {
        "it": "L'indirizzo indica già: {names}. Questi valori prevalgono su quelli di questa finestra.",
        "en": "The address already gives: {names}. Those values take precedence over this window."},
    "overridden": {"it": " L'indirizzo indica già questo parametro: prevale su questa impostazione.",
                   "en": " The address already gives this parameter: it takes precedence over this setting."},
    "extension_default": {"it": "Predefinito dell'estensione ({value})", "en": "Extension default ({value})"},
    "empty_means_default": {"it": "Vuoto = predefinito dell'estensione. Ora:",
                            "en": "Empty = extension default. Now:"},
    "yes": {"it": "sì", "en": "yes"},
    "no": {"it": "no", "en": "no"},
    "none": {"it": "nessuno", "en": "none"},
    "btn_ok": {"it": "OK", "en": "OK"},
    "btn_cancel": {"it": "Annulla", "en": "Cancel"},
    "btn_driver_defaults": {"it": "Predefiniti del driver", "en": "Driver Defaults"},
    "btn_extension": {"it": "Usa le impostazioni dell'estensione", "en": "Use extension settings"},
    "btn_browse": {"it": "Sfoglia…", "en": "Browse…"},
    "browse_title": {"it": "Cartella del registro diagnostico", "en": "Diagnostic log folder"},
    "db_address": {"it": "Indirizzo del database", "en": "Database address"},
    "db_address_hint": {
        "it": "Percorso del file ed eventuali opzioni dopo il «?». Per le istruzioni premi «?». Coincide con "
              "l'indirizzo di Modifica → Database → Proprietà. Il nuovo indirizzo vale dopo aver salvato, "
              "chiuso e riaperto il documento.",
        "en": "File path and any options after the \"?\". Press \"?\" for instructions. It matches the "
              "address in Edit → Database → Properties. The new address applies after saving, closing and "
              "reopening the document."},
    "btn_help": {"it": "?", "en": "?"},
    "help_title": {"it": "Come si scrive l'indirizzo del database", "en": "How to write the database address"},
    "help_html_intro": {
        "it": r"""<h2>Che cosa si scrive</h2>
<p>Nel campo si scrive il <b>percorso del file</b> del database SQLite, per esempio:</p>
<pre>C:\Dati\clienti.db3</pre>
<p>Il prefisso del driver (<code>sdbc:external:pysqlite:</code>) <b>non va scritto</b>: lo aggiunge il driver. Il percorso si può scrivere anche tra virgolette, come lo dà Windows con «Copia come percorso». Per scegliere il file si possono usare i pulsanti <b>«Apri…»</b> (un file che esiste) e <b>«Nuovo…»</b> (un file nuovo): scrivono solo il percorso e non aggiungono mai opzioni.</p>
<h2>Le opzioni</h2>
<p>Dopo il percorso si possono aggiungere, a mano, delle opzioni: si scrive <b>?</b> e poi le opzioni nella forma <b>nome=valore</b>, separate da <b>&amp;</b>. Per esempio:</p>
<pre>C:\Dati\clienti.db3?ReadOnly=true
C:\Dati\clienti.db3?CreateIfMissing=true&amp;LockTimeoutSeconds=10</pre>
<p>Regole:</p>
<ul>
<li>le maiuscole e le minuscole contano: <code>ReadOnly</code>, non <code>readonly</code>;</li>
<li>ogni nome si scrive una sola volta;</li>
<li>non ci vogliono spazi attorno ai nomi e ai valori;</li>
<li>un nome sconosciuto o un valore non ammesso dà un errore e l'indirizzo <b>non viene salvato</b>.</li>
</ul>
<h2>Quale valore vale</h2>
<p>Un'opzione scritta nell'indirizzo prevale sulla stessa impostazione della finestra delle impostazioni del documento, che prevale sulle Opzioni dell'estensione, che prevalgono sui valori predefiniti del driver. Le opzioni già indicate nell'indirizzo sono segnalate in alto nella finestra delle impostazioni.</p>
<h2>Le opzioni disponibili</h2>""",
        "en": r"""<h2>What you write</h2>
<p>In the field you write the <b>path of the file</b> of the SQLite database, for example:</p>
<pre>C:\Data\customers.db3</pre>
<p>The driver prefix (<code>sdbc:external:pysqlite:</code>) <b>must not be written</b>: the driver adds it. The path can also be written between quotation marks, as Windows gives it with "Copy as path". To choose the file you can use the <b>"Open…"</b> (an existing file) and <b>"New…"</b> (a new file) buttons: they write only the path and never add options.</p>
<h2>The options</h2>
<p>After the path you can add options by hand: write <b>?</b> and then the options in the form <b>name=value</b>, separated by <b>&amp;</b>. For example:</p>
<pre>C:\Data\customers.db3?ReadOnly=true
C:\Data\customers.db3?CreateIfMissing=true&amp;LockTimeoutSeconds=10</pre>
<p>Rules:</p>
<ul>
<li>upper and lower case matter: <code>ReadOnly</code>, not <code>readonly</code>;</li>
<li>each name is written only once;</li>
<li>no spaces around names and values;</li>
<li>an unknown name or a value that is not allowed gives an error and the address is <b>not saved</b>.</li>
</ul>
<h2>Which value applies</h2>
<p>An option written in the address wins over the same setting in the document settings window, which wins over the extension Options, which win over the driver defaults. The options already given in the address are shown at the top of the settings window.</p>
<h2>The available options</h2>"""},
    "help_values": {"it": "Valori ammessi", "en": "Allowed values"},
    "help_default": {"it": "Predefinito del driver", "en": "Driver default"},
    "help_bool": {"it": "<b>true</b> (attivo) oppure <b>false</b> (non attivo)",
                  "en": "<b>true</b> (on) or <b>false</b> (off)"},
    "help_value": {"it": "Valore", "en": "Value"},
    "help_meaning": {"it": "Significato", "en": "Meaning"},
    "filter_db3": {"it": "Database SQLite (*.db3)", "en": "SQLite database (*.db3)"},
    "filter_sqlite": {"it": "Tutti i database SQLite (*.db3, *.db, *.sqlite, *.sqlite3)",
                      "en": "All SQLite databases (*.db3, *.db, *.sqlite, *.sqlite3)"},
    "filter_all": {"it": "Tutti i file (*.*)", "en": "All files (*.*)"},
    "btn_open_file": {"it": "Apri…", "en": "Open…"},
    "btn_new_file": {"it": "Nuovo…", "en": "New…"},
    "open_file_title": {"it": "Apri un database SQLite", "en": "Open a SQLite database"},
    "new_file_title": {"it": "Nuovo database SQLite", "en": "New SQLite database"},
    "msg_address_invalid": {"it": "L'indirizzo del database non è valido e non è stato salvato:\n{detail}",
                            "en": "The database address is not valid and was not saved:\n{detail}"},
    "btn_open": {"it": "Apri le impostazioni…", "en": "Open settings…"},
    "msg_title": {"it": "Impostazioni PySQLite", "en": "PySQLite settings"},
    "msg_no_document": {"it": "Questo documento non usa il driver PySQLite.",
                        "en": "This document does not use the PySQLite driver."},
    "msg_document_saved": {
        "it": "Le modifiche sono state salvate nel documento. Per renderle effettive occorre salvare, "
              "chiudere e riaprire il documento.",
        "en": "The changes were stored in the document. To make them effective, save, close and reopen "
              "the document."},
    "btn_reset_advanced": {"it": "Reimposta le opzioni avanzate del documento",
                           "en": "Reset the document's advanced options"},
    "reset_advanced_hint": {
        "it": "Le impostazioni avanzate di Base (Modifica → Database → Impostazioni avanzate) che questo "
              "driver fissa da sé vengono riportate al valore del driver. Serve se il documento ne ha "
              "salvata una scelta più vecchia, per esempio dopo l'aggiornamento dell'estensione. Le due "
              "voci che Base mostra restano come sono.",
        "en": "The Base advanced settings (Edit → Database → Advanced Settings) that this driver fixes by "
              "itself are set back to the driver's value. Use it if the document saved an older choice, "
              "for example after updating the extension. The two entries that Base shows are left as they "
              "are."},
    "msg_reset_confirm": {
        "it": "Le opzioni avanzate di Base di questo documento (quelle che il driver fissa da sé) saranno "
              "riportate ai valori del driver. Continuare?",
        "en": "The Base advanced options of this document (those the driver fixes by itself) will be set "
              "back to the driver's values. Continue?"},
    "msg_reset_done": {
        "it": "Opzioni avanzate reimpostate: {changed} riportate al valore del driver, {same} già a posto.{extra}\n"
              "Per renderle effettive occorre salvare, chiudere e riaprire il documento.",
        "en": "Advanced options reset: {changed} set back to the driver's value, {same} already correct.{extra}\n"
              "To make them effective, save, close and reopen the document."},
    "msg_reset_failed_part": {
        "it": "\nNon è stato possibile scrivere {count} voci (vedi il registro).",
        "en": "\n{count} entries could not be written (see the log)."},
    "msg_reset_nothing": {
        "it": "Le opzioni avanzate di questo documento sono già a posto: nessuna modifica.",
        "en": "The advanced options of this document are already correct: no changes."},
    "msg_no_change": {"it": "Nessuna modifica.", "en": "No changes."},
    "msg_options_saved": {
        "it": "Le modifiche valgono per i documenti aperti da ora in poi. Per applicarle a un documento già "
              "aperto, chiuderlo e riaprirlo.",
        "en": "The changes apply to documents opened from now on. To apply them to a document that is "
              "already open, close and reopen it."},
    "msg_invalid": {"it": "Valori non validi:\n{list}", "en": "Invalid values:\n{list}"},
    "msg_options_invalid": {
        "it": "Queste impostazioni non sono valide e non sono state salvate:\n{list}",
        "en": "These settings are not valid and were not saved:\n{list}"},
    "msg_save_failed": {"it": "Impossibile salvare le impostazioni (vedi il registro).",
                        "en": "The settings could not be saved (see the log)."},
    "err_int_min": {"it": "{label}: inserire un numero intero da {minimum} in su.",
                    "en": "{label}: enter a whole number, {minimum} or more."},
    "err_int_range": {"it": "{label}: inserire un numero intero da {minimum} a {maximum}.",
                      "en": "{label}: enter a whole number from {minimum} to {maximum}."},
}


def text(key, language, **values):
    template = pick(STRINGS[key], language)
    return template.format(**values) if values else template


def fields_for(mode):
    return tuple(field for field in FIELDS if mode == "options" or not field.options_only)


def groups_for(mode):
    return tuple(group for group in GROUPS if mode == "options" or not group.options_only)


def group_of(field):
    return next(group for group in GROUPS if group.key == field.group)


def driver_defaults():
    values = {"Trace": False, "LogPath": "", "LogRetentionDays": DEFAULT_RETENTION_DAYS}
    values.update(parameters.DEFAULTS)
    return values


def format_value(field, value, language):
    if field.kind == "bool":
        return text("yes" if value else "no", language)
    if value in ("", None):
        return text("none", language)
    return str(value)


def parse_number(field, entered):
    entered = entered.strip()
    if re.fullmatch(r"[0-9]+", entered):
        number = int(entered)
        if number >= field.minimum and (field.maximum is None or number <= field.maximum):
            return number
    raise ValueError(entered)


def error_text(field, language):
    label = pick(field.label, language)
    if field.maximum is not None:
        return text("err_int_range", language, label=label, minimum=field.minimum, maximum=field.maximum)
    return text("err_int_min", language, label=label, minimum=field.minimum)


def check_pair(values):
    zone = values.get(parameters.DATE_TIME_ZONE)
    date_format = values.get(parameters.DATE_TIME_FORMAT)
    if zone is None and date_format is None:
        return True
    zone = parameters.DEFAULTS[parameters.DATE_TIME_ZONE] if zone is None else zone
    date_format = parameters.DEFAULTS[parameters.DATE_TIME_FORMAT] if date_format is None else date_format
    return parameters.check_date_time(zone, date_format)


_HELP_STYLE = """
body { font-family: "Segoe UI", sans-serif; font-size: 15px; line-height: 1.5; max-width: 52em;
       margin: 1.5em auto; padding: 0 1em; color: #1b1b1b; background: #ffffff; }
h1 { font-size: 1.6em; margin-bottom: .2em; }
h2 { font-size: 1.25em; margin-top: 1.6em; border-bottom: 2px solid #c8c8c8; padding-bottom: .15em; }
h3 { font-size: 1.05em; margin: 1.4em 0 .3em; }
code, pre { font-family: Consolas, monospace; background: #eeeeee; border-radius: 3px; }
code { padding: 0 .25em; }
pre { padding: .6em .9em; overflow-x: auto; }
table { border-collapse: collapse; margin: .4em 0 .4em 1em; }
th, td { border: 1px solid #c8c8c8; padding: .25em .6em; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
.note { font-style: italic; }
@media (prefers-color-scheme: dark) {
  body { color: #e8e8e8; background: #202020; }
  h2 { border-bottom-color: #555555; }
  code, pre { background: #333333; }
  th, td { border-color: #555555; }
  th { background: #2c2c2c; }
}
"""


def address_help_html(language):
    esc = html.escape
    out = ["<!DOCTYPE html>", '<html lang="%s">' % language, "<head>", '<meta charset="utf-8">',
           "<title>%s</title>" % esc(text("help_title", language)), "<style>%s</style>" % _HELP_STYLE,
           "</head>", "<body>", "<h1>%s</h1>" % esc(text("help_title", language)),
           text("help_html_intro", language)]
    for field in fields_for("document"):
        if field.name not in parameters.PARAMETER_NAMES:
            continue
        default = parameters.DEFAULTS[field.name]
        if isinstance(default, bool):
            default = "true" if default else "false"
        if field.kind == "bool":
            allowed = text("help_bool", language)
        elif field.choices:
            allowed = ", ".join("<b>%s</b>" % esc(value) for value in field.choices)
        else:
            allowed = "<b>%s</b>" % esc(parameters.allowed_text(field.name, language))
        out.append("<h3><code>%s</code> — %s</h3>" % (esc(field.name), esc(pick(field.label, language))))
        out.append("<p>%s: %s. %s: <b>%s</b>.</p>" % (text("help_values", language), allowed,
                                                      text("help_default", language), esc(str(default))))
        out.append('<p class="note">%s</p>' % esc(pick(field.note, language).strip()))
        rows = []
        for value in field.choices:
            note = (field.choice_notes or {}).get(value)
            if note:
                meaning = pick(note, language)
                if meaning.startswith(value + ": "):
                    meaning = meaning[len(value) + 2:]
                rows.append("<tr><td><b>%s</b></td><td>%s</td></tr>" % (esc(value), esc(meaning)))
        if rows:
            out.append("<table><tr><th>%s</th><th>%s</th></tr>%s</table>"
                       % (text("help_value", language), text("help_meaning", language), "".join(rows)))
    out.extend(["</body>", "</html>"])
    return "\n".join(out) + "\n"


def address_help(language):
    body = address_help_html(language)
    body = body[body.index("<body>"):]
    body = re.sub(r"<pre>(.*?)</pre>", lambda found: "<pre>" + found.group(1).replace("\n", "<br>") + "</pre>",
                  body, flags=re.S)
    body = body.replace("\n", "")
    body = re.sub(r"<tr><th>.*?</tr>", "", body)
    body = re.sub(r"</td><td>", ": ", body)
    body = re.sub(r"</(p|h1|h2|h3|tr|ul|pre|table)>|<br>", "\n", body)
    body = re.sub(r"<li>", "• ", body)
    body = re.sub(r"</li>", "\n", body)
    body = re.sub(r"<[^>]+>", "", body)
    body = html.unescape(body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip() + "\n"
