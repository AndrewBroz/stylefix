"""Command-line entry point."""

from __future__ import annotations

import argparse
import difflib
import math
import os
import re
import sys
from pathlib import Path

from adjudicate import check_endpoint, run_setup

from . import __version__, api, changelog, report, styleguides
from .adjudicate import Cache
from .api import partition  # noqa: F401
from .llm import ConfigError, resolve_endpoint
from .vale_runner import ValeError, find_vale


DESCRIPTION = """\
Regularize a Markdown file to US or UK English and a style guide, without
touching code, links, URLs or front matter.

Vale decides what to change. Unambiguous spelling variants (colour/color,
organise/organize, centre/center ...) and style-guide preferences
(towards/toward) are replaced outright, with case preserved. Words whose
correct form depends on meaning (licence/license, programme/program,
cheque/check, storey/story ...), and any replacement that sits inside a
quotation or looks like a proper name, are put to a language model as a
multiple-choice question with the surrounding sentence; it picks one of the
supplied options or KEEP, and never rewrites prose. Everything the tool will
not decide is listed in a report written next to the output.

A final pass fixes punctuation: curly quotes with the right primary style
(double for US, single for UK), apostrophes, em or spaced en dashes, en dashes
in number ranges, and date order (September 4, 2026 / 4 September 2026).
"""

EPILOG = """\
examples:
  stylefix --setup
      choose and test a model endpoint, and save it for stylefix and proofix

  stylefix draft.md --target us
      write draft.us.md and draft.us.md.report.md, Chicago conventions,
      ambiguous words decided by the configured model, or local Ollama

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
      the model endpoint for stylefix (same as --url, --model, and the API key)
  ADJUDICATE_LLM_URL, ADJUDICATE_LLM_MODEL, ADJUDICATE_LLM_KEY
      the same, shared with proofix; below the stylefix variables and config
  OLLAMA_HOST   Ollama base URL (default http://localhost:11434)

files:
  ~/.config/stylefix/config.toml     [llm] url, model, api_key or api_key_env,
                                     timeout, thinking_switch (stylefix only)
  ~/.config/adjudicate/config.toml   the same table, shared with proofix
  <output>.report.md      every replacement, every model decision with its
                          reason and confidence, and alerts left for review
  .stylefix/cache.json    model decisions keyed on word and sentence; edit an
                          entry to override it on the next run

Requires the vale binary on PATH (brew install vale). Full documentation:
https://github.com/AndrewBroz/stylefix (man page: man/stylefix.1 in the source)
"""


def positive_seconds(text: str) -> float:
    """argparse type for --timeout: a positive, finite number of seconds."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not (math.isfinite(value) and value > 0):
        raise argparse.ArgumentTypeError(f"must be a positive number of seconds, not {text}")
    return value


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
    m.add_argument("--llm", choices=["auto", "ollama", "none"], default="auto",
                   help="auto: the endpoint from --url, STYLEFIX_LLM_*, "
                        "~/.config/stylefix/config.toml, ADJUDICATE_LLM_* or "
                        "~/.config/adjudicate/config.toml, else local Ollama; "
                        "ollama: local Ollama only; none: skip the model, ambiguous "
                        "words go to the report (default: %(default)s)")
    m.add_argument("--url", metavar="URL",
                   help="OpenAI-compatible base URL ending in /v1; overrides every configured "
                        "url. A --url or STYLEFIX_LLM_URL drops keys set in lower layers; set "
                        "STYLEFIX_LLM_KEY (or api_key_env in the same config file) alongside it")
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
    m.add_argument("--timeout", type=positive_seconds, default=None, metavar="SEC",
                   help="seconds to wait for one model request (default: 120, or timeout in config.toml)")
    m.add_argument("--cache", type=Path, default=Path(".stylefix/cache.json"), metavar="FILE",
                   help="where model decisions are cached (default: %(default)s)")
    m.add_argument("--no-cache", action="store_true",
                   help="neither read nor write the decision cache")

    c = p.add_argument_group("configuration", "set up or check the model endpoint, then exit")
    c.add_argument("--setup", action="store_true",
                   help="choose a model endpoint interactively, test it, and save it to "
                        "~/.config/adjudicate/config.toml or ~/.config/stylefix/config.toml")
    c.add_argument("--check-endpoint", action="store_true",
                   help="show the endpoint stylefix would use and where each setting comes "
                        "from, then test it; exit 0 if it answers, 1 if not, 2 on a config error")
    return p


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
    if args.setup:
        return run_setup("stylefix")
    if args.check_endpoint:
        return check_endpoint("stylefix", preset=args.llm, url=args.url, model=args.model,
                              timeout=args.timeout)
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
        find_vale()                       # same error, same order as before the endpoint
    except ValeError as e:
        print(f"stylefix: {e}", file=sys.stderr)
        return 2
    try:
        ep = resolve_endpoint("stylefix", args.llm, url=args.url, model=args.model,
                              think=args.think, timeout=args.timeout)
    except ConfigError as e:
        print(f"stylefix: {e}", file=sys.stderr)
        return 2
    cache = Cache(None if args.no_cache else args.cache)
    try:
        r = api.fix(text, api.Options(target=args.target, style=args.style,
                                      oxford_ize=args.oxford_ize, accept=accept,
                                      abbreviation_nouns=args.abbreviation_nouns,
                                      min_confidence=args.min_confidence,
                                      batch_size=args.batch_size, parallel=args.parallel,
                                      verbose=args.verbose), ep, cache)
    except ValeError as e:
        print(f"stylefix: {e}", file=sys.stderr)
        return 2
    if r.unasked:
        print(f"stylefix: no model endpoint available (--llm {args.llm}); "
              f"{r.unasked} ambiguous word(s) will be listed for review"
              + ("; run `stylefix --setup` to configure one" if args.llm == "auto" else ""),
              file=sys.stderr)
    guide, new_text, applied, skipped = r.guide, r.text, r.applied, r.rejected
    decisions, stats, review = r.decisions, r.stats, r.review_alerts

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
