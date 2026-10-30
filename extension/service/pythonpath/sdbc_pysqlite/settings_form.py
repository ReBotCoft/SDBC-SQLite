# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import math
from dataclasses import dataclass
from dataclasses import field as dataclass_field

import uno
import unohelper

from com.sun.star.awt import XActionListener
from com.sun.star.awt import XAdjustmentListener
from com.sun.star.awt import XFocusListener
from com.sun.star.awt import XItemListener
from com.sun.star.awt import XTextListener

from sdbc_pysqlite import parameters
from sdbc_pysqlite import settings_model as model

MARGIN = 6
NAV_WIDTH = 84
CONTENT_WIDTH = 346
OPTIONS_CONTENT_WIDTH = 280
PAGE_WIDTH = OPTIONS_CONTENT_WIDTH + 2 * MARGIN
DOC_WIDTH = NAV_WIDTH + CONTENT_WIDTH + 3 * MARGIN
CONTENT_HEIGHT = 250
OPTIONS_BUTTONS = 22
OPTIONS_PAGE_HEIGHT = CONTENT_HEIGHT + OPTIONS_BUTTONS + 2 * MARGIN
BUTTON_HEIGHT = 14
TITLE_LINE = 12
LINE = 9
NOTE_LINE = 8.5
CHECK_LINE = 9
CONTROL = 12
GAP = 4
GREY = 0x808080
CHAR_NORMAL = 2.6
CHAR_NOTE = 2.35
CHAR_TITLE = 4.2
CHAR_ADDRESS = 3.4
BROWSE_WIDTH = 54
CHAR_NOTE_WIDE = 2.6
DESC_NAME_WIDTH = 42
DB_BUTTON_WIDTH = 50
DB_HELP_WIDTH = 20
INT_EDIT_WIDTH = 60
SPIN_WIDTH = 10



def text_lines(text, width, char=CHAR_NORMAL):
    per_line = max(1, int(width / char * 0.96))
    total = 0
    for part in text.split("\n"):
        total += max(1, -(-len(part) // per_line))
    return total


@dataclass
class Element:
    kind: str
    name: str
    x: int
    y: int
    width: int
    height: int
    text: str = ""
    items: tuple = ()
    field: object = None
    enabled: bool = True


@dataclass
class Page:
    key: str
    title: str
    elements: list = dataclass_field(default_factory=list)
    fields: list = dataclass_field(default_factory=list)
    height: int = 0


@dataclass
class Layout:
    mode: str
    language: str
    header: list
    header_height: int
    pages: list
    extension_values: dict = dataclass_field(default_factory=dict)

    @property
    def fields(self):
        return model.fields_for(self.mode)

    @property
    def paged(self):
        return self.mode == "document"

    @property
    def origin_x(self):
        return NAV_WIDTH + 2 * MARGIN if self.paged else MARGIN

    @property
    def origin_y(self):
        return self.header_height if self.paged else MARGIN

    def page(self, key):
        return next(page for page in self.pages if page.key == key)


def _note_text(field, language, mode, extension_values, overridden):
    note = model.pick(field.note, language)
    if mode == "document" and field.name in overridden:
        note += model.text("overridden", language)
    return note.strip()


def _list_items(field, mode, language, extension_values):
    if field.kind == "bool":
        values = (model.text("yes", language), model.text("no", language))
    else:
        values = tuple(field.choices)
    if mode == "options":
        return values
    current = (extension_values or {}).get(field.name)
    default = model.text("extension_default", language,
                         value=model.format_value(field, current, language))
    return (default,) + values


def description(field, value, language):
    notes = field.choice_notes or {}
    return model.pick(notes[value], language) if value in notes else ""


def description_parts(field, value, language):
    text = description(field, value, language)
    if value and text.startswith(str(value) + ": "):
        return str(value), text[len(str(value)) + 2:]
    return "", text


def _desc_height(field, language, width):
    lines = max(text_lines(description_parts(field, value, language)[1], width, CHAR_NOTE)
                for value in (field.choice_notes or {}))
    return lines * NOTE_LINE


def _field_block(field, mode, language, extension_values, overridden, width):
    elements = []
    y = 0
    label = model.pick(field.label, language)
    note = _note_text(field, language, mode, extension_values, overridden)
    if field.kind == "bool" and mode == "options":
        height = text_lines(label, width - 14) * CHECK_LINE + 2
        elements.append(Element("check", "ctl_" + field.name, 0, y, width, height, label,
                                field=field, enabled=field.enabled))
        y += height
    else:
        label_height = text_lines(label, width) * LINE
        elements.append(Element("label", "lbl_" + field.name, 0, y, width, label_height, label))
        y += label_height + 1
        if field.kind == "int":
            elements.append(Element("edit", "ctl_" + field.name, 0, y, INT_EDIT_WIDTH, CONTROL,
                                    field=field, enabled=field.enabled))
            elements.append(Element("spin", "spin_" + field.name, INT_EDIT_WIDTH + 1, y, SPIN_WIDTH, CONTROL,
                                    enabled=field.enabled))
        elif field.kind == "text":
            edit_width = width - BROWSE_WIDTH - 4 if mode == "options" else width
            elements.append(Element("edit", "ctl_" + field.name, 0, y, edit_width, CONTROL,
                                    field=field, enabled=field.enabled))
            if mode == "options":
                elements.append(Element("browse", "btn_browse", width - BROWSE_WIDTH, y, BROWSE_WIDTH,
                                        CONTROL, model.text("btn_browse", language)))
        else:
            items = _list_items(field, mode, language, extension_values)
            elements.append(Element("list", "ctl_" + field.name, 0, y, 170 if mode == "document" else 120,
                                    CONTROL, items=items, field=field, enabled=field.enabled))
        y += CONTROL
    if note:
        y += 2
        height = text_lines(note, width, CHAR_NOTE) * NOTE_LINE
        elements.append(Element("note", "note_" + field.name, 0, y, width, height, note))
        y += height
    if mode == "document" and field.kind == "int" and extension_values is not None:
        label = model.text("empty_means_default", language)
        label_width = math.ceil(len(label) * CHAR_NOTE_WIDE) + 2
        elements.append(Element("note", "dflt_" + field.name, 0, y, label_width, NOTE_LINE, label))
        elements.append(Element("notevalue", "dfltv_" + field.name, label_width + 2, y, 80, NOTE_LINE,
                                model.format_value(field, extension_values.get(field.name), language)))
        y += NOTE_LINE
    if field.choice_notes:
        y += 2
        text_width = width - DESC_NAME_WIDTH
        height = _desc_height(field, language, text_width)
        elements.append(Element("descname", "descname_" + field.name, 0, y, DESC_NAME_WIDTH - 2, NOTE_LINE))
        elements.append(Element("desc", "desc_" + field.name, DESC_NAME_WIDTH, y, text_width, height))
        y += height
    return elements, y


def _page(group, mode, language, extension_values, overridden, width):
    page = Page(group.key, model.pick(group.title, language))
    y = 0
    page.elements.append(Element("title", "title_" + group.key, 0, y, width, TITLE_LINE, page.title))
    y += TITLE_LINE + 2
    if group.connection:
        sentence = model.pick(model.CONNECTION_NOTE_DOCUMENT if mode == "document"
                              else model.CONNECTION_NOTE_OPTIONS, language)
        height = text_lines(sentence, width, CHAR_NOTE) * NOTE_LINE
        page.elements.append(Element("note", "note_group_" + group.key, 0, y, width, height, sentence))
        y += height + 2
    if mode == "document" and group.key == "access":
        y += GAP
        label = model.text("db_address", language)
        page.elements.append(Element("label", "lbl_db_address", 0, y, width, LINE, label))
        y += LINE + 1
        page.elements.append(Element("edit", "edit_address", 0, y, width, CONTROL))
        y += CONTROL + 2
        new_x = width - DB_BUTTON_WIDTH
        open_x = new_x - 4 - DB_BUTTON_WIDTH
        page.elements.append(Element("browse", "btn_help_db", open_x - 4 - DB_HELP_WIDTH, y, DB_HELP_WIDTH,
                                     CONTROL, model.text("btn_help", language)))
        page.elements.append(Element("browse", "btn_open_db", open_x, y, DB_BUTTON_WIDTH, CONTROL,
                                     model.text("btn_open_file", language)))
        page.elements.append(Element("browse", "btn_new_db", new_x, y, DB_BUTTON_WIDTH, CONTROL,
                                     model.text("btn_new_file", language)))
        y += CONTROL + 1
        hint = model.text("db_address_hint", language)
        height = text_lines(hint, width, CHAR_NOTE) * NOTE_LINE
        page.elements.append(Element("note", "hint_address", 0, y, width, height, hint))
        y += height
    number = 0
    for field in model.fields_for(mode):
        if field.group != group.key:
            continue
        number += 1
        y += GAP
        page.elements.append(Element("line", "line_%s_%d" % (group.key, number), 0, y, width, 1))
        y += 1 + GAP
        elements, height = _field_block(field, mode, language, extension_values, overridden, width)
        for element in elements:
            element.y += y
            page.elements.append(element)
        page.fields.append(field)
        y += height
    if mode == "document" and group.key == "system":
        y += 3 * GAP
        page.elements.append(Element("browse", "btn_reset_advanced", 0, y, min(width, 190), CONTROL,
                                     model.text("btn_reset_advanced", language)))
        y += CONTROL + 2
        hint = model.text("reset_advanced_hint", language)
        height = text_lines(hint, width, CHAR_NOTE) * NOTE_LINE
        page.elements.append(Element("note", "hint_reset_advanced", 0, y, width, height, hint))
        y += height
    page.height = y
    return page


def layout(mode, language, extension_values=None, address=None, overridden=()):
    groups = model.groups_for(mode)
    header = []
    header_height = 0
    if mode == "document":
        width = DOC_WIDTH - 2 * MARGIN
        y = MARGIN
        hint = model.text("address_hint", language)
        height = text_lines(hint, width, CHAR_NOTE) * NOTE_LINE
        header.append(Element("note", "note_address_hint", MARGIN, y, width, height, hint))
        y += height + 2
        shown = address if address is not None else ""
        height = text_lines(shown, width, CHAR_ADDRESS) * 10
        header.append(Element("address", "lbl_address", MARGIN, y, width, height, shown))
        y += height + 2
        if overridden:
            note = model.text("address_overrides", language, names=", ".join(sorted(overridden)))
            height = text_lines(note, width, CHAR_NOTE) * NOTE_LINE
            header.append(Element("note", "note_address", MARGIN, y, width, height, note))
            y += height + 2
        header.append(Element("line", "line_header", 0, y, DOC_WIDTH, 1))
        header_height = y + 1 + MARGIN
        titles = tuple(model.pick(group.title, language) for group in groups)
        header.append(Element("nav", "nav", MARGIN, header_height, NAV_WIDTH, CONTENT_HEIGHT, items=titles))
    page_width = CONTENT_WIDTH if mode == "document" else OPTIONS_CONTENT_WIDTH
    pages = [_page(group, mode, language, extension_values, overridden, page_width) for group in groups]
    return Layout(mode, language, header, header_height, pages, dict(extension_values or {}))


_SERVICES = {
    "title": "FixedText", "label": "FixedText", "note": "FixedText", "desc": "FixedText",
    "descname": "FixedText", "notevalue": "FixedText", "spin": "SpinButton",
    "address": "FixedText", "check": "CheckBox", "list": "ListBox", "nav": "ListBox",
    "edit": "Edit", "browse": "Button", "line": "FixedLine",
}


def _font(item, height=None, weight=None):
    descriptor = item.FontDescriptor
    if height is not None:
        descriptor.Height = height
    if weight is not None:
        descriptor.Weight = weight
    item.FontDescriptor = descriptor


def _add(dialog_model, element, left, top, step):
    item = dialog_model.createInstance("com.sun.star.awt.UnoControl%sModel" % _SERVICES[element.kind])
    properties = {
        "PositionX": math.ceil(left + element.x), "PositionY": math.ceil(top + element.y),
        "Width": math.ceil(element.width), "Height": math.ceil(element.height), "Step": step,
    }
    if element.kind in ("descname", "notevalue"):
        properties["Label"] = element.text
    elif element.kind in ("title", "label", "note", "desc", "address"):
        properties["Label"] = element.text
        properties["MultiLine"] = True
        if element.kind in ("note", "desc"):
            properties["TextColor"] = GREY
    elif element.kind == "check":
        properties["Label"] = element.text
        properties["MultiLine"] = True
        properties["Enabled"] = element.enabled
    elif element.kind == "list":
        properties["Dropdown"] = True
        properties["StringItemList"] = tuple(element.items)
        properties["LineCount"] = max(1, min(len(element.items), 12))
        properties["Enabled"] = element.enabled
    elif element.kind == "nav":
        properties["Dropdown"] = False
        properties["StringItemList"] = tuple(element.items)
        properties["Step"] = 0
    elif element.kind == "browse":
        properties["Label"] = element.text
    elif element.kind == "edit":
        properties["Enabled"] = element.enabled
    elif element.kind == "spin":
        properties.update({"Orientation": 1, "SpinValueMin": 0, "SpinValueMax": 2, "SpinValue": 1,
                           "SpinIncrement": 1, "Repeat": True, "Enabled": element.enabled})
    for key, value in properties.items():
        setattr(item, key, value)
    if element.kind == "title":
        _font(item, 11, 150)
    elif element.kind == "address":
        _font(item, 10, 150)
    elif element.kind in ("note", "desc"):
        _font(item, 8)
    elif element.kind in ("descname", "notevalue"):
        _font(item, 8, 150)
    dialog_model.insertByName(element.name, item)


def build(dialog_model, lay, key=None):
    for element in lay.header:
        _add(dialog_model, element, 0, 0, 0)
    if lay.paged:
        for number, page in enumerate(lay.pages, 1):
            for element in page.elements:
                _add(dialog_model, element, lay.origin_x, lay.origin_y, number)
        dialog_model.Step = 1
    else:
        for element in lay.page(key).elements:
            _add(dialog_model, element, lay.origin_x, lay.origin_y, 0)


class _Nav(unohelper.Base, XItemListener):

    def __init__(self, dialog_model):
        self._model = dialog_model

    def itemStateChanged(self, event):
        self._model.Step = int(event.Selected) + 1

    def disposing(self, event):
        pass


class _Choice(unohelper.Base, XItemListener):

    def __init__(self, function):
        self._function = function

    def itemStateChanged(self, event):
        self._function()

    def disposing(self, event):
        pass


class _Action(unohelper.Base, XActionListener):

    def __init__(self, function):
        self._function = function

    def actionPerformed(self, event):
        self._function()

    def disposing(self, event):
        pass


class _Digits(unohelper.Base, XTextListener):

    def __init__(self, control):
        self._control = control

    def textChanged(self, event):
        control = self._control
        text = control.getText()
        clean = "".join(char for char in text if char in "0123456789")
        if clean != text:
            control.setText(clean)
            end = uno.createUnoStruct("com.sun.star.awt.Selection")
            end.Min = end.Max = len(clean)
            control.setSelection(end)

    def disposing(self, event):
        pass


def clamp_number(field, text):
    if text == "":
        return ""
    number = max(int(text), field.minimum)
    if field.maximum is not None:
        number = min(number, field.maximum)
    return str(number)


class _Clamp(unohelper.Base, XFocusListener):

    def __init__(self, field, control):
        self._field = field
        self._control = control

    def focusGained(self, event):
        pass

    def focusLost(self, event):
        control = self._control
        text = control.getText()
        fixed = clamp_number(self._field, text)
        if fixed != text:
            control.setText(fixed)

    def disposing(self, event):
        pass


class _Spin(unohelper.Base, XAdjustmentListener):

    def __init__(self, control, field, start, spin):
        self._control = control
        self._field = field
        self._start = start
        self._spin = spin

    def _step(self, delta):
        text = self._control.getText().strip()
        if text == "":
            number = self._start
        else:
            number = int(text) + delta
        self._control.setText(clamp_number(self._field, str(max(number, 0))))

    def adjustmentValueChanged(self, event):
        value = event.Value
        if value == 1:
            return
        self._step(1 if value > 1 else -1)
        self._spin.setValue(1)

    def disposing(self, event):
        pass


def _page_fields(lay, key=None):
    if lay.paged or key is None:
        return list(lay.fields)
    return list(lay.page(key).fields)


def connect_controls(container, dialog_model, lay, key=None):
    listeners = []
    if lay.paged:
        listener = _Nav(dialog_model)
        nav = container.getControl("nav")
        nav.addItemListener(listener)
        nav.selectItemPos(0, True)
        listeners.append(listener)
    for field in _page_fields(lay, key):
        if field.choice_notes:
            listener = _Choice(lambda field=field: update_description(container, dialog_model, lay, field))
            container.getControl("ctl_" + field.name).addItemListener(listener)
            listeners.append(listener)
        if field.kind == "int" and field.enabled:
            edit = container.getControl("ctl_" + field.name)
            digits, clamp = _Digits(edit), _Clamp(field, edit)
            edit.addTextListener(digits)
            edit.addFocusListener(clamp)
            start = (lay.extension_values or {}).get(field.name)
            start = field.minimum if not isinstance(start, int) else start
            arrows = container.getControl("spin_" + field.name)
            spin = _Spin(edit, field, start, arrows)
            arrows.addAdjustmentListener(spin)
            listeners.extend((digits, clamp, spin))
    return listeners


def update_description(container, dialog_model, lay, field):
    position = container.getControl("ctl_" + field.name).getSelectedItemPos()
    offset = 1 if lay.mode == "document" else 0
    if position < 0:
        value = None
    elif lay.mode == "document" and position == 0:
        value = lay.extension_values.get(field.name)
    else:
        value = field.choices[position - offset]
    name, text = description_parts(field, value, lay.language)
    dialog_model.getByName("descname_" + field.name).Label = name
    dialog_model.getByName("desc_" + field.name).Label = text


def on_click(container, name, function):
    listener = _Action(function)
    container.getControl(name).addActionListener(listener)
    return listener


def _index(field, value, mode):
    offset = 1 if mode == "document" else 0
    if value is None:
        return 0
    if field.kind == "bool":
        return offset + (0 if value else 1)
    return offset + list(field.choices).index(value)


def apply_values(container, lay, values, key=None):
    for field in _page_fields(lay, key):
        control = container.getControl("ctl_" + field.name)
        value = values.get(field.name)
        if field.kind == "bool" and lay.mode == "options":
            control.setState(1 if value else 0)
        elif field.kind in ("int", "text"):
            control.setText("" if value is None else str(value))
        else:
            control.selectItemPos(_index(field, value, lay.mode), True)
            if field.choice_notes:
                update_description(container, container.getModel(), lay, field)


def read_values(container, lay, key=None):
    values = {}
    errors = []
    offset = 1 if lay.mode == "document" else 0
    for field in _page_fields(lay, key):
        if not field.enabled:
            continue
        control = container.getControl("ctl_" + field.name)
        if field.kind == "bool" and lay.mode == "options":
            values[field.name] = control.getState() == 1
        elif field.kind == "text":
            values[field.name] = control.getText().strip()
        elif field.kind == "int":
            entered = control.getText().strip()
            if entered == "" and lay.mode == "document":
                values[field.name] = None
                continue
            try:
                values[field.name] = model.parse_number(field, entered)
            except ValueError:
                errors.append(model.error_text(field, lay.language))
        else:
            position = max(control.getSelectedItemPos(), 0)
            if lay.mode == "document" and position <= 0:
                values[field.name] = None
            elif field.kind == "bool":
                values[field.name] = (position - offset) == 0
            else:
                values[field.name] = field.choices[position - offset]
    if not errors and not model.check_pair(values):
        errors.append(parameters.pair_text(lay.language))
    return values, errors
