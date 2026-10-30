# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "extension"
DIST_DIR = ROOT / "dist"
OXT_PATH = DIST_DIR / "SDBC-SQLite.oxt"

SUPPRESS_LICENSE = True

EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_FILES = {"Thumbs.db", "desktop.ini"}
EXCLUDED_SUFFIXES = {".pyc"}


def fail(message):
    print(f"ERRORE: {message}")
    sys.exit(1)


def read_identifier():
    description = EXTENSION_DIR / "description.xml"
    try:
        tree = ET.parse(description)
    except ET.ParseError as error:
        fail(f"description.xml non e' un XML valido: {error}")
    for element in tree.getroot().iter():
        if element.tag.split("}")[-1] == "identifier":
            value = element.get("value")
            if value:
                return value
    fail("description.xml non contiene l'elemento <identifier value=\"...\"/>.")


def is_excluded(path):
    relative = path.relative_to(EXTENSION_DIR)
    if any(part in EXCLUDED_DIRS for part in relative.parts[:-1]):
        return True
    name = path.name
    return (
        name in EXCLUDED_FILES
        or name.startswith(".~lock.")
        or path.suffix in EXCLUDED_SUFFIXES
    )


def build():
    if not EXTENSION_DIR.is_dir():
        fail(f"cartella dei sorgenti non trovata: {EXTENSION_DIR}")
    for required in ("description.xml", "META-INF/manifest.xml"):
        if not (EXTENSION_DIR / required).is_file():
            fail(f"manca {required} in {EXTENSION_DIR}")

    identifier = read_identifier()
    files = sorted(
        path for path in EXTENSION_DIR.rglob("*") if path.is_file() and not is_excluded(path)
    )

    DIST_DIR.mkdir(exist_ok=True)
    if OXT_PATH.exists():
        OXT_PATH.unlink()
    with zipfile.ZipFile(OXT_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(EXTENSION_DIR).as_posix())

    print(f"Creato {OXT_PATH} ({len(files)} file, identificatore {identifier}).")
    return identifier


def find_unopkg():
    program_dir = Path(sys.executable).resolve().parent
    for name in ("unopkg.com", "unopkg.exe"):
        candidate = program_dir / name
        if candidate.is_file():
            return candidate
    fail(f"unopkg non trovato in {program_dir}. Lo script va eseguito con il Python di LibreOffice.")


def libreoffice_is_running():
    try:
        result = subprocess.run(
            ["tasklist", "/NH"], capture_output=True, text=True, errors="replace"
        )
    except OSError:
        print("AVVISO: impossibile controllare i processi (tasklist non disponibile).")
        return False
    output = result.stdout.lower()
    return "soffice.bin" in output or "soffice.exe" in output


def install(identifier, force):
    if libreoffice_is_running():
        fail("LibreOffice e' aperto. Chiudilo (anche l'avvio veloce) e rilancia.")
    unopkg = find_unopkg()

    print("Rimozione della versione precedente...")
    removed = subprocess.run([str(unopkg), "remove", identifier])
    if removed.returncode != 0:
        print("(la rimozione non e' riuscita: probabilmente l'estensione non era installata; si prosegue)")

    print("Installazione della nuova versione...")
    command = [str(unopkg), "add"]
    if SUPPRESS_LICENSE:
        command.append("--suppress-license")
    if force:
        command.append("--force")
    command.append(str(OXT_PATH))
    added = subprocess.run(command)
    if added.returncode != 0:
        fail(f"unopkg add e' terminato con codice {added.returncode}.")
    print("Installazione completata.")


def main():
    parser = argparse.ArgumentParser(description="Costruisce e installa l'estensione .oxt.")
    parser.add_argument("command", nargs="?", choices=["build", "install"], default="build")
    parser.add_argument("--force", action="store_true", help='passa --force a "unopkg add"')
    args = parser.parse_args()

    identifier = build()
    if args.command == "install":
        install(identifier, args.force)


if __name__ == "__main__":
    main()
