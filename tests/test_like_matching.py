# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2026 ReBotCoft

import random
import re
import time
import unittest

import support

from sdbc_pysqlite import functions


def reference_like(pattern, text, escape=None):
    folded = functions.fold(pattern)
    esc = functions.fold(escape) if escape else None
    out = []
    i = 0
    while i < len(folded):
        char = folded[i]
        if esc is not None and char == esc and i + 1 < len(folded):
            i += 1
            out.append(re.escape(folded[i]))
        elif char == "%":
            out.append(".*")
        elif char == "_":
            out.append(".")
        else:
            out.append(re.escape(char))
        i += 1
    return 1 if re.compile("".join(out), re.DOTALL).fullmatch(functions.fold(text)) else 0


class SameResultTests(unittest.TestCase):

    def test_random_patterns_give_the_same_answer_as_the_regular_expression(self):
        generator = random.Random(20261030)
        alphabet_pattern = "abAB%_!è"
        alphabet_text = "abAB!è\n e"
        for _ in range(6000):
            pattern = "".join(generator.choice(alphabet_pattern) for _ in range(generator.randint(0, 8)))
            text = "".join(generator.choice(alphabet_text) for _ in range(generator.randint(0, 9)))
            for escape in (None, "!"):
                self.assertEqual(functions.like(pattern, text, escape), reference_like(pattern, text, escape),
                                 (pattern, text, escape))

    def test_known_cases(self):
        cases = (
            ("a%", "Abc", 1), ("%c", "abC", 1), ("a_c", "abc", 1), ("a_c", "ac", 0), ("%", "", 1),
            ("_", "", 0), ("", "", 1), ("", "a", 0), ("%%a%%", "xxa", 1), ("È", "e", 1), ("e", "È", 1),
            ("a%b", "a\nb", 1), ("%a", "ab", 0),
        )
        for pattern, text, expected in cases:
            self.assertEqual(functions.like(pattern, text), expected, (pattern, text))

    def test_escape(self):
        self.assertEqual(functions.like("a!%b", "a%b", "!"), 1)
        self.assertEqual(functions.like("a!%b", "axb", "!"), 0)
        self.assertEqual(functions.like("a!_b", "a_b", "!"), 1)
        self.assertEqual(functions.like("a!", "a!", "!"), 1)
        with self.assertRaises(ValueError):
            functions.like("a", "a", "!!")

    def test_null(self):
        self.assertIsNone(functions.like(None, "a"))
        self.assertIsNone(functions.like("a", None))


class SpeedTests(unittest.TestCase):

    def test_many_percent_signs_do_not_slow_down(self):
        text = "a" * 3000
        for pieces in (4, 8, 40):
            pattern = "%a" * pieces + "%b"
            started = time.perf_counter()
            self.assertEqual(functions.like(pattern, text), 0)
            self.assertLess(time.perf_counter() - started, 2.0, pieces)

    def test_matches_on_long_text_are_fast(self):
        started = time.perf_counter()
        self.assertEqual(functions.like("%a%a%a%a%a%a%", "a" * 5000), 1)
        self.assertLess(time.perf_counter() - started, 2.0)


if __name__ == "__main__":
    unittest.main()
