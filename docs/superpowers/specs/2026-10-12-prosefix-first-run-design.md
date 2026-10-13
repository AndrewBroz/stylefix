# prosefix first-run experience — design

A walkthrough of a new user's first runs (2026-10-12: `uv tool install
prosefix`, then `prosefix draft.md` on a short British draft) found six
problems. This design fixes all six, plus an audit of every edit applied without the model (section 7), in one release: prosefix 0.2.0, with
stylefix 0.8.1, proofix 0.7.0 and, only if needed, adjudicate 0.3.2.

## The walkthrough, briefly

| step | what happened |
|---|---|
| no Vale/LanguageTool/typos, no model | four "skipped" lines; 2 changes (a dash, curled quotes); typo, doubled word and comma spacing untouched |
| with the tools | 9 good changes in ~6 s, but the British draft was silently converted to US (default target) |
| `--target uk` | correct result; "6 for review", visible only with `--report` |
| review items | useful, plus noise: "3 September" flagged as a numeral to spell out; LanguageTool suggesting -ize after stylefix chose -ise |

## The rule every tier follows

The aim is a fixer that saves a person time and makes clear what still
needs them. Every candidate edit takes exactly one of three routes:

1. **Deterministic** — one right answer, applied outright (a known typo, a
   comma space, `the the`).
2. **Adjudicated** — judgement needed: the edit becomes an item with its
   sentence and a closed set of choices (always including KEEP) for the
   model; applied only above the confidence threshold.
3. **Review** — genuine uncertainty: the model is unsure, or unavailable, or
   there is no candidate fix; listed for the person, with the reason.

Anything not provably safe to apply outright goes to route 2 when a model is
available and route 3 when it is not. Nothing uncertain is applied silently.

## Goals

1. A note with no configured variety is regularised to the variety it is
   already written in, not silently converted to US.
2. Review items are visible where the user is looking.
3. A run without the external tools still fixes the obvious mechanical
   faults, and says once, in one line, how to get the rest.
4. A vault-sized run starts LanguageTool once, not twice per file.
5. Review output carries no contradictory or false-positive items from the
   cases found, and each change is one readable edit.
6. `--help` and the first in-place run tell a newcomer what to do first.

## Non-goals

- Detecting varieties other than US and UK, or languages other than English.
- A LanguageTool server shared across separate prosefix invocations (a
  daemon). The server lives for one run.
- Changing stylefix's or proofix's own CLIs beyond the bug fixes listed
  below (their CLIs gain nothing they must opt into).
- The Obsidian plugin.

## 1. Variety detection (stylefix 0.8.1, prosefix 0.2.0)

`stylefix.api.detect_variety(text) -> Detection(target, uk, us)`:

- Counts words in prose regions (`adjudicate.prose_regions`, excluding text
  inside quotation marks via `adjudicate.inside_quotes`) whose VarCon entry
  marks them British-only or American-only. Words valid in both varieties,
  capitalised words (names), and words in the accept lists don't count. Each distinct word counts
  once (lower-cased), so one repeated word cannot decide a note.
- `target` is `"uk"` when `uk >= 2` and `uk >= 2 * us`, `"us"` when
  `us >= 2` and `us >= 2 * uk`, otherwise `None`.
- Pure function; no I/O; fast enough for every note in a vault (one pass
  over the words with a set lookup).

prosefix uses it only when nothing else sets a target: no `--target` flag,
no project `target`, no front-matter `prosefix: {target: …}` or `lang:`.
Then:

- `target` is the detected variety, or `"us"` if detection returns `None`.
- `Settings` gains `target_source`: `"flag"`, `"front matter"`, `"lang"`,
  `"project"`, `"detected"` or `"default"`.
- When the source is `"detected"` or `"default"`, the per-file line says so:
  `draft.md: en-GB (detected) · 5 change(s), 6 for review` and, for the
  default, `draft.md: no clear variety (0 UK, 0 US words); using en-US — set --target or lang:`.
- (Final review ruling R2.) When detection is undecided with evidence
  (`uk + us > 0`, no threshold met), the variety-spelling conversion is
  skipped for that file: prosefix adds stylefix's `variety` and `ambiguous`
  tiers to the file's style skip and drops stylefix's other-variety spelling
  review notes; everything else follows the US default (LanguageTool runs as
  en-US; its "is British English" spelling matches are already filtered). The
  line reads `no clear variety (1 UK, 1 US words); variety spellings left alone — set --target or lang:`,
  and `--json` settings gain `"variety_conversion": false`.
- `--json` file entries gain `"target_source"` in `settings`, plus
  `"detected": {"uk": n, "us": m}` when detection ran.
- Detection runs per file, so mixed vaults keep each note consistent.

## 2. Review items you can see (prosefix 0.2.0)

- `--changes` prints review items after a file's changes:
  `draft.md:5: review — A comma may be missing after 'However'. [proofix SENT_START_CONJUNCTIVE_LINKING_ADVERB_COMMA]`.
- When the run's inputs are exactly one file (or stdin), default mode
  prints that file's review items to stderr without `--changes`. With
  several files, per-file lines show counts and the total line adds
  `(--changes lists them)` when any review items exist.
- `-q` suppresses both.
- Each change line in `--changes` and `--report` shows a context window:
  the change plus up to 12 characters either side, trimmed to word
  boundaries, e.g. `'programme , which' -> 'programme, which'`.

## 3. Useful without the tools (proofix 0.7.0, prosefix 0.2.0)

proofix gains a tier `basics` (pure Python, no external tools), which runs
only when LanguageTool will not run for tier `mechanical` (missing, or
`mechanical` skipped while `basics` is not):

- doubled word (see "Doubled words" below for the routing);
- space before `,` `.` `;` `:` `!` `?` removed (`programme ,` → `programme,`),
  except before `...` and in protected spans;
- missing space after `,` `;` `:` added between two letters (`analysis,design`
  → `analysis, design`); never between digits (`1,000`), in URLs, times
  (`10:30`), or protected spans.

All three skip protected spans and code. `basics` is a proofix tier name
(`PROOF_TIERS` gains it) and can be skipped like any other.

### Doubled words

A doubled word is the same word twice in a row, case-insensitive, separated
by a single space or by a newline within the same paragraph — never across a
blank line or into a line starting with a list, quote, heading or table
marker. Some doubles are grammatical ("How do you know that that is wrong?",
"What it is is unclear", "I had had enough"), emphatic ("very very") or names
("Bora Bora"), so no list of exceptions can be complete. Routing, applied
identically to doubles found by `basics` and to LanguageTool's
`ENGLISH_WORD_REPEAT_RULE` (which leaves proofix's always-apply list):

- **Deterministic**: the word is in a closed list whose doubling is never
  grammatical — articles (`a`, `an`, `the`), prepositions (`of`, `to`, `at`,
  `for`, `with`, `from`, `into`, `onto`), and `and`, `or`, `but`, `nor`, `it`,
  `we`, `they`, `my`, `your`, `our`, `their`. One copy is removed. (Final
  review ruling R1: `in`, `on`, `by` and `about` left the list, since they
  double as a particle before a preposition: "log in in the corner", "turn it
  on on Monday".) When LanguageTool's mechanical pass ran and did not flag a
  closed-list double, it is adjudicated or reviewed instead: LanguageTool
  knows exceptions the list does not.
- **Not a double**: a hyphen touching either copy (`to to-do`, `for
  for-profit`, `in in-house`).
- **Adjudicated** (model available): any other doubled word becomes an item
  with the sentence as context, options `[<word>]` (one copy) and `KEEP`,
  and a rule telling the model that repeats like "that that" and "had had"
  are often correct.
- **Review** (no model, or below the confidence threshold):
  `review — repeated word 'that that'`.
- **Untouched**: capitalised doubles (likely names), accept-listed phrases,
  and doubles separated by punctuation (`New York, New York`).

prosefix's skipped-capability lines become at most two:

- tools: `prosefix: most fixes need Vale and LanguageTool — brew install andrewbroz/tap/prosefix (or: brew install vale languagetool typos-cli)`, listing only what is missing in the parenthesis;
- model: `prosefix: model decisions and comma placement need a model — prosefix --setup` (or the existing cached-mode wording).

`--doctor` and `--json` keep the per-capability detail.

## 4. LanguageTool server mode (proofix 0.7.0, prosefix 0.2.0)

proofix `lt.py` gains:

- `class LanguageToolServer` (context manager): finds `languagetool-server`
  on PATH, starts it on a free port with `--port N` and without `--public`
  (so it accepts only local connections) and without `--allow-origin`, waits until
  `GET /v2/languages` answers (polling, up to 30 s), and terminates it on
  exit (terminate, then kill after 5 s). Raises `LTError` if it cannot start.
- `run_languagetool(text, target, level, disabled, timeout, server=None)`:
  with `server`, POST to `/v2/check` (`language`, `text`, `level`,
  `disabledRules`) and parse the same JSON as the command line produces,
  through the same `parse_matches` (offsets are UTF-16 in both).
- `proofix.api.fix(..., lt_server=None)` passes it through; proofix's own CLI
  does not use a server (unchanged).

prosefix starts one `LanguageToolServer` per run, lazily on the first file
that needs LanguageTool, when `languagetool-server` exists; all workers share
it (requests are concurrent-safe on the server). If it fails to start,
prosefix prints `prosefix: LanguageTool server did not start (<reason>); using the command line` once and continues with the command line. It is
always stopped at exit, including on Ctrl-C and errors.

## 5. Less noise (stylefix 0.8.1, proofix 0.7.0, adjudicate 0.3.2 if needed)

- stylefix `Numbers`: a numeral directly before or after a month name
  (January…December and their three-letter abbreviations, any case), or
  inside a date pattern (`3/9/2026`, `2026-10-12`, `9th`), is not flagged.
- proofix: when the target is UK and the guide does not use -ize (stylefix's
  `oxford_ize` is off — prosefix passes it), disable `OXFORD_SPELLING_Z_NOT_S`
  and any other LanguageTool rule that suggests -ize/-yze spellings; when
  the target is US, disable rules suggesting British spellings. The list
  lives beside proofix's existing disabled rules.
- Granularity: "recieved the the" must come out as two changes
  (`recieved` → `received`, labelled by the typo/LanguageTool record; `the `
  deleted, labelled as a doubled word). Fix in `adjudicate.derive_changes`
  if the token diff merges them (prefer splitting a replace opcode whose
  pieces each match an annotation), else in proofix's annotations.
- The two pre-existing stylefix dash bugs found during 0.1.0 review: a
  two-hyphen GFM table delimiter row (`|--|--|`, `| -- | :--: |`) is left
  alone, and a dash rule never eats the space after a list or quote marker
  (`- -- item`, `> -- quote`) or turns a marker into prose.

## 6. A friendlier first screen (prosefix 0.2.0)

- `--help` opens with: `prosefix fixes spelling, style, typos and punctuation in Markdown files, in place.` and three examples (`prosefix draft.md`,
  `prosefix draft.md --diff`, `prosefix vault/ --check`). The tier list and
  stylefix/proofix detail move below the options. The man page and README
  get the same opening.
- First-run tip: in default (in-place) mode, when no prosefix cache file
  exists in the cache location that applies, print once to stderr
  `tip: prosefix --diff <path> shows changes without writing them`. Nothing
  is written to remember the tip; it stops appearing once a cache exists.
  `-q` suppresses it.

## 7. Audit of edits applied outright (proofix 0.7.0)

Every source that applies edits without the model is checked against the
three routes: it stays deterministic only if its edit is right in every
prose context; otherwise its matches become adjudication items (model
available) or review items (no model). Sources:

- proofix `tiers.DETERMINISTIC` (LanguageTool rules applied outright):
  `COMMA_PARENTHESIS_WHITESPACE`, `SENTENCE_WHITESPACE`, `DOUBLE_PUNCTUATION`,
  `UNLIKELY_OPENING_PUNCTUATION`, `WHITESPACE_RULE` (`ENGLISH_WORD_REPEAT_RULE`
  leaves the list, per "Doubled words"). Known risks to test for each:
  `DOUBLE_PUNCTUATION` on `?!`, `!!`, `...` and `..` in paths; whitespace rules
  on alignment, Markdown line-break double spaces, and table cells;
  `UNLIKELY_OPENING_PUNCTUATION` on a sentence that legitimately opens with
  punctuation (`...and then`, `—`, `(`).
- the `typos` pre-pass: its corrections are dictionary-based and can hit
  names, identifiers outside code spans, and non-English words. Its edits are
  deterministic only when the original is all lower-case, not accept-listed,
  and not within a word containing a digit or underscore; otherwise they
  become spelling adjudication items (`SPELLING_RULE`) or review items.
- proofix `mechanical_edits` and `hygiene` (invisible characters, entities,
  line endings): confirm each is always right; hygiene's decisions are
  already conservative (entities that change Markdown parsing or carry meaning
  are left alone).
- stylefix deterministic swaps (Vale `action: replace` rules and pattern
  families): out of scope for change here — their table entries are
  single-answer by construction and ambiguous words are already adjudicated
  — but the audit notes any entry found during testing that is not.

The outcome of each rule is recorded beside it in the code (a one-line
reason it is safe, or the move to adjudication), and each moved or kept
rule gets a test with the risky input.

## Testing

- stylefix: `detect_variety` on UK, US, mixed, empty, quoted-only and code-only
  texts; threshold edges (2 vs 1, 2 vs 2); numerals in dates not flagged;
  `|--|` tables and `- --` / `> --` lines untouched.
- proofix: each `basics` rule and its exceptions (`1,000`, `10:30`, URLs,
  protected spans), running only without LanguageTool; doubled-word routing:
  `the the`/`of of` fixed; `that that`, `had had`, `is is`, `very very`
  adjudicated with a fake endpoint (KEEP honoured, a remove decision applied)
  and listed for review without one; `Bora Bora` and `New York, New York`
  untouched; a doubled word across two list items untouched; the same routing
  for a replayed LanguageTool `ENGLISH_WORD_REPEAT_RULE` match;
  `LanguageToolServer` start/stop (skipped if `languagetool-server` is
  missing) and that a server run gives the same matches as the command line
  on the e2e fixture; the rule filter for UK/US.
- adjudicate (if changed): the "recieved the the" split.
- prosefix:
  - the walkthrough as an end-to-end test (draft in the test data): no tools →
    doubled word and comma spacing fixed, one tools line, review items printed;
    with tools → UK draft stays UK with `en-GB (detected)`; `--target us` →
    converted;
  - detection precedence (flag, project, front matter, lang, detected, default);
  - `--json` `target_source` and `detected`;
  - review items in `--changes`, single-file default, multi-file hint, `-q`;
  - context windows in change lines;
  - LanguageTool server: shared across files, stopped at exit (including on an
    exception), fallback message when it can't start; a timing test that 10
    files with the server are faster than without (skipped without the tools);
  - first-run tip shown once, not with `-q`, not when a cache exists;
  - the drift test (new tier name, help text).

## Releases

stylefix 0.8.1 and adjudicate 0.3.2 (if changed) first, then proofix 0.7.0
(`adjudicate>=0.3.1,<0.4`), then prosefix 0.2.0 (`stylefix>=0.8.1,<0.9`,
`proofix>=0.7,<0.8`), then the Homebrew formula (new url/sha256 and
resources). Same release checks as before: suites, `uv build --no-sources`,
`tar tzf`, `twine check --strict`, prosefix CI green, clean install, tags.

## Risks

- **Detection guesses wrong** on a short note with few marker words: the
  2-word, 2:1 threshold falls back to US and says so; a project `target` or
  `lang:` overrides detection entirely.
- **`basics` false positives** (a ratio like `3:2`): exceptions are tested;
  the tier can be skipped; it never runs when LanguageTool runs. Deliberate
  repetitions are not a risk of silent damage: outside the closed list they
  are adjudicated or reviewed, never applied outright.
- **Server lifecycle**: an orphaned Java process if prosefix is killed with
  SIGKILL. Mitigated by binding to localhost on a random port and starting
  it in its own process group; ordinary exits and Ctrl-C stop it.
