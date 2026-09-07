"""Suffix families whose spelling varies by variety, handled as patterns.

A pattern hit is split into stem + ending + inflection, rewritten
mechanically, and confirmed against the dictionaries using the *base*
forms (stem + ending), since the vendored word lists carry base words
only. The outcome for one word is one of:

- skip:   already right for the target
- auto:   the rewrite's base form is a known word; apply it
- ask:    the rewrite is in no dictionary; a coinage, a name or a typo, so
          the adjudicator chooses between the rewrite and KEEP
- reject: not an instance of the family after all
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import dictionary


@dataclass(frozen=True)
class Outcome:
    status: str                  # skip | auto | ask | reject
    candidate: str | None = None
    family: str = ""


ISE_TAILS = "ationally|ational|ations|ation|ability|ably|able|ers|er|es|ed|ing|e"
OUR_TAILS = "fully|ful|less|able|ings|ing|ed|s"
ISE_RX = re.compile(rf"^(?P<stem>[A-Za-z]{{2,}})(?P<v>[iy])(?P<c>[sz])(?P<tail>{ISE_TAILS})$")
OUR_RX = re.compile(rf"^(?P<stem>[A-Za-z]{{2,}})(?P<o>ou|o)r(?P<tail>(?:{OUR_TAILS})?)$")
RE_RX = re.compile(r"^(?P<stem>[A-Za-z]{2,}[bcdfghklmnpstvz])(?P<tail>res|red|ring|re)$")
ER_RX = re.compile(r"^(?P<stem>[A-Za-z]{2,}[bcdfghklmnpstvz])(?P<tail>ers|ered|ering|er)$")
LL_RX = re.compile(r"^(?P<stem>[A-Za-z]*[^aeiouAEIOU][aeiou]l)(?P<tail>ling|led|lers|ler)$")

# Base words that must never be rewritten by a family, because both
# spellings exist as different words or the dictionary lists a variant we
# must not produce.
IZE_TO_ISE_NEVER = {"prize", "seize", "size", "capsize", "assize"}
ISE_TO_IZE_NEVER = {"merchandise", "expertise", "advertise", "advise", "arise", "chastise",
                    "comprise", "compromise", "despise", "devise", "disguise", "enterprise",
                    "excise", "exercise", "franchise", "improvise", "premise", "promise",
                    "revise", "supervise", "surprise", "televise", "otherwise", "likewise",
                    "clockwise", "precise", "concise", "treatise", "reprise", "demise",
                    "apprise", "incise", "circumcise", "exorcise", "surmise", "guise",
                    "practise"}     # practise -> practice, not -ize; the table handles it
OR_TO_OUR_NEVER = {"meter", "tenor", "tremor", "error", "mirror", "terror", "pallor", "stupor",
                   "liquor", "squalor", "torpor", "rigor", "motor", "rotor", "tutor", "actor"}
OUR_TO_OR_NEVER = {"four", "tour", "hour", "sour", "flour", "pour", "scour", "devour", "dour",
                   "velour", "contour", "detour", "glamour", "paramour", "amour", "troubadour",
                   "tambour", "pompadour", "our", "your"}
ER_TO_RE_NEVER = {"meter", "timber", "eager", "sober", "number", "member", "ember", "amber",
                  "umber", "cover", "sever", "cater", "later", "water", "enter", "letter",
                  "matter", "master", "filter", "tender", "wonder", "order", "border"}
RE_TO_ER_NEVER = {"timbre", "genre", "oeuvre", "cadre", "macabre", "padre", "acre", "ogre",
                  "lucre", "mediocre", "massacre", "wiseacre", "euchre", "chancre",
                  "manoeuvre"}    # -> maneuver (oe changes too); the table handles it
LL_NEVER = {"control", "patrol", "enrol", "compel", "propel", "expel", "rebel", "repel",
            "dispel", "excel", "impel", "extol", "appal", "instil", "distil", "fulfil", "annul",
            "parallel", "unparallel"}

_RE_ER = {"re": "er", "res": "ers", "red": "ered", "ring": "ering"}
_ER_RE = {v: k for k, v in _RE_ER.items()}


def _confirm(base_candidate: str, candidate: str, family: str, variety: str | None = None) -> Outcome:
    ok = dictionary.known(base_candidate, variety) if variety else dictionary.known_anywhere(base_candidate)
    return Outcome("auto" if ok else "ask", candidate, family)


# ---------------------------------------------------------------- -ise/-ize

def ise_family(word: str, target: str, oxford: bool = False) -> Outcome:
    m = ISE_RX.match(word)
    if not m:
        return Outcome("reject", family="ise")
    stem, v, c, tail = m["stem"], m["v"], m["c"].lower(), m["tail"]
    to_ize = target == "us" or (target == "uk" and oxford)
    if to_ize:
        if c == "z":
            return Outcome("skip", family="ise")
        if v == "y" and target == "uk":              # Oxford keeps analyse
            return Outcome("skip", family="ise")
        base = (stem + v + "se").lower()
        if base in ISE_TO_IZE_NEVER or stem.lower().endswith("w"):
            return Outcome("reject", family="ise")
        # en_US lists no -ise verbs except the ones that are -ise everywhere,
        # so "base is a US word" means leave it. en_GB lists Oxford -ize
        # forms too, so that test is not available for the UK target.
        if target == "us" and dictionary.known(base, "us"):
            return Outcome("skip", family="ise")
        return _confirm(stem + v + "ze", stem + v + "z" + tail, "ise")
    if c == "s":
        return Outcome("skip", family="ise")
    base = (stem + v + "ze").lower()
    if base in IZE_TO_ISE_NEVER:
        return Outcome("reject", family="ise")
    return _confirm(stem + v + "se", stem + v + "s" + tail, "ise", "uk")


# ---------------------------------------------------------------- -our/-or

def our_family(word: str, target: str) -> Outcome:
    m = OUR_RX.match(word)
    if not m:
        return Outcome("reject", family="our")
    stem, o, tail = m["stem"], m["o"], m["tail"]
    if target == "us":
        if o == "o":
            return Outcome("skip", family="our")
        base = (stem + "our").lower()
        if base in OUR_TO_OR_NEVER:
            return Outcome("reject", family="our")
        if dictionary.known(base, "us"):
            return Outcome("skip", family="our")
        return _confirm(stem + "or", stem + "or" + tail, "our")
    if o == "ou":
        return Outcome("skip", family="our")
    base = (stem + "or").lower()
    if base in OR_TO_OUR_NEVER:
        return Outcome("reject", family="our")
    if dictionary.known(stem + "our", "uk"):
        return Outcome("auto", stem + "our" + tail, "our")
    return Outcome("skip" if dictionary.known(base, "uk") else "reject", family="our")


# ---------------------------------------------------------------- -re/-er

def re_family(word: str, target: str) -> Outcome:
    if target == "us":
        m = RE_RX.match(word)
        if not m:
            return Outcome("reject", family="re")
        stem, tail = m["stem"], m["tail"]
        base = (stem + "re").lower()
        if base in RE_TO_ER_NEVER:
            return Outcome("reject", family="re")
        if dictionary.known(base, "us"):
            return Outcome("skip", family="re")
        return _confirm(stem + "er", stem + _RE_ER[tail], "re")
    m = ER_RX.match(word)
    if not m:
        return Outcome("reject", family="re")
    stem, tail = m["stem"], m["tail"]
    base = (stem + "er").lower()
    if base in ER_TO_RE_NEVER:
        return Outcome("reject", family="re")
    if dictionary.known(stem + "re", "uk"):
        return Outcome("auto", stem + _ER_RE[tail], "re")
    return Outcome("skip" if dictionary.known(base, "uk") else "reject", family="re")


# ---------------------------------------------------------------- -ll-/-l-

def ll_family(word: str, target: str) -> Outcome:
    """UK doubles the l in travelling/modelled; US does not unless the last
    syllable is stressed (controlled, patrolled). To US only; the to-UK
    direction stays a table because en_GB's base list lacks the inflected
    forms and the stress rule is not mechanical."""
    if target != "us":
        return Outcome("reject", family="ll")
    m = LL_RX.match(word)
    if not m:
        return Outcome("reject", family="ll")
    stem, tail = m["stem"], m["tail"]
    if stem.lower() in LL_NEVER:
        return Outcome("reject", family="ll")
    if dictionary.known(word.lower(), "us"):
        return Outcome("skip", family="ll")
    if dictionary.known(stem, "us"):
        return Outcome("auto", stem + tail[1:], "ll")
    return Outcome("reject", family="ll")


def decide(word: str, family: str, target: str, oxford: bool = False) -> Outcome:
    if family == "ise":
        return ise_family(word, target, oxford)
    return {"our": our_family, "re": re_family, "ll": ll_family}[family](word, target)


# Detection regexes for the Vale existence rules.
VALE_TOKENS = {
    "us": {
        "PatIse": rf"\b[A-Za-z]{{2,}}[iy]s(?:{ISE_TAILS})\b",
        "PatOur": rf"\b[A-Za-z]{{2,}}our(?:{OUR_TAILS})?\b",
        "PatRe": r"\b[A-Za-z]{2,}[bcdfghklmnpstvz](?:res|red|ring|re)\b",
        "PatLl": r"\b[A-Za-z]*[^aeiouAEIOU\W][aeiou]l(?:ling|led|lers|ler)\b",
    },
    "uk": {
        "PatIze": rf"\b[A-Za-z]{{2,}}[iy]z(?:{ISE_TAILS})\b",
        "PatIse": rf"\b[A-Za-z]{{2,}}[iy]s(?:{ISE_TAILS})\b",      # Oxford only
        "PatOr": rf"\b[A-Za-z]{{2,}}or(?:{OUR_TAILS})?\b",
        "PatEr": r"\b[A-Za-z]{2,}[bcdfghklmnpstvz](?:ers|ered|ering|er)\b",
    },
}
CHECK_FAMILY = {"PatIse": "ise", "PatIze": "ise", "PatOur": "our", "PatOr": "our",
                "PatRe": "re", "PatEr": "re", "PatLl": "ll"}


def write_vale_rules(styles_dir) -> None:
    from pathlib import Path
    styles_dir = Path(styles_dir)
    for target, rules in VALE_TOKENS.items():
        d = styles_dir / ("ToUS" if target == "us" else "ToUK")
        d.mkdir(parents=True, exist_ok=True)
        for name, rx in rules.items():
            (d / f"{name}.yml").write_text(
                "# Generated by `python -m stylefix.wordlist`. Pattern family detector;\n"
                "# stylefix/patterns.py decides what to do with each hit.\n"
                "extends: existence\n"
                f"message: \"'%s' may need the {target.upper()} spelling of its ending.\"\n"
                "level: suggestion\n"
                "ignorecase: false\n"
                "tokens:\n"
                f"  - '{rx}'\n")
