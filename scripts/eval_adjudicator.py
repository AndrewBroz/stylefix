"""Measure adjudication accuracy and latency against a model endpoint.

    uv run python scripts/eval_adjudicator.py --llm dgx [--think] [--model X] [--parallel 4]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from stylefix import candidates                                  # noqa: E402
from stylefix.adjudicate import Cache, Item, adjudicate         # noqa: E402
from stylefix.llm import resolve_endpoint                        # noqa: E402

# (target, word, sentence, gold)
CASES = [
    ("uk", "license", "You need a [[license]] to drive a lorry.", "licence"),
    ("uk", "license", "We [[license]] the software to schools.", "license"),
    ("uk", "licenses", "The council issues [[licenses]] for street trading.", "licences"),
    ("uk", "practice", "In [[practice]] the rule is ignored.", "practice"),
    ("uk", "practice", "They [[practice]] every morning before school.", "practise"),
    ("uk", "practices", "She [[practices]] law in Leeds.", "practises"),
    ("uk", "program", "The [[program]] crashed after the update.", "program"),
    ("uk", "program", "The evening [[program]] begins at seven with a concert.", "programme"),
    ("uk", "programs", "Government training [[programs]] were cut.", "programmes"),
    ("uk", "check", "The [[check]] cleared two days later.", "cheque"),
    ("uk", "check", "Please [[check]] the figures again.", "check"),
    ("uk", "checks", "He paid by [[checks]] drawn on a London bank.", "cheques"),
    ("uk", "story", "The office is on the third [[story]].", "storey"),
    ("uk", "story", "She told a long [[story]] about the war.", "story"),
    ("uk", "stories", "A building of six [[stories]] overlooks the park.", "storeys"),
    ("uk", "tire", "The rear [[tire]] was flat.", "tyre"),
    ("uk", "tire", "Long meetings [[tire]] everyone.", "tire"),
    ("uk", "meter", "The gas [[meter]] is under the stairs.", "meter"),
    ("uk", "meter", "The pool is fifty [[meter]] long, or close to it.", "metre"),
    ("uk", "meters", "Run four hundred [[meters]] and stop.", "metres"),
    ("uk", "curb", "He tripped on the [[curb]].", "kerb"),
    ("uk", "curb", "We must [[curb]] spending.", "curb"),
    ("uk", "inquiry", "A public [[inquiry]] into the crash was ordered.", "inquiry"),
    ("uk", "inquiry", "Thank you for your [[inquiry]] about room rates.", "enquiry"),
    ("uk", "draft", "The first [[draft]] of the report is due Monday.", "draft"),
    ("uk", "draft", "There is a cold [[draft]] from the window.", "draught"),
    ("uk", "draft", "Two pints of [[draft]] beer, please.", "draught"),
    ("uk", "judgment", "The court handed down its [[judgment]] on Friday.", "judgment"),
    ("uk", "judgment", "Use your own [[judgment]] when choosing a colour.", "judgement"),
    ("uk", "learned", "A [[learned]] professor gave the lecture.", "learned"),
    ("uk", "learned", "We [[learned]] a great deal from the failure.", "learnt"),
    ("uk", "disk", "The [[disk]] was corrupted, so back up the server.", "disk"),
    ("uk", "disk", "Put the compact [[disk]] in the player.", "disc"),
    ("uk", "ton", "The truck carries a [[ton]] of gravel, that is 1000 kg.", "tonne"),
    ("uk", "ton", "We have a [[ton]] of work to do.", "ton"),
    ("uk", "mom", "Ask your [[mom]] before you go.", "mum"),
    ("uk", "mom", "The band Mom and Dad, whose song [[Mom]] topped the chart.", "KEEP"),
    ("us", "disc", "Insert the compact [[disc]] and press play.", "disc"),
    ("us", "disc", "Format the hard [[disc]] before installing.", "disk"),
    ("us", "tonne", "The crane lifts one [[tonne]].", "metric ton"),
    ("us", "mum", "She kept [[mum]] about the surprise.", "mum"),
    ("us", "mum", "My [[mum]] rang this morning.", "mom"),
    # proper nouns / quotations (capitalised deterministic hits)
    ("us", "Labour", "The [[Labour]] Party lost the vote.", "KEEP"),
    ("us", "Centre", "Meet at the [[Centre]] for Digital Behaviour on Monday.", "KEEP"),
    ("us", "Colour", "We discussed [[Colour]] theory in the first lecture.", "Color"),
    ("us", "colour", "As the report said, \"the [[colour]] scheme was poor\".", "KEEP"),
    ("us", "Defence", "The [[Defence]] Ministry released a statement.", "KEEP"),
    ("uk", "Color", "Read [[Color]] Theory for Designers, the new book by Ito.", "KEEP"),
]


def build_items() -> list[Item]:
    items = []
    for i, (target, word, sentence, _gold) in enumerate(CASES, 1):
        cand = candidates.lookup(target, word)
        if cand:
            options, rule = cand.options, cand.rule
        elif word[:1].isupper():
            us_or_uk = {"Labour": "Labor", "Centre": "Center", "Colour": "Color",
                        "Defence": "Defense", "Color": "Colour"}[word]
            options = (us_or_uk, "KEEP")
            rule = "Capitalised mid-sentence: may be a proper name or title. Otherwise use the target spelling."
        else:
            options = ("color", "KEEP")
            rule = "Inside a quotation: quoted text keeps its own spelling. Otherwise use the target spelling."
        items.append(Item(i, word, options, rule, sentence, 1, 1, 1))
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default="auto")
    ap.add_argument("--model")
    ap.add_argument("--url")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--repeat", type=int, default=1, help="duplicate the case set N times (latency test)")
    args = ap.parse_args()
    ep = resolve_endpoint(args.llm, args.model, args.url, think=args.think, timeout=args.timeout)
    if ep is None:
        print("no endpoint"); return 2
    items = [it for _ in range(args.repeat) for it in build_items()]
    for i, it in enumerate(items, 1):
        it.id = i
    by_target: dict[str, list[Item]] = {}
    for it in items:
        by_target.setdefault(CASES[(it.id - 1) % len(CASES)][0], []).append(it)
    t0 = time.time()
    decisions = {}
    for target, its in by_target.items():
        for d in adjudicate(ep, target, its, Cache(None), args.batch_size, args.parallel):
            decisions[d.item.id] = d
    elapsed = time.time() - t0
    right = 0
    for it in items[:len(CASES)]:
        gold = CASES[it.id - 1][3]
        d = decisions[it.id]
        # Choosing the word itself is the same decision as KEEP.
        norm = lambda c: "keep" if c.lower() in ("keep", it.word.lower()) else c.lower()
        ok = norm(d.choice or "") == norm(gold)
        right += ok
        if not ok:
            print(f"  MISS {it.word!r} in {it.context!r}: got {d.choice!r} ({d.confidence:.2f}, {d.reason}), want {gold!r}")
    n = len(CASES)
    print(f"{ep.name}:{ep.model} think={args.think} parallel={args.parallel} "
          f"batch={args.batch_size}: {right}/{n} correct ({100*right/n:.0f}%), "
          f"{len(items)} items in {elapsed:.1f}s ({elapsed/len(items)*1000:.0f} ms/item)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
