"""Command-line entry point."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

from . import __version__, candidates, report
from .adjudicate import Cache, Item, adjudicate
from .apply import Edit, apply_edits, match_case, to_offsets
from .context import at_sentence_start, inside_quotes, sentence_context
from .conventions import normalize
from .llm import resolve_endpoint
from .vale_runner import Alert, ValeError, run_vale

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stylefix",
        description="Regularize a Markdown file to US or UK English and a style guide.")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, help="default: <input>.<target>.md")
    p.add_argument("-i", "--in-place", action="store_true", help="overwrite the input file")
    p.add_argument("--target", choices=["us", "uk"], required=True)
    p.add_argument("--style", choices=["chicago", "oxford", "none"],
                   help="default: chicago for us, oxford for uk")
    p.add_argument("--oxford-ize", action="store_true",
                   help="UK target keeps -ize spellings (Oxford)")
    p.add_argument("--llm", choices=["auto", "dgx", "ollama", "none"], default="auto",
                   help="which model endpoint adjudicates ambiguous words (default: auto)")
    p.add_argument("--model", help="model name at the endpoint")
    p.add_argument("--url", help="OpenAI-compatible base URL ending in /v1")
    p.add_argument("--think", action="store_true",
                   help="let a reasoning model think before answering (slower, more accurate)")
    p.add_argument("--timeout", type=float, default=120.0, help="seconds per model request")
    p.add_argument("--min-confidence", type=float, default=0.7)
    p.add_argument("--batch-size", type=int, default=20)
    p.add_argument("--parallel", type=int, default=4, help="concurrent model requests")
    p.add_argument("--accept", type=Path, help="file of words/phrases to leave alone, one per line")
    p.add_argument("--cache", type=Path, default=Path(".stylefix/cache.json"))
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--report", type=Path, help="default: <output>.report.md")
    p.add_argument("--no-report", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="print a diff, write nothing")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"stylefix {__version__}")
    return p


def partition(text: str, alerts: list[Alert], target: str, guide: str):
    """Split Vale alerts into deterministic edits, adjudication items, and review."""
    fm = FRONT_MATTER.match(text)
    fm_lines = text[:fm.end()].count("\n") if fm else 0
    edits: list[Edit] = []
    items: list[Item] = []
    review: list[Alert] = []
    next_id = 1
    for a in alerts:
        if a.line <= fm_lines:
            continue  # never touch front matter
        s, e = to_offsets(text, Edit(a.line, a.start, a.end, a.match, "", ""))
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
        elif a.check.endswith(".Ambiguous"):
            cand = candidates.lookup(target, a.match)
            if cand is None:
                review.append(a)
                continue
            items.append(Item(next_id, a.match, cand.options, cand.rule,
                              sentence_context(text, s, e), a.line, a.start, a.end))
            next_id += 1
        else:
            review.append(a)
    return edits, items, review


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.input.exists():
        print(f"stylefix: no such file: {args.input}", file=sys.stderr)
        return 2
    guide = args.style or ("chicago" if args.target == "us" else "oxford")
    output = args.input if args.in_place else (
        args.output or args.input.with_suffix(f".{args.target}{args.input.suffix or '.md'}"))
    report_path = args.report or output.with_suffix(output.suffix + ".report.md")
    text = args.input.read_text(encoding="utf-8")

    accept = [w.strip() for w in args.accept.read_text().splitlines() if w.strip()] if args.accept else None
    try:
        alerts = run_vale(args.input, args.target, guide, args.oxford_ize, accept)
    except ValeError as e:
        print(f"stylefix: {e}", file=sys.stderr)
        return 2
    edits, items, review = partition(text, alerts, args.target, guide)

    ep = resolve_endpoint(args.llm, args.model, args.url, think=args.think,
                          timeout=args.timeout)
    if items and ep is None:
        print(f"stylefix: no model endpoint available (--llm {args.llm}); "
              f"{len(items)} ambiguous word(s) will be listed for review", file=sys.stderr)
    cache = Cache(None if args.no_cache else args.cache)
    decisions = adjudicate(ep, args.target, items, cache, args.batch_size,
                           args.parallel, args.verbose)
    for d in decisions:
        if d.choice is not None and d.confidence < args.min_confidence:
            d.reason = f"low confidence ({d.confidence:.2f}): {d.reason}"
            d.choice = None
        # With no model, capitalised deterministic swaps are still applied.
        if d.choice is None and ep is None and d.item.source == "capitalized":
            d.choice, d.reason = d.item.options[0], "applied without adjudication"
        rep = d.replacement
        if rep:
            edits.append(Edit(d.item.line, d.item.start, d.item.end, d.item.word, rep, "adjudicated"))

    new_text, skipped = apply_edits(text, edits)
    new_text, stats = normalize(new_text, args.target, guide)
    applied = [e for e in edits if e not in skipped]

    if args.dry_run:
        sys.stdout.writelines(difflib.unified_diff(
            text.splitlines(keepends=True), new_text.splitlines(keepends=True),
            str(args.input), str(output)))
    else:
        output.write_text(new_text, encoding="utf-8")
    rep_md = report.render(source=str(args.input), output=str(output), target=args.target,
                           guide=guide, model=f"{ep.name}:{ep.model}" if ep else "none",
                           applied=applied, skipped=skipped, decisions=decisions,
                           review=review, stats=stats)
    if not args.no_report and not args.dry_run:
        report_path.write_text(rep_md, encoding="utf-8")
    undecided = sum(1 for d in decisions if d.choice is None)
    print(f"stylefix: {len(applied)} replacement(s), {len(decisions)} adjudicated "
          f"({undecided} undecided), {len(review)} alert(s) for review"
          + ("" if args.dry_run else f" -> {output}, report {report_path}"), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
