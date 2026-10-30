# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import math
import os
import tempfile
import traceback

import unohelper

from com.sun.star.awt.MessageBoxType import ERRORBOX
from com.sun.star.awt.MessageBoxType import INFOBOX
from com.sun.star.awt.MessageBoxType import QUERYBOX
from com.sun.star.ui.dialogs.TemplateDescription import FILEOPEN_SIMPLE
from com.sun.star.ui.dialogs.TemplateDescription import FILESAVE_AUTOEXTENSION

from sdbc_pysqlite import LOG_FILE_NAME
from sdbc_pysqlite import address
from sdbc_pysqlite import logger
from sdbc_pysqlite import messages
from sdbc_pysqlite.errors import DriverError
from sdbc_pysqlite import settings_form as form
from sdbc_pysqlite import settings_model as model

_BUTTON_OK = 1
_BUTTON_CANCEL = 2


def show_message(ctx, parent, title, text, error=False):
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    box = toolkit.createMessageBox(parent, ERRORBOX if error else INFOBOX, 1, title, text)
    try:
        box.execute()
    finally:
        box.dispose()


def ask_yes_no(ctx, parent, title, text):
    toolkit = ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    box = toolkit.createMessageBox(parent, QUERYBOX, 3, title, text)
    try:
        return box.execute() == 2
    finally:
        box.dispose()


def _add_button(dialog_model, name, label, x, y, width, height, push_type=0, multiline=False, default=False):
    button = dialog_model.createInstance("com.sun.star.awt.UnoControlButtonModel")
    for key, value in (("PositionX", x), ("PositionY", y), ("Width", width), ("Height", height),
                       ("Label", label), ("PushButtonType", push_type), ("MultiLine", multiline),
                       ("DefaultButton", default), ("Step", 0)):
        setattr(button, key, value)
    dialog_model.insertByName(name, button)


def add_options_buttons(dialog_model, lay, with_log):
    top = form.MARGIN + form.CONTENT_HEIGHT + 4
    third = (form.PAGE_WIDTH - 4 * form.MARGIN) // 3
    _add_button(dialog_model, "btn_driver", model.text("btn_driver_defaults", lay.language),
                form.MARGIN, top, third if with_log else 120, form.BUTTON_HEIGHT)
    if with_log:
        _add_button(dialog_model, "btn_log", model.text("btn_log", lay.language),
                    2 * form.MARGIN + third, top, third, form.BUTTON_HEIGHT)
        _add_button(dialog_model, "btn_folder", model.text("btn_folder", lay.language),
                    3 * form.MARGIN + 2 * third, top, third, form.BUTTON_HEIGHT)


def pick_folder(ctx, parent, language, current_path):
    picker = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FolderPicker", ctx)
    picker.setTitle(model.text("browse_title", language))
    try:
        if current_path and os.path.isdir(current_path):
            picker.setDisplayDirectory(unohelper.systemPathToFileUrl(current_path))
    except Exception:
        pass
    if picker.execute() != 1:
        return None
    return unohelper.fileUrlToSystemPath(picker.getDirectory())


def pick_database_file(ctx, parent, language, current_text, new_file):
    picker = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FilePicker", ctx)
    if new_file:
        picker.initialize((FILESAVE_AUTOEXTENSION, ))
        picker.setTitle(model.text("new_file_title", language))
    else:
        picker.initialize((FILEOPEN_SIMPLE, ))
        picker.setTitle(model.text("open_file_title", language))
    picker.appendFilter(model.text("filter_db3", language), "*.db3")
    picker.appendFilter(model.text("filter_sqlite", language), "*.db3;*.db;*.sqlite;*.sqlite3")
    picker.appendFilter(model.text("filter_all", language), "*.*")
    picker.setCurrentFilter(model.text("filter_db3" if new_file else "filter_sqlite", language))
    try:
        path = address.split_address(current_text, unohelper.fileUrlToSystemPath).path
        folder = os.path.dirname(path)
        if folder and os.path.isdir(folder):
            picker.setDisplayDirectory(unohelper.systemPathToFileUrl(folder))
            if not new_file and os.path.isfile(path):
                picker.setDefaultName(os.path.basename(path))
    except Exception:
        pass
    if picker.execute() != 1:
        return None
    files = picker.getSelectedFiles()
    if not files:
        return None
    chosen = unohelper.fileUrlToSystemPath(files[0])
    if new_file and picker.getCurrentFilter() in (model.text("filter_db3", language),
                                                  model.text("filter_sqlite", language)):
        chosen = address.with_default_extension(chosen)
    return chosen


def show_help(ctx, parent, language):
    try:
        folder = os.path.join(tempfile.gettempdir(), "sdbc-pysqlite")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "address-help-%s.html" % language)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(model.address_help_html(language))
        shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
        shell.execute(unohelper.systemPathToFileUrl(path), "", 0)
        return
    except Exception:
        logger.error("settings_dialogs.show_help", traceback.format_exc())
    show_help_text(ctx, parent, language)


def show_help_text(ctx, parent, language):
    manager = ctx.ServiceManager
    width, height = 420, 270
    dialog_model = manager.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    dialog_model.PositionX = 100
    dialog_model.PositionY = 40
    dialog_model.Width = width
    dialog_model.Height = height
    dialog_model.Title = model.text("help_title", language)
    box = dialog_model.createInstance("com.sun.star.awt.UnoControlEditModel")
    for key, value in (("PositionX", form.MARGIN), ("PositionY", form.MARGIN), ("Width", width - 2 * form.MARGIN),
                       ("Height", height - 3 * form.MARGIN - form.BUTTON_HEIGHT), ("MultiLine", True),
                       ("ReadOnly", True), ("VScroll", True), ("HScroll", False), ("AutoVScroll", False),
                       ("Border", 1), ("Step", 0)):
        setattr(box, key, value)
    box.Text = model.address_help(language).replace("\n", "\r\n")
    dialog_model.insertByName("help_text", box)
    _add_button(dialog_model, "btn_ok", model.text("btn_ok", language),
                width - 54 - form.MARGIN, height - form.MARGIN - form.BUTTON_HEIGHT, 54, form.BUTTON_HEIGHT,
                default=True, push_type=_BUTTON_OK)
    dialog = manager.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dialog_model)
    toolkit = manager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, parent)
    try:
        dialog.execute()
    finally:
        dialog.dispose()


def address_problem(text, language):
    try:
        address.check_address(text, unohelper.fileUrlToSystemPath)
    except DriverError as exception:
        return messages.describe(exception, language, "settings_dialogs").message
    return None


def open_log_folder(ctx, parent, language):
    folder = logger.log_folder()
    try:
        shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
        shell.execute(unohelper.systemPathToFileUrl(folder), "", 0)
    except Exception:
        logger.error("settings_dialogs.open_log_folder", traceback.format_exc())
        show_message(ctx, parent, model.text("msg_title", language),
                     model.text("msg_folder_failed", language, path=folder), error=True)


def open_log(ctx, parent, language):
    path = os.path.join(logger.log_folder(), LOG_FILE_NAME)
    title = model.text("msg_title", language)
    if not os.path.exists(path):
        show_message(ctx, parent, title, model.text("msg_log_missing", language, folder=logger.log_folder()))
        return
    try:
        shell = ctx.ServiceManager.createInstanceWithContext("com.sun.star.system.SystemShellExecute", ctx)
        shell.execute(unohelper.systemPathToFileUrl(path), "", 0)
    except Exception:
        logger.error("settings_dialogs.open_log", traceback.format_exc())
        show_message(ctx, parent, title, model.text("msg_log_failed", language, path=path), error=True)


def run_document_dialog(ctx, language, extension_values, document_values, address_text, overridden,
                        frame_window=None, reset_advanced=None):
    manager = ctx.ServiceManager
    shown_address = address.display_text(address_text)
    lay = form.layout("document", language, extension_values, shown_address, overridden)
    dialog_model = manager.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
    top = math.ceil(lay.header_height) + form.CONTENT_HEIGHT + 4
    width = form.DOC_WIDTH
    dialog_model.PositionX = 100
    dialog_model.PositionY = 40
    dialog_model.Width = width
    dialog_model.Height = top + 24 + form.BUTTON_HEIGHT + 6
    dialog_model.Title = model.text("doc_title", language)
    form.build(dialog_model, lay)
    half = (width - 3 * form.MARGIN) // 2
    _add_button(dialog_model, "btn_driver", model.text("btn_driver_defaults", language),
                form.MARGIN, top, half, 20, multiline=True)
    _add_button(dialog_model, "btn_extension", model.text("btn_extension", language),
                2 * form.MARGIN + half, top, half, 20, multiline=True)
    _add_button(dialog_model, "btn_log", model.text("btn_log", language),
                form.MARGIN, top + 24, 100, form.BUTTON_HEIGHT)
    _add_button(dialog_model, "btn_folder", model.text("btn_folder", language),
                2 * form.MARGIN + 100, top + 24, 100, form.BUTTON_HEIGHT)
    _add_button(dialog_model, "btn_ok", model.text("btn_ok", language),
                width - 2 * 54 - 2 * form.MARGIN, top + 24, 54, form.BUTTON_HEIGHT, default=True)
    _add_button(dialog_model, "btn_cancel", model.text("btn_cancel", language),
                width - 54 - form.MARGIN, top + 24, 54, form.BUTTON_HEIGHT, push_type=_BUTTON_CANCEL)

    dialog = manager.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
    dialog.setModel(dialog_model)
    toolkit = manager.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
    dialog.createPeer(toolkit, frame_window)
    result = {}
    try:
        listeners = list(form.connect_controls(dialog, dialog_model, lay))
        form.apply_values(dialog, lay, document_values)
        address_edit = dialog.getControl("edit_address")
        address_edit.setText(shown_address)

        def driver_defaults():
            form.apply_values(dialog, lay, {name: value for name, value in model.driver_defaults().items()
                                            if name in {field.name for field in lay.fields if field.enabled}})

        def use_extension():
            form.apply_values(dialog, lay, {})

        def browse_database(new_file):
            chosen_path = pick_database_file(ctx, dialog.getPeer(), language, address_edit.getText(), new_file)
            if chosen_path:
                address_edit.setText(address.with_path(address_edit.getText(), chosen_path))

        def accept():
            values, errors = form.read_values(dialog, lay)
            problem = address_problem(address_edit.getText(), language)
            if problem:
                errors.append(model.text("msg_address_invalid", language, detail=problem))
            if errors:
                show_message(ctx, dialog.getPeer(), model.text("msg_title", language),
                             model.text("msg_invalid", language, list="\n".join(errors)), error=True)
                return
            result.update(values)
            typed = address_edit.getText()
            result["__address__"] = (address_text.strip() if typed.strip() == shown_address
                                     else address.full_address(typed, unohelper.fileUrlToSystemPath))
            result["__accepted__"] = True
            dialog.endExecute()

        listeners.append(form.on_click(dialog, "btn_driver", driver_defaults))
        listeners.append(form.on_click(dialog, "btn_extension", use_extension))
        listeners.append(form.on_click(dialog, "btn_help_db", lambda: show_help(ctx, dialog.getPeer(), language)))
        listeners.append(form.on_click(dialog, "btn_open_db", lambda: browse_database(False)))
        listeners.append(form.on_click(dialog, "btn_new_db", lambda: browse_database(True)))
        def do_reset_advanced():
            peer = dialog.getPeer()
            title = model.text("msg_title", language)
            if reset_advanced is None:
                return
            if not ask_yes_no(ctx, peer, title, model.text("msg_reset_confirm", language)):
                return
            show_message(ctx, peer, title, reset_advanced())

        listeners.append(form.on_click(dialog, "btn_reset_advanced", do_reset_advanced))
        listeners.append(form.on_click(dialog, "btn_ok", accept))
        listeners.append(form.on_click(dialog, "btn_log", lambda: open_log(ctx, dialog.getPeer(), language)))
        listeners.append(form.on_click(dialog, "btn_folder",
                                       lambda: open_log_folder(ctx, dialog.getPeer(), language)))
        dialog.execute()
    finally:
        dialog.dispose()
    if not result.pop("__accepted__", False):
        return None
    return result
