# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import html
import re
import sys
from pathlib import Path

MANUAL_FILE = re.compile(r"^\d{4}-\d{2}-\d{2} - Manual - (?P<title>.+)\.md$")

STYLE = """
:root { color-scheme: light dark; }
body { font-family: system-ui, "Segoe UI", sans-serif; line-height: 1.55; margin: 0; padding: 1.5rem 1rem; }
main { max-width: 62rem; margin: 0 auto; }
h1, h2, h3, h4, h5, h6 { line-height: 1.25; margin: 1.6em 0 0.5em; }
h1 { margin-top: 0; }
table { border-collapse: collapse; margin: 1rem 0; display: block; overflow-x: auto; }
th, td { border: 1px solid #8884; padding: 0.35rem 0.6rem; text-align: left; vertical-align: top; }
th { background: #8882; }
code { font-family: Consolas, "Courier New", monospace; background: #8882; padding: 0.05em 0.3em; border-radius: 3px; }
pre { background: #8882; padding: 0.8rem 1rem; overflow-x: auto; border-radius: 4px; }
pre code { background: none; padding: 0; }
hr { border: 0; border-top: 1px solid #8884; margin: 1.5rem 0; }
"""

_CODE_SPAN = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*\s][^*]*?)\*(?![*\w])")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RULE = re.compile(r"^(?:-{3,}|\*{3,})\s*$")
_ITEM = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
_TABLE_SEPARATOR = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def slug(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def manual_files(docs_dir):
    found = []
    for path in sorted(Path(docs_dir).glob("*.md")):
        match = MANUAL_FILE.match(path.name)
        if match:
            found.append((path, slug(match.group("title")) + ".html"))
    return found


def _emphasis(text):
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    return _ITALIC.sub(r"<em>\1</em>", text)


def inline(text):
    codes = []

    def keep(match):
        codes.append("<code>%s</code>" % html.escape(match.group(1), quote=False))
        return "\x00%d\x00" % (len(codes) - 1)

    text = _emphasis(html.escape(_CODE_SPAN.sub(keep, text), quote=False))
    return re.sub(r"\x00(\d+)\x00", lambda match: codes[int(match.group(1))], text)


def _cells(line):
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells, current, in_code = [], [], False
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and text[index + 1:index + 2] == "|":
            current.append("|")
            index += 2
            continue
        if char == "`":
            in_code = not in_code
        if char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _is_table_start(lines, index):
    return (lines[index].lstrip().startswith("|") and index + 1 < len(lines)
            and lines[index + 1].lstrip().startswith("|") and _TABLE_SEPARATOR.match(lines[index + 1].strip()))


def _starts_block(lines, index):
    line = lines[index]
    return (line.startswith("```") or _HEADING.match(line) or _RULE.match(line) or _ITEM.match(line)
            or _is_table_start(lines, index))


def _table(lines, index):
    header = _cells(lines[index])
    rows = []
    index += 2
    while index < len(lines) and lines[index].lstrip().startswith("|"):
        rows.append(_cells(lines[index]))
        index += 1
    out = ["<table>", "<thead><tr>%s</tr></thead>" % "".join("<th>%s</th>" % inline(cell) for cell in header),
           "<tbody>"]
    for row in rows:
        out.append("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(cell) for cell in row))
    out.extend(["</tbody>", "</table>"])
    return "\n".join(out), index


def _list(lines, index):
    ordered = lines[index].lstrip()[0].isdigit()
    items = []
    while index < len(lines):
        match = _ITEM.match(lines[index])
        if not match or match.group(2)[0].isdigit() != ordered:
            break
        text = [match.group(3)]
        index += 1
        while index < len(lines) and lines[index].strip() and lines[index].startswith(" ") \
                and not _ITEM.match(lines[index]):
            text.append(lines[index].strip())
            index += 1
        items.append("<li>%s</li>" % inline(" ".join(text)))
        while index < len(lines) and not lines[index].strip() and index + 1 < len(lines) \
                and _ITEM.match(lines[index + 1]) \
                and _ITEM.match(lines[index + 1]).group(2)[0].isdigit() == ordered:
            index += 1
    tag = "ol" if ordered else "ul"
    return "<%s>\n%s\n</%s>" % (tag, "\n".join(items), tag), index


def to_html_body(markdown):
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    title = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
        elif line.startswith("```"):
            language = line[3:].strip()
            code = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            css = ' class="language-%s"' % html.escape(language) if language else ""
            out.append("<pre><code%s>%s</code></pre>" % (css, html.escape("\n".join(code), quote=False)))
        elif _HEADING.match(line):
            match = _HEADING.match(line)
            level = len(match.group(1))
            out.append("<h%d>%s</h%d>" % (level, inline(match.group(2)), level))
            if not title:
                title = re.sub(r"[*`]", "", match.group(2)).strip()
            index += 1
        elif _RULE.match(line):
            out.append("<hr>")
            index += 1
        elif _is_table_start(lines, index):
            block, index = _table(lines, index)
            out.append(block)
        elif _ITEM.match(line):
            block, index = _list(lines, index)
            out.append(block)
        else:
            paragraph = [line.strip()]
            index += 1
            while index < len(lines) and lines[index].strip() and not _starts_block(lines, index):
                paragraph.append(lines[index].strip())
                index += 1
            out.append("<p>%s</p>" % inline(" ".join(paragraph)))
    return "\n".join(out), title


def to_html_page(markdown):
    body, title = to_html_body(markdown)
    return ("<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "<title>%s</title>\n<style>%s</style>\n</head>\n<body>\n<main>\n%s\n</main>\n</body>\n</html>\n"
            % (html.escape(title, quote=False), STYLE, body))


def build_pages(docs_dir):
    return [(name, to_html_page(path.read_text(encoding="utf-8"))) for path, name in manual_files(docs_dir)]


def main(argv):
    if len(argv) != 3:
        print("Uso: manuals_html.py <cartella docs> <cartella di destinazione>")
        return 1
    target = Path(argv[2])
    target.mkdir(parents=True, exist_ok=True)
    for name, page in build_pages(argv[1]):
        (target / name).write_text(page, encoding="utf-8")
        print("Scritto %s" % (target / name))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
