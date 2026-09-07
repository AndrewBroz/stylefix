from stylefix.adjudicate import Decision, Item
from stylefix.apply import Edit
from stylefix.changelog import render
from stylefix.conventions import Stats


def test_changelog_lists_edits_with_context():
    text = "The colour of the licence plate.\n"
    edits = [Edit(1, 5, 10, "colour", "color", "ToUS.Variants"),
             Edit(1, 19, 25, "licence", "license", "adjudicated")]
    item = Item(1, "licence", ("license", "licence", "KEEP"), "r", "ctx", 1, 19, 25)
    decisions = [Decision(item, "license", 0.93, "noun, US collapses both")]
    out = render(text=text, target="us", applied=edits, decisions=decisions,
                 stats=Stats(quotes=2, dashes=1))
    assert "2 word edit(s)" in out
    assert "L1    colour -> color          auto" in out
    assert "The [colour] of the licence plate." in out
    assert "licence -> license        model 0.93: noun" in out
    assert "punctuation: quotes 2, dashes 1" in out


def test_changelog_reports_kept_and_undecided():
    item = Item(1, "check", ("cheque", "check", "KEEP"), "r", "ctx", 3, 1, 5)
    ds = [Decision(item, "check", 0.9, "verb"), Decision(item, None, 0.0, "no model configured")]
    out = render(text="x\n\ncheck it\n", target="uk", applied=[], decisions=ds, stats=Stats())
    assert "kept after adjudication: 1" in out and "0.90: verb" in out
    assert "undecided (left as is, see report): 1" in out and "no model configured" in out
