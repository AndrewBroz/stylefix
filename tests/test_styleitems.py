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
    rep, _ = candidate("Guardian.SerialComma",
                       "stronger cybersecurity defences, more trustworthy and reliable consumer products, "
                       "financial stability, and more predictable AI deployments", get("guardian"))
    assert rep.endswith("financial stability and more predictable AI deployments")
    rep, _ = candidate("Guardian.SerialComma", "1) cybersecurity, 2) model containment, or 3) monitoring", get("guardian"))
    assert rep == "1) cybersecurity, 2) model containment or 3) monitoring"
    rep, _ = candidate("Chicago.SerialComma", "harm business, financial stability and US leadership", get("chicago"))
    assert rep == "harm business, financial stability, and US leadership"
    assert candidate("Chicago.SerialComma", "odd text", get("chicago")) is None


def test_number_candidates():
    rep, rule = candidate("Chicago.Numbers", " 10 ", get("chicago"))
    assert rep == " ten " and "percentages" in rule
    assert candidate("GPO.Numbers", " 10 ", get("gpo")) is None      # numerals from 10
    assert candidate("GPO.Numbers", " 4 ", get("gpo"))[0] == " four "


def test_find_series_handles_markup_entities_numbers():
    from adjudicate import apply_edits
    from stylefix.styleitems import find_series
    text = ("Labs must monitor, detect, and correct&#32;**unsanctioned AI actions**. "
            "Undermined by **inadequate 1) cybersecurity, 2) model containment, or 3) monitoring** of harm. "
            "Defences, more trustworthy and reliable products, financial stability, and more predictable deployments. "
            "Reviewed the budget, and the timeline.\n")
    found = find_series(text, get("guardian"))
    cands = [f.candidate for f in found]
    assert any("monitor, detect and correct&#32;**unsanctioned" in c for c in cands)
    assert any("2) model containment or 3) monitoring" in c for c in cands)
    assert any("financial stability and more predictable" in c for c in cands)
    new, skipped = apply_edits(text, [f.edit for f in found])
    assert not skipped
    assert "monitor, detect and correct&#32;**unsanctioned AI actions**." in new
    assert "**inadequate 1) cybersecurity, 2) model containment or 3) monitoring**" in new
    assert "Reviewed the budget, and the timeline" in new          # two items: not a series
    # the reverse direction
    found = find_series(new, get("chicago"))
    new2, skipped = apply_edits(new, [f.edit for f in found])
    assert not skipped and "monitor, detect, and correct&#32;**unsanctioned" in new2
    assert "2) model containment, or 3) monitoring**" in new2
