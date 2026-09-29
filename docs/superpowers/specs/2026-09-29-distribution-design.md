# Distribution: adjudicate, stylefix and proofix on PyPI — design

Make the three packages installable by anyone with `uv tool install` or
`pipx install`, and let each user point them at any OpenAI-compatible
endpoint, local or hosted, without editing code.

## Goals

- `uv tool install stylefix` and `uv tool install proofix` work on a
  machine that has never seen `~/Code`.
- One small config file sets the model endpoint for both tools; either
  tool can override it.
- Hosted APIs that reject unknown request fields (OpenAI's, for one)
  work, as do vLLM, LiteLLM and Ollama.
- The author's current setup (the dgx-llm gateway) keeps working, through
  config rather than code.
- Licensing of bundled third-party data is stated correctly.

## Non-goals

- Bundling Vale or LanguageTool. They stay documented prerequisites with
  the clear errors they already give.
- Installing man pages. Wheels cannot place them; they stay in the repos.
- Named endpoint profiles, a `config` subcommand, or a setup wizard.
- Reshaping adjudicate for users other than stylefix and proofix. It is
  published because they depend on it, at 0.x, with no stability promise.
- mdmemo. It keeps installing stylefix from a path; switching it to the
  PyPI release is a later one-line change.

## Current state

All three test suites pass (adjudicate 20, stylefix 113, proofix 13).
None of the repos has a remote. stylefix and proofix depend on
adjudicate through `[tool.uv.sources] adjudicate = { path = "../adjudicate" }`.
adjudicate's `resolve_endpoint` reads `STYLEFIX_LLM_URL/MODEL/KEY` and
offers a `dgx` preset that reads `~/Code/dgx-llm/.env`; proofix calls the
same function, so today it is configured by stylefix's variables.
stylefix imports `adjudicate.context._HTML_ENTITY`; proofix imports
`_FENCE` and `_FRONT`. The en_US Hunspell dictionary ships in adjudicate
without its license file, which sits in stylefix instead. All three names
are free on PyPI (checked 2026-09-29).

## 1. adjudicate 0.3.0

### Endpoint resolution

```python
resolve_endpoint(app: str, preset: str = "auto", url: str | None = None,
                 model: str | None = None, key: str | None = None,
                 think: bool = False, timeout: float | None = None) -> Endpoint | None
```

`preset` is `auto | ollama | none`. The `dgx` preset and `dgx_endpoint`
are removed. `read_env_file` goes with them.

Settings come from these layers, highest first:

1. function arguments (the CLI flags)
2. `<APP>_LLM_URL`, `<APP>_LLM_MODEL`, `<APP>_LLM_KEY`
   (`STYLEFIX_LLM_*`, `PROOFIX_LLM_*`)
3. `$XDG_CONFIG_HOME/<app>/config.toml`, table `[llm]`
4. `ADJUDICATE_LLM_URL`, `ADJUDICATE_LLM_MODEL`, `ADJUDICATE_LLM_KEY`
5. `$XDG_CONFIG_HOME/adjudicate/config.toml`, table `[llm]`

`$XDG_CONFIG_HOME` defaults to `~/.config`. Layers merge field by field,
with one rule: a layer that sets `url` discards `model` and the key from
every layer below it, since those belonged to a different server. So an
app config that sets only `model` refines the shared endpoint, while
`--url` on the command line never inherits a model name meant for
another host.

The `[llm]` table:

| key | type | meaning |
|---|---|---|
| `url` | string | base URL ending in `/v1` |
| `model` | string | model name; discovered if absent |
| `api_key` | string | bearer token |
| `api_key_env` | string | name of an environment variable holding the token |
| `timeout` | number | seconds per request (120 if no layer sets it) |
| `thinking_switch` | bool | the server accepts `chat_template_kwargs.enable_thinking` |

Setting both `api_key` and `api_key_env` in one table is an error. An
`api_key_env` naming an unset variable is an error. Unknown keys are an
error, so a typo is not silently ignored. A file that is not valid TOML
is an error. Errors raise `ConfigError` (a subclass of `LLMError`) naming
the file and key; the CLIs print it and exit 2. Files are read with the
standard library's `tomllib`.

Outcome:

- `preset == "none"`: return `None`, and read no files.
- A `url` from any layer: return that endpoint. It is not probed. If it
  is unreachable, the first request fails with the existing
  `LLMError` ("cannot reach … at …"), and the items fall through to the
  report as transport errors do today. It never falls back to Ollama.
- No `url`, `preset` `auto` or `ollama`: try local Ollama as today
  (`OLLAMA_HOST`, default `http://localhost:11434`), applying any
  `model`, key, `timeout` from the layers. `auto` returns `None` if
  Ollama is not there.

### Model discovery

If the resolved endpoint has no model, `resolve_endpoint` calls
`GET <url>/models` and takes the first `data[].id`. If that request fails
or lists nothing, it raises `ConfigError`: "no model set for <url> and the
server lists none; set `model` in config.toml or pass --model".

### Request body

`Endpoint` gains `thinking_switch: bool = False`. `chat_template_kwargs`
is sent only when `think` or `thinking_switch` is true. The 400/422
retry gains a step: if the request had `chat_template_kwargs`, retry
without it, then (as now) without `response_format`. Each dropped field
stays dropped for later requests on that `Endpoint`, so a strict server
is probed once per run, not once per batch.

For a thinking model on vLLM (the dgx gateway), `thinking_switch = true`
keeps today's behaviour of sending `enable_thinking: false`.

### Public names

`context.HTML_ENTITY`, `context.FENCE` and `context.FRONT_MATTER` become
public and are exported from the package. The underscored names stay as
aliases for 0.3 so an old consumer does not break mid-upgrade.

### Licensing and docs

- Add `LICENSE` (MIT, Andrew Brož).
- Move `LICENSE-en_US.txt` from `stylefix/dict/` to `adjudicate/dict/`,
  next to the data it covers. Keep `LICENSE-en_GB.txt`.
- `license = "MIT AND LGPL-2.1-or-later"` in `pyproject.toml`, and a
  README section saying the code is MIT and `adjudicate/dict/` carries the
  dictionaries' own licenses. The implementer confirms the exact SPDX
  identifiers against the en_US and en_GB license texts before release.
- README: describe it as the toolkit behind stylefix and proofix, list
  the modules, document the config layers and the `[llm]` table, and
  replace `../` links with GitHub URLs.

## 2. stylefix 0.7.0

- `dependencies = ["spylls>=0.1.7", "adjudicate>=0.3,<0.4"]`. The
  `[tool.uv.sources]` path entry stays: uv uses it for local development
  and it never appears in the published metadata. Release builds use
  `uv build --no-sources` to prove the package builds against the
  published adjudicate.
- `--llm` choices become `auto | ollama | none`; the help text describes
  the config layers. `resolve_endpoint(app="stylefix", …)`.
- `--timeout` defaults to `None` rather than 120, in the CLI and the eval
  script, so a `timeout` in config.toml is not overridden by a flag the
  user never passed. The same rule applies to every flag that maps to a
  config key.
- `stylefix/llm.py` re-exports as before; nothing else imports `dgx_endpoint`.
- `scripts/eval_adjudicator.py` already takes `--llm`, `--url`, `--model`;
  it switches to `app="stylefix"`, and the README's example command drops
  `--llm dgx`.
- Replace the `_HTML_ENTITY` import with `HTML_ENTITY`.
- Remove `stylefix/dict/LICENSE-en_GB.txt` and `LICENSE-en_US.txt` (the
  data lives in adjudicate). Keep `README-varcon.txt` with VarCon.
  `license = "MIT"` plus a README note that `stylefix/dict/varcon.txt.gz`
  is VarCon under its own notice.
- README "Install": `uv tool install stylefix` (or pipx), Vale as a
  prerequisite with install links for macOS, Linux and Windows.
- README "The model": the layer order, then three sample configs:
  Ollama (nothing to configure), a hosted API (`url`, `model`,
  `api_key_env`), and self-hosted vLLM (`thinking_switch = true`). The
  DGX measurements stay as one example, without the `../dgx-llm` link.
- `man/stylefix.1`: the same `--llm` and configuration changes.

## 3. proofix 0.5.0

- `dependencies = ["adjudicate>=0.3,<0.4"]`, the same path source, and
  the same `--no-sources` release build.
- `--llm auto | ollama | none`, `resolve_endpoint(app="proofix", …)`,
  and `--timeout` defaulting to `None` as in stylefix.
- Replace the `_FENCE`/`_FRONT` imports with `FENCE`/`FRONT_MATTER`.
- Add `LICENSE` (MIT) and `license = "MIT"`.
- README "Install": `uv tool install proofix`; LanguageTool (Java) and
  `typos` as optional prerequisites with what is lost without each.
  Replace `../stylefix` and `../mdmemo` with their GitHub URLs, and the
  config paragraph with a pointer to the shared adjudicate config.
- `man/proofix.1`: the `--llm {auto|dgx|ollama|none}` line and the
  configuration text.

## 4. Release work, all three

- `pyproject.toml`: `readme = "README.md"`, `license`, `authors`,
  `[project.urls]` (Homepage, Issues), classifiers (Python 3.11+,
  environment console for the two CLIs, topic text processing).
- One public GitHub repo per package under `AndrewBroz`, created with
  `gh repo create` only after the author confirms each one. `master` is
  pushed as-is.
- Order: adjudicate, then stylefix, then proofix, since each release
  must resolve its dependency from an index.
- Per package: `uv build --no-sources`; upload to TestPyPI; in a scratch
  directory, `uv tool install --index-url https://test.pypi.org/simple/
  --extra-index-url https://pypi.org/simple/ <pkg>` and run the CLI on
  its `examples/` file with `--llm none`; then, with the author's
  go-ahead, upload to PyPI. Uploads use the author's tokens; the
  implementer does not hold them.
- The author's setup: write `~/.config/adjudicate/config.toml` with the
  dgx gateway's URL, model alias, `api_key_env` for the LiteLLM key, and
  `thinking_switch = true`, then run both tools once against a sample
  file to confirm they reach the gateway.

## Testing

- adjudicate, new tests with a temporary `XDG_CONFIG_HOME` and cleared
  env: every layer alone; a higher layer overriding a lower one field by
  field; a `url` in a higher layer discarding a lower `model`; `api_key`
  and `api_key_env` together, unset, and valid; unknown key; invalid
  TOML; `preset="none"` reading nothing.
- adjudicate, against a local `http.server` fake: model discovery with a
  listing, with an empty listing, and with the listing endpoint down; a
  server that returns 400 on `chat_template_kwargs`, checked for exactly
  one retry and a dropped field on the next call; `thinking_switch`
  sending the field.
- stylefix and proofix: existing suites pass after the dependency and
  import changes. A CLI test that `--llm dgx` is rejected, and one that a
  `config.toml` URL reaches the fake server.
- Release: the clean TestPyPI install above, per package.

## Risks

- A strict server may reject `response_format` with a status other than
  400/422. The fallback covers the statuses seen so far; others surface
  as transport errors in the report, which is safe.
- Picking the first model from `/v1/models` may choose an embedding
  model on a server that hosts several. The error text and README tell
  the user to set `model`; discovery is a convenience for single-model
  servers such as Ollama with one pull or a dedicated vLLM.
- `STYLEFIX_LLM_*` no longer configures proofix. Anyone relying on that
  (the author) moves to `ADJUDICATE_LLM_*` or the shared config file;
  the proofix release notes say so.
