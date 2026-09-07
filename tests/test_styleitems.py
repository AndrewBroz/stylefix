from stylefix.styleguides import get
from stylefix.styleitems import candidate, number_words


def test_number_words():
    assert [number_words(n) for n in (1, 10, 15, 20, 21, 99, 100)] == \
        ["one", "ten", "fifteen", "twenty", "twenty-one", "ninety-nine", "one hundred"]


def test_serial_comma_candidates():
    rep, rule = candidate("Chicago.SerialComma", "attacks, intentional and unintentional", get("chicago"))
    assert rep == "attacks, intentional, and unintentional" and "KEEP if" in rule
    rep, rule = candidate("AP.SerialComma", "red, white, and blue", get("ap"))
    assert rep == "red, white and blue"
    assert candidate("Chicago.SerialComma", "odd text", get("chicago")) is None


def test_number_candidates():
    rep, rule = candidate("Chicago.Numbers", " 10 ", get("chicago"))
    assert rep == " ten " and "percentages" in rule
    assert candidate("GPO.Numbers", " 10 ", get("gpo")) is None      # numerals from 10
    assert candidate("GPO.Numbers", " 4 ", get("gpo"))[0] == " four "
