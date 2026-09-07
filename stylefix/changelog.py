"""Plain-text change log: one line per edit, for --changes and for callers."""

from __future__ import annotations

from collections import defaultdict

from .adjudicate import Decision
from .apply import Edit, match_case
from .conventions import Stats
from .vale_runner import Alert


def _context(text: str, edit: Edit, width: int = 28) -> str:
    lines = text.split("\n")
    line = lines[edit.line - 1] if edit.line - 1 < len(lines) else ""
    s, e = edit.start - 1, edit.end
    left = line[max(0, s - width):s]
    right = line[e:e + width]
    return f"{'…' if s > width else ''}{left}[{line[s:e]}]{right}{'…' if len(line) > e + width else ''}"


def render(*, text: str, target: str, applied: list[Edit], decisions: list[Decision],
           stats: Stats, skipped: list[Edit] | None = None,
           review: list[Alert] | None = None) -> str:
    """Every change, grouped: word edits in document order, then punctuation
    counts, then adjudications that were kept or left undecided."""
    by_pos = {(d.item.line, d.item.start): d for d in decisions}
    out = [f"stylefix changes (target {target.upper()}): {len(applied)} word edit(s)"]
    for e in sorted(applied, key=lambda e: (e.line, e.start)):
        d = by_pos.get((e.line, e.start))
        how = "auto"
        if e.source == "adjudicated" and d:
            how = f"model {d.confidence:.2f}: {d.reason}"
        elif e.source == "adjudicated":
            how = "model"
        out.append(f"  L{e.line:<4} {e.original} -> {match_case(e.original, e.replacement):<14} {how}")
        out.append(f"        {_context(text, e)}")
    kept = [d for d in decisions if d.choice == "KEEP"
            or (d.choice and d.choice.lower() == d.item.word.lower())]
    if kept:
        out.append(f"kept after adjudication: {len(kept)}")
        for d in kept:
            out.append(f"  L{d.item.line:<4} {d.item.word:<20} {d.confidence:.2f}: {d.reason}")
    undecided = [d for d in decisions if d.choice is None]
    if undecided:
        out.append(f"undecided (left as is, see report): {len(undecided)}")
        for d in undecided:
            out.append(f"  L{d.item.line:<4} {d.item.word:<20} {d.reason}")
    if skipped:
        out.append(f"skipped (text moved): {len(skipped)}")
    punct = stats.as_dict()
    if punct:
        out.append("punctuation: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in punct.items()))
    if review:
        out.append(f"for review (not changed): {len(review)}")
        by_check: dict[str, list[Alert]] = defaultdict(list)
        for a in review:
            by_check[a.check].append(a)
        for check, items in sorted(by_check.items()):
            out.append(f"  {check}")
            for a in items:
                out.append(f"    L{a.line:<4} {a.message}")
    return "\n".join(out) + "\n"
