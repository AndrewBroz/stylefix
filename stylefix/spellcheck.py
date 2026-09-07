"""Review-only check: words that look like the other variety's spelling.

Replaces Vale's bundled-dictionary spelling rule. A word is flagged only
when it carries a variety marker (-our, -re, -ise, -yse, -ll-, ae/oe for
UK; -or, -er, -ize, -yze for US), is in the other variety's dictionary,
and is not in the target's. Words in neither dictionary are not our
business; typos are not flagged.
"""

from __future__ import annotations

import re

from . import dictionary
from .conventions import prose_regions
from .patterns import LL_NEVER
from .vale_runner import Alert

UK_MARKERS = re.compile(r"(our|ours|oured|ouring|re|res|red|ring|ise|ises|ised|ising|isation|"
                        r"yse|ysed|ysing|lled|lling|ller|ae\w*|oe\w*|ence|ogue)$")
US_MARKERS = re.compile(r"(or|ors|ored|oring|er|ers|ered|ering|ize|izes|ized|izing|ization|"
                        r"yze|yzed|yzing|ense|og)$")
# US single-l inflections (traveled, modeling) of verbs that UK doubles: the
# base list lacks inflected forms, so test the stem instead.
US_L_FORM = re.compile(r"^([a-z]*[^aeiou][aeiou]l)(ed|ing|er|ers)$")
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*[A-Za-z]|[A-Za-z]")


_INFLECTIONS = ("ings", "ing", "ed", "es", "s", "d")


def _other_variety(word: str, target: str, other: str) -> bool:
    """True when the word, or its base form, is in the other variety's list
    and not in the target's."""
    forms = [word] + [word[:-len(x)] for x in _INFLECTIONS if word.endswith(x) and len(word) > len(x) + 2]
    forms += [word[:-len(x)] + "e" for x in ("d", "s") if word.endswith(x)]
    for f in forms:
        if dictionary.known(f, target):
            return False
        if dictionary.known(f, other):
            return True
    return False


def review_spellings(text: str, target: str, accept: set[str] | None = None) -> list[Alert]:
    other = "uk" if target == "us" else "us"
    markers = UK_MARKERS if target == "us" else US_MARKERS
    accept = {w.lower() for w in (accept or ())}
    out: list[Alert] = []
    seen: set[str] = set()
    for s, e in prose_regions(text):
        for m in WORD.finditer(text, s, e):
            w = m.group(0)
            lw = w.lower()
            if lw in seen or lw in accept or "'" in lw or "’" in lw or "-" in lw:
                continue
            lm = US_L_FORM.match(lw) if target == "uk" else None
            if lm:
                stem = lm.group(1)
                if stem in LL_NEVER or not dictionary.known(stem, "uk") or dictionary.known(lw, "uk"):
                    continue
            elif not markers.search(lw):
                continue
            elif not _other_variety(lw, target, other):
                continue
            seen.add(lw)
            line = text.count("\n", 0, m.start()) + 1
            col = m.start() - (text.rfind("\n", 0, m.start()) + 1) + 1
            out.append(Alert(line, col, col + len(w) - 1, f"Spelling.{target.upper()}Variant", w,
                             f"'{w}' looks like a {other.upper()} spelling.", "suggestion", "", []))
    return out
