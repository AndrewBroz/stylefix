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


def _ok(out, want):
    """The pattern may defer to the table (skip, ask, or an explicit reject
    for words on a never-list) but must never confirm a different spelling."""
    return out.status != "auto" or out.candidate == want


def test_patterns_cover_the_curated_tables():
    """Every -ise/-our/-re/-ll table entry must be handled consistently by
    the pattern mechanism alone, in both directions where the pattern
    applies. The tables still win on overlap in the real pipeline."""
    misses = []
    auto = 0
    for uk, us in wordlist.to_us_map().items():
        fam = _family_for(uk)
        if fam is None:
            continue
        out = decide(uk, fam, "us")
        auto += out.status == "auto"
        if not _ok(out, us):
            misses.append(("us", uk, us, out))
    for us, uk in wordlist.to_uk_map(ise=True).items():
        fam = None
        for check, rx in VALE_TOKENS["uk"].items():
            if check != "PatIse" and re.fullmatch(rx.strip("\\b"), us):
                fam = CHECK_FAMILY[check]
        if fam is None:
            continue
        out = decide(us, fam, "uk")
        auto += out.status == "auto"
        if not _ok(out, uk):
            misses.append(("uk", us, uk, out))
    assert not misses, "\n".join(map(str, misses[:40])) + f"\n{len(misses)} misses"
    assert auto > 900, auto      # the mechanism, not the table, carries the bulk
