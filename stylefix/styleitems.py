"""Style-guide questions that become adjudication items: one concrete edit
versus KEEP, decided from the sentence.

Serial commas are detected here, in Python over the raw prose, rather
than by a Vale rule: Vale strips inline markup from its match text and
misses a series that runs into bold or contains an HTML entity. Each
decision is applied as a one-character edit at the comma's raw position,
so markup inside the series is never touched."""

from __future__ import annotations

import re
from dataclasses import dataclass

from adjudicate import Edit, Item, protected_spans, sentence_context
from adjudicate.context import _HTML_ENTITY

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


# The series as Vale matched it: items may be multi-word, numbered or
# emphasised. The conjunction that matters is the last one.
_SERIAL_MISSING = re.compile(r"^(.*[^,\s])( (?:and|or) [^,]+)$", re.S)
_SERIAL_PRESENT = re.compile(r"^(.*[^\s]),( (?:and|or) [^,]+)$", re.S)
_NUMBER = re.compile(r"^(\s)(\d{1,3})(\s)$")

# A series item: up to eight words, where a word may carry markup or an
# HTML entity, but never sentence punctuation or a comma.
_W = r"(?:&#?\w+;|[^\s,.;:!?])+"
_ITEM = rf"{_W}(?:[ \t]+{_W}){{0,7}}"
SERIES_MISSING = re.compile(rf"{_ITEM}, {_ITEM} (?:and|or) {_ITEM}")
SERIES_PRESENT = re.compile(rf"{_ITEM}, {_ITEM}, (?:and|or) {_ITEM}")
_LAST_CONJ_NO_COMMA = re.compile(r"([^,\s])(\s+(?:and|or)\s)(?!.*\s(?:and|or)\s)", re.S)
_LAST_CONJ_COMMA = re.compile(r",(\s+(?:and|or)\s)(?!.*,\s+(?:and|or)\s)", re.S)


OMIT_RULES = {
    "guardian": (
        "The Guardian and Observer style guide ('Oxford comma' entry) says: a comma before the "
        "final 'and' in lists: straightforward ones ('he ate ham, eggs and chips') do not need one, "
        "but sometimes it can help the reader ('he ate cereal, kippers, bacon, eggs, toast and "
        "marmalade, and tea'), and sometimes it is essential: compare 'I dedicate this book to my "
        "parents, Martin Amis, and JK Rowling' with '... my parents, Martin Amis and JK Rowling'. "
        "Here no item adjacent to the final 'and' contains its own 'and'. Choose the version without "
        "the comma unless the last two items could be read as an apposition (the second naming or "
        "explaining the first, as with the parents), or the conjunction joins two independent "
        "clauses rather than list items; then KEEP. An 'and' elsewhere in the list does not by "
        "itself call for the comma, and neither does numbering of the items (1) ..., 2) ..., "
        "or 3) ...)."),
    "ap": (
        "AP Stylebook: no comma before the conjunction in a simple series ('the flag is red, white "
        "and blue'); use one when an element of the series contains a conjunction or when the "
        "series is made up of complex phrases. Here no item adjacent to the final conjunction "
        "contains its own. Choose the version without the comma unless the items are long complex "
        "phrases or the last two could be read as one; then KEEP."),
    "default": (
        "{t} omits the comma before 'and'/'or' in a simple series. Choose the version without it "
        "unless the last two items could be misread as one, or the conjunction joins two "
        "independent clauses; then KEEP."),
}


@dataclass
class Series:
    start: int          # absolute offsets of the matched series
    end: int
    text: str
    edit: Edit          # the one-character change that would apply the guide
    candidate: str      # the series as it would read after the change


def _line_col(text: str, pos: int) -> tuple[int, int]:
    return text.count("\n", 0, pos) + 1, pos - (text.rfind("\n", 0, pos) + 1) + 1


def _regions(text: str) -> list[tuple[int, int]]:
    """Prose regions for series detection: code, links, URLs, HTML tags and
    front matter are skipped, but an HTML entity is text (a series can
    contain one)."""
    spans = [(s, e) for s, e in protected_spans(text) if not _HTML_ENTITY.fullmatch(text[s:e])]
    regions, cursor = [], 0
    for s, e in spans:
        if s > cursor:
            regions.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < len(text):
        regions.append((cursor, len(text)))
    return regions


def find_series(text: str, guide: StyleGuide) -> list[Series]:
    """Every series the guide has an opinion about, with its minimal edit."""
    if guide.serial_comma not in ("require", "omit"):
        return []
    rx = SERIES_MISSING if guide.serial_comma == "require" else SERIES_PRESENT
    out: list[Series] = []
    for rs, re_ in _regions(text):
        for m in rx.finditer(text, rs, re_):
            raw = m.group(0)
            if guide.serial_comma == "require":
                c = list(_LAST_CONJ_NO_COMMA.finditer(raw))
                if not c:
                    continue
                pos = m.start() + c[-1].end(1)
                line, col = _line_col(text, pos)
                edit = Edit(line, col, col - 1, "", ",", "style")          # insertion
                cand = raw[:c[-1].end(1)] + "," + raw[c[-1].end(1):]
            else:
                c = list(_LAST_CONJ_COMMA.finditer(raw))
                if not c:
                    continue
                pos = m.start() + c[-1].start()
                line, col = _line_col(text, pos)
                edit = Edit(line, col, col, ",", "", "style")                # deletion
                cand = raw[:c[-1].start()] + raw[c[-1].start() + 1:]
            out.append(Series(m.start(), m.end(), raw, edit, cand))
    return out


def series_items(text: str, guide: StyleGuide, next_id: int = 1) -> tuple[list[Item], dict[int, Edit]]:
    """Adjudication items for every series, and the edit each decision applies."""
    items, edits = [], {}
    for sr in find_series(text, guide):
        built = candidate(f"{guide.title}.SerialComma", sr.text, guide)
        if built is None:                 # the guide settles it mechanically; nothing to ask
            continue
        rule = built[1]
        line, col = _line_col(text, sr.start)
        items.append(Item(next_id, sr.text, (sr.candidate, "KEEP"), rule,
                          sentence_context(text, sr.start, sr.end), line, col,
                          col + (sr.end - sr.start) - 1, source="style"))
        edits[next_id] = sr.edit
        next_id += 1
    return items, edits


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
                    "unintentional'), if the words after the conjunction belong to the item "
                    "before it ('bread and butter'), or if the conjunction joins two clauses "
                    "rather than list items.")
        if guide.serial_comma == "omit":
            m = _SERIAL_PRESENT.match(match)
            if not m:
                return None
            # The guide's mechanical case: a compound item immediately before
            # the final conjunction ("toast and marmalade, and tea") keeps the
            # comma. No judgement needed; leave it and ask nothing.
            penultimate = m.group(1).rsplit(", ", 1)[-1]
            if re.search(r"\b(?:and|or)\b", penultimate):
                return None
            return (m.group(1) + m.group(2), OMIT_RULES.get(guide.name, OMIT_RULES["default"]).format(t=t))
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
