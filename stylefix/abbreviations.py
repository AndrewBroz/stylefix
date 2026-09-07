"""Abbreviation forms the style guides rule on as a class.

Two general rules, from the guides themselves:

- Chicago 10.4 (and Oxford, Guardian): an abbreviation in full capitals
  takes no periods, whether two letters or more (US, UK, EU, NATO, PhD,
  MA, DC). Applied generally: every period-group of capitals is closed up.
  The one hazard is personal initials ("J.K. Rowling"), which look the
  same; a group followed by a capitalised word is therefore adjudicated,
  as is the sentence-end case ("in the U.S. The ...").
- AP "abbreviations and acronyms" (and GPO): periods in most two-letter
  abbreviations (U.S., U.N., U.K., B.A., B.C.), with named exceptions (AP,
  GI, ID, EU); none in longer ones (FBI, NATO, USA). AP applies "most" to
  countries, places, degrees and eras, not to AI, IT, PR or TV, so the keep
  rule is applied by category. APA keeps U.S. but writes degrees without
  periods (PhD).

Also: clock times (10 a.m. / 10am), vs., and the Latin tags e.g., i.e.,
etc. And the noun rule of GPO and APA: "U.S." only as an adjective; the
noun is "the United States". That one is a warning by default and an
enforcement on request (--abbreviation-nouns enforce), decided per
occurrence because it is a part-of-speech question."""

from __future__ import annotations

import re
from dataclasses import dataclass

from adjudicate import Edit, Item, prose_regions, sentence_context

# Period-groups of capitals, allowing a lowercase letter after a capital
# (Ph.D., B.Sc., D.Phil.), two or more parts.
_GROUP = re.compile(r"(?<![A-Za-z.])(?:[A-Z][a-z]?\.\s?){2,}(?<=\.)(?![A-Za-z])")
# Categories AP and GPO give periods to.
COUNTRIES = {"US": "U.S.", "UK": "U.K.", "UN": "U.N.", "DC": "D.C."}
DEGREES = {"BA": "B.A.", "MA": "M.A.", "PhD": "Ph.D.", "MD": "M.D.", "JD": "J.D.", "BS": "B.S.",
           "MS": "M.S.", "BSc": "B.Sc.", "MSc": "M.Sc.", "LLB": "LL.B.", "LLM": "LL.M.",
           "DPhil": "D.Phil."}
ERAS = {"BC": "B.C.", "AD": "A.D."}
KEEP_EXCEPTIONS = {"EU", "AP", "GI", "ID", "USA", "OK"}          # AP's named exceptions
KNOWN = set(COUNTRIES) | set(DEGREES) | set(ERAS) | KEEP_EXCEPTIONS | {
    "NY", "LA", "UAE", "USSR", "NATO", "FBI", "CIA", "NASA", "CEO", "VP", "CE", "BCE", "NYC"}

_TIME = re.compile(r"(?<=\d)\s?([aApP])\.?[mM]\.?(?![A-Za-z])")
_VS = re.compile(r"\bvs\.?(?=[\s,;:)])")
_EG = re.compile(r"\b[eE]\.?[gG]\.(?=[\s,;:)])|\beg(?=[\s,])")
_IE = re.compile(r"\b[iI]\.?[eE]\.(?=[\s,;:)])|\bie(?=[\s,])")
_ETC = re.compile(r"\betc\.?(?![A-Za-z])")
_NOUN_US = re.compile(r"\b[Tt]he (U\.S\.|US)(?![A-Za-z])")
# "the US" followed by something that cannot be a modified noun: a verb,
# a preposition, a conjunction, or punctuation. Used for the warning count.
_NOUN_TAIL = re.compile(r"\s+(?:and|or|is|has|have|had|will|would|should|could|can|must|may|might|"
                        r"to|in|on|at|by|for|with|from|as|than|that|which|who|does|did|do|was|were|"
                        r"are|be|also|still|now|then|already|itself|alone|too)\b|[.,;:!?)]")


@dataclass(frozen=True)
class Abbreviations:
    caps: str | None               # "drop" (Chicago rule) | "keep" (AP/GPO categories) | None
    degrees_periods: bool | None   # under keep: Ph.D. (True) or PhD (False)
    time: str | None               # "a.m." | "am"
    vs: str | None                 # "vs." | "vs" | "v"
    latin_periods: bool | None
    noun_rule: bool = False        # guide says "U.S." is an adjective only


PROFILES = {
    "chicago": Abbreviations("drop", None, "a.m.", "vs.", True),
    "gpo": Abbreviations("keep", True, "a.m.", "vs.", True, noun_rule=True),
    "ap": Abbreviations("keep", True, "a.m.", "vs.", True),
    "apa": Abbreviations("keep", False, "a.m.", "vs.", True, noun_rule=True),
    "oxford": Abbreviations("drop", None, "a.m.", "vs", True),
    "guardian": Abbreviations("drop", None, "am", "v", False),
    "none": Abbreviations(None, None, None, None, None),
}

DROP_RULE = ("The style guide writes abbreviations in capitals without periods. This one is followed "
             "by a capitalised word, so it is one of: the last word of its sentence, part of a name "
             "or title ('U.S. Treasury'), or a person's initials ('J.K. Rowling'). The readings:\n"
             "  A (sentence ends here): {a}\n  B (name or title continues): {b}\n"
             "Choose '{end}' for A, '{bare}' for B. KEEP if these are a person's initials, which keep "
             "their periods.")
NOUN_RULE = ("{guide} uses '{abbr}' only as an adjective ('{abbr} policy', '{abbr} exports') and writes "
             "the noun out: 'the United States'. Here it follows 'the'. Choose 'United States' if the "
             "abbreviation stands alone as a noun (subject or object: 'the US has', 'in the US', "
             "'the US and its allies'). Choose '{abbr}' if it modifies a following noun ('the US "
             "economy'). KEEP only if neither.")


def _line_col(text: str, pos: int) -> tuple[int, int]:
    return text.count("\n", 0, pos) + 1, pos - (text.rfind("\n", 0, pos) + 1) + 1


def _edit(text: str, start: int, end: int, replacement: str) -> Edit:
    line, col = _line_col(text, start)
    return Edit(line, col, col + (end - start) - 1, text[start:end], replacement, "abbreviations")


def _item(text: str, s: int, e: int, options: tuple[str, ...], rule: str, next_id: int) -> Item:
    line, col = _line_col(text, s)
    return Item(next_id, text[s:e], options, rule, sentence_context(text, s, e),
                line, col, col + (e - s) - 1, source="abbreviation")


def bare(group: str) -> str:
    return group.replace(".", "").replace(" ", "")


def plan(text: str, guide: str, nouns: str = "default", next_id: int = 1
         ) -> tuple[list[Edit], list[Item], list[tuple[int, str]]]:
    """Deterministic edits, adjudication items, and noun-rule warnings
    (line, phrase). `nouns`: default (warn if the guide has the rule),
    warn, enforce, off."""
    prof = PROFILES.get(guide, PROFILES["none"])
    noun_mode = nouns if nouns != "default" else ("warn" if prof.noun_rule else "off")
    edits: list[Edit] = []
    items: list[Item] = []
    warnings: list[tuple[int, str]] = []
    claimed: set[int] = set()          # start offsets already handled by a noun item

    for rs, re_ in prose_regions(text):
        region = text[rs:re_]

        # --- the noun rule: "the U.S." / "the US"
        if prof.noun_rule and noun_mode != "off":
            for m in _NOUN_US.finditer(region):
                s, e = rs + m.start(1), rs + m.end(1)
                tail = region[m.end():m.end() + 12]
                if noun_mode == "enforce":
                    canonical = COUNTRIES["US"] if prof.caps == "keep" else "US"
                    rule = NOUN_RULE.format(guide={"gpo": "GPO", "apa": "APA"}.get(guide, "The guide"),
                                            abbr=canonical)
                    items.append(_item(text, s, e, ("United States", canonical, "KEEP"), rule, next_id))
                    next_id += 1
                    claimed.add(s)
                elif _NOUN_TAIL.match(tail):
                    warnings.append((_line_col(text, s)[0], text[s - 4:e + min(12, len(tail))].strip()))

        # --- capitals: drop (general) or keep (by category)
        if prof.caps == "drop":
            for m in _GROUP.finditer(region):
                s, e = rs + m.start(), rs + m.end()
                if s in claimed:
                    continue
                group = m.group(0)
                canonical = bare(group)
                following = region[m.end():m.end() + 3]
                if re.match(r"\s*$", following) or following.startswith("\n"):
                    edits.append(_edit(text, s, e, canonical + "."))       # paragraph end
                elif re.match(r"\s+[A-Z“\"(]", following):
                    lo, hi = max(rs, s - 45), min(re_, e + 45)
                    before, after = text[lo:s], text[e:hi]
                    rule = DROP_RULE.format(a="…" + before + canonical + "." + after + "…",
                                            b="…" + before + canonical + after + "…",
                                            end=canonical + ".", bare=canonical)
                    items.append(_item(text, s, e, (canonical + ".", canonical, "KEEP"), rule, next_id))
                    next_id += 1
                else:
                    edits.append(_edit(text, s, e, canonical))
        elif prof.caps == "keep":
            table = dict(COUNTRIES) | dict(ERAS)
            if prof.degrees_periods:
                table |= DEGREES
            else:
                # APA: degrees without periods; U.S. with.
                for k, v in DEGREES.items():
                    table[v] = k
            alts = "|".join(re.escape(k) for k in sorted(table, key=len, reverse=True))
            for m in re.finditer(rf"(?<![A-Za-z.])(?:{alts})(?![A-Za-z])", region):
                s, e = rs + m.start(), rs + m.end()
                if s in claimed:
                    continue
                want = table[m.group(0)]
                if want.endswith(".") and text[e:e + 1] == "." and text[e:e + 2] != "..":
                    e += 1                                               # absorb the sentence period
                edits.append(_edit(text, s, e, want))

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
                            e += 1
                        edits.append(_edit(text, rs + m.start(), e, want))
    return edits, items, warnings
