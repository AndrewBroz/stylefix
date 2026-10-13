import importlib.util
from pathlib import Path

from stylefix import patterns, varcon, wordlist

_spec = importlib.util.spec_from_file_location("legacy_table", Path(__file__).parent / "legacy_table.py")
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)


def test_generated_styles_are_up_to_date(tmp_path):
    from stylefix import styleguides
    wordlist.write_styles(tmp_path)
    patterns.write_vale_rules(tmp_path)
    styleguides.write_styles(tmp_path)
    for style in ("ToUS", "ToUK", "Chicago", "Oxford", "AP", "GPO", "APA", "Guardian"):
        made = {p.name: p.read_text() for p in (tmp_path / style).glob("*.yml")}
        have = {p.name: p.read_text() for p in (wordlist.STYLES_DIR / style).glob("*.yml")}
        assert made == have, f"{style} is stale: run `python -m stylefix.wordlist`"


def test_asymmetric_words_only_go_one_way():
    us, uk = wordlist.to_us_map(), wordlist.to_uk_map()
    assert us["licence"] == "license" and "license" not in uk
    assert us["programme"] == "program" and "program" not in uk
    assert us["practise"] == "practice" and "practice" not in uk
    assert "disc" not in us and "disk" not in uk
    assert uk["mold"] == "mould" and uk["color"] == "colour"
    for w in ("license", "program", "practice", "check", "story", "tire", "meter"):
        assert w in varcon.maps("uk").ambiguous, w


def test_oxford_ize_split():
    uk, ox = wordlist.to_uk_map(ise=True), wordlist.to_uk_map(ise=False)
    assert uk["organize"] == "organise" and ox["organise"] == "organize"
    assert ox["analyze"] == "analyse" and ox["color"] == "colour"
    assert "prise" not in ox or ox["prise"] != "prize"


def test_glosses_make_rules():
    m = varcon.maps("uk")
    assert m.rule("check", "British") == "British: 'check' for verify; 'cheque' for bank."
    assert "'licence' for noun" in m.rule("license", "British")


def test_legacy_tables_are_covered():
    """Everything the hand tables of 0.1/0.2 converted must still be
    converted (by table or pattern) or explicitly adjudicated. Inflections
    the old table generated that are not words are skipped."""
    import re
    from stylefix import candidates, dictionary
    us_map = wordlist.to_us_map()
    us_amb = set(varcon.maps("us").ambiguous) | set(candidates.TABLES["us"])
    misses = []
    for uk_w, us_w, cls in legacy.BOTH + legacy.ISE:
        for u, a in legacy.inflect(uk_w, us_w, cls):
            if u == a or not dictionary.known(u, "uk"):
                continue
            if us_map.get(u) == a or u in us_amb:
                continue
            fam = next((patterns.CHECK_FAMILY[c] for c, rx in patterns.VALE_TOKENS["us"].items()
                        if re.fullmatch(rx.strip("\\b"), u)), None)
            o = patterns.decide(u, fam, "us") if fam else None
            if o and ((o.status == "auto" and o.candidate == a) or o.status == "ask"):
                continue
            misses.append((u, a, us_map.get(u), o))
    assert not misses, "\n".join(map(str, misses[:30])) + f"\n{len(misses)} misses"


def test_no_swap_has_a_source_shorter_than_three_letters():
    for m in (wordlist.to_us_map(), wordlist.to_uk_map(), wordlist.to_uk_map(False),
              varcon.maps("us").convert, varcon.maps("uk").convert, varcon.maps("oxford").convert):
        assert not [k for k in m if len(k) < 3]
    for p in (wordlist.STYLES_DIR / "ToUK").glob("*.yml"):
        assert "  et: aet" not in p.read_text()
