"""Command-line entry point."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from pathlib import Path

from . import __version__, abbreviations, candidates, changelog, patterns, report, spellcheck, styleguides, styleitems
from .adjudicate import Cache, Item, adjudicate
from .apply import Edit, apply_edits, match_case, to_offsets
from .context import at_sentence_start, inside_quotes, sentence_context
from .conventions import normalize
from .llm import resolve_endpoint
from .vale_runner import Alert, ValeError, run_vale

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


DESCRIPTION = """\
Regularize a Markdown file to US or UK English and a style guide, without
touching code, links, URLs or front matter.

Vale decides what to change. Unambiguous spelling variants (colour/color,
organise/organize, centre/center ...) and style-guide preferences
(towards/toward) are replaced outright, with case preserved. Words whose
correct form depends on meaning (licence/license, programme/program,
cheque/check, storey/story ...), and any replacement that sits inside a
quotation or looks like a proper name, are put to a local language model as a
multiple-choice question with the surrounding sentence; it picks one of the
supplied options or KEEP, and never rewrites prose. Everything the tool will
not decide is listed in a report written next to the output.

A final pass fixes punctuation: curly quotes with the right primary style
(double for US, single for UK), apostrophes, em or spaced en dashes, en dashes
in number ranges, and date order (September 4, 2026 / 4 September 2026).
"""

EPILOG = """\
examples:
  stylefix draft.md --target us
      write draft.us.md and draft.us.md.report.md, Chicago conventions,
      ambiguous words decided by the first reachable model (DGX, then Ollama)

  stylefix draft.md --target uk --oxford-ize -o final.md
      British spelling with Oxford -ize, Oxford dash and quote style

  stylefix draft.md --target us --style gpo
      federal (Government Publishing Office) conventions; --list-styles for all

  stylefix draft.md --target us --dry-run
      print a unified diff of what would change; write nothing

  stylefix draft.md --target uk --llm none
      no model: ambiguous words are left alone and listed in the report

  stylefix draft.md --target us --think --batch-size 8 --timeout 600
      slower, more careful pass for an important document

  stylefix draft.md --target us --accept house-terms.txt
      never touch the words or phrases listed in house-terms.txt (these add
      to a built-in list of technical and policy terms, plus
      ~/.config/stylefix/accept.txt and ./.stylefix/accept.txt if present)

environment:
  STYLEFIX_LLM_URL, STYLEFIX_LLM_MODEL, STYLEFIX_LLM_KEY
      override the model endpoint (same as --url, --model, and the API key)
  DGX_LLM_DIR   directory holding the dgx-llm .env (default ~/Code/dgx-llm)
  OLLAMA_HOST   Ollama base URL (default http://localhost:11434)

files:
  <output>.report.md      every replacement, every model decision with its
                          reason and confidence, and alerts left for review
  .stylefix/cache.json    model decisions keyed on word and sentence; edit an
                          entry to override it on the next run

Requires the vale binary on PATH (brew install vale). Full documentation:
man stylefix, or README.md in the source tree.
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="stylefix", description=DESCRIPTION, epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", type=Path, nargs="?", help="Markdown file to regularize")
    p.add_argument("--version", action="version", version=f"stylefix {__version__}")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="report model batches on stderr as they are sent")

    t = p.add_argument_group("target")
    t.add_argument("--target", choices=["us", "uk"],
                   help="English variety to convert to (required)")
    t.add_argument("--style", choices=styleguides.choices(), metavar="GUIDE",
                   help="style guide for dashes, serial commas, numerals, toward/towards and "
                        "punctuation placement: " + ", ".join(styleguides.choices()) +
                        " (default: chicago for us, oxford for uk; --list-styles explains each)")
    t.add_argument("--abbreviation-nouns", choices=["default", "warn", "enforce", "off"], default="default",
                   help="GPO and APA use 'U.S.' only as an adjective and write the noun out as "
                        "'the United States'. default: warn when the guide has the rule; enforce: "
                        "decide each 'the U.S.' with the model; off")
    t.add_argument("--list-styles", action="store_true",
                   help="describe every style guide and exit")
    t.add_argument("--oxford-ize", action="store_true",
                   help="with --target uk, keep -ize spellings (Oxford) instead of -ise")
    t.add_argument("--accept", type=Path, metavar="FILE",
                   help="extra words or phrases to leave alone, one per line, on top of the "
                        "built-in list, ~/.config/stylefix/accept.txt and .stylefix/accept.txt")
    t.add_argument("--no-default-accept", action="store_true",
                   help="use only the --accept file, ignoring the built-in and user lists")

    o = p.add_argument_group("output")
    o.add_argument("-o", "--output", type=Path, metavar="FILE",
                   help="where to write the result (default: <input>.<target>.md)")
    o.add_argument("-i", "--in-place", action="store_true",
                   help="overwrite the input file instead")
    o.add_argument("--dry-run", action="store_true",
                   help="print a unified diff to stdout and write nothing")
    o.add_argument("--report", type=Path, metavar="FILE",
                   help="where to write the report (default: <output>.report.md)")
    o.add_argument("--no-report", action="store_true", help="do not write a report")
    o.add_argument("--changes", action="store_true",
                   help="print every change to stderr: line, before -> after, context, and "
                        "how it was decided (-v implies this)")

    m = p.add_argument_group("model", "how ambiguous words are adjudicated")
    m.add_argument("--llm", choices=["auto", "dgx", "ollama", "none"], default="auto",
                   help="endpoint preset: dgx (dgx-llm gateway), ollama (local), none (skip the "
                        "model; ambiguous words go to the report), auto (first reachable of "
                        "dgx, ollama) (default: %(default)s)")
    m.add_argument("--url", metavar="URL",
                   help="OpenAI-compatible base URL ending in /v1; overrides --llm")
    m.add_argument("--model", metavar="NAME", help="model name at the endpoint")
    m.add_argument("--think", action="store_true",
                   help="let a reasoning model think before answering: slower, slightly "
                        "more accurate; pair with a small --batch-size and a long --timeout")
    m.add_argument("--min-confidence", type=float, default=0.7, metavar="X",
                   help="decisions below this confidence are not applied and go to the "
                        "report (default: %(default)s)")
    m.add_argument("--batch-size", type=int, default=20, metavar="N",
                   help="items per model request (default: %(default)s)")
    m.add_argument("--parallel", type=int, default=4, metavar="N",
                   help="concurrent model requests (default: %(default)s)")
    m.add_argument("--timeout", type=float, default=120.0, metavar="SEC",
                   help="seconds to wait for one model request (default: %(default)s)")
    m.add_argument("--cache", type=Path, default=Path(".stylefix/cache.json"), metavar="FILE",
                   help="where model decisions are cached (default: %(default)s)")
    m.add_argument("--no-cache", action="store_true",
                   help="neither read nor write the decision cache")
    return p


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
    for a in alerts:
        if a.line <= fm_lines:
            continue  # never touch front matter
        s, e = to_offsets(text, Edit(a.line, a.start, a.end, a.match, "", ""))
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
        elif adjudicate_style and a.check.rsplit(".", 1)[-1] in ("SerialComma", "Numbers"):
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


BUILTIN_ACCEPT = Path(__file__).parent / "accept.txt"


def accept_sources(explicit: Path | None, no_default: bool) -> list[Path]:
    """Accept lists in precedence order: built-in, user, project, --accept."""
    paths: list[Path] = []
    if not no_default:
        paths.append(BUILTIN_ACCEPT)
        cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        paths.append(cfg / "stylefix" / "accept.txt")
        paths.append(Path(".stylefix") / "accept.txt")
    if explicit:
        paths.append(explicit)
    return paths


def load_accept_lists(explicit: Path | None, no_default: bool) -> list[str] | None:
    words: list[str] = []
    for path in accept_sources(explicit, no_default):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                words.append(line)
    return words or None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list_styles:
        sys.stdout.write(styleguides.describe())
        return 0
    if args.target is None:
        build_parser().error("the following arguments are required: --target")
    if args.input is None or not args.input.exists():
        print(f"stylefix: no such file: {args.input}", file=sys.stderr)
        return 2
    guide = args.style or styleguides.DEFAULT_FOR[args.target]
    g = styleguides.get(guide)
    if g.variety and g.variety != args.target:
        print(f"stylefix: note: {guide} is a {g.variety.upper()} style guide applied to a "
              f"{args.target.upper()} target; spelling follows the target, conventions the guide",
              file=sys.stderr)
    output = args.input if args.in_place else (
        args.output or args.input.with_suffix(f".{args.target}{args.input.suffix or '.md'}"))
    report_path = args.report or output.with_suffix(output.suffix + ".report.md")
    text = args.input.read_text(encoding="utf-8")

    accept = load_accept_lists(args.accept, args.no_default_accept)
    try:
        alerts = run_vale(args.input, args.target, guide, args.oxford_ize, accept)
    except ValeError as e:
        print(f"stylefix: {e}", file=sys.stderr)
        return 2
    ep = resolve_endpoint(args.llm, args.model, args.url, think=args.think,
                          timeout=args.timeout)
    edits, items, review = partition(text, alerts, args.target, guide, args.oxford_ize,
                                     adjudicate_style=ep is not None)
    ab_edits, ab_items, ab_warnings = abbreviations.plan(text, guide, args.abbreviation_nouns,
                                                         next_id=len(items) + 1)
    edits += ab_edits
    title = styleguides.get(guide).title or "Style"
    if ep is not None:
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
    review += spellcheck.review_spellings(new_text, args.target, set(accept or ()))

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
    if args.changes or args.verbose:
        sys.stderr.write(changelog.render(text=text, target=args.target, applied=applied,
                                          decisions=decisions, stats=stats, skipped=skipped,
                                          review=review))
    undecided = sum(1 for d in decisions if d.choice is None)
    wrote = "" if args.dry_run else f" -> {output}"
    if not args.dry_run and not args.no_report:
        wrote += f", report {report_path}"
    print(f"stylefix: {len(applied)} replacement(s), {len(decisions)} adjudicated "
          f"({undecided} undecided), {len(review)} alert(s) for review{wrote}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
