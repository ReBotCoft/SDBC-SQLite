# Contributing

This project is provided free of charge and "as is", without any
promise of support, maintenance or response times (see the notice
in the README).

## Reporting a problem

Open an issue and include:

- the extension version, the Windows version and the LibreOffice
  version;
- what you did, step by step, and what you expected to happen;
- the full text of the message, including its last line (code,
  SQLState and location);
- if possible, the diagnostic log (Base: Edit -> Database ->
  PySQLite settings... -> Open the log) and a small sample
  database with non-confidential data.

The log can contain paths and SQL commands: check it before
sharing.

## Proposing a change

Changes are welcome as pull requests, but there is no guarantee
that they will be reviewed or merged. Before you start, please
keep in mind:

- the code is licensed under the LGPL-3.0-or-later; by submitting
  a change you agree that it is released under the same license;
- every code file starts with the lines
  `SPDX-License-Identifier: LGPL-3.0-or-later` and
  `Copyright (c) <year> <holder>`;
- run the automated tests before submitting (see `test.cmd`).

## Forking

You are free to fork the project and develop it independently,
under the terms of the license. See the `NOTICE` file for what
must be kept when redistributing.
