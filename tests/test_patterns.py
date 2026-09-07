import pytest

from stylefix import wordlist
from stylefix.patterns import CHECK_FAMILY, VALE_TOKENS, decide
import re


@pytest.mark.parametrize("word,family,target,status,candidate", [
    ("organise", "ise", "us", "auto", "organize"),
    ("Organisation", "ise", "us", "auto", "Organization"),
    ("incentivised", "ise", "us", "auto", "incentivized"),
    ("analysed", "ise", "us", "auto", "analyzed"),
    ("platformise", "ise", "us", "ask", "platformize"),
    ("advertised", "ise", "us", "reject", None),
    ("otherwise", "ise", "us", "reject", None),
    ("precise", "ise", "us", "reject", None),
    ("expertise", "ise", "us", "reject", None),
    ("organized", "ise", "us", "skip", None),
    ("organize", "ise", "uk", "auto", "organise"),
    ("weaponizing", "ise", "uk", "auto", "weaponising"),
    ("analyzed", "ise", "uk", "auto", "analysed"),
    ("prizes", "ise", "uk", "reject", None),
    ("seized", "ise", "uk", "reject", None),
    ("capsize", "ise", "uk", "reject", None),
    ("platformized", "ise", "uk", "ask", "platformised"),
    ("colour", "our", "us", "auto", "color"),
    ("Behaviours", "our", "us", "auto", "Behaviors"),
    ("honoured", "our", "us", "auto", "honored"),
    ("glamour", "our", "us", "reject", None),
    ("four", "our", "us", "reject", None),
    ("tour", "our", "us", "reject", None),
    ("color", "our", "uk", "auto", "colour"),
    ("favored", "our", "uk", "auto", "favoured"),
    ("actor", "our", "uk", "reject", None),
    ("meter", "our", "uk", "reject", None),
    ("humorous", "our", "uk", "reject", None),
    ("centre", "re", "us", "auto", "center"),
    ("centred", "re", "us", "auto", "centered"),
    ("centring", "re", "us", "auto", "centering"),
    ("theatres", "re", "us", "auto", "theaters"),
    ("acre", "re", "us", "reject", None),
    ("timbre", "re", "us", "reject", None),
    ("genre", "re", "us", "reject", None),
    ("center", "re", "uk", "auto", "centre"),
    ("centered", "re", "uk", "auto", "centred"),
    ("fibers", "re", "uk", "auto", "fibres"),
    ("water", "re", "uk", "reject", None),
    ("timber", "re", "uk", "reject", None),
    ("meter", "re", "uk", "reject", None),
    ("travelling", "ll", "us", "auto", "traveling"),
    ("modelled", "ll", "us", "auto", "modeled"),
    ("travellers", "ll", "us", "auto", "travelers"),
    ("controlled", "ll", "us", "reject", None),
    ("patrolling", "ll", "us", "reject", None),
    ("paralleled", "ll", "us", "reject", None),
])
def test_family_decisions(word, family, target, status, candidate):
    out = decide(word, family, target)
    assert (out.status, out.candidate) == (status, candidate)


def test_oxford_direction():
    assert decide("organised", "ise", "uk", oxford=True).candidate == "organized"
    assert decide("analyse", "ise", "uk", oxford=True).status == "skip"
    assert decide("expertise", "ise", "uk", oxford=True).status == "reject"
    assert decide("organized", "ise", "uk", oxford=True).status == "skip"


def _family_for(word: str) -> str | None:
    for check, rx in VALE_TOKENS["us"].items():
        if re.fullmatch(rx.strip("\\b"), word):
            return CHECK_FAMILY[check]
    return None


def test_patterns_agree_with_varcon():
    """Over VarCon's whole map, a pattern that fires must give VarCon's answer
    or a spelling the dictionaries know (a valid variant the table will
    override); it must never manufacture a non-word. And it must carry a
    real share of the work."""
    from stylefix import dictionary
    checked = auto = 0
    bad = []
    for target, full, oxford in (("us", wordlist.to_us_map(), False),
                                 ("uk", wordlist.to_uk_map(ise=True), False)):
        for src, want in full.items():
            fam = None
            for check, rx in VALE_TOKENS[target].items():
                if target == "uk" and check == "PatIse":
                    continue
                if re.fullmatch(rx.strip("\\b"), src):
                    fam = CHECK_FAMILY[check]
            if fam is None:
                continue
            checked += 1
            out = decide(src, fam, target, oxford)
            if out.status == "auto":
                auto += 1
                c = out.candidate.lower()
                forms = [c] + [c[:-len(x)] for x in ("rs", "r", "s", "d") if c.endswith(x)]
                if c != want.lower() and not any(dictionary.known_anywhere(f) for f in forms):
                    bad.append((target, src, want, out.candidate))
    assert not bad, "\n".join(map(str, bad[:30])) + f"\n{len(bad)} non-words"
    # VarCon is far larger than the Hunspell lists, so most of its obscure
    # entries come back "ask"; the table covers those. Roughly 40% auto.
    assert checked > 5000 and auto / checked > 0.35, (checked, auto)
