# prosefix First-Run Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a new user's first `prosefix draft.md` right and useful: keep the note's own variety, show what needs review, fix the obvious faults even without the external tools, run fast on vaults, cut noise, and route every uncertain edit to the model or to review — never apply it silently.

**Architecture:** stylefix 0.8.1 adds `api.detect_variety`, date-aware numerals and two dash fixes. proofix 0.7.0 adds a pure-Python `basics` tier, three-route doubled-word handling (also for LanguageTool's repeat rule), an audit of every outright edit, a variety-aware LanguageTool rule filter, and a `LanguageToolServer` usable through `api.fix(lt_server=...)`. prosefix 0.2.0 uses detection when nothing sets a target, shows review items, consolidates the missing-capability lines, shares one LanguageTool server per run, adds context to change lines, and gets a friendlier `--help` and first-run tip. adjudicate 0.3.2 only if Task 3 finds the change-granularity fix belongs there.

**Tech Stack:** Python ≥3.11, the four sibling packages via editable uv path sources, LanguageTool's `languagetool-server` (HTTP, `/v2/check`), pytest, uv, hatchling, Homebrew.

**Spec:** `docs/superpowers/specs/2026-10-12-prosefix-first-run-design.md` (in stylefix). Read it — especially "The rule every tier follows", "Doubled words" and section 7 — before any task.

**Repos:** `/Users/andrewbroz/Code/{adjudicate,stylefix,proofix,prosefix,homebrew-tap}`, each on `master`, all pushed and released (adjudicate 0.3.1, stylefix 0.8.0, proofix 0.6.0, prosefix 0.1.0). Do the work on a branch `first-run` in each repo you change (create it from `master`; prosefix too). Commit messages end with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Use `set -o pipefail` when piping test output. Hands-on runs use scratch `XDG_CONFIG_HOME`/`XDG_CACHE_HOME` (never the user's real ones) and `--llm none` or `--llm cached`; to hide the external tools use `PATH=$(dirname $(uv run which python)):/usr/bin:/bin`.

## Global Constraints

- The three routes (spec): an edit is applied outright only if provably always right in prose; otherwise it is an adjudication item (sentence context, options always including `KEEP`) when a model is available, else a review item with its reason. Nothing uncertain is applied silently.
- Versions: stylefix `0.8.1`, proofix `0.7.0`, prosefix `0.2.0`, adjudicate `0.3.2` only if changed — in `pyproject.toml`, `__init__.py`, and man `.TH` where a man page exists (drift tests enforce it).
- Pins: proofix `adjudicate>=0.3.1,<0.4` (or `>=0.3.2` if adjudicate changed); prosefix `stylefix>=0.8.1,<0.9`, `proofix>=0.7,<0.8`, adjudicate as above.
- stylefix's and proofix's own CLIs behave as before except for the bug fixes named in the spec (dates, dashes, doubled words, the audit). proofix's CLI does not use a LanguageTool server.
- New tier name `basics` (proofix); prosefix `PROOF_TIERS` gains it.
- Detection thresholds exactly: `uk >= 2 and uk >= 2 * us` → uk; `us >= 2 and us >= 2 * uk` → us; else none.
- `target_source` values exactly: `flag`, `front matter`, `lang`, `project`, `detected`, `default`.
- Closed doubled-word list exactly: `a an the of to in on at for with from by into onto about and or but nor it we they my your our their`.
- LanguageTool server: `languagetool-server --port N` (never `--public`), started per prosefix run, stopped at exit including errors and Ctrl-C; 30 s start timeout; fallback to the command line with one stderr line.
- Messages (exact): tools line `prosefix: most fixes need Vale and LanguageTool — brew install andrewbroz/tap/prosefix (or: brew install <missing tools>)`; model line `prosefix: model decisions and comma placement need a model — prosefix --setup`; first-run tip `tip: prosefix --diff <path> shows changes without writing them`; server fallback `prosefix: LanguageTool server did not start (<reason>); using the command line`.
- Never write to the user's real `~/.config` or `~/.cache` in tests; conftest already isolates XDG and `*_LLM_*`.

## Review Focus

1. **A British note in a vault with a US project setting.** Expected: the project setting wins (no detection); the per-file line does not say "detected". Pinned in Task 6 (`test_project_target_beats_detection`).
2. **A note whose only variety evidence is inside quotes or code, or a single repeated word.** Expected: no detection (falls back to US with the "no clear variety" note). Pinned in Task 1 (`test_quotes_code_and_repeats_dont_count`).
3. **"How do you know that that is wrong?" with LanguageTool installed and no model.** Expected: unchanged text, a review item `repeated word 'that that'`. Pinned in Task 4 (`test_languagetool_repeat_outside_closed_list_is_reviewed`).
4. **`1,000`, `10:30`, `https://a.b/c,d`, `e.g.,` and `3:2` in a no-tools run.** Expected: untouched. Pinned in Task 4 (`test_basics_leaves_numbers_times_urls`).
5. **prosefix interrupted (exception mid-run) while the LanguageTool server is up.** Expected: the server process is gone afterwards. Pinned in Task 8 (`test_server_stopped_after_exception`).

---

### Task 1: stylefix — `detect_variety`

**Files:** Modify `stylefix/stylefix/api.py`; Test `stylefix/tests/test_detect.py` (create).

**Interfaces:**
- Produces: `stylefix.api.Detection` (frozen dataclass: `target: str | None`, `uk: int`, `us: int`) and `stylefix.api.detect_variety(text: str, accept: Iterable[str] = ()) -> Detection`.

- [ ] **Step 1: Failing tests** — `tests/test_detect.py`:

```python
from stylefix.api import Detection, detect_variety


def test_british_note():
    d = detect_variety("We recieved the new colour scheme. The programme is on track. Finalise the licence.\n")
    assert d.target == "uk" and d.uk >= 2 and d.us == 0


def test_american_note():
    d = detect_variety("The color scheme and the program are finalized. Check the license.\n")
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
```

- [ ] **Step 2: Run** `uv run pytest tests/test_detect.py -q` → ImportError.
- [ ] **Step 3: Implement** in `api.py`:

```python
@dataclass(frozen=True)
class Detection:
    target: str | None
    uk: int
    us: int


_DETECT_WORD = re.compile(r"[a-z]+(?:[’'][a-z]+)?")


@functools.lru_cache(maxsize=1)
def _variety_words() -> tuple[frozenset[str], frozenset[str]]:
    """Spellings VarCon gives to one variety and not the other."""
    uk, us = set(), set()
    for c in varcon.clusters():
        b, a = c.accepted("B"), c.accepted("A")
        uk |= b - a
        us |= a - b
    return frozenset(uk), frozenset(us)


def detect_variety(text: str, accept=()) -> Detection:
    """Which variety a text is written in, from words only one variety uses."""
    uk_words, us_words = _variety_words()
    skip = {w.lower() for w in accept}
    seen_uk, seen_us = set(), set()
    for s, e in prose_regions(text):
        for m in _DETECT_WORD.finditer(text, s, e):
            w = m.group(0)
            if w in skip or inside_quotes(text, m.start()):
                continue
            if w in uk_words:
                seen_uk.add(w)
            elif w in us_words:
                seen_us.add(w)
    uk, us = len(seen_uk), len(seen_us)
    if uk >= 2 and uk >= 2 * us:
        return Detection("uk", uk, us)
    if us >= 2 and us >= 2 * uk:
        return Detection("us", uk, us)
    return Detection(None, uk, us)
```

`_DETECT_WORD` matches lower-case only, so capitalised words never count. Imports: `functools`, `re`, `from . import varcon`, `from adjudicate import prose_regions, inside_quotes` (check the names `adjudicate` exports; `inside_quotes` lives in `adjudicate.context`). If a test word (`honour`, `flavor`, `finalise`) is not single-variety in VarCon, pick another clearly single-variety word in the test and say so.
- [ ] **Step 4: Run** the new tests, then the full stylefix suite (327 + 10 xfailed + new).
- [ ] **Step 5: Commit** (stylefix, branch `first-run`): `api.detect_variety: which variety a text is written in, from words only one variety uses`.

---

### Task 2: stylefix — numerals in dates, dash fixes; 0.8.1

**Files:** Modify `stylefix/stylefix/api.py` (`partition`, the `Numbers` branch), `stylefix/stylefix/conventions.py` (`_DASH` / `parenthetical_dashes`), `pyproject.toml`, `stylefix/__init__.py`, `man/stylefix.1`; Test `tests/test_api.py`, `tests/test_conventions.py`.

- [ ] **Step 1: Failing tests:**

```python
# tests/test_api.py
@pytest.mark.parametrize("text", ["It arrived on 3 September.\n", "Due September 3 at noon.\n",
                                  "Filed 3 Sept and 4 Oct.\n", "On 3/9/2026 we met.\n",
                                  "Since 2026-10-12.\n", "The 9th of May.\n"])
def test_numerals_in_dates_are_not_flagged(text):
    r = api.fix(text, api.Options(target="uk", style="oxford"), None, Cache(None))
    assert not [a for a in r.review_alerts if a.check.endswith("Numbers")]
    assert not [i for i in r.review if i.check.endswith("Numbers")]


def test_numerals_elsewhere_still_flagged():
    r = api.fix("We hired 3 people.\n", api.Options(target="uk", style="oxford"), None, Cache(None))
    assert [a for a in r.review_alerts if a.check.endswith("Numbers")]
```

```python
# tests/test_conventions.py
@pytest.mark.parametrize("target", ["us", "uk"])
@pytest.mark.parametrize("text", ["| A | B |\n|--|--|\n| x | y |\n",
                                  "| A | B |\n| -- | :--: |\n| x | y |\n",
                                  "- -- dashed item\n", "> -- quoted aside\n", "1. -- numbered\n"])
def test_markdown_structure_survives_dashes(text, target):
    out, _ = normalize(text, target, "chicago" if target == "us" else "oxford")
    for line_in, line_out in zip(text.splitlines(), out.splitlines()):
        marker = line_in.split(" ", 1)[0]
        assert line_out.startswith(marker + " ") or line_out == line_in   # marker and its space kept
    if text.startswith("|"):
        assert out == text                                                 # delimiter rows untouched
```

- [ ] **Step 2: Run** → the date cases and dash cases fail.
- [ ] **Step 3: Implement:**
  - In `partition`, before the `Numbers` branch builds an item or review alert, skip the alert when the matched numeral is next to a month name or inside a date:

```python
_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_DATE_BEFORE = re.compile(rf"\b{_MONTH}\s*$", re.I)
_DATE_AFTER = re.compile(rf"^\s*(?:(?:st|nd|rd|th)\b\s*)?(?:of\s+)?{_MONTH}\b", re.I)
_DATE_SHAPE = re.compile(r"\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}|\d+(?:st|nd|rd|th)\b")


def _is_date_numeral(text: str, s: int, e: int) -> bool:
    before, after = text[max(0, s - 16):s], text[e:e + 24]
    if _DATE_BEFORE.search(before) or _DATE_AFTER.match(after):
        return True
    window = text[max(0, s - 6):e + 8]
    return bool(_DATE_SHAPE.search(window))
```

    (`s`, `e` are the alert's offsets, computed as the branch already does; the Vale match includes surrounding spaces — strip them before calling.)
  - In `conventions.py`: a line that is a GFM table delimiter row (`^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$`) is skipped by the dash rule entirely; and the dash rule never consumes the whitespace after a list or quote marker at line start (`^\s*(?:[-*+]|\d+[.)]|>+)\s`): exclude that prefix from the text the rule sees (the same masking approach as protected spans, or by applying the rule per line to the part after the marker).
- [ ] **Step 4: Run** the new tests and the full suite; rerun the CLI captures from `/Users/andrewbroz/Code/stylefix/docs/superpowers/plans/2026-10-12-prosefix.md` Task 3 Step 0 (sample.md uk and us, `--llm none --dry-run --no-cache --changes`) against fresh `before` captures taken at the start of this task; explain every difference (only dates/dashes may change).
- [ ] **Step 5: Version 0.8.1** — pyproject, `__init__`, `.TH STYLEFIX 1 "October 2026" "stylefix 0.8.1" "User Commands"`; drift test passes.
- [ ] **Step 6: Commit**: `Numerals in dates are not flagged; dashes leave table delimiter rows and list/quote markers alone; v0.8.1`.

---

### Task 3: change granularity — "recieved the the" (adjudicate or proofix)

**Files:** to be determined by Step 1 (one of `adjudicate/adjudicate/changes.py` + `tests/test_changes.py`, or `proofix/proofix/api.py` + `tests/test_api.py`).

- [ ] **Step 1: Reproduce and locate.** With the external tools on PATH, in prosefix: run `engine.process` (or `prosefix - --json --llm none`) on `We recieved the the new colour scheme.\n` and print the changes. Then call `adjudicate.derive_changes(before, after, annotations)` directly with proofix's annotations for that sentence (print them from `proofix.api.fix`). Decide: if the annotations are right (`recieved`→`received` and `the `→`` as separate records) and `derive_changes` merges them into one hunk, the fix is in adjudicate; if proofix's records themselves are merged (one LanguageTool match covering both), the fix is in proofix (split the record, or annotate both parts). Write the finding in the report before coding.
- [ ] **Step 2: Failing test** in the owning repo: the sentence above yields two changes — one `recieved`→`received` labelled with its spelling source, one deleting `the ` labelled as a doubled word — and `apply_changes(before, changes) == after`.
- [ ] **Step 3: Implement** the smallest fix where Step 1 located it. In adjudicate, prefer: when a replace opcode's token range can be partitioned so that each part matches an annotation exactly (or by sub-hunk), emit one change per part.
- [ ] **Step 4: Run** the owning suite and prosefix's suite.
- [ ] **Step 5: Version** — if adjudicate changed: 0.3.2 (pyproject, `__init__`), and record that proofix/prosefix pins become `>=0.3.2`. Commit: `A typo next to a doubled word is two changes, each with its own label` (+ `; v0.3.2` if adjudicate).

---

### Task 4: proofix — `basics` tier and doubled-word routing

**Files:** Modify `proofix/proofix/tiers.py`, `proofix/proofix/api.py`; Create `proofix/proofix/basics.py`; Test `proofix/tests/test_basics.py`.

**Interfaces:**
- Produces: `proofix.basics.CLOSED_DOUBLES: frozenset[str]`; `basics.doubled_words(text, spans) -> list[Double]` (`Double(start, end, word, closed: bool)`, where `start..end` covers the second copy plus the separating space); `basics.spacing_edits(text, spans) -> list[Edit]`; `api.TIERS` gains `"basics"` (insert after `"mechanical"`); `Options` unchanged.

- [ ] **Step 1: Failing tests** — `tests/test_basics.py` (use the existing fake-endpoint pattern from `tests/test_api.py`; `run(text, ep=None, **kw)` helper calling `api.fix(text, api.Options(**kw), ep, Cache(None), CommaCache(None))` with tools hidden via `monkeypatch.setenv("PATH", "/nonexistent")` where the test needs "no LanguageTool"):

```python
def test_closed_list_doubles_fixed_without_model(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert run("We got the the scheme, most of of it.\n").text == "We got the scheme, most of it.\n"


@pytest.mark.parametrize("text", ["How do you know that that is wrong?\n", "What it is is unclear.\n",
                                  "I had had enough.\n", "It was very very good.\n"])
def test_other_doubles_reviewed_without_model(monkeypatch, text):
    monkeypatch.setenv("PATH", "/nonexistent")
    r = run(text)
    assert r.text == text
    assert any(i.kind == "undecided" or "repeated word" in i.message for i in r.review)


def test_other_doubles_adjudicated_with_model(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    keep = FakeEndpoint(choice="KEEP")
    assert run("How do you know that that is wrong?\n", ep=keep).text == "How do you know that that is wrong?\n"
    drop = FakeEndpoint(choice=1)          # option 1 = one copy
    assert run("It was very very good.\n", ep=drop).text == "It was very good.\n"


@pytest.mark.parametrize("text", ["We flew to Bora Bora.\n", "New York, New York is a song.\n",
                                  "- the\n- the\n", "# The\n\nthe end\n"])
def test_doubles_left_alone(monkeypatch, text):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert run(text).text == text


def test_basics_spacing(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert run("The programme , which covers analysis,design and testing.\n").text == \
        "The programme, which covers analysis, design and testing.\n"


@pytest.mark.parametrize("text", ["It cost 1,000 dollars at 10:30.\n", "See https://a.b/c,d now.\n",
                                  "A ratio of 3:2 holds, e.g., here.\n", "Wait ... then.\n", "`a ,b`\n"])
def test_basics_leaves_numbers_times_urls(monkeypatch, text):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert run(text).text == text


def test_basics_does_not_run_with_languagetool(monkeypatch):
    monkeypatch.setattr(api, "find_languagetool", lambda: "/replay/languagetool")
    monkeypatch.setattr(api, "run_languagetool", lambda *a, **k: [])     # LanguageTool "runs", finds nothing
    r = run("The the end , ok.\n")
    assert not [e for e in r.applied if e.source == "basics"]


def test_languagetool_repeat_outside_closed_list_is_reviewed(replay_lt_repeat):
    # replay a LanguageTool ENGLISH_WORD_REPEAT_RULE match on "that that", no model
    r = run("How do you know that that is wrong?\n")
    assert r.text == "How do you know that that is wrong?\n"
    assert any("repeated word 'that that'" in i.message for i in r.review)


def test_languagetool_repeat_in_closed_list_still_fixed(replay_lt_repeat_the):
    assert run("We got the the scheme.\n").text == "We got the scheme.\n"
```

Write the two `replay_lt_repeat*` fixtures like `tests/test_e2e.py`'s `replay_lt`, with a hand-written LanguageTool JSON match (`rule.id = ENGLISH_WORD_REPEAT_RULE`, offsets in UTF-16, `replacements = [{"value": "that"}]`). Write `test_basics_does_not_run_with_languagetool` fully (assert on `r.applied` sources). `FakeEndpoint(choice=...)` is a small subclass of `adjudicate.llm.Endpoint` whose `chat` returns `{"decisions":[{"id":<each id>,"choice":<choice>,"confidence":0.95,"reason":"t"}]}` for every item id in the prompt (reuse the one in `tests/test_api.py` if it fits).
- [ ] **Step 2: Run** → failures.
- [ ] **Step 3: Implement:**
  - `basics.py`:

```python
"""Pure-Python mechanical checks that run when LanguageTool does not."""

import re
from dataclasses import dataclass

from adjudicate import Edit

CLOSED_DOUBLES = frozenset("a an the of to in on at for with from by into onto about "
                           "and or but nor it we they my your our their".split())
_DOUBLE = re.compile(r"\b([A-Za-z]+)( |\n(?![ \t]*(?:[-*+>#|]|\d+[.)])))(\1)\b", re.I)
_SPACE_BEFORE = re.compile(r"(?<=\w)[ \t]+(?=[,;:!?]|\.(?!\.))")
_NO_SPACE_AFTER = re.compile(r"(?<=[A-Za-z])([,;:])(?=[A-Za-z])")


@dataclass(frozen=True)
class Double:
    start: int          # start of the separator before the second copy
    end: int            # end of the second copy
    word: str
    closed: bool


def _inside(pos, spans):
    return any(s <= pos < e for s, e in spans)


def doubled_words(text, spans):
    out = []
    for m in _DOUBLE.finditer(text):
        first, second = m.group(1), m.group(3)
        if _inside(m.start(), spans) or _inside(m.end() - 1, spans):
            continue
        if first[:1].isupper() and second[:1].isupper():
            continue                                   # Bora Bora: a name
        if "\n\n" in m.group(2):
            continue
        out.append(Double(m.start(2), m.end(3), second, first.lower() in CLOSED_DOUBLES))
    return out


def _edit(text, start, original, replacement):
    line = text.count("\n", 0, start) + 1
    col = start - (text.rfind("\n", 0, start) + 1) + 1
    return Edit(line, col, col + len(original) - 1, original, replacement, "basics")


def spacing_edits(text, spans):
    """Space before , . ; : ! ? removed; a missing space after , ; : between letters added.
    Protected spans (code, URLs, links, Obsidian syntax) and anything next to a digit are skipped."""
    edits = []
    for m in _SPACE_BEFORE.finditer(text):
        if _inside(m.start(), spans) or re.search(r"\d", text[max(0, m.start() - 2):m.end() + 2]):
            continue
        edits.append(_edit(text, m.start(), m.group(0), ""))
    for m in _NO_SPACE_AFTER.finditer(text):
        if _inside(m.start(), spans) or re.search(r"\d", text[max(0, m.start() - 2):m.end() + 2]):
            continue
        edits.append(_edit(text, m.start(), m.group(1), m.group(1) + " "))
    return edits
```
  - Routing in `api.fix` / `tiers.partition`:
    - Remove `ENGLISH_WORD_REPEAT_RULE` from `DETERMINISTIC`. In `partition`, for that rule: if the repeated word (lower-cased) is in `CLOSED_DOUBLES` and not capitalised-pair → deterministic edit (remove the second copy and its separator); else if a model is available → `Item(original="<w> <w>", options=("<w>", "KEEP"), rule=DOUBLE_RULE, ...)`, `source="repeat"`; else → review with message `repeated word '<w> <w>'`.
    - `basics` runs in `api.fix` when `"basics" not in skip` and LanguageTool will not run for `mechanical` (missing, or `mechanical` skipped): apply `spacing_edits`, and for `doubled_words`: closed → Edit (source `basics`); other → adjudication item (same `DOUBLE_RULE`, `source="repeat"`) when a model is available or `replay_cache`, else a review item (`kind="alert"`, check `basics`, message `repeated word '<w> <w>'`).
    - `DOUBLE_RULE = ("A word is repeated. Choose the single word if the repeat is a typo. KEEP if it is grammatical or deliberate — repeats like 'that that', 'had had', 'is is' and emphatic doubles like 'very very' are often correct.")`
    - Adjudicated decisions apply by replacing `"<w> <w>"` with `"<w>"` (case of the first copy kept).
- [ ] **Step 4: Run** the new tests, then the full proofix suite; rerun the proofix CLI capture (`uv run proofix examples/typos.md --llm none --no-typos --dry-run --no-cache --changes`, before captured at the start of this task) and explain differences (only doubled words may change).
- [ ] **Step 5: Commit** (proofix, branch `first-run`): `basics tier without LanguageTool; doubled words fixed only from a closed list, otherwise adjudicated or reviewed — LanguageTool's repeat rule too`.

---

### Task 5: proofix — audit of outright edits, variety rule filter, LanguageTool server; 0.7.0

**Files:** Modify `proofix/proofix/tiers.py`, `proofix/proofix/lt.py`, `proofix/proofix/api.py`, `pyproject.toml`, `proofix/__init__.py`, `man/proofix.1`; Test `proofix/tests/test_audit.py`, `proofix/tests/test_lt_server.py` (create both).

**Interfaces:**
- Produces: `proofix.lt.LanguageToolServer` (context manager; `.url`), `run_languagetool(text, target, level="default", disabled=None, timeout=600, server=None)`; `proofix.api.fix(text, options, endpoint, cache, comma_cache, lt_server=None)`; `Options.oxford_ize: bool = False`; `tiers.VARIETY_DISABLED: dict[str, frozenset[str]]`.

- [ ] **Step 1: Audit (no code yet).** For each rule in `DETERMINISTIC` (after Task 4: `COMMA_PARENTHESIS_WHITESPACE`, `SENTENCE_WHITESPACE`, `DOUBLE_PUNCTUATION`, `UNLIKELY_OPENING_PUNCTUATION`, `WHITESPACE_RULE`), the `typos` pre-pass, `mechanical_edits`, and hygiene: run the risky inputs from spec §7 through the replayed or real tool, and write in the report, per source, "keep (why always right)" or "move to adjudication (counter-example)". Risky inputs at minimum: `Really?!`, `Wow!!`, `Wait...`, `see ../notes` (path), `a  b` (double space) and a Markdown hard line break (`line  \n`), a table row with aligned spaces, `...and then`, `(as noted)`, `— a dash opening`, typos on `Teh` (capitalised), `teh`, `foo_bar_teh`, `teh2`, and a non-English word typos knows (e.g. `alle`).
- [ ] **Step 2: Failing tests** — `tests/test_audit.py`: one test per risky input asserting the post-audit behaviour (kept rules: applied; moved rules: unchanged text and an adjudication item with a fake endpoint / review item without). Typos: `teh` fixed; `Teh`, `foo_bar_teh`, `teh2` not applied outright (adjudicated/reviewed). Variety filter: with a replayed `OXFORD_SPELLING_Z_NOT_S` match on `Finalise` and `target="uk"`, `oxford_ize=False` → no review item; with `oxford_ize=True` → the match is not filtered. US target: replayed British-spelling suggestion rules (find their ids by running LanguageTool en-US on `colour` and `organise`) are filtered.
- [ ] **Step 3: Implement the audit outcome:** edit `DETERMINISTIC` per Step 1; moved rules go through the existing `m.replacements and adjudicate_available` path; add a one-line comment per kept rule stating why it is always right. Typos: `typos_edits` returns edits only for all-lower-case originals not in accept, not inside a word with a digit or underscore; others become spelling items (`SPELLING_RULE`) via the adjudication path, or review.
- [ ] **Step 4: Variety filter:** `VARIETY_DISABLED = {"uk_ise": frozenset({"OXFORD_SPELLING_Z_NOT_S", ...}), "us": frozenset({...})}` with the rule ids found in Step 2; `api.fix` passes them in `disabled=` to LanguageTool (target uk and not `oxford_ize` → `uk_ise`; target us → `us`).
- [ ] **Step 5: LanguageTool server — failing tests** `tests/test_lt_server.py` (module-level `pytest.importorskip`-style skip if `shutil.which("languagetool-server")` is None):

```python
def test_server_matches_command_line():
    text = "We recieved the the new color scheme.\n"
    with LanguageToolServer() as srv:
        via_server = run_languagetool(text, "us", server=srv)
    via_cli = run_languagetool(text, "us")
    assert [(m.start, m.end, m.rule) for m in via_server] == [(m.start, m.end, m.rule) for m in via_cli]


def test_server_stops_on_exit_and_on_error():
    with LanguageToolServer() as srv:
        pid = srv.process.pid
    assert not _alive(pid)
    with pytest.raises(RuntimeError):
        with LanguageToolServer() as srv:
            pid = srv.process.pid
            raise RuntimeError("boom")
    assert not _alive(pid)


def test_server_start_failure_raises_lterror(monkeypatch):
    monkeypatch.setattr(lt, "SERVER_START_TIMEOUT", 0.01)
    with pytest.raises(LTError):
        with LanguageToolServer():
            pass
```

(`_alive(pid)`: `os.kill(pid, 0)` in try/except ProcessLookupError, after a short wait loop.)
- [ ] **Step 6: Implement** in `lt.py`:

```python
SERVER_START_TIMEOUT = 30.0


class LanguageToolServer:
    """A local languagetool-server for one run: bound to localhost (no --public),
    on a free port, stopped on exit."""

    def __enter__(self):
        exe = shutil.which("languagetool-server")
        if not exe:
            raise LTError("languagetool-server not found")
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        self.process = subprocess.Popen([exe, "--port", str(port)], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + SERVER_START_TIMEOUT
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            try:
                urllib.request.urlopen(self.url + "/v2/languages", timeout=1).read()
                return self
            except OSError:
                time.sleep(0.2)
        self._stop()
        raise LTError(f"languagetool-server did not answer within {SERVER_START_TIMEOUT:g} s")

    def __exit__(self, *exc):
        self._stop()
        return False

    def _stop(self):
        p = getattr(self, "process", None)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
```

  and in `run_languagetool`, when `server` is given: POST `urllib.parse.urlencode({"language": LANG[target], "text": text, "level": "picky" if level == "picky" else "default", **({"disabledRules": ",".join(disabled)} if disabled else {})})` to `server.url + "/v2/check"`; on HTTP or connection errors raise `LTError`; pass the body to `parse_matches(body, text)` (offsets are UTF-16 in both APIs). Thread-safe: no shared state beyond the URL. `api.fix(..., lt_server=None)` passes `server=lt_server` to both LanguageTool calls.
- [ ] **Step 7: Run** the new tests and the full suite; CLI capture unchanged except doubled words / audit outcomes (explain each).
- [ ] **Step 8: Version 0.7.0** (pyproject, `__init__`, `.TH PROOFIX 1 "October 2026" "proofix 0.7.0" "User Commands"`; adjudicate pin per Task 3); man page documents `basics` in the tier list (drift test passes).
- [ ] **Step 9: Commit**: `Audit of outright edits; LanguageTool rules that contradict the variety are disabled; LanguageToolServer for callers that check many files; v0.7.0`.

---

### Task 6: prosefix — variety detection and `target_source`

**Files:** Modify `prosefix/prosefix/settings.py`, `prosefix/prosefix/jsonout.py`, `prosefix/prosefix/engine.py`, `pyproject.toml` (pins); Test `tests/test_settings.py`, `tests/test_cli.py`.

**Interfaces:**
- Consumes: `stylefix.api.detect_variety`, `Detection`.
- Produces: `Settings.target_source: str` and `Settings.detected: tuple[int, int] | None` (uk, us counts when detection ran).

- [ ] **Step 1: Failing tests:**

```python
# test_settings.py
UK = "The colour scheme and the programme. Finalise the licence.\n"
US = "The color scheme and the program. Finalize the license.\n"


def test_detected_when_nothing_sets_a_target(tmp_path):
    p = proj(tmp_path, "")
    s = resolve(tmp_path / "n.md", UK, {}, p)
    assert (s.target, s.target_source) == ("uk", "detected") and s.detected[0] >= 2


def test_default_when_unclear(tmp_path):
    s = resolve(tmp_path / "n.md", "Plain words only.\n", {}, proj(tmp_path, ""))
    assert (s.target, s.target_source, s.detected) == ("us", "default", (0, 0))


@pytest.mark.parametrize("body, flags, front, want", [
    ("", {"target": "us"}, "", ("us", "flag")),
    ('target = "us"\n', {}, "", ("us", "project")),
    ("", {}, "---\nprosefix: {target: us}\n---\n", ("us", "front matter")),
    ("", {}, "---\nlang: en-US\n---\n", ("us", "lang")),
])
def test_explicit_targets_beat_detection(tmp_path, body, flags, front, want):
    s = resolve(tmp_path / "n.md", front + UK, flags, proj(tmp_path, body))
    assert (s.target, s.target_source) == want and s.detected is None


def test_project_target_beats_detection(tmp_path):
    s = resolve(tmp_path / "n.md", UK, {}, proj(tmp_path, 'target = "us"\n'))
    assert (s.target, s.target_source) == ("us", "project")
```

```python
# test_cli.py
def test_detected_variety_is_reported_and_kept(tmp_path, capsys):
    p = tmp_path / "n.md"
    p.write_text("The colour scheme and the programme -- finalise the licence.\n")
    assert main([str(p), "--llm", "none"]) == 0
    assert "colour" in p.read_text() and "programme" in p.read_text()
    assert "en-GB (detected)" in capsys.readouterr().err


def test_json_target_source(tmp_path, capsys):
    p = tmp_path / "n.md"
    p.write_text("The colour scheme and the programme.\n")
    main([str(p), "--json", "--llm", "none"])
    s = json.loads(capsys.readouterr().out)["files"][0]["settings"]
    assert s["target_source"] == "detected" and s["detected"]["uk"] >= 2
```

- [ ] **Step 2: Run** → failures.
- [ ] **Step 3: Implement:** in `resolve`, track the source as each layer sets `target` (project → `project`; front-matter `prosefix.target` → `front matter`; `lang:` → `lang`; flag → `flag`). If no layer set it: `d = detect_variety(body_without_front_matter, accept=accept)`; target = `d.target or "us"`, source `detected` if `d.target` else `default`, `detected=(d.uk, d.us)`. `jsonout.file_entry` adds `"target_source"` to `settings` and `"detected": {"uk": u, "us": s}` when not None. The per-file stderr line gains the label (Task 7 formats it; here store it).
- [ ] **Step 4: Run** the new tests and the full suite.
- [ ] **Step 5: Commit** (prosefix, branch `first-run`): `A note with no configured variety keeps the variety it is written in`.

---

### Task 7: prosefix — what the user sees

**Files:** Modify `prosefix/prosefix/cli.py`; Test `tests/test_cli.py`.

- [ ] **Step 1: Failing tests:**

```python
def test_single_file_prints_review_items(tmp_path, capsys):
    p = tmp_path / "n.md"
    p.write_text("However the budget is tight and we may need to revisit priorities.\n")
    main([str(p), "--llm", "none", "--target", "us"])
    err = capsys.readouterr().err
    assert "review —" in err


def test_many_files_hint_instead_of_items(tmp_path, capsys):
    for n in "ab":
        (tmp_path / f"{n}.md").write_text("I had had enough of it.\n")
    main([str(tmp_path), "--llm", "none", "--target", "us"])
    err = capsys.readouterr().err
    assert "review —" not in err and "(--changes lists them)" in err


def test_changes_lists_review_and_context(tmp_path, capsys):
    p = tmp_path / "n.md"
    p.write_text("The programme , which covers analysis,design and testing.\n")
    main([str(p), "--llm", "none", "--target", "uk", "--changes"])
    err = capsys.readouterr().err
    assert "'programme , which' -> 'programme, which'" in err


def test_one_tools_line_and_one_model_line(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    p = tmp_path / "n.md"
    p.write_text("The the end.\n")
    main([str(p), "--llm", "auto", "--target", "us"])
    err = capsys.readouterr().err
    assert err.count("most fixes need Vale and LanguageTool") == 1
    assert err.count("need a model — prosefix --setup") == 1
    assert "skipped" not in err


def test_first_run_tip_once(tmp_path, capsys):
    p = tmp_path / "n.md"
    p.write_text("The color -- here.\n")
    main([str(p), "--llm", "none"])
    assert "tip: prosefix --diff" in capsys.readouterr().err
    main([str(p), "--llm", "none", "-q"])
    assert "tip:" not in capsys.readouterr().err


def test_help_opens_plainly(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    head = capsys.readouterr().out.split("\n\n")[1]
    assert head.startswith("prosefix fixes spelling, style, typos and punctuation in Markdown files, in place.")
```

(Adjust the review-item input if LanguageTool isn't on PATH in CI: use a doubled word outside the closed list, which `basics` reviews without tools.)
- [ ] **Step 2: Run** → failures.
- [ ] **Step 3: Implement:**
  - Per-file line: `prosefix: <path>: en-GB (detected) · 5 change(s), 6 for review` when `target_source` is `detected`; `prosefix: <path>: no clear variety (<uk> UK, <us> US words); using en-US — set --target or lang: · …` when `default`; unchanged otherwise.
  - Review items: `_review_line(path, item) -> f"{path}:{item.line}: review — {item.message} [{item.pass_} {item.check}]"`. Printed under `--changes` after the file's change lines; printed by default when exactly one input file or stdin; with several inputs, the total line appends ` (--changes lists them)` when any review items exist. `-q` suppresses all of it.
  - `_change_line`: show a context window — up to 12 characters either side from `r.original`/`r.output`, trimmed to word boundaries, newlines shown as `⏎` — as `'<before-context>' -> '<after-context>'`, followed by the existing bracket.
  - Skipped lines: build at most two from the deduplicated `Skipped` list — tools (any of Vale, LanguageTool, typos missing; list the missing brew names in the parenthesis: `vale`, `languagetool`, `typos-cli`) and model (exact strings in Global Constraints; for `--llm cached` keep the existing cached wording on the model line). `--json` and `--doctor` unchanged.
  - First-run tip: default (in-place) mode, not `-q`, and the cache file that applies to the first input (`settings.cache`) does not exist before the run → after the run print `tip: prosefix --diff <path> shows changes without writing them` once (with `<path>` the first input). Nothing is written to remember it.
  - `DESCRIPTION`/epilog: first paragraph exactly `prosefix fixes spelling, style, typos and punctuation in Markdown files, in place.`, then three examples (`prosefix draft.md`, `prosefix draft.md --diff`, `prosefix vault/ --check`); the stylefix/proofix and tier detail move to the epilog.
- [ ] **Step 4: Run** new tests and full suite.
- [ ] **Step 5: Commit**: `Review items and context shown; one line for missing tools, one for the model; a first-run tip; a plain --help`.

---

### Task 8: prosefix — shared LanguageTool server, wiring, docs, 0.2.0

**Files:** Modify `prosefix/prosefix/engine.py`, `prosefix/prosefix/cli.py`, `prosefix/prosefix/settings.py` (`PROOF_TIERS` gains `basics`), `pyproject.toml`, `prosefix/__init__.py`, `README.md`, `man/prosefix.1`, `uv.lock`; Create `tests/data/walkthrough.md` (the draft from the spec's walkthrough, verbatim below); Test `tests/test_engine.py`, `tests/test_cli.py`, `tests/test_walkthrough.py` (create).

```markdown
# Quarterly update

We recieved the the new colour scheme on 3 September -- it looks great.
The teams programme , which covers analysis,design and testing is on track.
However the budget is tight and we may need to "revisit" priorities.

Next steps:

- Finalise the licence agreement
- Schedule a review meeting w/ the vendor
```

- [ ] **Step 1: Failing tests:**

```python
# test_engine.py
needs_server = pytest.mark.skipif(not shutil.which("languagetool-server"), reason="no languagetool-server")


@needs_server
def test_one_server_for_many_files(tmp_path, monkeypatch):
    starts = []
    real = proofix.lt.LanguageToolServer.__enter__
    monkeypatch.setattr(proofix.lt.LanguageToolServer, "__enter__",
                        lambda self: (starts.append(1), real(self))[1])
    for i in range(3):
        (tmp_path / f"{i}.md").write_text("We recieved the the scheme.\n")
    assert main([str(tmp_path), "--llm", "none", "--target", "us"]) == 0
    assert len(starts) == 1


@needs_server
def test_server_stopped_after_exception(tmp_path, monkeypatch):
    pids = []
    real = proofix.lt.LanguageToolServer.__enter__
    def enter(self):
        out = real(self); pids.append(self.process.pid); return out
    monkeypatch.setattr(proofix.lt.LanguageToolServer, "__enter__", enter)
    monkeypatch.setattr(engine, "_after_file_hook", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    (tmp_path / "n.md").write_text("We recieved the scheme.\n")
    with pytest.raises(RuntimeError):
        main([str(tmp_path / "n.md"), "--llm", "none", "--target", "us"])
    assert pids and not _alive(pids[0])


def test_server_fallback_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(proofix.lt, "SERVER_START_TIMEOUT", 0.01)
    (tmp_path / "n.md").write_text("We recieved the scheme.\n")
    main([str(tmp_path / "n.md"), "--llm", "none", "--target", "us"])
    err = capsys.readouterr().err
    assert ("LanguageTool server did not start" in err) == bool(shutil.which("languagetool-server"))
```

(Replace the `_after_file_hook` device with any clean way to inject an exception after the server started — e.g. monkeypatching `engine.process` to raise on its first call — and keep the assertion that the server process is gone.)

```python
# test_walkthrough.py — the spec's walkthrough, end to end
DRAFT = (Path(__file__).parent / "data" / "walkthrough.md").read_text()


def test_without_tools(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    p = tmp_path / "draft.md"; p.write_text(DRAFT)
    main([str(p), "--llm", "none"])
    out, err = p.read_text(), capsys.readouterr().err
    assert "the the" not in out and "programme ," not in out and "analysis, design" in out
    assert err.count("most fixes need Vale and LanguageTool") == 1
    assert "review —" in err


@pytest.mark.skipif(not (shutil.which("vale") and shutil.which("languagetool")), reason="needs tools")
def test_with_tools_keeps_british(tmp_path, capsys):
    p = tmp_path / "draft.md"; p.write_text(DRAFT)
    main([str(p), "--llm", "none"])
    out, err = p.read_text(), capsys.readouterr().err
    assert "colour" in out and "programme" in out and "received" in out and "the the" not in out
    assert "en-GB (detected)" in err
    assert "3 September" in out and "spells out" not in err


@pytest.mark.skipif(not shutil.which("vale"), reason="needs vale")
def test_explicit_us_converts(tmp_path):
    p = tmp_path / "draft.md"; p.write_text(DRAFT)
    main([str(p), "--llm", "none", "--target", "us"])
    assert "color" in p.read_text()


@needs_server
def test_server_faster_than_command_line(tmp_path):
    for i in range(10):
        (tmp_path / f"{i}.md").write_text(DRAFT)
    t0 = time.monotonic(); main([str(tmp_path), "--llm", "none", "--check"]); with_server = time.monotonic() - t0
    os.environ["PROSEFIX_NO_LT_SERVER"] = "1"
    try:
        t0 = time.monotonic(); main([str(tmp_path), "--llm", "none", "--check"]); without = time.monotonic() - t0
    finally:
        del os.environ["PROSEFIX_NO_LT_SERVER"]
    assert with_server < without
```

(`PROSEFIX_NO_LT_SERVER=1` is a test/diagnostic switch the engine honours to skip the server; document it in the man page's ENVIRONMENT.)
- [ ] **Step 2: Run** → failures.
- [ ] **Step 3: Implement:**
  - `engine`: a run-scoped `LanguageToolRunner` object created by `cli.main`: lazily enters `proofix.lt.LanguageToolServer()` on the first `process` call that will use LanguageTool (when `languagetool-server` exists and `PROSEFIX_NO_LT_SERVER` is unset), under a lock; on `LTError` prints the fallback line once and uses the command line thereafter; passes `lt_server=` to `proof.fix`. `cli.main` wraps the whole run in `try/finally` that closes the runner (stops the server) — together with the existing cache flush.
  - Pass `oxford_ize=False` explicitly to `proof.Options` (prosefix has no -ize setting; uk means -ise).
  - `settings.PROOF_TIERS` gains `"basics"`; `--skip` help lists it; man TIERS documents it.
  - Pins and version 0.2.0 (pyproject, `__init__`, `.TH PROSEFIX 1 "October 2026" "prosefix 0.2.0" "User Commands"`); `uv lock`.
  - README and man page: the new opening sentence and examples; variety detection (how it decides, how to override); review items (single file vs many, `--changes`); the no-tools run (what `basics` does, the one install line); the three routes, stated once in plain words ("prosefix applies a fix only when it is always right; when judgement is needed it asks the model; anything uncertain is listed for you"); `PROSEFIX_NO_LT_SERVER`.
- [ ] **Step 4: Run** the full suite with tools on PATH and with tools hidden; drift test passes; `man ./man/prosefix.1` renders; `uv build --no-sources`; `tar tzf`; `twine check --strict`.
- [ ] **Step 5: Commit**: `One LanguageTool server per run; basics tier wired; README and man page for the first run; v0.2.0`.

---

### Task 9: Releases and the Homebrew formula

- [ ] **Step 1:** Merge each `first-run` branch into `master` (fast-forward) in the repos that changed; run every changed repo's suite on `master`.
- [ ] **Step 2:** In order — adjudicate (if changed), stylefix, proofix: build, `tar tzf`, `twine check --strict`, push `master` (stylefix: `git -c http.postBuffer=157286400 push`), publish (`UV_PUBLISH_TOKEN="$(cat ~/.config/pypi-token)" uv publish dist/*`), confirm on PyPI, clean `uv tool install` check, tag.
- [ ] **Step 3:** prosefix: test in a fresh clone with `uv sync --no-sources` (published libraries); push; CI green (`gh run watch`); build, check, publish, clean install (`prosefix --version`, the walkthrough draft with tools hidden), tag `v0.2.0`.
- [ ] **Step 4:** Homebrew tap: update `url`/`sha256` for prosefix 0.2.0 and the resource blocks for every changed library (from PyPI JSON — `brew update-python-resources` refuses releases under a day old); verify every URL and sha256 against PyPI; `brew tap andrewbroz/tap ~/Code/homebrew-tap`, `brew install --build-from-source`, `brew test`, `brew audit --strict`, man pages, `--doctor`; then `brew uninstall prosefix` and `brew untap andrewbroz/tap` (the author's man-page symlinks for stylefix/proofix conflict with `brew link` — move them aside during the install and restore them, as in the 0.1.0 release); commit and push the tap; `brew tap` from GitHub, `brew audit --strict --online`, `brew fetch`, untap.
- [ ] **Step 5:** Update the memory note `pypi-release-status` with the new versions.
