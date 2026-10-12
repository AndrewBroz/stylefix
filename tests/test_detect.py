from stylefix.api import Detection, detect_variety


def test_british_note():
    d = detect_variety("We recieved the new colour scheme. The programme is on track. Finalise the licence.\n")
    assert d.target == "uk" and d.uk >= 2 and d.us == 0


def test_american_note():
    d = detect_variety("The color scheme and the behavior at the center are organized.\n")
    assert d.target == "us" and d.us >= 2


def test_mixed_and_empty_are_undecided():
    assert detect_variety("The colour of the program.\n").target is None      # 1 v 1
    assert detect_variety("Nothing to see here.\n") == Detection(None, 0, 0)


def test_threshold_edges():
    assert detect_variety("colour, honour, flavor.\n").target == "uk"          # 2 v 1
    assert detect_variety("colour, honour, flavor, color.\n").target is None   # 2 v 2


def test_quotes_code_and_repeats_dont_count():
    text = 'He wrote "colour and honour".\n\n`colour honour`\n\ncolour colour colour\n'
    d = detect_variety(text)
    assert d.uk <= 1 and d.target is None


def test_capitalised_and_accepted_words_dont_count():
    assert detect_variety("Colour Corp and Honour Ltd.\n").target is None
    assert detect_variety("colour honour\n", accept=["colour", "honour"]).target is None


def test_shared_words_are_not_evidence():
    d = detect_variety("Good practice: check the draft story before the programme review. "
                       "We licence the software and the neighbour's colour is grey.\n")
    assert d.target == "uk"
    d = detect_variety("I practise the guitar. Check the story, the draft, and the program. "
                       "The programme colours were organised.\n")
    assert d.target == "uk"
    d = detect_variety("Install the program and write to the disk. Practice the license steps. "
                       "Check the program log, the analog output, the catalog, and the cheque.\n")
    assert d.target != "us"


def test_indented_code_block_doesnt_count():
    assert detect_variety("Intro.\n\n    colour honour\n\nEnd.\n").uk == 0
