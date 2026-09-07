from stylefix import wordlist


def test_generated_styles_are_up_to_date(tmp_path):
    wordlist.write_styles(tmp_path)
    for rel in ("ToUS/Variants.yml", "ToUK/Variants.yml", "ToUK/Ise.yml"):
        assert (tmp_path / rel).read_text() == (wordlist.STYLES_DIR / rel).read_text(), \
            f"{rel} is stale: run `python -m stylefix.wordlist`"


def test_asymmetric_words_only_go_one_way():
    us = wordlist.to_us_map()
    uk = wordlist.to_uk_map()
    assert us["licence"] == "license" and "license" not in uk
    assert us["programme"] == "program" and "program" not in uk
    assert us["practising"] == "practicing" and uk["practicing"] == "practising"
    assert "practice" not in uk
    assert "disc" not in us and "disk" not in uk
    assert uk["mold"] == "mould"


def test_inflections():
    assert wordlist.inflect("centre", "center", "re") == [
        ("centre", "center"), ("centres", "centers"), ("centred", "centered"), ("centring", "centering")]
    assert ("travelling", "traveling") in wordlist.inflect("travel", "travel", "ll")
    assert ("analysing", "analyzing") in wordlist.inflect("analyse", "analyze", "yse")
    assert ("analyses", "analyzes") not in wordlist.inflect("analyse", "analyze", "yse")


def test_oxford_ize_split():
    assert "organise" in wordlist.to_uk_map(ise=True).values()
    assert "organize" not in wordlist.to_uk_map(ise=False)
    assert wordlist.to_uk_map(ise=False)["analyze"] == "analyse"


def test_accept_list_does_not_shadow_word_table():
    """A word in accept.txt is never flagged, so it must not be one that the
    US/UK tables convert; otherwise the conversion is silently suppressed."""
    from pathlib import Path
    accept = {l.strip().lower() for l in (wordlist.STYLES_DIR.parent / "accept.txt").read_text().splitlines()
              if l.strip() and not l.startswith("#")}
    converted = set(wordlist.to_us_map()) | set(wordlist.to_uk_map(ise=True)) | set(wordlist.to_uk_map(ise=False))
    assert not (accept & converted), accept & converted
