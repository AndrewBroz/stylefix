# stylefix

Regularize a Markdown file to **US or UK English** and a **style guide**
(Chicago or Oxford), fully automatically and fully locally.

```
stylefix draft.md --target us              # -> draft.us.md + draft.us.md.report.md
stylefix draft.md --target uk --oxford-ize # UK with Oxford -ize spellings
stylefix draft.md --target us --dry-run    # print a diff, write nothing
```

[Vale](https://vale.sh) decides what to change; a small Python wrapper applies
the changes. The few words that need judgement (UK *licence*/*license*,
*programme*/*program*, *cheque*/*check*, ...) are put to a local model as a
multiple-choice question with the surrounding sentence. The model never
rewrites prose: it picks one of the options you supply, or KEEP.

## Install

```
brew install vale            # or see https://vale.sh/docs/install
uv tool install .            # or: pip install .
ln -s "$PWD/man/stylefix.1" /opt/homebrew/share/man/man1/   # optional: man stylefix
```

Python 3.11+, no third-party dependencies. `stylefix --help` gives the full
option reference with examples; `man stylefix` the long form.

## How it works

Every Vale alert lands in one of three tiers:

| tier | Vale rule | what happens |
|---|---|---|
| deterministic | `ToUS/Variants`, `ToUK/Variants`, `ToUK/Ise`, `Chicago/Toward`, `Oxford/Towards` (substitution rules with `action: replace`) | applied, case preserved |
| adjudicated | `ToUS/Ambiguous`, `ToUK/Ambiguous` (existence rules) plus any deterministic hit that is capitalised mid-sentence or inside a quotation | the model chooses between candidates from `stylefix/candidates.py`, or KEEP |
| review | everything else (`Spelling`, `SerialComma`, `Numbers`) | listed in the report |

After the word-level edits, a punctuation pass handles what a regex rule
cannot: curly quotes, primary double (US) or single (UK) quotes with correct
nesting, apostrophes, parenthetical dashes (Chicago em dash / Oxford spaced en
dash), en dashes in number ranges, and date order (September 4, 2026 /
4 September 2026). Chicago also moves commas and periods inside closing
quotes. Front matter, fenced code, inline code, link targets and URLs are
never touched.

The report next to the output lists every deterministic swap, every model
decision with its confidence and reason, and every alert left for a human.

## The model

Any OpenAI-compatible `/v1/chat/completions` endpoint works. `--llm auto`
(the default) tries, in order:

1. `dgx` — the LiteLLM gateway of the [dgx-llm](../dgx-llm) stack, configured
   from `$DGX_LLM_DIR/.env` (default `~/Code/dgx-llm/.env`).
2. `ollama` — `http://localhost:11434`, first installed model.

`--llm none` skips the model: ambiguous words are left alone and listed in the
report; capitalised deterministic swaps are applied anyway.

Override anything with `--url`, `--model`, or the environment variables
`STYLEFIX_LLM_URL`, `STYLEFIX_LLM_MODEL`, `STYLEFIX_LLM_KEY`.

Requests go out in batches of `--batch-size` items (20), `--parallel` (4) at a
time, so a serving stack with continuous batching (vLLM) answers a document's
worth of questions in a couple of round-trips. Decisions are cached in
`.stylefix/cache.json` keyed on target, word and sentence; re-runs are
instant and reproducible, and you can edit a cached choice to override it.
Answers below `--min-confidence` (0.7), invalid answers, and transport errors
all fall through to the report rather than being applied.

### Choosing a model

The question the model answers is narrow (pick one of two or three options,
given a sentence), so any current instruct model handles it; what differs is
speed. `scripts/eval_adjudicator.py` scores an endpoint on 48 gold cases
(noun/verb splits, sense splits, proper nouns, quotations) and reports latency:

```
uv run python scripts/eval_adjudicator.py --llm dgx [--think] [--parallel 8] [--repeat 4]
```

Measured on a DGX Spark serving Qwen3.8-27B (NVFP4) through vLLM:

| mode | accuracy | per item |
|---|---|---|
| thinking off, `--parallel 1` | 47/48 | ~1.0 s |
| thinking off, `--parallel 8` | 47/48 | ~0.33 s |
| `--think`, batch 8, `--parallel 4` | 48/48 | ~3.2 s |

The one miss without thinking is a capitalised common noun ("Colour theory")
kept as if it were a title, which is the conservative failure. Thinking buys
the last case at four to ten times the latency; use `--think` with
`--batch-size 8 --timeout 600` for a final pass on an important document,
and the default for everyday runs. Throughput scales with `--parallel`
because vLLM batches concurrent requests, so a mixture-of-experts model with
few active parameters (e.g. Gemma-4-26B-A4B) will be faster still on large
batches without changing accuracy noticeably.

## Exceptions

Put words or phrases to leave alone in a file, one per line, and pass
`--accept exceptions.txt`. They become a Vale vocabulary and are skipped by
every rule.

## Extending

- **Word pairs** live in `stylefix/wordlist.py`. Edit the table, then run
  `python -m stylefix.wordlist` to regenerate the Vale rules (a test fails if
  they drift).
- **Ambiguous words** live in `stylefix/candidates.py` and the matching
  `Ambiguous.yml` token regex.
- **Style rules** are plain Vale YAML under `stylefix/styles/Chicago` and
  `stylefix/styles/Oxford`; any substitution rule with `action: replace` is
  applied automatically, anything else goes to the report.

## Limitations

- The UK direction does not move punctuation outside quotation marks: whether
  a comma belongs to the quote is not knowable mechanically.
- `Numbers` and `SerialComma` are heuristics and only ever flag.
- `.docx` files: convert with pandoc first
  (`pandoc in.docx -t gfm -o in.md`), fix, convert back.

## Development

```
uv sync
uv run pytest
```
