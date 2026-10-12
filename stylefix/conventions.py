"""Punctuation and date conventions that a Vale regex cannot express.

Runs only over prose regions of the Markdown: front matter, fenced code,
inline code, link destinations and URLs are left untouched.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MONTHS = ("January|February|March|April|May|June|July|August|September|"
          "October|November|December")

from adjudicate.context import map_prose, prose_regions, protected_spans  # noqa: F401


@dataclass
class Stats:
    quotes: int = 0
    apostrophes: int = 0
    dashes: int = 0
    ranges: int = 0
    dates: int = 0
    punctuation_moved: int = 0

    def as_dict(self) -> dict[str, int]:
        return {k: v for k, v in self.__dict__.items() if v}



# --- quotes ---------------------------------------------------------------

_WORD = "\ue000"       # stands for a protected span that behaves like a word
_OPENER = "\ue001"     # ... or like a line start / tag boundary (a quote after it opens)
_OPEN_BEFORE = set(" \t\n([{—–-/" + _OPENER)


def straighten_apostrophes(s: str, stats: Stats) -> str:
    def rep(m):
        stats.apostrophes += 1
        return "’"
    s = re.sub(r"(?<=\w)'(?=\w)", rep, s)            # don't, it's, o'clock
    s = re.sub(r"(?<=\w)'(?=\s|$|[.,;:!?)])(?![\"'])", lambda m: rep(m) if _plural_possessive(s, m) else m.group(0), s)
    s = re.sub(r"(?<![\w])'(?=\d\ds\b)", rep, s)       # '90s
    return s


def _plural_possessive(s: str, m: re.Match) -> bool:
    # "the Joneses' house" — apostrophe after an s that is not closing a quote.
    i = m.start()
    if i == 0 or s[i - 1] != "s":
        return False
    # If there's an unmatched opening single quote earlier in this paragraph, it's a close quote.
    para = s.rfind("\n\n", 0, i)
    seg = s[para + 1:i]
    opens = len(re.findall(r"(?:^|[\s(\[])'", seg)) + seg.count("‘")
    closes = len(re.findall(r"'(?=[\s.,;:!?)\]]|$)", seg)) + seg.count("’")
    return opens <= closes


def curl_straight_quotes(s: str, stats: Stats) -> str:
    out = []
    for i, ch in enumerate(s):
        if ch == '"':
            stats.quotes += 1
            out.append("“" if i == 0 or s[i - 1] in _OPEN_BEFORE else "”")
        elif ch == "'":
            stats.quotes += 1
            out.append("‘" if i == 0 or s[i - 1] in _OPEN_BEFORE else "’")
        else:
            out.append(ch)
    return "".join(out)


def set_primary_quotes(s: str, primary: str, stats: Stats, move_punct: bool) -> str:
    """Rewrite nesting so level 1 uses `primary` ("double" or "single")."""
    if primary == "double":
        pairs = [("“", "”"), ("‘", "’")]
    else:
        pairs = [("‘", "’"), ("“", "”")]
    out, stack = [], []   # stack of the *original* opening chars
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in "“‘" and not (ch == "‘" and i + 1 < len(s) and s[i + 1].isdigit()):
            stack.append(ch)
            o, _ = pairs[(len(stack) - 1) % 2]
            if o != ch:
                stats.quotes += 1
            out.append(o)
        elif ch == "”" or (ch == "’" and stack and stack[-1] == "‘"
                           and not (i + 1 < len(s) and s[i + 1].isalnum() and i > 0 and s[i - 1].isalnum())):
            if not stack:
                out.append(ch)
            else:
                depth = len(stack)
                stack.pop()
                _, c = pairs[(depth - 1) % 2]
                if c != ch:
                    stats.quotes += 1
                if move_punct and i + 1 < len(s) and s[i + 1] in ".," and (i == 0 or s[i - 1] not in ".,!?"):
                    out.append(s[i + 1]); out.append(c); i += 1
                    stats.punctuation_moved += 1
                else:
                    out.append(c)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


# --- dashes, ranges, dates --------------------------------------------------

# A parenthetical dash: "--", an em dash, or a spaced en dash, with any
# surrounding blanks (a single newline counts, so a dash at a line end is
# handled without crossing a paragraph break). Digit-hugged en dashes are
# ranges and are left alone; "---" is a rule or front-matter fence.
_DASH = re.compile(r"(?<![-\d–])(?:[ \t]|\n(?!\n))*(?:(?<!-)--(?!-)|—|(?<=\s)–(?=\s))(?:[ \t]|\n(?!\n))*(?![-\d–])")


def parenthetical_dashes(s: str, style: str, stats: Stats) -> str:
    """style: 'em' unspaced em dash; 'em-spaced' spaced em dash; 'en-spaced'."""
    want = {"em": "—", "em-spaced": " — ", "en-spaced": " – "}[style]

    def rep(m):
        if m.group(0) == want:
            return want
        stats.dashes += 1
        return want
    return _DASH.sub(rep, s)


def number_ranges(s: str, stats: Stats) -> str:
    def rep(m):
        stats.ranges += 1
        return f"{m.group(1)}–{m.group(2)}"
    return re.sub(r"(?<![\w\-–])(\d+)-(\d+)(?![\w\-–])", rep, s)


def dates_us(s: str, stats: Stats) -> str:
    def rep(m):
        stats.dates += 1
        return f"{m.group(2)} {int(m.group(1))}, {m.group(3)}"
    return re.sub(rf"\b(\d{{1,2}})(?:st|nd|rd|th)? ({MONTHS}),? (\d{{4}})\b", rep, s)


def dates_uk(s: str, stats: Stats) -> str:
    def rep(m):
        stats.dates += 1
        return f"{int(m.group(2))} {m.group(1)} {m.group(3)}"
    return re.sub(rf"\b({MONTHS}) (\d{{1,2}})(?:st|nd|rd|th)?, (\d{{4}})\b", rep, s)


# --- driver ----------------------------------------------------------------

def normalize(text: str, target: str, guide: str = "none") -> tuple[str, Stats]:
    from .styleguides import get
    g = get(guide)
    stats = Stats()
    primary = "double" if target == "us" else "single"
    move = g.punctuation_inside_quotes

    def fn(seg: str) -> str:
        seg = straighten_apostrophes(seg, stats)
        seg = curl_straight_quotes(seg, stats)
        seg = set_primary_quotes(seg, primary, stats, move_punct=move)
        if g.dash:
            seg = parenthetical_dashes(seg, g.dash, stats)
        seg = number_ranges(seg, stats)
        seg = dates_us(seg, stats) if target == "us" else dates_uk(seg, stats)
        return seg

    # Protected spans become one sentinel each, so a quote is judged by what really
    # surrounds it in the document and quotes pair up across constructs.
    if _WORD in text or _OPENER in text:
        return map_prose(text, fn), stats
    spans, masked, cursor = protected_spans(text), [], 0
    held = []
    for st, en in spans:
        masked.append(text[cursor:st])
        held.append(text[st:en])
        masked.append(_OPENER if held[-1][-1:].isspace() or held[-1][-1:] == ">" else _WORD)
        cursor = en
    masked.append(text[cursor:])
    out = fn("".join(masked))
    parts = iter(held)
    return re.sub(f"[{_WORD}{_OPENER}]", lambda m: next(parts), out), stats
