from stylefix.conventions import normalize, prose_regions


def test_protected_regions():
    text = '---\ntitle: "x"\n---\nsay "hi" `"code"` and\n\n```\n"block"\n```\n[t](http://a.b/"q") http://x.y/"z"\n'
    out, _ = normalize(text, "us", "chicago")
    assert out.startswith('---\ntitle: "x"\n---\n')
    assert '`"code"`' in out and '"block"' in out
    assert 'http://a.b/"q"' in out and 'http://x.y/"z"' in out
    assert "say “hi”" in out


def test_us_curly_double_primary_and_nested():
    text = "She said 'he called it \"done\" then', and left.\n"
    out, stats = normalize(text, "us", "chicago")
    assert out == "She said “he called it ‘done’ then,” and left.\n"
    assert stats.punctuation_moved == 1


def test_uk_single_primary_no_punctuation_move():
    text = 'She said "he called it \'done\' then", and left.\n'
    out, _ = normalize(text, "uk", "oxford")
    assert out == "She said ‘he called it “done” then’, and left.\n"


def test_apostrophes_survive():
    text = "It's the Joneses' house, don't say 'no' to the '90s.\n"
    out, _ = normalize(text, "uk", "oxford")
    assert out == "It’s the Joneses’ house, don’t say ‘no’ to the ’90s.\n"


def test_ranges_and_dates():
    us, _ = normalize("pages 10-20, on 4 September 2026 and 2026-09-04.\n", "us", "chicago")
    assert us == "pages 10–20, on September 4, 2026 and 2026-09-04.\n"
    uk, _ = normalize("on September 4, 2026 and Sept 4, 2026.\n", "uk", "oxford")
    assert uk == "on 4 September 2026 and Sept 4, 2026.\n"


def test_already_curly_double_to_uk_single():
    out, _ = normalize("He said “that’s ‘fine’ by me”.\n", "uk", "oxford")
    assert out == "He said ‘that’s “fine” by me’.\n"


def test_dashes_chicago_and_oxford():
    src = "one -- two—three – four, pages 5–6, x --\nnext, and a\n\n---\n\nrule 2020-21.\n"
    us, st = normalize(src, "us", "chicago")
    assert us == "one—two—three—four, pages 5–6, x—next, and a\n\n---\n\nrule 2020–21.\n"
    assert st.dashes == 3
    uk, _ = normalize("one -- two—three – four --\nnext\n", "uk", "oxford")
    assert uk == "one – two – three – four – next\n"


def test_html_comments_and_tags_are_protected():
    src = "<!-- note -- keep -->\nvalue -- here\n<a href=\"x--y\">it's</a>\n"
    out, _ = normalize(src, "us", "chicago")
    assert out == "<!-- note -- keep -->\nvalue—here\n<a href=\"x--y\">it’s</a>\n"


def test_quotes_next_to_protected_text_keep_their_direction():
    for text, want in [('"[[Note]]"', "“[[Note]]”"), ('"$x$"', "“$x$”"),
                       ('"word"', "“word”"), ('He said "[[Programme Notes]]".', "He said “[[Programme Notes]]”.")]:
        out, _ = normalize(text + "\n", "us")
        assert out == want + "\n", (text, out)


def test_single_quotes_around_a_tag():
    assert normalize("'#tag'\n", "uk")[0] == "‘#tag’\n"
    assert normalize("'#tag'\n", "us")[0] == "“#tag”\n"


def test_uk_single_primary_across_a_construct():
    out, _ = normalize('"[[Note]]" and "word"\n', "uk")
    assert out == "‘[[Note]]’ and ‘word’\n"


def test_dash_beside_protected_quotes():
    out, _ = normalize('Read "#draft" and "$x$" -- now.\n', "us", "chicago")
    assert out == "Read “#draft” and “$x$”—now.\n"


def test_quote_after_a_line_start_or_tag_opens():
    for text, want in [('---\ntitle: x\n---\n"Hello," she said.\n', '---\ntitle: x\n---\n“Hello,” she said.\n'),
                       ('<b>"bold"</b>\n', "<b>“bold”</b>\n"),
                       ('Say <em>"hi"</em>.\n', "Say <em>“hi”</em>.\n"),
                       ('said. <br>"Bye," she said.\n', "said. <br>“Bye,” she said.\n"),
                       ('<https://x.y>"quoted"\n', "<https://x.y>“quoted”\n")]:
        assert normalize(text, "us")[0] == want, text
