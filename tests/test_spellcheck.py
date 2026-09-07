from stylefix.spellcheck import review_spellings


def test_flags_only_other_variety_marker_words():
    text = "The flavour and glamour of the theatre; `colour` in code. Otherwise incentivized.\n"
    us = review_spellings(text, "us")
    words = {a.match for a in us}
    assert "theatre" in words and "flavour" in words
    assert "glamour" not in words            # valid US
    assert "incentivized" not in words       # not a UK marker word, and fine
    assert "colour" not in words             # inside code
    uk = review_spellings("The color of the center was honored.\n", "uk")
    assert {a.match for a in uk} == {"color", "center", "honored"}


def test_accept_and_dedupe():
    text = "colour colour colour\n"
    assert len(review_spellings(text, "us")) == 1
    assert review_spellings(text, "us", {"colour"}) == []


def test_l_forms_use_stem_rule():
    uk = review_spellings("They traveled, controlled, sailed, paralleled and modeled.\n", "uk")
    assert {a.match for a in uk} == {"traveled", "modeled"}


def test_inflected_forms_valid_in_target_are_not_flagged():
    us = review_spellings("Compromising measures were honoured and centred.\n", "us")
    assert {a.match for a in us} == {"honoured", "centred"}
