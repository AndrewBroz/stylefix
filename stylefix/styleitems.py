"""Style-guide alerts that become adjudication items: one concrete edit
versus KEEP, decided from the sentence."""

from __future__ import annotations

import re

from .styleguides import StyleGuide

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
         "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def number_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else "-" + _ONES[n % 10])
    if n == 100:
        return "one hundred"
    raise ValueError(n)


_SERIAL_MISSING = re.compile(r"^(\w+, \w+)( (?:and|or) \w+)$")
_SERIAL_PRESENT = re.compile(r"^(\w+, \w+), ((?:and|or) \w+)$")
_NUMBER = re.compile(r"^(\s)(\d{1,3})(\s)$")


def candidate(check: str, match: str, guide: StyleGuide) -> tuple[str, str] | None:
    """(replacement, rule of thumb) for a style alert, or None if not adjudicable."""
    rule = check.rsplit(".", 1)[-1]
    t = guide.title or "The style guide"
    if rule == "SerialComma":
        if guide.serial_comma == "require":
            m = _SERIAL_MISSING.match(match)
            if not m:
                return None
            return (m.group(1) + "," + m.group(2),
                    f"{t} puts a comma before 'and'/'or' in a list of three or more items. "
                    "Choose the version with the comma only if this is such a list. KEEP if the "
                    "first comma introduces an aside or a restatement ('attacks, intentional and "
                    "unintentional'), or the last two words form a pair that belongs together.")
        if guide.serial_comma == "omit":
            m = _SERIAL_PRESENT.match(match)
            if not m:
                return None
            return (m.group(1) + " " + m.group(2),
                    f"{t} omits the comma before 'and'/'or' in a simple series. Choose the version "
                    "without it only if every item is a single simple term. KEEP if any item "
                    "contains a conjunction or the comma prevents misreading.")
        return None
    if rule == "Numbers":
        m = _NUMBER.match(match)
        if not m or not guide.spell_out_below:
            return None
        n = int(m.group(2))
        if not 0 < n < guide.spell_out_below:
            return None
        return (m.group(1) + number_words(n) + m.group(3),
                f"{t} spells out whole numbers below {guide.spell_out_below} in running text. "
                "Choose the spelled-out form for an ordinary count in prose ('three options', "
                "'ten years'). KEEP for percentages, measurements with units, money, dates, "
                "times, ages in technical text, page, figure, table, section and version "
                "numbers, scores, ratios, and any number in a table or a list of figures.")
    return None
