import pytest

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
    # A line-end dash is normalised in place; the line break stays (it used to
    # join "x—next", which broke callouts, fences and headings on the next line).
    assert us == "one—two—three—four, pages 5–6, x—\nnext, and a\n\n---\n\nrule 2020–21.\n"
    assert st.dashes == 3
    uk, _ = normalize("one -- two—three – four --\nnext\n", "uk", "oxford")
    assert uk == "one – two – three – four –\nnext\n"


@pytest.mark.parametrize("src, us, uk", [
    ("> He paused —\n> then spoke.\n", "> He paused—\n> then spoke.\n", "> He paused –\n> then spoke.\n"),
    ("> [!note] Aside --\n> body\n", "> [!note] Aside—\n> body\n", "> [!note] Aside –\n> body\n"),
    ("Intro —\n```\ncode -- here\n```\n", "Intro—\n```\ncode -- here\n```\n", "Intro –\n```\ncode -- here\n```\n"),
    ("Text --\n# Heading\n", "Text—\n# Heading\n", "Text –\n# Heading\n"),
    ("Sum —\n$$\nx -- y\n$$\n", "Sum—\n$$\nx -- y\n$$\n", "Sum –\n$$\nx -- y\n$$\n"),
    ("Note --  \n%% aside -- %%\n", "Note—\n%% aside -- %%\n", "Note –\n%% aside -- %%\n"),
    ("- first item —\n- second -- item\n", "- first item—\n- second—item\n", "- first item –\n- second – item\n"),
    ("Table --\n| a -- b | c |\n|---|---|\n", "Table—\n| a—b | c |\n|---|---|\n",
     "Table –\n| a – b | c |\n|---|---|\n"),
    ("Pipe —\n|\n", "Pipe—\n|\n", "Pipe –\n|\n"),
    ("He paused\n— then spoke.\n", "He paused\n—then spoke.\n", "He paused\n– then spoke.\n"),
    ("Intro\n    -- indented start\n", "Intro\n    —indented start\n", "Intro\n    – indented start\n"),
])
def test_dash_never_joins_lines(src, us, uk):
    assert normalize(src, "us", "chicago")[0] == us
    assert normalize(src, "uk", "oxford")[0] == uk


def test_indented_code_block_is_left_alone():
    # four spaces at the start of the text, or after a blank line, is an indented code block
    for src in ("    -- indented start\n", "Intro.\n\n    a -- b\n"):
        assert normalize(src, "us", "chicago")[0] == src
        assert normalize(src, "uk", "oxford")[0] == src


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


def _xfail(text, us, uk, reason):
    return pytest.param(text, us, uk, marks=pytest.mark.xfail(reason=reason, strict=True))


# (input, US output, UK output). Spans of two kinds: word-like ones (wikilinks, inline
# code, #tags, inline maths, entities, link targets, URLs) read as a word; boundary-like
# ones (front matter, fences, block maths, %% comments, HTML tags, comments and
# autolinks, callouts) read as a boundary, after which a quote opens unless what
# follows ends a phrase.
ROWS = [
    ('He called it "[[Note]]".', 'He called it “[[Note]]”.', 'He called it ‘[[Note]]’.'),
    ('He called it "[[Note]]", then left.', 'He called it “[[Note]]”, then left.', 'He called it ‘[[Note]]’, then left.'),
    ('Run "`ls`" now.', 'Run “`ls`” now.', 'Run ‘`ls`’ now.'),
    ('Type "`ls`".', 'Type “`ls`”.', 'Type ‘`ls`’.'),
    ('Tagged "#draft" today.', 'Tagged “#draft” today.', 'Tagged ‘#draft’ today.'),
    ('Tagged "#draft".', 'Tagged “#draft”.', 'Tagged ‘#draft’.'),
    ('See "$x^2$" here.', 'See “$x^2$” here.', 'See ‘$x^2$’ here.'),
    ('Visit "<https://x.y>".', 'Visit “<https://x.y>”.', 'Visit ‘<https://x.y>’.'),
    _xfail('Visit "https://x.y" now.', 'Visit “https://x.y” now.', 'Visit ‘https://x.y’ now.',
           'the URL span (adjudicate _URL) swallows the closing quote, so it is protected text'),
    ('"Read <b>this</b>" she said.', '“Read <b>this</b>” she said.', '‘Read <b>this</b>’ she said.'),
    ('"Read <b>this</b>," she said.', '“Read <b>this</b>,” she said.', '‘Read <b>this</b>,’ she said.'),
    ('"Read <b>this</b>." She left.', '“Read <b>this</b>.” She left.', '‘Read <b>this</b>.’ She left.'),
    ('"See [[A]]" today.', '“See [[A]]” today.', '‘See [[A]]’ today.'),
    ('"See [[A]]"—then go.', '“See [[A]]”—then go.', '‘See [[A]]’—then go.'),
    ('"See [[A]]"\nNext line.', '“See [[A]]”\nNext line.', '‘See [[A]]’\nNext line.'),
    ('He said "see [[A]]"', 'He said “see [[A]]”', 'He said ‘see [[A]]’'),
    ('"see `x`"!', '“see `x`”!', '‘see `x`’!'),
    ('"[[A]]"?', '“[[A]]”?', '‘[[A]]’?'),
    ('"Use &amp;" ok', '“Use &amp;” ok', '‘Use &amp;’ ok'),
    ('("[[A]]")', '(“[[A]]”)', '(‘[[A]]’)'),
    ('<b>"Hello"</b>', '<b>“Hello”</b>', '<b>‘Hello’</b>'),
    ('<em>"2024"</em> was', '<em>“2024”</em> was', '<em>‘2024’</em> was'),
    ('<b>"[[A]]"</b>', '<b>“[[A]]”</b>', '<b>‘[[A]]’</b>'),
    ('<i>"`x`"</i>', '<i>“`x`”</i>', '<i>‘`x`’</i>'),
    ('<b>"…and"</b>', '<b>“…and”</b>', '<b>‘…and’</b>'),
    ('<p>"Élan" is</p>', '<p>“Élan” is</p>', '<p>‘Élan’ is</p>'),
    ('<br>"Yes."', '<br>“Yes.”', '<br>‘Yes.’'),
    ('---\ntitle: x\n---\n"Hello"', '---\ntitle: x\n---\n“Hello”', '---\ntitle: x\n---\n‘Hello’'),
    ('---\ntitle: x\n---\n"[[A]]" is a note.', '---\ntitle: x\n---\n“[[A]]” is a note.', '---\ntitle: x\n---\n‘[[A]]’ is a note.'),
    _xfail("---\ntitle: x\n---\n'Tis the season.", '---\ntitle: x\n---\n’Tis the season.', '---\ntitle: x\n---\n’Tis the season.',
           "a leading apostrophe ('Tis, 'twas) is curled as an opening quote, as at any line start"),
    ('```\nx\n```\n"Hello," she said.', '```\nx\n```\n“Hello,” she said.', '```\nx\n```\n‘Hello,’ she said.'),
    ('```\nx\n```\n\n"Hello," she said.', '```\nx\n```\n\n“Hello,” she said.', '```\nx\n```\n\n‘Hello,’ she said.'),
    ('```\nx\n```\n"[[A]]" is good.', '```\nx\n```\n“[[A]]” is good.', '```\nx\n```\n‘[[A]]’ is good.'),
    ('%%c%%"Hi"', '%%c%%“Hi”', '%%c%%‘Hi’'),
    ('<!-- c -->"Hi"', '<!-- c -->“Hi”', '<!-- c -->‘Hi’'),
    ('> [!note] "Hi," she said.', '> [!note] “Hi,” she said.', '> [!note] ‘Hi,’ she said.'),
    ('> [!note]\n> "Hi"', '> [!note]\n> “Hi”', '> [!note]\n> ‘Hi’'),
    ("[[A]]'s idea", '[[A]]’s idea', '[[A]]’s idea'),
    ("`x`'s value", '`x`’s value', '`x`’s value'),
    ("#tag's use", '#tag’s use', '#tag’s use'),
    _xfail("<b>Bob</b>'s car", '<b>Bob</b>’s car', '<b>Bob</b>’s car',
           'HTML tags are boundary-like, so a quote after </b> followed by a letter opens'),
    ("$x$'s value", '$x$’s value', '$x$’s value'),
    ("the [[Smiths]]' house", 'the [[Smiths]]’ house', 'the [[Smiths]]’ house'),
    ("the `foo`s' values", 'the `foo`s’ values', 'the `foo`s’ values'),
    ('He ran `x`\n"Hello," she said.', 'He ran `x`\n“Hello,” she said.', 'He ran `x`\n‘Hello,’ she said.'),
    ('See [[A]]\n"Hello," she said.', 'See [[A]]\n“Hello,” she said.', 'See [[A]]\n‘Hello,’ she said.'),
    ('"quoted `x`\n" end', '“quoted `x`\n” end', '‘quoted `x`\n’ end'),
    ('"He said `x`\n"', '“He said `x`\n”', '‘He said `x`\n’'),
    _xfail('"line one [[A]]\n"Second," she said.', '“line one [[A]]\n“Second,” she said.', '‘line one [[A]]\n‘Second,’ she said.',
           'a single newline does not end a quotation, so the second quote nests, as in plain text'),
    ('"He said \'see [[A]]\' today"', '“He said ‘see [[A]]’ today”', '‘He said “see [[A]]” today’'),
    ('"He said \'see [[A]]\'"', '“He said ‘see [[A]]’”', '‘He said “see [[A]]”’'),
    ('"He said \'see `x`.\'"', '“He said ‘see `x`.’”', '‘He said “see `x`.”’'),
    ('"[[A]] is" fine', '“[[A]] is” fine', '‘[[A]] is’ fine'),
    ('"`x` is" fine', '“`x` is” fine', '‘`x` is’ fine'),
    ('"#tag is" fine', '“#tag is” fine', '‘#tag is’ fine'),
    ('x "<b>bold</b>" y', 'x “<b>bold</b>” y', 'x ‘<b>bold</b>’ y'),
    ("'[[A]]'", '“[[A]]”', '‘[[A]]’'),
    ("Call it '`x`'.", 'Call it “`x`”.', 'Call it ‘`x`’.'),
    ("<b>'Hi'</b>", '<b>“Hi”</b>', '<b>‘Hi’</b>'),
    ("'#tag', she said", '“#tag”, she said', '‘#tag’, she said'),
    ("'see [[A]]' today", '“see [[A]]” today', '‘see [[A]]’ today'),
    ('["colour"](url)', '[“colour”](url)', '[‘colour’](url)'),
    ('["colour"](https://x.y) is', '[“colour”](https://x.y) is', '[‘colour’](https://x.y) is'),
    ('[the "colour" page](url)', '[the “colour” page](url)', '[the ‘colour’ page](url)'),
    ('"[colour](url)" here', '“[colour](url)” here', '‘[colour](url)’ here'),
    ('"see [colour](url)" here', '“see [colour](url)” here', '‘see [colour](url)’ here'),
    ('[x](url)"Hi"', '[x](url)“Hi”', '[x](url)‘Hi’'),
    ('"see [x](url)"', '“see [x](url)”', '‘see [x](url)’'),
    _xfail('"[[A]]""[[B]]"', '“[[A]]”“[[B]]”', '‘[[A]]’‘[[B]]’',
           'a quote right after a closing quote closes, as in plain text ("a""b")'),
    ('[[A]]"Hello" said', '[[A]]“Hello” said', '[[A]]‘Hello’ said'),
    ('"[[Note]]"', '“[[Note]]”', '‘[[Note]]’'),
    ('"$x$"', '“$x$”', '‘$x$’'),
    ('He said "[[Programme Notes]]".', 'He said “[[Programme Notes]]”.', 'He said ‘[[Programme Notes]]’.'),
    ('---\ntitle: x\n---\n"Hello," she said.', '---\ntitle: x\n---\n“Hello,” she said.', '---\ntitle: x\n---\n‘Hello,’ she said.'),
    ('<b>"bold"</b>', '<b>“bold”</b>', '<b>‘bold’</b>'),
    ('Say <em>"hi"</em>.', 'Say <em>“hi”</em>.', 'Say <em>‘hi’</em>.'),
    ('said. <br>"Bye," she said.', 'said. <br>“Bye,” she said.', 'said. <br>‘Bye,’ she said.'),
    ('<https://x.y>"quoted"', '<https://x.y>“quoted”', '<https://x.y>‘quoted’'),
    ('"see <b>this</b>" ok', '“see <b>this</b>” ok', '‘see <b>this</b>’ ok'),
    ('"<https://x.y>" z', '“<https://x.y>” z', '‘<https://x.y>’ z'),
    ('"a <i>b</i>" and \'c\'', '“a <i>b</i>” and “c”', '‘a <i>b</i>’ and ‘c’'),
    ('"code `x`" end', '“code `x`” end', '‘code `x`’ end'),
    ('"line\n```\nx\n```\n" end', '“line\n```\nx\n```\n” end', '‘line\n```\nx\n```\n’ end'),
    ("'#tag'", '“#tag”', '‘#tag’'),
    ('"[[Note]]" and "word"', '“[[Note]]” and “word”', '‘[[Note]]’ and ‘word’'),
    ("I like [[Obsidian]]'s graph view.", "I like [[Obsidian]]’s graph view.", "I like [[Obsidian]]’s graph view."),
    ('---\na: 1\n---\n"[[Home]]" is the index.', '---\na: 1\n---\n“[[Home]]” is the index.', '---\na: 1\n---\n‘[[Home]]’ is the index.'),
]


@pytest.mark.parametrize("target", ["us", "uk"])
@pytest.mark.parametrize("text, us, uk", ROWS)
def test_quote_direction_around_protected_spans(text, us, uk, target):
    want = us if target == "us" else uk
    assert normalize(text + "\n", target)[0] == want + "\n"


@pytest.mark.parametrize("target", ["us", "uk"])
@pytest.mark.parametrize("text", ["| A | B |\n|--|--|\n| x | y |\n",
                                  "| A | B |\n| -- | :--: |\n| x | y |\n",
                                  "- -- dashed item\n", "> -- quoted aside\n", "1. -- numbered\n",
                                  "---\n", "- - -\n"])
def test_markdown_structure_survives_dashes(text, target):
    out, _ = normalize(text, target, "chicago" if target == "us" else "oxford")
    for line_in, line_out in zip(text.splitlines(), out.splitlines()):
        marker = line_in.split(" ", 1)[0]
        assert line_out.startswith(marker + " ") or line_out == line_in   # marker and its space kept
    if text.startswith(("|", "---", "- - -")):
        assert out == text                                                 # delimiter rows, rules untouched
