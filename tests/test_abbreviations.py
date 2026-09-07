from adjudicate import apply_edits

from stylefix.abbreviations import plan


def run(text, guide, nouns="default"):
    edits, items, warnings = plan(text, guide, nouns)
    new, skipped = apply_edits(text, edits)
    assert not skipped
    return new, items, warnings


def test_chicago_drops_periods_generally():
    new, items, _ = run("The U.S. and the U.K. agree; the E.U. and N.A.T.O. too. Ph.D. holders at 10 am, "
                        "vs the EU, e.g. Britain, in Washington, D.C., since 44 B.C.\n", "chicago")
    assert new == ("The US and the UK agree; the EU and NATO too. PhD holders at 10 a.m., vs. the EU, "
                   "e.g. Britain, in Washington, DC, since 44 BC.\n")
    assert items == []


def test_drop_adjudicates_capital_follows_and_initials():
    text = "We live in the U.S. The policy is U.S. Policy. Written by J.K. Rowling. Done in the U.S.\n"
    new, items, _ = run(text, "chicago")
    assert new.endswith("Done in the US.\n")
    assert [(i.word, i.options) for i in items] == [("U.S.", ("US.", "US", "KEEP"))] * 2 + \
        [("J.K.", ("JK.", "JK", "KEEP"))]
    assert "initials" in items[2].rule


def test_ap_keeps_by_category():
    new, items, w = run("US policy in the US. The UK, a PhD, an MA, AI and IT staff at 3pm vs Rome, "
                        "the EU, in DC, etc\n", "ap")
    assert new == ("U.S. policy in the U.S. The U.K., a Ph.D., an M.A., AI and IT staff at 3 p.m. vs. "
                   "Rome, the EU, in D.C., etc.\n")
    assert items == [] and w == []


def test_apa_keeps_countries_not_degrees_and_warns_on_nouns():
    new, items, w = run("The US has a Ph.D. program; the US economy grows.\n", "apa")
    assert new == "The U.S. has a PhD program; the U.S. economy grows.\n"
    assert len(w) == 1 and "US has" in w[0][1]


def test_gpo_noun_enforcement_items():
    text = "The US has grown. The US economy grew. Exports to the US rose.\n"
    new, items, w = run(text, "gpo", "enforce")
    assert [i.options for i in items] == [("United States", "U.S.", "KEEP")] * 3
    assert new == text and w == []           # the item decides both the noun and the periods


def test_noun_rule_off_and_other_guides():
    new, items, w = run("The US has grown.\n", "gpo", "off")
    assert new == "The U.S. has grown.\n" and w == []
    new, items, w = run("The US has grown.\n", "chicago")
    assert w == []


def test_guardian_and_none_and_protection():
    new, _, _ = run("At 10 a.m. the U.S. side, e.g. Ohio, etc., won vs. Rome.\n", "guardian")
    assert new == "At 10am the US side, eg Ohio, etc, won v Rome.\n"
    text = "U.S. in `U.S.` code and [U.S. link](http://x.y/U.S.).\n"
    assert run(text, "none")[0] == text
    assert run(text, "chicago")[0] == "US in `U.S.` code and [US link](http://x.y/U.S.).\n"
