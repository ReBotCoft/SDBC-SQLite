# Exact Decimals in SQL Commands — a guide for Base users

*For those who write SQL commands by hand (SQL window, Queries, macros) on tables with columns of type `LO_DECIMAL`.*

---

## 1. The `LO_DECIMAL` type in brief

SQLite has no exact decimal number. A `12.35` saved as a real number can become `12.3499999…` after some calculations, and sums accumulate small errors. The driver solves the problem with the **`LO_DECIMAL`** type: in the file the value is saved as an **integer** (`12.35` becomes `1235`), which is exact forever. When you read it, the driver puts the decimal point back.

- It is declared like this: `LO_DECIMAL(10,2)`. The first number is the total length, the second is the number of **decimals**, from 0 to 18. When you write a value only the decimals matter; the total length is checked only if you change the type of a column that already contains data (section 6). With 0 decimals the value is a normal integer and there is nothing to translate.
- From Base's table window, in forms and in reports you **don't have to do anything**: values are already read and written correctly.
- A value too large to fit gives a clear error and the file does not change. The limit is that of 64-bit integers, about 9.2 × 10¹⁸ once multiplied by the decimals: a value of 18 digits in total always fits.

This guide concerns **SQL commands written by hand**: the driver rewrites them before running them, so that they work on the values with the decimal point.

## 2. What to write and what you get

Always write numbers **with the point** (`12.5`), as in any SQL command. The examples use the column `importo` of type `LO_DECIMAL(10,2)`.

| What you write | What happens |
|---|---|
| `SELECT importo FROM persone` | Shows `12.35`, not `1235`. |
| `SELECT SUM(importo), AVG(importo), MAX(importo) FROM persone` | Sums, averages, maximums and minimums with the decimal point. The sum is exact. |
| `WHERE importo > 12.5`, `= 0.07`, `BETWEEN 1 AND 5`, `IN (3, 0.07)` | The comparison is with the true value. If there is an index on the column, it can still be used. |
| `WHERE importo > ?` or `> :soglia` | Also applies to parameters: the value you pass is compared as it is. |
| `INSERT INTO persone(importo) VALUES (12.5)` | Saves `12.50`. |
| `UPDATE persone SET importo = importo + 1` | Calculates with the true values and saves the result. |
| `UPDATE … RETURNING importo` | Returns the value with the decimal point. |
| `SELECT importo * 2 FROM persone` | The result has the decimal point and the column is still called `importo * 2`: the name does not change. |
| Subqueries, `WITH`, `UNION`, `JOIN` with full names (`persone.importo`) | They work. |
| `INSERT … SELECT` from a decimal column to the same scale | The value is copied identically. |
| `INSERT … SELECT` between different scales, or from a normal column | The value is converted and rounded to the destination scale. |
| `INSERT … ON CONFLICT … DO UPDATE SET importo = excluded.importo` | Works as you expect. |

### Rounding on write

If you write more decimals than the column has (`12.345` in a column with 2 decimals), the value is rounded to the nearest **without an error**: if the first digit removed is from 0 to 4 it is rounded down (`12.344` becomes `12.34`), from 5 to 9 it is rounded up (`12.345` becomes `12.35`, `-12.345` becomes `-12.35`).

In **comparisons**, on the other hand, there is never any rounding: `WHERE importo > 12.345` compares with the exact `12.345`, so a value saved as `12.35` is greater.

## 3. Rejected commands

In these cases the command **is not executed** and the message says what is wrong. A value wrong by a factor of 100 with no warning would be worse than a rejection.

### 3.1 Ambiguous column name (error 50316)

**When it happens:** the column name exists in more than one table of the command and at least one is `LO_DECIMAL`.

```sql
-- persone.importo is LO_DECIMAL, ordini.importo is a normal number
SELECT importo FROM persone JOIN ordini ON ordini.pid = persone.id;   -- rejected
```

**Why:** the two columns do not have the same format (one is multiplied, the other is not): the driver cannot know which one you mean and the value would be wrong.

**What to write:** the table name in front of the column.

```sql
SELECT persone.importo FROM persone JOIN ordini ON ordini.pid = persone.id;
```

### 3.2 `NATURAL JOIN` and `USING` on a decimal column (error 50317)

**When it happens:** `NATURAL JOIN`, or `USING (column)`, with an `LO_DECIMAL` column.

```sql
SELECT * FROM persone NATURAL JOIN ordini;                    -- rejected
SELECT * FROM persone JOIN ordini USING (importo);            -- rejected
```

**Why:** these joins compare the numbers **as they are saved**. Between two columns with different scales, or between a decimal and a normal one, the numbers do not match. `LO_DECIMAL` should be used only between columns of the same type and the same scale.

**What to write:** the explicit join, which compares the true values even with different scales.

```sql
SELECT * FROM persone JOIN ordini ON persone.importo = ordini.importo;
```

### 3.3 Construct the driver cannot read (error 50318)

**When it happens:** the command names an `LO_DECIMAL` column but the driver cannot work out where it is or how to translate it. The message indicates which part.

Known cases:
- `INSERT … SELECT *` into a table with decimal columns: the asterisk does not allow the source and destination columns to be matched.
- `INSERT INTO table VALUES (…)` without a column list, with a number of values different from the table's columns.
- `UPDATE … SET (a, b) = (…)` that includes a decimal column.
- `SELECT *` in a subquery together with `USING`/`NATURAL`, or with another subquery in the same `FROM`.
- Unbalanced parentheses or other unrecognized syntax.

**What to write:** a simpler form, with the list of columns written out in full.

```sql
INSERT INTO persone(nome, importo) SELECT nome, importo FROM altra;
UPDATE persone SET nome = 'a', importo = 5;
```

### 3.4 Triggers (error 50319)

**When it happens:** `CREATE TRIGGER` whose text names an `LO_DECIMAL` column.

**Why:** a trigger is run by SQLite on its own, on the numbers as they are saved (`1235`), and for now the driver does not translate it.

**What to do:** carry out the operation with a separate command or macro; or write the trigger bearing in mind that the values are **multiplied by 10 to the power of the column's decimals** (with 2 decimals, `importo > 500` means "greater than 5.00"). A trigger that does not name decimal columns goes through.

## 4. Warnings

In these cases the command **is executed** and a warning arrives (it can be seen in the log; Base's SQL window may not show it).

### 4.1 `CREATE TABLE … AS SELECT` (warning 50320)

```sql
CREATE TABLE copia AS SELECT importo FROM persone;
```

The values in the new table already have the decimal point (`12.35`), but the column is a normal number, not `LO_DECIMAL`. **To have it as a decimal:** first create the table with the right type, then copy.

```sql
CREATE TABLE copia(importo LO_DECIMAL(10,2));
INSERT INTO copia(importo) SELECT importo FROM persone;
```

### 4.2 `CREATE VIEW` (warning 50321)

```sql
CREATE VIEW v AS SELECT importo FROM persone;
```

The view already shows the numbers with the decimal point and its column is a normal number, not `LO_DECIMAL`. What stays saved in the file is the text already rewritten by the driver (with the division inside). Nothing needs to be done: read `SELECT importo FROM v` and you get `12.35`.

## 5. Things to know

- **Calculations and rounding.** The result of a calculation (an average, a multiplication) is a real number: exact to about 15 significant digits, but not in exact halfway cases. The exception is `ROUND` of a decimal column: `ROUND(importo)` and `ROUND(importo, 1)` (with a hand-written number smaller than the column's decimals) round on the saved value and are exact: `12.35` gives `12.4`, `-12.35` gives `-12.4`, `8.5` gives `9`. With `ROUND` of an **expression** (`ROUND(importo * 1.1, 1)`) the limit of real numbers applies instead: a calculated `12.35` may be `12.349999…` and give `12.3`. For an exact rounding after a calculation one can write, for one decimal: `ROUND(ROUND(expression * 100) / 10.0) / 10.0` (`ROUND(expression * 100)` brings it back to the integer, which is exact, and the rounding starts from there). The saved value is never touched: the imprecision concerns only the result of the calculation.
- **Sums.** `SUM` is done on the saved integers, so it is exact: it is divided only once, at the end. `AVG` gets the same treatment.
- **Inside a `CREATE TABLE` or a `CREATE INDEX`.** `CHECK` constraints, `DEFAULT` values, generated columns and partial indexes are not translated: there the numbers are the saved ones (`CHECK (importo > 500)` means "greater than 5.00"). An index on the column, on the other hand, is normal and useful.
- **Views and triggers created by other programs.** They are in the file and do not pass through the driver: they cannot be translated.
- **Other programs that open the file** (DB Browser, command-line tools) see the multiplied numbers (`1235` instead of `12.35`). Exactness is guaranteed only with Base and with this driver.
- **Base's language.** When typing a value by hand in the grid of a table with Italian settings, the comma is needed (`7,25`); with the point Base reads it wrongly and saves `0`. This is Base's behavior, the driver already receives the wrong value. In SQL commands, instead, the point is always the right one.
- **Parameters.** `?` and `:name` (also `@name`, `$name`) work in the same way. A repeated name is the same parameter.

## 6. Changing the decimals of an existing column

The scale can be changed in the table structure in Base. The driver rebuilds the table and converts the values to the new representation: increasing the decimals keeps the value, while decreasing them rounds to the nearest as in writes (`12.345` becomes `12.35`). If a value has more digits than the total length of the new type allows, or does not fit in 64-bit integers, the operation is rejected with error 50405 and the table does not change; if a value cannot be converted at all, the error is 50403.

This operation must be distinguished from changing only an SQL label: the stored numbers must be recalculated, otherwise the value read turns out multiplied or divided by a power of ten.

For a conversion done with SQL, create a new table with the desired type and scale and copy the data through the driver, with an explicit list of columns. For example, going from two to three decimals:

```sql
CREATE TABLE persone_nuova(id INTEGER PRIMARY KEY, nome TEXT, importo LO_DECIMAL(10,3));
INSERT INTO persone_nuova(id, nome, importo) SELECT id, nome, importo FROM persone;
```

The copy converts the values to the destination scale. It does not automatically transfer all the other objects of the table: you must think about indexes, constraints, relationships, triggers and views. Check the data and these dependencies before replacing the original table, and work on a copy of the database.
