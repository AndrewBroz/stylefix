from stylefix.styleguides import get
from stylefix.styleitems import candidate, number_words


def test_number_words():
    assert [number_words(n) for n in (1, 10, 15, 20, 21, 99, 100)] == \
        ["one", "ten", "fifteen", "twenty", "twenty-one", "ninety-nine", "one hundred"]


def test_serial_comma_candidates():
    rep, rule = candidate("Chicago.SerialComma", "attacks, intentional and unintentional", get("chicago"))
    assert rep == "attacks, intentional, and unintentional" and "KEEP only if" in rule
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


def test_guardian_oxford_comma_follows_the_guide():
    """The three verdicts from the memo, scored against the Guardian entry."""
    g = get("guardian")
    # compound item adjacent to the final 'and': kept, mechanically
    assert candidate("Guardian.SerialComma",
                     "for defection on model development and release safety, including potential "
                     "tariffs and sanctions, and gating chip access on compliance", g) is None
    # an 'and' inside the LAST item: straightforward list, comma offered for removal
    rep, rule = candidate("Guardian.SerialComma",
                          "leak financial data, jeopardize stock market stability, and damage the US AI "
                          "advantage and reputation", g)
    assert rep.endswith("stability and damage the US AI advantage and reputation")
    # an 'and' in the FIRST item: straightforward list
    rep, rule = candidate("Guardian.SerialComma",
                          "more trustworthy and reliable consumer products, financial stability, and "
                          "more predictable AI deployments", g)
    assert rep.endswith("financial stability and more predictable AI deployments")
    assert "Martin Amis" in rule and "toast and marmalade" in rule
    # the guide's own examples
    assert candidate("Guardian.SerialComma", "cereal, kippers, bacon, eggs, toast and marmalade, and tea", g) is None
    rep, _ = candidate("Guardian.SerialComma", "ham, eggs, and chips", g)
    assert rep == "ham, eggs and chips"


def test_series_items_skip_mechanically_settled_cases():
    from stylefix.styleitems import series_items
    text = "He ate cereal, kippers, toast and marmalade, and tea. Then ham, eggs, and chips.\n"
    items, edits = series_items(text, get("guardian"))
    assert [i.word for i in items] == ["Then ham, eggs, and chips"]


def test_two_series_in_one_sentence():
    from adjudicate import apply_edits
    from stylefix.styleitems import find_series
    text = ("Procedures that create alerts, halting, and correction mechanisms during frontier AI "
            "training, testing, and deployment. Red, white, and blue; salt, pepper, and oil.\n")
    found = find_series(text, get("guardian"))
    assert len(found) == 4
    new, skipped = apply_edits(text, [f.edit for f in found])
    assert not skipped
    assert new == ("Procedures that create alerts, halting and correction mechanisms during frontier AI "
                   "training, testing and deployment. Red, white and blue; salt, pepper and oil.\n")
    back = find_series(new, get("chicago"))
    assert len(back) == 4
    new2, skipped = apply_edits(new, [f.edit for f in back])
    assert not skipped and new2 == text


def test_require_rule_states_the_grammar():
    rep, rule = candidate("Chicago.SerialComma", "create alerts, halting and correction mechanisms", get("chicago"))
    assert rep == "create alerts, halting, and correction mechanisms"
    assert "two-item series has no comma" in rule and "6.19" in rule
    assert "attacks, intentional and unintentional" in rule


def test_paired_question_words_are_not_a_series():
    from stylefix.styleitems import find_series
    text = ("It will include which organizations to involve, how and under what conditions reporting "
            "is shared, and at which parts levers will be deployed. Decide when and where to meet, who "
            "and why. Ham, eggs and chips.\n")
    found = find_series(text, get("chicago"))
    assert [f.candidate[-20:] for f in found] == ["ham, eggs, and chips".title()[-20:]] or \
        [f.text for f in found] == ["Ham, eggs and chips"]
