"""Library API: regularize a Markdown string to a variety and style guide."""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

from adjudicate import prose_regions, protected_spans, Annotation, Change, ReviewItem, Skipped, derive_changes
from adjudicate.core import Decision
from adjudicate.llm import Endpoint

from . import abbreviations, candidates, patterns, spellcheck, styleguides, styleitems, varcon
from .adjudicate import Cache, Item, adjudicate
from .apply import Edit, apply_edits, match_case, to_offsets
from .context import at_sentence_start, inside_quotes, sentence_context
from .conventions import Stats, normalize
from .vale_runner import Alert, ValeNotFound, run_vale_text

FRONT_MATTER = re.compile(r"\A\ufeff?---\n.*?\n---\n", re.S)  # an optional byte-order mark first


@dataclass(frozen=True)
class Detection:
    target: str | None
    uk: int
    us: int


_DETECT_WORD = re.compile(r"[a-z]+(?:[’'][a-z]+)?")


@functools.lru_cache(maxsize=1)
def _variety_words() -> tuple[frozenset[str], frozenset[str]]:
    """Spellings VarCon gives to one variety and not the other."""
    uk, us = set(), set()
    for c in varcon.clusters():
        b, a = c.accepted("B"), c.accepted("A")
        uk |= b - a
        us |= a - b
    return frozenset(uk), frozenset(us)


def detect_variety(text: str, accept=()) -> Detection:
    """Which variety a text is written in, from words only one variety uses."""
    uk_words, us_words = _variety_words()
    skip = {w.lower() for w in accept}
    seen_uk, seen_us = set(), set()
    for s, e in prose_regions(text):
        for m in _DETECT_WORD.finditer(text, s, e):
            w = m.group(0)
            if w in skip or inside_quotes(text, m.start()):
                continue
            if w in uk_words:
                seen_uk.add(w)
            elif w in us_words:
                seen_us.add(w)
    uk, us = len(seen_uk), len(seen_us)
    if uk >= 2 and uk >= 2 * us:
        return Detection("uk", uk, us)
    if us >= 2 and us >= 2 * uk:
        return Detection("us", uk, us)
    return Detection(None, uk, us)


def partition(text: str, alerts: list[Alert], target: str, guide: str,
              oxford: bool = False, adjudicate_style: bool = False):
    """Split Vale alerts into deterministic edits, adjudication items, and review.

    Style-guide alerts (serial comma, numerals) become items when a model is
    available to adjudicate them; otherwise they stay review alerts."""
    style = styleguides.get(guide)
    fm = FRONT_MATTER.match(text)
    fm_lines = text[:fm.end()].count("\n") if fm else 0
    edits: list[Edit] = []
    items: list[Item] = []
    review: list[Alert] = []
    next_id = 1
    # Table hits win over pattern hits on the same span.
    table_spans = {(a.line, a.start, a.end) for a in alerts if a.replacement}
    table_lines = {}
    for a in alerts:
        if a.replacement:
            table_lines.setdefault(a.line, []).append((a.start, a.end))
    protected = protected_spans(text)
    for a in alerts:
        if a.line <= fm_lines:
            continue  # never touch front matter
        s, e = to_offsets(text, Edit(a.line, a.start, a.end, a.match, "", ""))
        if any(s < pe and e > ps for ps, pe in protected):
            continue  # code, links, Obsidian syntax: never edited, never asked about
        rule = a.check.rsplit(".", 1)[-1]
        if rule in patterns.CHECK_FAMILY:
            if any(st <= a.start <= en or st <= a.end <= en for st, en in table_lines.get(a.line, [])):
                continue
            out = patterns.decide(a.match, patterns.CHECK_FAMILY[rule], target, oxford)
            if out.status in ("skip", "reject"):
                continue
            if out.status == "ask":
                items.append(Item(next_id, a.match, (match_case(a.match, out.candidate), "KEEP"),
                                  f"'{a.match}' looks like it takes the {target.upper()} ending "
                                  f"'{out.candidate[-4:]}', but neither spelling is in our dictionaries. "
                                  "Choose the rewritten form if this is an ordinary English word with "
                                  "that ending; KEEP if it is a name, a deliberate coinage, or not "
                                  "that suffix at all.",
                                  sentence_context(text, s, e), a.line, a.start, a.end,
                                  source="pattern"))
                next_id += 1
                continue
            # auto: treat exactly like a table replacement from here on
            a = Alert(a.line, a.start, a.end, a.check, a.match, a.message, a.severity,
                      "replace", [out.candidate])
        if a.replacement:
            capitalized = a.match[:1].isupper() and not a.match.isupper() \
                and not at_sentence_start(text, s)
            quoted = inside_quotes(text, s)
            if capitalized or quoted:
                why = ("Capitalised mid-sentence: may be a proper name or title."
                       if capitalized else "Inside a quotation: quoted text keeps its own spelling.")
                items.append(Item(next_id, a.match,
                                  (match_case(a.match, a.replacement), "KEEP"),
                                  why + " Otherwise use the target spelling.",
                                  sentence_context(text, s, e), a.line, a.start, a.end,
                                  source="capitalized" if capitalized else "quoted"))
                next_id += 1
            else:
                edits.append(Edit(a.line, a.start, a.end, a.match, a.replacement, a.check))
        elif adjudicate_style and a.check.rsplit(".", 1)[-1] == "Numbers":
            built = styleitems.candidate(a.check, a.match, style)
            if built is None:
                review.append(a)
                continue
            cand, rule = built
            items.append(Item(next_id, a.match, (cand, "KEEP"), rule,
                              sentence_context(text, s, e), a.line, a.start, a.end, source="style"))
            next_id += 1
        elif a.check.endswith(".Ambiguous"):
            cand = candidates.lookup(target, a.match, oxford)
            if cand is None:
                review.append(a)
                continue
            items.append(Item(next_id, a.match, cand.options, cand.rule,
                              sentence_context(text, s, e), a.line, a.start, a.end))
            next_id += 1
        else:
            review.append(a)
    return edits, items, review


TIERS = ("variety", "guide", "ambiguous", "numbers", "serial-comma", "abbreviations", "punctuation")
VALE_TIERS = frozenset(TIERS[:4])


def tier_of(check: str) -> str:
    rule = check.rsplit(".", 1)[-1]
    if rule == "Ambiguous":
        return "ambiguous"
    if rule == "Numbers":
        return "numbers"
    if check.startswith(("ToUS.", "ToUK.")):
        return "variety"
    return "guide"


@dataclass
class Options:
    target: str
    style: str | None = None
    oxford_ize: bool = False
    accept: list[str] | None = None
    abbreviation_nouns: str = "default"
    min_confidence: float = 0.7
    batch_size: int = 20
    parallel: int = 4
    verbose: bool = False
    skip: frozenset[str] = frozenset()
    require_vale: bool = True
    replay_cache: bool = False


@dataclass
class Result:
    text: str
    changes: list[Change]
    review: list[ReviewItem]
    skipped: list[Skipped]
    guide: str
    applied: list[Edit]
    rejected: list[Edit]
    decisions: list[Decision]
    review_alerts: list[Alert]        # exactly what the CLI's report and change log list for review
    stats: Stats
    unasked: int


def _annotations(applied: list[Edit], decisions: list[Decision],
                 model_used: bool, series_edits: dict | None = None) -> list[Annotation]:
    by_edit = {}
    for d in decisions:
        if d.replacement:
            e = (series_edits or {}).get(d.item.id)
            key = (e.original, e.replacement) if e else (d.item.word, d.replacement)
            by_edit.setdefault(key, d)
    out = []
    for e in applied:
        d = by_edit.get((e.original, e.replacement)) if e.source == "adjudicated" else None
        if d is not None:
            out.append(Annotation(e.original, e.replacement, d.item.source or "adjudicated",
                                  d.reason, "cache" if d.cached else ("model" if model_used else "rule"),
                                  d.confidence))
        else:
            out.append(Annotation(e.original, e.replacement, e.source,
                                  decided_by="model" if model_used and e.source == "adjudicated" else "rule"))
    return out


def fix(text: str, options: Options, endpoint: Endpoint | None, cache: Cache) -> Result:
    """Regularise text to options.target and the style guide; no I/O on the caller's files."""
    o = options
    guide = o.style or styleguides.DEFAULT_FOR[o.target]
    skipped: list[Skipped] = []
    alerts: list[Alert] = []
    if not VALE_TIERS <= o.skip:
        try:
            alerts = run_vale_text(text, o.target, guide, o.oxford_ize, o.accept)
        except ValeNotFound:
            if o.require_vale:
                raise
            skipped.append(Skipped("variety spelling, style-guide rules, ambiguous words and numerals",
                                   "Vale not found", "brew install vale"))
    alerts = [a for a in alerts if tier_of(a.check) not in o.skip]
    ep = endpoint
    asking = ep is not None or o.replay_cache
    edits, items, review = partition(text, alerts, o.target, guide, o.oxford_ize,
                                     adjudicate_style=asking)
    if "serial-comma" in o.skip:
        series, series_edits = [], {}
    else:
        series, series_edits = styleitems.series_items(text, styleguides.get(guide),
                                                       next_id=len(items) + 1)
    if asking:
        items += series
    else:
        for it in series:
            review.append(Alert(it.line, it.start, it.end, f"{styleguides.get(guide).title}.SerialComma",
                                it.word, f"{styleguides.get(guide).title}: check the comma before "
                                f"'and'/'or' in '{it.word[:60]}'.", "suggestion", "", []))
    if "abbreviations" in o.skip:
        ab_edits, ab_items, ab_warnings = [], [], []
    else:
        ab_edits, ab_items, ab_warnings = abbreviations.plan(text, guide, o.abbreviation_nouns,
                                                             next_id=len(items) + 1)
    edits += ab_edits
    title = styleguides.get(guide).title or "Style"
    if asking:
        items += ab_items
    else:
        for it in ab_items:
            review.append(Alert(it.line, it.start, it.end, f"{title}.Abbreviation", it.word,
                                f"'{it.word}': sentence end, name, or initials? Needs a model to decide.",
                                "suggestion", "", []))
    for line, phrase in ab_warnings:
        review.append(Alert(line, 1, 1, f"{title}.AbbreviationNoun", phrase,
                            f"'{phrase}': {title} writes the noun out as 'the United States' and keeps "
                            f"the abbreviation for adjectives. --abbreviation-nouns enforce applies it.",
                            "suggestion", "", []))
    decisions = adjudicate(ep, o.target, items, cache, o.batch_size, o.parallel, o.verbose)
    for d in decisions:
        if d.choice is not None and d.confidence < o.min_confidence:
            d.reason = f"low confidence ({d.confidence:.2f}): {d.reason}"
            d.choice = None
        # With no model, capitalised deterministic swaps are still applied.
        if d.choice is None and ep is None and not o.replay_cache and d.item.source == "capitalized":
            d.choice, d.reason = d.item.options[0], "applied without adjudication"
        rep = d.replacement
        if rep and d.item.id in series_edits:
            e = series_edits[d.item.id]
            edits.append(Edit(e.line, e.start, e.end, e.original, e.replacement, "adjudicated"))
        elif rep:
            edits.append(Edit(d.item.line, d.item.start, d.item.end, d.item.word, rep, "adjudicated"))

    new_text, rejected = apply_edits(text, edits)
    if "punctuation" in o.skip:
        stats = Stats()
    else:
        new_text, stats = normalize(new_text, o.target, guide)
    applied = [e for e in edits if e not in rejected]
    review += spellcheck.review_spellings(new_text, o.target, set(o.accept or ()))

    unasked = len(items) if ep is None and not o.replay_cache else 0
    review_items = [ReviewItem(a.line, "alert", a.message, a.check, "stylefix") for a in review]
    review_items += [ReviewItem(d.item.line, "undecided", f"'{d.item.word}': {d.reason}",
                                d.item.source, "stylefix") for d in decisions if d.choice is None]
    changes = derive_changes(text, new_text, _annotations(applied, decisions, ep is not None, series_edits), "punctuation")
    for c in changes:
        c.pass_ = "stylefix"
    return Result(new_text, changes, review_items, skipped, guide, applied, rejected,
                  decisions, review, stats, unasked)
