# stylefix — design

A local command-line tool that takes a Markdown file and writes a copy
regularized to one English variety (US or UK) and one style guide
(Chicago or Oxford/New Hart's), using Vale to decide and a small Python
wrapper to apply.

## Goals

- One command, no interaction: `stylefix draft.md --target us --style chicago`.
- Fully local by default: Vale binary + Python stdlib + an OpenAI-compatible
  local model endpoint (Ollama) for the few cases that need judgement.
- Reproducible: model decisions are cached and logged so a re-run makes the
  same edits and an editor can override them.

## Non-goals

- Grammar checking, citation formatting, capitalization of titles,
  hyphenation of compounds. These stay as warnings in the report.
- `.docx` round-tripping (pandoc handles that outside the tool).

## Three tiers

1. **Deterministic** — Vale `substitution` rules with `action: replace`.
   `ToUS/Variants.yml`, `ToUK/Variants.yml`, plus style-guide swaps
   (`Chicago/Toward.yml`, `Oxford/Towards.yml`, dash and date rules).
   The applier splices `Action.Params[0]` over `Span`, preserving case.
2. **Adjudicated** — Vale `existence` rules (`ToUS/Ambiguous.yml`,
   `ToUK/Ambiguous.yml`) that only flag. The wrapper owns a candidates
   table (word -> options + rule of thumb) and asks the model to choose one
   option or KEEP, given the surrounding sentence. Invalid or low-confidence
   answers fall through to tier 3.
3. **Human** — everything else (spelling warnings, serial comma, numbers)
   goes into a report next to the output file.

## Components

- `styles/` — Vale styles: `ToUS`, `ToUK`, `Chicago`, `Oxford`.
- `stylefix/vale_runner.py` — writes a temporary `.vale.ini`, runs
  `vale --output=JSON`, returns alerts.
- `stylefix/apply.py` — pure function: text + alerts -> edited text.
- `stylefix/candidates.py` — ambiguous-word tables per target.
- `stylefix/adjudicate.py` — batches items, calls the chat-completions
  endpoint, validates JSON, caches by (target, token, sentence).
- `stylefix/punctuation.py` — quote-style pass (curly quotes, primary
  single vs double, apostrophes) that a regex rule cannot express.
- `stylefix/cli.py` — argparse entry point.

## Data flow

```
input.md
  -> vale (ToXX + style) -> alerts JSON
  -> partition: replace / ambiguous / other
  -> adjudicate ambiguous (cache -> LLM -> validate)
  -> apply replacements (descending offsets)
  -> punctuation pass
  -> output.md + output.report.md
```

## Error handling

- Vale missing: exit 2 with an install hint.
- LLM endpoint unreachable or returning bad JSON: the affected items are
  reported as "needs review", the rest of the run completes. `--no-llm`
  skips the call entirely.
- Never edit inside code spans, code blocks, links/URLs, or front matter.
  Vale already scopes these out; the wrapper only acts on Vale alerts.

## Decisions

- UK target defaults to `-ise` spellings; `--oxford-ize` switches to
  Oxford `-ize`.
- Case preservation: `Colour` -> `Color`, `COLOUR` -> `COLOR`.
- Cache lives at `.stylefix/cache.json` in the working directory.
- Model: any OpenAI-compatible `/v1/chat/completions`; defaults come from
  `STYLEFIX_LLM_URL` and `STYLEFIX_LLM_MODEL`.
