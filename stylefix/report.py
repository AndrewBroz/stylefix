"""Markdown report written next to the output file."""

from __future__ import annotations

from collections import Counter, defaultdict

from .adjudicate import Decision
from .apply import Edit
from .conventions import Stats
from .vale_runner import Alert


def _md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def render(*, source: str, output: str, target: str, guide: str, model: str,
           applied: list[Edit], skipped: list[Edit], decisions: list[Decision],
           review: list[Alert], stats: Stats) -> str:
    L = [f"# stylefix report", "",
         f"- source: `{source}`", f"- output: `{output}`",
         f"- target: {target.upper()} / {guide}", f"- model: {model}", ""]
    auto = [e for e in applied if e.source != "adjudicated"]
    adj_applied = [e for e in applied if e.source == "adjudicated"]
    needs = [d for d in decisions if d.choice is None]
    kept = [d for d in decisions if d.choice == "KEEP"]
    L += ["## Summary", "",
          f"| | count |", f"|---|---|",
          f"| deterministic replacements | {len(auto)} |",
          f"| adjudicated replacements | {len(adj_applied)} |",
          f"| adjudicated, kept as is | {len(kept)} |",
          f"| adjudication failed (needs review) | {len(needs)} |",
          f"| other alerts for review | {len(review)} |"]
    for k, v in stats.as_dict().items():
        L.append(f"| {k.replace('_', ' ')} | {v} |")
    if skipped:
        L.append(f"| edits skipped (text moved) | {len(skipped)} |")
    L.append("")
    if auto:
        c = Counter((e.original.lower(), e.replacement.lower()) for e in auto)
        L += ["## Deterministic replacements", "", "| from | to | n |", "|---|---|---|"]
        L += [f"| {a} | {b} | {n} |" for (a, b), n in sorted(c.items())]
        L.append("")
    if decisions:
        L += ["## Adjudicated", "",
              "| line | word | choice | conf | reason | context |", "|---|---|---|---|---|---|"]
        for d in sorted(decisions, key=lambda d: (d.item.line, d.item.start)):
            choice = d.choice or "**UNDECIDED**"
            tag = " (cached)" if d.cached else ""
            L.append(f"| {d.item.line} | {d.item.word} | {choice} | {d.confidence:.2f} | "
                     f"{_md_escape(d.reason)}{tag} | {_md_escape(d.item.context)} |")
        L.append("")
    if review:
        L += ["## For human review", ""]
        by_check = defaultdict(list)
        for a in review:
            by_check[a.check].append(a)
        for check, items in sorted(by_check.items()):
            L += [f"### {check} ({len(items)})", ""]
            for a in items[:200]:
                L.append(f"- line {a.line}: {_md_escape(a.message)}")
            if len(items) > 200:
                L.append(f"- … and {len(items) - 200} more")
            L.append("")
    return "\n".join(L).rstrip() + "\n"
