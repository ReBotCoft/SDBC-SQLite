# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

import manuals_html

ROOT = Path(__file__).resolve().parents[1]
EXTENSION_DIR = ROOT / "extension"
DOCS_DIR = ROOT / "docs"
MANUALS_FOLDER = "manuals"
DIST_DIR = ROOT / "dist"
OXT_PATH = DIST_DIR / "SDBC-SQLite.oxt"

SUPPRESS_LICENSE = True

EXCLUDED_DIRS = {"__pycache__"}
EXCLUDED_FILES = {"Thumbs.db", "desktop.ini"}
EXCLUDED_SUFFIXES = {".pyc"}


def fail(message):
    print(f"ERRORE: {message}")
    sys.exit(1)


def parse_description():
    try:
        return ET.parse(EXTENSION_DIR / "description.xml").getroot()
    except ET.ParseError as error:
        fail(f"description.xml non e' un XML valido: {error}")


def local_name(element):
    return element.tag.split("}")[-1]


def read_value(root, name):
    for element in root.iter():
        if local_name(element) == name and element.get("value"):
            return element.get("value")
    fail(f"description.xml non contiene l'elemento <{name} value=\"...\"/>.")


def read_update_url(root):
    for element in root.iter():
        if local_name(element) == "update-information":
            for source in element:
                href = source.get("{http://www.w3.org/1999/xlink}href")
                if href:
                    return href
    fail("description.xml non contiene <update-information> con un <src xlink:href=\"...\"/>.")


def read_identifier():
    return read_value(parse_description(), "identifier")


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


def write_update_file(root):
    update_url = read_update_url(root)
    base, _, file_name = update_url.rpartition("/")
    if not file_name:
        fail(f"indirizzo di aggiornamento senza nome di file: {update_url}")
    text = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<description xmlns="http://openoffice.org/extensions/update/2006"\n'
        '             xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        f'  <identifier value={quoteattr(read_value(root, "identifier"))}/>\n'
        f'  <version value={quoteattr(read_value(root, "version"))}/>\n'
        '  <update-download>\n'
        f'    <src xlink:href={quoteattr(base + "/" + OXT_PATH.name)}/>\n'
        '  </update-download>\n'
        '</description>\n'
    )
    path = DIST_DIR / file_name
    path.write_text(text, encoding="utf-8")
    return path


def build():
    if not EXTENSION_DIR.is_dir():
        fail(f"cartella dei sorgenti non trovata: {EXTENSION_DIR}")
    for required in ("description.xml", "META-INF/manifest.xml"):
        if not (EXTENSION_DIR / required).is_file():
            fail(f"manca {required} in {EXTENSION_DIR}")

    root = parse_description()
    identifier = read_value(root, "identifier")
    files = sorted(
        path for path in EXTENSION_DIR.rglob("*") if path.is_file() and not is_excluded(path)
    )
    pages = manuals_html.build_pages(DOCS_DIR)
    if not pages:
        fail(f"nessun manuale (file \"... - Manual - ....md\") in {DOCS_DIR}")

    DIST_DIR.mkdir(exist_ok=True)
    if OXT_PATH.exists():
        OXT_PATH.unlink()
    with zipfile.ZipFile(OXT_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(EXTENSION_DIR).as_posix())
        for name, page in pages:
            archive.writestr(f"{MANUALS_FOLDER}/{name}", page)

    print(f"Creato {OXT_PATH} ({len(files) + len(pages)} file, di cui {len(pages)} manuali, "
          f"identificatore {identifier}).")
    print(f"Creato {write_update_file(root)} (da allegare alla versione pubblicata, insieme al .oxt).")
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
