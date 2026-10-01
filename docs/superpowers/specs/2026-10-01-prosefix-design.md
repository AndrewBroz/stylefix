# prosefix — design

One distributable command that makes a Markdown file read as clean,
consistent prose: stylefix's variety and style-guide pass, then proofix's
typo, punctuation and comma pass, in one process, Markdown in and Markdown
out or rewritten in place. It is built for two kinds of use at once: an
author at the keyboard (a note, a folder, an Obsidian vault) and a
publishing pipeline (a site's content directory in CI).

## Goals

- `prosefix note.md` does everything stylefix and proofix do, with one
  endpoint, one decision cache and one change list.
- It fits workflows without glue: stdin → stdout filtering, in-place
  rewriting of files and folders, a `--check` mode for CI, a versioned JSON
  interface for editors, and stable, documented exit codes.
- Obsidian notes come through untouched outside their prose: wikilinks,
  embeds, tags, comments, block ids, callout markers and maths.
- Settings live where sites and vaults keep them: a project file, with
  per-note overrides in front matter.
- It is easy for a Homebrew user (`brew install andrewbroz/tap/prosefix`
  brings Vale, LanguageTool and typos) and degrades gracefully without them.
- The JSON interface is complete enough that an Obsidian plugin can be a
  thin client.

## Non-goals

- The Obsidian plugin itself. It is the second sub-project, with its own
  spec once this CLI settles. This spec only fixes the interface it needs.
- Moving mdmemo onto prosefix. A small follow-up (replace its two
  subprocess calls with one), not designed here.
- Pooling model requests across files. Each file batches its own items;
  files run in parallel.
- Windows packaging beyond what `uv tool install` gives. Homebrew is
  macOS and Linux.
- Any change to stylefix's or proofix's command-line behaviour.

## Current state (2026-10-01)

adjudicate 0.3.0, stylefix 0.7.0 and proofix 0.5.0 are on PyPI. Each CLI's
`main()` reads the input file, runs its pipeline, and writes output,
report and change log in one function. mdmemo (local only) chains the two
by running `stylefix` then `proofix` as subprocesses on a temporary copy.
adjudicate's `adjudicate()` consults the cache first and, with no endpoint,
leaves the remaining items undecided. stylefix needs Vale for its
substitution rules, ambiguous-word checks and numeral rule; its serial
commas, abbreviations, punctuation normalisation (dashes, quotes,
apostrophes, ranges) and spelling review are pure Python. proofix already
skips tiers 1–2 without LanguageTool and the typos pre-pass without
`typos`.

## 1. Architecture

```
adjudicate   library: endpoint, cache, model batches, Markdown spans
stylefix     library + CLI ─┐
proofix      library + CLI ─┼─▶ prosefix   CLI + JSON interface
                             ┘      ▲
                 mdmemo, the Obsidian plugin, site builds
```

### Library APIs in stylefix and proofix

Each gains a module `api.py` with one entry point:

```python
def fix(text: str, options: Options, endpoint: Endpoint | None,
        cache: Cache) -> Result
```

- `Options` is a dataclass of the settings the CLI's flags carry today
  (stylefix: target, style, oxford_ize, accept words, abbreviation_nouns,
  min_confidence, batch_size, parallel; proofix: target, accept words,
  lt_level, typos, lt, commas mode, optional_commas, max_sentences,
  min_confidence, parallel). Fields default to the CLI's defaults.
- `Result` holds `text` (the output), `changes: list[Change]`,
  `review: list[ReviewItem]`, `stats`, and `skipped: list[Skipped]` (tiers
  not run, with why and how to fix).
- `Change` holds: `pass_` (`"stylefix"` or `"proofix"`), `check` (the rule
  or tier name), `start`, `end` (code-point offsets into the text this pass
  received), `line`, `before`, `after`, `reason`, `decided_by` (`"rule"`,
  `"model"` or `"cache"`), `confidence` (1.0 for rules).
- `fix` does no file I/O and prints nothing. It reads no config files; the
  caller resolves the endpoint and passes the cache.

Each CLI's `main()` becomes: parse flags, read the file, build `Options`,
resolve the endpoint, call `fix`, write output, report and change log as
today. The existing test suites are the regression check: they must pass
unchanged.

### Composition in prosefix

For one file: split front matter; run `stylefix.api.fix` on the original
body; run `proofix.api.fix` on its output; translate proofix's offsets
back to the original body (§4); collect one change list with ids `s1…`
for stylefix and `p1…` for proofix; join front matter and output.

One endpoint: `resolve_endpoint("prosefix", …)`, so `PROSEFIX_LLM_*` and
`~/.config/prosefix/config.toml` apply, then the shared adjudicate config.
One cache file per project (§3), shared by both passes; cache keys already
carry a scope, and each pass keeps its own scope names.

## 2. Command line

```
prosefix PATH ...            rewrite each file in place
prosefix DIR ...             every *.md and *.markdown below DIR
prosefix -                   stdin → stdout
prosefix FILE -o OUT         one file, written elsewhere
```

With `-`, settings are looked up from the current directory, or from
`--stdin-filename PATH` when given; that path is also used for `exclude`
matching and as `path` in `--json` output (editors and the plugin pass the
note's real path this way).

Directory walks skip `.git/`, `.obsidian/`, `node_modules/`, any other
directory whose name starts with `.`, and the project's `exclude` globs.
Explicitly named files are processed even if excluded, with a note.
Front matter and code are never modified.

Output modes (none of these writes a file):

| flag | prints | exit |
|---|---|---|
| `--diff` | unified diff | 0 |
| `--check` | `would change N files` and their paths | 1 if any would change, else 0 |
| `--check --strict` | also counts review items as failures | 1 if any change or review item |
| `--json` | the §4 document on stdout | 0 |

Everyday flags: `--target us|uk`, `--style NAME`, `--only style|proof`,
`--skip TIER,...` (tier names: `variety`, `guide`, `ambiguous`, `numbers`,
`serial-comma`, `abbreviations`, `punctuation`, `hygiene`, `mechanical`,
`typos`, `adjudicated`, `compounds`, `commas`), `--changes` (change log
on stderr), `--report FILE` (one Markdown report for all files),
`-q/--quiet`, `-j N` (files in parallel, default 4). With `-j`, workers
share one in-memory cache, which is written once when the run ends.

Model: `--llm auto|ollama|none|cached`, plus `--url`, `--model`,
`--timeout` as in stylefix. `cached` applies decisions already in the
cache and never contacts a model; items not in the cache are left as
written and reported. `none` applies rules only and ignores the cache.
`--no-cache` neither reads nor writes the cache.

Mode flags (exit without input): `--setup`, `--check-endpoint` (from
adjudicate, with app `"prosefix"`), `--doctor` (§3), `--version`.

`--require TOOL,...` (`vale`, `languagetool`, `typos`, `model`) makes a
missing tool an error (exit 2) instead of a skip.

Exit status: 0 success; 1 from `--check`/`--strict` as above; 2 usage,
configuration or input errors, or a `--require` failure. A missing tool is
never an error unless required.

Guarantees, each tested:

- **Idempotent:** a second run over prosefix's own output makes no changes.
- **Faithful:** applying every reported change to the original yields the
  written output exactly.
- **Bounded:** nothing outside prose spans (front matter, code, protected
  Obsidian syntax, link targets, HTML) changes.

## 3. Settings, missing tools, Homebrew

### Project settings

For each file, prosefix looks upward from the file's directory for
`prosefix.toml`, `.prosefix.toml`, or a `[tool.prosefix]` table in
`pyproject.toml`, and uses the first found. Keys:

| key | type | meaning |
|---|---|---|
| `target` | `"us"` or `"uk"` | variety |
| `style` | string | style guide, as stylefix's `--style` |
| `only` | list of `"style"`, `"proof"` | passes to run (default both) |
| `skip` | list of tier names | tiers to skip |
| `exclude` | list of globs | paths, relative to the settings file, skipped in directory walks |
| `accept` | list of strings | words and phrases never changed |
| `accept_file` | string | a file of accept entries, relative to the settings file |
| `cache` | string | cache path relative to the settings file (default `.prosefix/cache.json` beside it) |

Unknown keys and wrong types are errors naming the file and key.

### Per-note overrides

In a note's front matter: `prosefix: off` skips the note (status
`skipped`); `prosefix: {target: uk, style: oxford, skip: [commas]}`
overrides the listed keys for that note (only `target`, `style`, `only`
and `skip` are allowed here). If `prosefix.target` is absent, a `lang`
key of `en-GB` or `en-US` (case-insensitive; `en-UK` accepted) sets the
target.

Precedence: flags > front matter > project settings > built-in defaults
(`us`, and stylefix's default guide for the target). Accept lists are
merged: stylefix's built-in list, `~/.config/stylefix/accept.txt`,
`~/.config/proofix/accept.txt`, the project's `accept` and `accept_file`.

Front matter is parsed with PyYAML's safe loader, prosefix's one new
runtime dependency (stylefix and proofix keep their dependencies). Front
matter that does not parse is left untouched and the file is processed
with project settings, with a note in `review`.

The model endpoint is never a project setting: it comes only from
adjudicate's layers, so a cloned site cannot direct your key elsewhere.

### Missing tools

Each tier declares its requirements; prosefix runs every tier whose
requirements are met.

| missing | skipped | still runs |
|---|---|---|
| Vale | stylefix `variety`, `guide`, `ambiguous`, `numbers` | stylefix `serial-comma`, `abbreviations`, `punctuation`, spelling review; all of proofix |
| LanguageTool | proofix `mechanical`, `adjudicated` | proofix `hygiene`, `compounds`, `commas` |
| typos | proofix `typos` | everything else |
| model | stylefix and proofix adjudicated decisions, `commas` | rule-based tiers; undecided items reported |

A run prints one line per skipped capability on stderr, not one per file:
`prosefix: skipped variety spelling (Vale not found: brew install vale)`.
`--quiet` suppresses it; `--json` carries it in `skipped`.

`prosefix --doctor` prints a table: each tool (found / version / path or
the install command), the resolved endpoint with sources (as
`--check-endpoint`), the settings file that applies to the current
directory, and which tiers would run. Exit 0 always.

### Homebrew

A tap repository `AndrewBroz/homebrew-tap` with `Formula/prosefix.rb`:
Python virtualenv formula installing prosefix with stylefix, proofix,
adjudicate and spylls as resources; `depends_on` Vale, LanguageTool and
typos-cli; installs `man/prosefix.1`, `man/stylefix.1`, `man/proofix.1`;
links the `prosefix`, `stylefix` and `proofix` executables; a `test do`
block running `prosefix --version` and a `--llm none` run on a small file.
Each release updates the formula's version, URLs and hashes (procedure in
the plan). `uv tool install prosefix` remains the non-Homebrew route.

## 4. JSON interface

`--json` prints one document (UTF-8):

```json
{
  "schema": 1,
  "prosefix": "0.1.0",
  "endpoint": {"url": "http://…/v1", "model": "…", "source": "…"},
  "skipped": [{"what": "variety spelling", "why": "Vale not found", "fix": "brew install vale"}],
  "files": [{
    "path": "notes/brief.md",
    "status": "changed",
    "reason": null,
    "settings": {"target": "uk", "style": "oxford", "only": ["style", "proof"], "skip": []},
    "changes": [{
      "id": "s3", "pass": "stylefix", "check": "ToUK.Variants",
      "start": 120, "end": 127, "line": 5,
      "before": "license", "after": "licence",
      "reason": "noun: UK spelling", "decided_by": "model", "confidence": 0.93,
      "depends_on": []
    }],
    "review": [{"pass": "proofix", "line": 9, "kind": "undecided", "message": "…"}],
    "output": "…full rewritten file…"
  }]
}
```

- `endpoint` is null when no model is used.
- `status` is `changed`, `unchanged`, `skipped` (with `reason`) or
  `error` (with `reason`, and no `changes` or `output`).
- `start`/`end` are offsets into the **whole original file** (front matter
  included) in **UTF-16 code units**, the unit JavaScript and CodeMirror
  use; `line` is 1-based. stdin input reports `"path": "-"`, or the
  `--stdin-filename` path when given.
- Offsets of proofix changes are translated to the original: stylefix's
  changes are non-overlapping splices, so a monotone map from
  stylefix-output positions to original positions exists. A proofix change
  whose span lies inside or overlaps a stylefix change's output span is
  given `depends_on: [that stylefix id]` and offsets covering the union of
  the two spans in the original, with `before`/`after` taken from the
  original and from the final text.
- `review[].kind` is `undecided`, `rejected` (a comma suggestion the guard
  refused), `alert` (a check left for a human) or `note`.
- Within schema 1, fields may be added and never removed or changed in
  meaning; a breaking change increments `schema`.

The Obsidian plugin applies a subset of changes by splicing in descending
offset order; any subset closed under `depends_on` yields valid text.

## 5. Obsidian syntax

adjudicate 0.3.1 adds these to `protected_spans` (purely additive; the
0.3 API is unchanged): `[[wikilink]]` and `[[wikilink|alias]]` (the alias
text is protected too), `![[embed]]`, `#tag` and `#nested/tag` (not
Markdown headings, which start a line with `#` and a space), `%%comment%%`
(inline and multi-line), `^block-id` at the end of a line, the
`> [!type]` marker of a callout (the callout's text stays prose), and
`$…$` / `$$…$$` maths. stylefix and proofix get the protection by
depending on 0.3.1.

## 6. Testing

- stylefix and proofix: existing suites pass unchanged after the API
  refactor; new tests call `fix()` directly and check that it does no
  file I/O.
- adjudicate: each new protected construct, including near-misses (a
  heading `# Title`, a dollar amount `$5`).
- prosefix:
  - an example vault under `tests/vault/` with every Obsidian construct;
    each is byte-identical after a run;
  - idempotence over every example;
  - faithfulness: applying all changes to the original equals `output`;
    applying random subsets closed under `depends_on` yields text that
    parses back to the same front matter;
  - offset mapping with emoji, combining accents and CRLF line endings;
  - settings discovery and precedence, front-matter overrides, `lang`
    mapping, unknown keys;
  - `--check`, `--strict`, `--diff`, `--json`, stdin mode, exit codes;
  - `--llm cached` against a committed cache fixture; `--llm none`
    ignoring it;
  - missing tools via a controlled PATH: exit 0, the right `skipped`
    entries, one stderr line per capability; `--require` exits 2;
  - the drift test (every long option in `man/prosefix.1`, `.TH`
    version), as in stylefix and proofix.
- CI: a GitHub Actions workflow in the prosefix repo running the suite on
  Ubuntu and macOS with Python 3.11 and 3.13, without Vale or LanguageTool
  (exercising degradation) and with them on macOS via Homebrew.

## 7. Releases

In order, each with the existing release checks (sdist listing,
`twine check --strict`, clean install, tag):

1. adjudicate 0.3.1 — Obsidian spans.
2. stylefix 0.8.0 and proofix 0.6.0 — library APIs; `adjudicate>=0.3.1,<0.4`.
3. prosefix 0.1.0 — new repository `AndrewBroz/prosefix`, PyPI, man page.
4. The Homebrew tap and formula.
5. Follow-up, not in this spec: mdmemo calls prosefix.

## Risks

- **Offset translation across passes** is the subtlest code here; the
  faithfulness and subset tests are the guard, and overlapping changes
  are merged under `depends_on` rather than reported separately.
- **The API refactor** touches each tool's largest function. Keeping CLI
  behaviour byte-identical, proved by the unchanged suites, contains it.
- **Homebrew's LanguageTool** pulls in a JDK, a large install. It is a
  dependency of the formula because the tiers it enables are the most
  valuable; a user who objects can use `uv tool install` instead.
- **`#tag` detection** can misfire on prose like "issue #42". Tags must
  start with a letter, and numbers after `#` stay prose; the near-miss
  tests pin this.
