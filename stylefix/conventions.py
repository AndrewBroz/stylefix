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

# While quotes are resolved each protected span becomes one sentinel character of its kind.
_WORD_SPAN = "\ue000"      # inline code, wikilinks/embeds, #tags, inline maths, entities, link targets, URLs
_BOUNDARY_SPAN = "\ue001"  # front matter, fences, block maths, %% comments, HTML tags/comments/autolinks, callouts
_SENTINELS = _WORD_SPAN + _BOUNDARY_SPAN
_CLOSE_AFTER_BOUNDARY = set(".,;:!?)]}—–\"'”’")
_OPEN_BEFORE = set(" \t\n([{—–-/")


def straighten_apostrophes(s: str, stats: Stats) -> str:
    def rep(m):
        stats.apostrophes += 1
        return "’"
    s = re.sub(r"(?<=[\w\ue000])'(?=\w)", rep, s)    # don't, it's, o'clock, [[Note]]'s
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

    def after_boundary(i: int) -> bool:
        # After a boundary (a tag, a fence, front matter, or a line break right after
        # any span) a quote opens unless what follows ends a phrase.
        nxt = s[i + 1] if i + 1 < len(s) else ""
        return bool(nxt) and not nxt.isspace() and nxt not in _CLOSE_AFTER_BOUNDARY

    def opens(i: int) -> bool:
        if i == 0:
            return True
        prev = s[i - 1]
        if prev == _BOUNDARY_SPAN or (prev == "\n" and i > 1 and s[i - 2] in _SENTINELS):
            return after_boundary(i)
        if prev == _WORD_SPAN:
            # As after a word: closing (an apostrophe was already curled), except that a
            # double quote run into a following word opens, as in [[A]]"Hello".
            return s[i] == '"' and i + 1 < len(s) and s[i + 1].isalnum()
        return prev in _OPEN_BEFORE

    for i, ch in enumerate(s):
        if ch == '"':
            stats.quotes += 1
            out.append("“" if opens(i) else "”")
        elif ch == "'":
            stats.quotes += 1
            out.append("‘" if opens(i) else "’")
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
                           and not (i + 1 < len(s) and s[i + 1].isalnum() and i > 0
                                    and (s[i - 1].isalnum() or s[i - 1] == _WORD_SPAN))):
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

# A parenthetical dash: "--", an em dash, or a spaced en dash, with the
# blanks around it on its own line. A newline is never consumed: a dash at a
# line end or start is normalised in place and both lines stay, because the
# next line may be a callout, a fence, a heading or a table row. Digit-hugged
# en dashes are ranges and are left alone; "---" is a rule or front-matter fence.
_DASH = re.compile(r"(?<![-\d–])([ \t]*)(?:(?<!-)--(?!-)|—|(?<=\s)–(?=\s))([ \t]*)(?![-\d–])")


# A GFM table delimiter row, and the list or quote marker (with its space) at a line start.
_DELIMITER_ROW = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$")
_LINE_MARKER = re.compile(r"^[ \t]*(?:>[ \t]?)*(?:(?:[-*+]|\d+[.)])[ \t]+)?")


def parenthetical_dashes(s: str, style: str, stats: Stats) -> str:
    """Per line: a table delimiter row is left alone, and a list or quote
    marker with its space is kept, the rule seeing only what follows it."""
    out = []
    for line in s.splitlines(keepends=True):
        if _DELIMITER_ROW.match(line):
            out.append(line)
            continue
        if "|" in line:
            out.append(_table_row_dashes(line, style, stats))
            continue
        cut = _LINE_MARKER.match(line).end()
        out.append(line[:cut] + _parenthetical_dashes(line[cut:], style, stats))
    return "".join(out)


_CELL_PLACEHOLDER = re.compile(r"^\s*(?:--|—|–)\s*$")


def _table_row_dashes(line: str, style: str, stats: Stats) -> str:
    """A row is split at its pipes so a pipe is never mistaken for a word:
    a cell holding only a dash is a placeholder and stays as written; the
    text of any other cell gets the guide's dashes, with the spacing against
    the pipes kept."""
    body = line.rstrip("\n")
    cells = body.split("|")
    for i, cell in enumerate(cells):
        if not cell.strip() or _CELL_PLACEHOLDER.match(cell):
            continue
        lead = cell[:len(cell) - len(cell.lstrip())]
        trail = cell[len(cell.rstrip()):]
        cells[i] = lead + _parenthetical_dashes(cell.strip(), style, stats) + trail
    return "|".join(cells) + line[len(body):]


def _parenthetical_dashes(s: str, style: str, stats: Stats) -> str:
    """style: 'em' unspaced em dash; 'em-spaced' spaced em dash; 'en-spaced'.
    The guide's spacing applies within the line: at a line start the
    indentation is kept and no space is added before the dash; at a line end
    no space is left after it."""
    want = {"em": "—", "em-spaced": " — ", "en-spaced": " – "}[style]

    def rep(m):
        out = want
        lead = ""
        if m.start() == 0 or s[m.start() - 1] == "\n":
            lead, out = m.group(1), out.lstrip()
        if m.end() == len(s) or s[m.end()] == "\n":
            out = out.rstrip()
        out = lead + out
        if m.group(0) != out:
            stats.dashes += 1
        return out
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
    if any(c in text for c in _SENTINELS):
        return map_prose(text, fn), stats
    masked, held, cursor = [], [], 0
    for st, en in protected_spans(text):
        span = text[st:en]
        masked.append(text[cursor:st])
        masked.append(_BOUNDARY_SPAN if _is_boundary(span) else _WORD_SPAN)
        held.append(span)
        cursor = en
    masked.append(text[cursor:])
    out = fn("".join(masked))
    parts = iter(held)
    return re.sub(f"[{_SENTINELS}]", lambda m: next(parts), out), stats


def _is_boundary(span: str) -> bool:
    """Front matter, fences, block maths, %% comments, HTML tags, comments and
    autolinks, and callout markers mark a boundary; anything else reads as a word."""
    return "\n" in span or span.endswith(">") or span.lstrip().startswith((">", "%%", "$$"))
