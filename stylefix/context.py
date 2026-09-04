"""Sentence context and position heuristics used by the adjudicator."""

from __future__ import annotations

import re

_SENT_END = re.compile(r"(?<=[.!?])\s+")


def paragraph_bounds(text: str, pos: int) -> tuple[int, int]:
    start = text.rfind("\n\n", 0, pos)
    start = 0 if start < 0 else start + 2
    end = text.find("\n\n", pos)
    end = len(text) if end < 0 else end
    return start, end


def sentence_context(text: str, start: int, end: int, radius: int = 1,
                     max_chars: int = 400) -> str:
    """The sentence containing [start, end) plus `radius` neighbours, with
    the target span marked as [[...]]."""
    ps, pe = paragraph_bounds(text, start)
    para = text[ps:pe]
    rel_s, rel_e = start - ps, end - ps
    pieces, cursor = [], 0
    for m in _SENT_END.finditer(para):
        pieces.append((cursor, m.start()))
        cursor = m.end()
    pieces.append((cursor, len(para)))
    idx = next((i for i, (a, b) in enumerate(pieces) if a <= rel_s < b), len(pieces) - 1)
    lo = pieces[max(0, idx - radius)][0]
    hi = pieces[min(len(pieces) - 1, idx + radius)][1]
    snippet = para[lo:rel_s] + "[[" + para[rel_s:rel_e] + "]]" + para[rel_e:hi]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if len(snippet) > max_chars:
        mark = snippet.find("[[")
        a = max(0, mark - max_chars // 2)
        snippet = ("…" if a else "") + snippet[a:a + max_chars] + "…"
    return snippet


_SENTENCE_START_PUNCT = set('.!?:"“‘\'([')


def at_sentence_start(text: str, pos: int) -> bool:
    """True when a capital at `pos` is explained by position, not by being a name."""
    line_start = text.rfind("\n", 0, pos) + 1
    before = text[line_start:pos].rstrip()
    if not before:
        return True
    # Markdown markers: headings, list bullets, numbered items, blockquotes.
    if re.fullmatch(r"(#{1,6}|[-*+]|\d+[.)]|>|\|)", before):
        return True
    return before[-1] in _SENTENCE_START_PUNCT


def inside_quotes(text: str, pos: int) -> bool:
    """Cheap check: an odd number of opening quotes precede `pos` in the paragraph."""
    ps, _ = paragraph_bounds(text, pos)
    seg = text[ps:pos]
    opens = seg.count("“") + seg.count("‘") + len(re.findall(r'(?:^|\s)["\']', seg))
    # `seg` ends where the word starts, so a quote at its very end is an opener.
    closes = seg.count("”") + seg.count("’") + len(re.findall(r'["\'](?=[\s.,;:!?)])', seg))
    return opens > closes
