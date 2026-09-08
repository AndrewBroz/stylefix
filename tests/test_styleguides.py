from stylefix.conventions import normalize
from stylefix.styleguides import GUIDES, describe, get, vale_rules


def test_every_guide_has_rules_or_is_none():
    for g in GUIDES.values():
        if g.name == "none":
            assert vale_rules(g) == {} and g.dash is None
        else:
            assert vale_rules(g) and g.variety in ("us", "uk")
    assert "none" in describe() and "gpo " in describe()


def test_dashes_per_guide():
    src = "one -- two—three – four\n"
    assert normalize(src, "us", "chicago")[0] == "one—two—three—four\n"
    assert normalize(src, "us", "gpo")[0] == "one—two—three—four\n"
    assert normalize(src, "us", "ap")[0] == "one — two — three — four\n"
    assert normalize(src, "uk", "oxford")[0] == "one – two – three – four\n"
    assert normalize(src, "uk", "guardian")[0] == "one – two – three – four\n"
    assert normalize(src, "us", "none")[0] == src


def test_punctuation_placement_per_guide():
    src = 'He said "done", and left.\n'
    assert normalize(src, "us", "chicago")[0] == "He said “done,” and left.\n"
    assert normalize(src, "us", "ap")[0] == "He said “done,” and left.\n"
    assert normalize(src, "us", "none")[0] == "He said “done”, and left.\n"
    assert normalize(src, "uk", "oxford")[0] == "He said ‘done’, and left.\n"


def test_serial_comma_and_numbers_rules():
    assert ", [^,.;:!?\\n]+ (?:and|or)" in vale_rules(get("chicago"))["SerialComma.yml"]
    assert ", [^,.;:!?\\n]+, (?:and|or)" in vale_rules(get("ap"))["SerialComma.yml"]
    assert "[1-9]|[1-9]\\d" in vale_rules(get("chicago"))["Numbers.yml"]
    assert "(?:[1-9])" in vale_rules(get("gpo"))["Numbers.yml"]
    assert "Toward.yml" in vale_rules(get("gpo")) and "Towards.yml" in vale_rules(get("guardian"))
    assert "Toward.yml" not in vale_rules(get("apa"))
