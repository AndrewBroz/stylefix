"""Variant Conversion Info (VarCon) from the SCOWL project, as conversion maps.

varcon.txt has one cluster per line: spellings of one word tagged by the
varieties that use them. Tags: A American, B British -ise, Z British -ize
(Oxford), C Canadian, D Australian, _ other. A tag may carry a variant
marker: none or "." preferred, "v" variant, "V" seldom, "-" avoid, "x"
improper. A trailing "| <N>" or "| <V>" marks sense (noun, verb).

For a target variety we convert every spelling in a cluster to that
variety's preferred form, when the cluster has exactly one. A spelling
that is *also* the target's preferred form in another cluster (licence
<N> / license <V>; "check | verify" alongside "check / cheque | bank") is
a homograph or sense split: it is collected as ambiguous, with the
clusters' glosses as the rule of thumb, and left to the adjudicator.
"""

from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

VARCON = Path(__file__).parent / "dict" / "varcon.txt.gz"
TARGET_TAG = {"us": "A", "uk": "B", "oxford": "Z"}
_TAG = re.compile(r"^([ABZCD_])([.vV\-x]?)$")


SENSE_WORD = {"N": "noun", "V": "verb", "Adj": "adjective", "Adv": "adverb",
              "Prep": "preposition", "Inj": "interjection", "abbr": "abbreviation"}


@dataclass
class Cluster:
    forms: dict[str, list[tuple[str, str]]]   # spelling -> [(variety, marker)]
    sense: str = ""                            # "N", "V", "Adj", ... or ""
    gloss: str = ""                            # free text after the bar

    def describe(self) -> str:
        parts = []
        if self.sense in SENSE_WORD:
            parts.append(SENSE_WORD[self.sense])
        if self.gloss:
            parts.append(self.gloss)
        return ", ".join(parts)

    def preferred(self, variety: str) -> str | None:
        """The one spelling this variety prefers, or None if none/several."""
        hits = [w for w, tags in self.forms.items()
                if any(v == variety and m in ("", ".") for v, m in tags)]
        if len(hits) == 1:
            return hits[0]
        # Oxford: fall back to American when the cluster has no Z entry and
        # the British form is not an -ise word (colour stays colour).
        return None

    def accepted(self, variety: str) -> set[str]:
        """Spellings this variety uses at all (preferred or variant)."""
        return {w for w, tags in self.forms.items()
                if any(v == variety and m in ("", ".", "v") for v, m in tags)}


def parse_line(line: str) -> Cluster | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    sense, gloss = "", ""
    if " | " in line:
        line, note = line.split(" | ", 1)
        m = re.search(r"<(\w+)>", note)
        sense = m.group(1) if m else ""
        gloss = re.sub(r"<\w+>|\(-\)|:\d+|\bBrit(?:ish)?\.?:?|\bAmer(?:ican)?\.?:?", "", note)
        gloss = re.sub(r"\s+", " ", gloss).strip(" ,;")
    forms: dict[str, list[tuple[str, str]]] = {}
    for part in line.split(" / "):
        if ": " not in part:
            return None
        tags, word = part.split(": ", 1)
        word = word.strip()
        parsed = []
        for t in tags.split():
            if t.isdigit():
                continue
            m = _TAG.match(t)
            if not m:
                return None
            parsed.append((m.group(1), m.group(2)))
        if not parsed or all(v == "_" for v, _ in parsed):
            continue
        forms.setdefault(word, []).extend(parsed)
    return Cluster(forms, sense, gloss) if forms else None


@lru_cache(maxsize=None)
def clusters() -> list[Cluster]:
    with gzip.open(VARCON, "rt", encoding="latin-1") as f:
        out = [c for c in (parse_line(l) for l in f) if c]
    return out


@dataclass
class Maps:
    convert: dict[str, str]                 # spelling -> target preferred
    ambiguous: dict[str, set[str]]          # spelling -> candidate target forms
    glosses: dict[str, list[str]]           # target form -> what it means

    def rule(self, word: str, variety_name: str) -> str:
        """A rule of thumb for the adjudicator, from VarCon's glosses."""
        parts = []
        for form in sorted(self.ambiguous.get(word, ())):
            g = [x for x in self.glosses.get(form, []) if x]
            parts.append(f"'{form}'" + (f" for {'; '.join(dict.fromkeys(g))}" if g else ""))
        return f"{variety_name}: " + "; ".join(parts) + "." if parts else ""


_ISE = re.compile(r"is(e|es|ed|ing|er|ers|ation|ations|able)$")
_IZE = re.compile(r"iz(e|es|ed|ing|er|ers|ation|ations|able)$")


def target_preferred(c: Cluster, target: str) -> str | None:
    pref = c.preferred(TARGET_TAG[target])
    if pref is None and target == "oxford":
        # VarCon tags Z only where Oxford differs from British; otherwise
        # Oxford agrees with British.
        return c.preferred("B")
    return pref


def is_ise_cluster(c: Cluster) -> bool:
    return any(v == "Z" for tags in c.forms.values() for v, _ in tags)


@lru_cache(maxsize=None)
def maps(target: str) -> Maps:
    """Conversion map into `target` ('us', 'uk' or 'oxford')."""
    proposals: dict[str, set[str]] = {}
    glosses: dict[str, list[str]] = {}
    own: set[str] = set()                    # preferred target forms, any cluster
    for c in clusters():
        pref = target_preferred(c, target)
        if pref is None:
            continue
        own.add(pref)
        if c.describe():
            glosses.setdefault(pref, []).append(c.describe())
        for w in c.forms:
            if w == pref or any(ch.isupper() for ch in w):
                continue
            proposals.setdefault(w, set()).add(pref)
    convert: dict[str, str] = {}
    ambiguous: dict[str, set[str]] = {}
    for w, targets in proposals.items():
        if len(targets) > 1 or w in own:
            ambiguous[w] = set(targets) | ({w} if w in own else set())
        else:
            convert[w] = next(iter(targets))
    return Maps(convert, ambiguous, glosses)


if __name__ == "__main__":
    for t in ("us", "uk", "oxford"):
        m = maps(t)
        print(f"{t}: {len(m.convert)} conversions, {len(m.ambiguous)} ambiguous")
        for w in ("colour", "color", "licence", "license", "programme", "program", "organise",
                  "organize", "practise", "practice", "analyse", "analyze", "tyre", "tire",
                  "catalogue", "travelling", "traveling", "aluminium", "grey", "cheque", "check",
                  "storey", "story", "metre", "meter", "incentivise", "incentivize", "prise", "prize"):
            print(f"   {w:13} -> {m.convert.get(w, '·'):13} {sorted(m.ambiguous.get(w, ()))}  {m.rule(w, t)}")
        print("   ambiguous sample:", [w for w in sorted(m.ambiguous) if "'" not in w][:50])
