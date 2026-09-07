from adjudicate import apply_edits

from stylefix.abbreviations import plan


def run(text, guide):
    edits, items = plan(text, guide)
    new, skipped = apply_edits(text, edits)
    assert not skipped
    return new, items


def test_chicago_drops_periods():
    new, items = run("The U.S. and the U.K. agree. In the U.S., yes. Ph.D. holders at 10 am, vs the EU, e.g. Britain.\n", "chicago")
    assert new == "The US and the UK agree. In the US, yes. PhD holders at 10 a.m., vs. the EU, e.g. Britain.\n"
    assert items == []


def test_sentence_end_when_dropping():
    text = "We live in the U.S. The policy is U.S. Policy. Done in the U.S.\n"
    new, items = run(text, "chicago")
    assert new.endswith("Done in the US.\n")                    # paragraph end: period restored
    assert [(i.word, i.options) for i in items] == [("U.S.", ("US.", "US", "KEEP"))] * 2


def test_ap_keeps_periods_and_absorbs_sentence_period():
    new, items = run("US policy in the US. Next, the UK and a PhD at 3pm vs Rome, etc\n", "ap")
    assert new == "U.S. policy in the U.S. Next, the U.K. and a Ph.D. at 3 p.m. vs. Rome, etc.\n"


def test_guardian_forms():
    new, _ = run("At 10 a.m. the U.S. side, e.g. Ohio, etc., won vs. Rome.\n", "guardian")
    assert new == "At 10am the US side, eg Ohio, etc, won v Rome.\n"


def test_none_and_protection():
    text = "U.S. in `U.S.` code and [U.S. link](http://x.y/U.S.).\n"
    assert run(text, "none") == (text, [])
    new, _ = run(text, "chicago")
    assert new == "US in `U.S.` code and [US link](http://x.y/U.S.).\n"
