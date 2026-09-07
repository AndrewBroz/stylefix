"""Abbreviation forms the style guides rule on as a class: periods in
two-letter country abbreviations (US / U.S.), degrees (PhD / Ph.D.), times
(10 a.m. / 10am), and the Latin tags (e.g., i.e., etc., vs.).

Position-independent, so deterministic, with one exception: when periods
are dropped, a "U.S." followed by a capitalised word may be the end of a
sentence ("in the U.S. The ...") or a name ("U.S. Policy"). Those go to the
adjudicator with the two readings as options."""

from __future__ import annotations

import re
from dataclasses import dataclass

from adjudicate import Edit, Item, prose_regions, sentence_context

# family -> the surface forms that mean the same thing
CAPS = {
    "US": ["U.S.", "U. S.", "US"],
    "UK": ["U.K.", "U. K.", "UK"],
    "UN": ["U.N.", "U. N.", "UN"],
    "USA": ["U.S.A.", "USA"],
    "PhD": ["Ph.D.", "Ph. D.", "PhD", "PHD"],
}
_TIME = re.compile(r"(?<=\d)\s?([aApP])\.?[mM]\.?(?![A-Za-z])")
_VS = re.compile(r"\bvs\.?(?=[\s,;:)])")
_EG = re.compile(r"\b[eE]\.?[gG]\.(?=[\s,;:)])|\beg(?=[\s,])")
_IE = re.compile(r"\b[iI]\.?[eE]\.(?=[\s,;:)])|\bie(?=[\s,])")
_ETC = re.compile(r"\betc\.?(?![A-Za-z])")


@dataclass(frozen=True)
class Abbreviations:
    """A guide's canonical forms. None = leave as written."""
    caps_periods: bool | None      # US -> U.S. (True) or U.S. -> US (False)
    phd: str | None                # "PhD" | "Ph.D."
    time: str | None               # "a.m." (spaced) | "am" (closed, Guardian)
    vs: str | None                 # "vs." | "vs" | "v"
    latin_periods: bool | None     # e.g., i.e., etc. (True) or eg, ie, etc (False)


PROFILES = {
    "chicago": Abbreviations(False, "PhD", "a.m.", "vs.", True),
    "gpo": Abbreviations(True, "Ph.D.", "a.m.", "vs.", True),
    "ap": Abbreviations(True, "Ph.D.", "a.m.", "vs.", True),
    "apa": Abbreviations(True, "PhD", "a.m.", "vs.", True),
    "oxford": Abbreviations(False, "PhD", "a.m.", "vs", True),
    "guardian": Abbreviations(False, "PhD", "am", "v", False),
    "none": Abbreviations(None, None, None, None, None),
}

SENTENCE_END_RULE = ("The style guide writes this abbreviation without periods. Here it is followed by a "
                     "capitalised word, so it is either the last word of its sentence (then the sentence "
                     "still needs its period: choose the form ending in a period) or part of a name or "
                     "the start of a title ('U.S. Policy': choose the bare form). KEEP only if neither.")


def _line_col(text: str, pos: int) -> tuple[int, int]:
    return text.count("\n", 0, pos) + 1, pos - (text.rfind("\n", 0, pos) + 1) + 1


def _edit(text: str, start: int, end: int, replacement: str) -> Edit:
    line, col = _line_col(text, start)
    return Edit(line, col, col + (end - start) - 1, text[start:end], replacement, "abbreviations")


def plan(text: str, guide: str, next_id: int = 1) -> tuple[list[Edit], list[Item]]:
    """Deterministic edits plus the sentence-end ambiguities as items."""
    prof = PROFILES.get(guide, PROFILES["none"])
    edits: list[Edit] = []
    items: list[Item] = []
    for rs, re_ in prose_regions(text):
        region = text[rs:re_]
        # --- two-letter country abbreviations and PhD
        for family, forms in CAPS.items():
            want_periods = prof.phd is not None and family == "PhD" and "." in prof.phd \
                if family == "PhD" else prof.caps_periods
            if family == "PhD" and prof.phd is None:
                continue
            if family != "PhD" and prof.caps_periods is None:
                continue
            canonical = prof.phd if family == "PhD" else (forms[0] if want_periods else forms[-1])
            alts = "|".join(re.escape(f) for f in sorted(forms, key=len, reverse=True))
            for m in re.finditer(rf"(?<![A-Za-z.])(?:{alts})(?![A-Za-z])", region):
                form = m.group(0)
                s, e = rs + m.start(), rs + m.end()
                after = region[m.end():m.end() + 2]
                if "." in canonical:
                    # US -> U.S.; a following sentence period is absorbed
                    if form == canonical:
                        continue
                    if after.startswith(".") and not after.startswith(".."):
                        e += 1
                    edits.append(_edit(text, s, e, canonical))
                else:
                    if form == canonical or "." not in form:
                        continue
                    following = region[m.end():m.end() + 3]
                    if re.match(r"\s*$", following) or re.match(r"\n", following):
                        edits.append(_edit(text, s, e, canonical + "."))       # paragraph end
                    elif re.match(r"\s+[A-Z“\"(]", following):
                        items.append(Item(next_id, form, (canonical + ".", canonical, "KEEP"),
                                          SENTENCE_END_RULE, sentence_context(text, s, e),
                                          *_line_col(text, s), _line_col(text, s)[1] + (e - s) - 1,
                                          source="abbreviation"))
                        next_id += 1
                    else:
                        edits.append(_edit(text, s, e, canonical))
        # --- times
        if prof.time:
            for m in _TIME.finditer(region):
                letter = m.group(1).lower()
                want = (" " + letter + ".m.") if prof.time == "a.m." else (letter + "m")
                if m.group(0) != want:
                    edits.append(_edit(text, rs + m.start(), rs + m.end(), want))
        # --- vs
        if prof.vs:
            for m in _VS.finditer(region):
                if m.group(0) != prof.vs:
                    edits.append(_edit(text, rs + m.start(), rs + m.end(), prof.vs))
        # --- e.g., i.e., etc.
        if prof.latin_periods is not None:
            for rx, with_, without in ((_EG, "e.g.", "eg"), (_IE, "i.e.", "ie"), (_ETC, "etc.", "etc")):
                want = with_ if prof.latin_periods else without
                for m in rx.finditer(region):
                    if m.group(0) != want:
                        e = rs + m.end()
                        if want.endswith(".") and text[e:e + 1] == "." and text[e:e + 2] != "..":
                            e += 1                              # "etc.." never
                        edits.append(_edit(text, rs + m.start(), e, want))
    return edits, items
