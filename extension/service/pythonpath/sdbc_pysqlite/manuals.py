# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import os

MANUALS_FOLDER = "manuals"


def manual_pages(package_folder):
    folder = os.path.join(package_folder, MANUALS_FOLDER)
    try:
        names = sorted(name for name in os.listdir(folder) if name.lower().endswith(".html"))
    except OSError:
        return []
    return [os.path.join(folder, name) for name in names]
