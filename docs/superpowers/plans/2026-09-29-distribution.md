# Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish adjudicate 0.3.0, stylefix 0.7.0 and proofix 0.5.0 to PyPI, each configurable to any OpenAI-compatible endpoint through layered flags, env vars and TOML config files, with an interactive `--setup` and a `--check-endpoint` in both CLIs, and help and man pages that a test keeps in step with the parser.

**Architecture:** Endpoint resolution moves wholly into `adjudicate.llm`: `resolve_endpoint(app, …)` merges five layers (flags, `<APP>_LLM_*`, `~/.config/<app>/config.toml`, `ADJUDICATE_LLM_*`, `~/.config/adjudicate/config.toml`) and falls back to local Ollama. The `dgx` preset is deleted; the author's gateway becomes a config file. `adjudicate.setup` holds the interactive setup and the provenance-printing check; stylefix and proofix become thin callers exposing them as mode flags. Release goes adjudicate → stylefix → proofix via TestPyPI.

**Tech Stack:** Python ≥3.11 (stdlib `tomllib`, `urllib`, `http.server` for test fakes), hatchling (PEP 639 license metadata), uv 0.8 (`uv build --no-sources`, `uv publish`), pytest, `gh`.

**Spec:** `docs/superpowers/specs/2026-09-29-distribution-design.md` (in the stylefix repo). Read it before starting any task.

**Repos:** three sibling directories, each its own git repo on branch `master`:
- `/Users/andrewbroz/Code/adjudicate` (library)
- `/Users/andrewbroz/Code/stylefix` (CLI; this plan lives here)
- `/Users/andrewbroz/Code/proofix` (CLI)

Run each repo's commands from its own directory. Commit in the repo you changed. End every commit message with a blank line and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Existing commit subjects are sentences ending in `; vX.Y.Z` when the version changes; follow that.

## Global Constraints

- `requires-python = ">=3.11"`; config files are read with stdlib `tomllib`; no new runtime dependencies in any package.
- Versions: adjudicate `0.3.0`, stylefix `0.7.0`, proofix `0.5.0`, set in both `pyproject.toml` and the package `__init__.py`.
- stylefix and proofix depend on `adjudicate>=0.3,<0.4`. The `[tool.uv.sources]` path entry stays; release builds use `uv build --no-sources`.
- `--llm` accepts exactly `auto | ollama | none` in both CLIs and the eval script.
- Env var names: `STYLEFIX_LLM_URL/MODEL/KEY`, `PROOFIX_LLM_URL/MODEL/KEY`, `ADJUDICATE_LLM_URL/MODEL/KEY`.
- Config path: `$XDG_CONFIG_HOME/<name>/config.toml` (`~/.config` when unset), table `[llm]`, keys exactly `url`, `model`, `api_key`, `api_key_env`, `timeout`, `thinking_switch`.
- Default request timeout 120 seconds, applied only when no layer sets one; CLI `--timeout` defaults to `None`.
- Code license MIT, copyright "Andrew Brož". No `License ::` classifiers (PEP 639 forbids them alongside a license expression).
- GitHub: `https://github.com/AndrewBroz/<package>`. Repo creation, pushes and every upload need the author's explicit go-ahead at that moment.
- No `../` sibling links and no `~/Code` paths in any README, man page or help text.
- Both CLIs have mode flags `--setup` and `--check-endpoint` in a "configuration" help group; exit statuses as spec §1b (0 works, 1 no working endpoint or cancelled, 2 configuration error or no terminal).
- Every long option in `build_parser()` appears in the tool's man page, and the man page's `.TH` carries the package version; a test in each CLI repo enforces both.

## Review Focus

1. **The author's shared config carries a dgx `model` and `thinking_switch = true`, and they pass `--url` to try another server.** Expected: nothing from the dgx layer leaks through (the model is discovered or taken from `--model`, and `chat_template_kwargs` is not sent). Pinned in Task 3 (`test_higher_url_discards_lower_server_settings`).
2. **Default `--llm auto` on a machine where Ollama is running but no model is pulled.** Expected: the run proceeds as `--llm none`, not exit 2. Pinned in Task 3 (`test_auto_with_empty_ollama_is_none`).
3. **Running the test suites on the author's machine, which will have a real `~/.config/adjudicate/config.toml` after Task 9.** Expected: no test reaches a real endpoint. Pinned by the autouse isolation fixture in each repo's `tests/conftest.py` (Tasks 2, 5, 7) and `test_isolation_hides_real_config` in each.
4. **Running `--setup` a second time, over a config file that already has an `[llm]` table and other tables.** Expected: the old table is shown, nothing changes without a yes, a `.bak` is kept, and the other tables survive byte for byte. Pinned in Task 3b (`test_replace_keeps_other_tables_and_backs_up`, `test_declining_replace_changes_nothing`).
5. **A malformed config file when running the CLI.** Expected: `stylefix: <path>: …` / `proofix: <path>: …` on stderr and exit 2, not a traceback. Pinned in Tasks 5 and 7 (`test_bad_config_exits_2`).

---

### Task 1: adjudicate — public names for the Markdown regexes

stylefix imports `adjudicate.context._HTML_ENTITY`; proofix imports `_FENCE` and `_FRONT`. Make them public, keep the underscored names as aliases for 0.3.

**Files:**
- Modify: `adjudicate/adjudicate/context.py:9-16`
- Modify: `adjudicate/adjudicate/__init__.py`
- Test: `adjudicate/tests/test_context.py`

**Interfaces:**
- Produces: `adjudicate.FENCE`, `adjudicate.FRONT_MATTER`, `adjudicate.HTML_ENTITY` (compiled `re.Pattern`s, also importable from `adjudicate.context`). Tasks 5 and 7 import them.

- [ ] **Step 1: Write the failing test** — append to `tests/test_context.py`:

```python
def test_public_regex_names():
    import adjudicate
    from adjudicate import context
    assert adjudicate.FENCE is context.FENCE is context._FENCE
    assert adjudicate.FRONT_MATTER is context.FRONT_MATTER is context._FRONT
    assert adjudicate.HTML_ENTITY is context.HTML_ENTITY is context._HTML_ENTITY
    assert context.FRONT_MATTER.match("---\ntitle: x\n---\nbody")
    assert context.HTML_ENTITY.fullmatch("&mdash;")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_context.py::test_public_regex_names -v`
Expected: FAIL with `AttributeError: module 'adjudicate' has no attribute 'FENCE'`

- [ ] **Step 3: Implement** — in `adjudicate/context.py`, rename the three definitions and add aliases directly below the block of regexes (after the `_HTML_ENTITY` line):

```python
FENCE = re.compile(r"^(```|~~~)[^\n]*\n.*?^\1[ \t]*$", re.M | re.S)
```
```python
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
```
```python
HTML_ENTITY = re.compile(r"&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]*);")

# Pre-0.3 names, kept so an old consumer does not break mid-upgrade; removed in 0.4.
_FENCE, _FRONT, _HTML_ENTITY = FENCE, FRONT_MATTER, HTML_ENTITY
```

Then replace every other use of `_FENCE`, `_FRONT` and `_HTML_ENTITY` inside `context.py` with the public names (`grep -n "_FENCE\|_FRONT\|_HTML_ENTITY" adjudicate/context.py` lists them). In `adjudicate/__init__.py`, extend the context import:

```python
from .context import (FENCE, FRONT_MATTER, HTML_ENTITY, at_sentence_start,  # noqa: F401
                      inside_quotes, map_prose, paragraph_bounds, prose_regions,
                      protected_spans, sentence_context)
```

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: 21 passed

- [ ] **Step 5: Commit**

```bash
git add adjudicate/context.py adjudicate/__init__.py tests/test_context.py
git commit -m "Public FENCE, FRONT_MATTER and HTML_ENTITY; underscored names kept as aliases"
```

---

### Task 2: adjudicate — request body works against strict servers

Stop sending vLLM's `chat_template_kwargs` by default; on 400/422 drop the offending optional field for the rest of the run. Add the test fixtures every later adjudicate task uses.

**Files:**
- Create: `adjudicate/tests/conftest.py`
- Create: `adjudicate/tests/test_llm.py`
- Modify: `adjudicate/adjudicate/llm.py` (the `Endpoint` class, lines 18-68)

**Interfaces:**
- Produces: `Endpoint(url, model, key="", name="custom", think=False, timeout=120.0, thinking_switch=False)`; `Endpoint.chat(system, user, timeout=None, json_mode=True) -> str` (unchanged signature); `Endpoint._headers() -> dict[str, str]`; module constant `DEFAULT_TIMEOUT = 120.0`. Fixtures `server` (a `FakeServer` with `.url`, `.base`, `.models`, `.models_status`, `.reject`, `.requests`, `.auth`) and autouse `isolated_llm_config`.

- [ ] **Step 1: Write the fixtures** — create `tests/conftest.py`:

```python
"""Shared fixtures: no test may see the developer's real endpoint config,
and HTTP tests talk to a local fake OpenAI-compatible server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

LLM_ENV = [f"{app}_LLM_{s}" for app in ("ADJUDICATE", "STYLEFIX", "PROOFIX")
           for s in ("URL", "MODEL", "KEY")]


@pytest.fixture(autouse=True)
def isolated_llm_config(tmp_path_factory, monkeypatch):
    """An empty XDG config home, no *_LLM_* variables, and an Ollama address
    that refuses connections at once."""
    xdg = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    for name in LLM_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    return xdg


class FakeServer:
    def __init__(self):
        self.models = ["served-model"]   # listed by /v1/models and /api/tags
        self.models_status = 200         # status for GET /v1/models
        self.reject = set()              # chat body fields answered with HTTP 400
        self.requests = []               # every chat body received, parsed
        self.auth = []                   # Authorization header of every request


@pytest.fixture
def server():
    state = FakeServer()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            state.auth.append(self.headers.get("Authorization"))
            if self.path == "/v1/models":
                if state.models_status != 200:
                    return self._send(state.models_status, {"error": "down"})
                return self._send(200, {"data": [{"id": m} for m in state.models]})
            if self.path == "/api/tags":           # Ollama's own listing
                return self._send(200, {"models": [{"name": m} for m in state.models]})
            self._send(404, {})

        def do_POST(self):
            state.auth.append(self.headers.get("Authorization"))
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append(body)
            bad = state.reject & body.keys()
            if bad:
                return self._send(400, {"error": f"unrecognized fields: {sorted(bad)}"})
            self._send(200, {"choices": [{"message": {"content": '{"decisions": []}'}}]})

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    state.base = f"http://127.0.0.1:{httpd.server_port}"
    state.url = state.base + "/v1"
    yield state
    httpd.shutdown()
    httpd.server_close()
```

- [ ] **Step 2: Write the failing tests** — create `tests/test_llm.py`:

```python
import os

import pytest

from adjudicate.llm import Endpoint, LLMError


def test_isolation_hides_real_config(isolated_llm_config):
    assert os.environ["XDG_CONFIG_HOME"] == str(isolated_llm_config)
    assert not any(os.environ.get(f"{app}_LLM_{s}") for app in ("ADJUDICATE", "STYLEFIX", "PROOFIX")
                   for s in ("URL", "MODEL", "KEY"))


def test_default_body_has_no_vllm_extension(server):
    Endpoint(server.url, "m").chat("s", "u")
    body = server.requests[-1]
    assert "chat_template_kwargs" not in body
    assert body["response_format"] == {"type": "json_object"}
    assert body["model"] == "m" and body["temperature"] == 0


def test_thinking_switch_sends_enable_thinking_false(server):
    Endpoint(server.url, "m", thinking_switch=True).chat("s", "u")
    assert server.requests[-1]["chat_template_kwargs"] == {"enable_thinking": False}


def test_think_sends_enable_thinking_true(server):
    Endpoint(server.url, "m", think=True).chat("s", "u")
    assert server.requests[-1]["chat_template_kwargs"] == {"enable_thinking": True}


def test_rejected_extension_is_dropped_once_for_the_run(server):
    server.reject = {"chat_template_kwargs"}
    ep = Endpoint(server.url, "m", thinking_switch=True)
    ep.chat("s", "u")
    ep.chat("s", "u")
    # first call: rejected, then retried without; second call: sent without
    assert len(server.requests) == 3
    assert ["chat_template_kwargs" in b for b in server.requests] == [True, False, False]
    assert all("response_format" in b for b in server.requests)


def test_both_optional_fields_dropped_in_order(server):
    server.reject = {"chat_template_kwargs", "response_format"}
    ep = Endpoint(server.url, "m", thinking_switch=True)
    assert ep.chat("s", "u") == '{"decisions": []}'
    assert [sorted(b.keys() & server.reject) for b in server.requests] == [
        ["chat_template_kwargs", "response_format"], ["response_format"], []]


def test_400_with_nothing_to_drop_raises(server):
    server.reject = {"messages"}
    with pytest.raises(LLMError, match="HTTP 400"):
        Endpoint(server.url, "m").chat("s", "u")
    assert len(server.requests) == 2   # with response_format, then without it
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_llm.py -v`
Expected: `test_isolation_hides_real_config` PASS; `test_default_body_has_no_vllm_extension` FAIL (`chat_template_kwargs` present); the `thinking_switch` tests FAIL with `TypeError: … unexpected keyword argument 'thinking_switch'`.

- [ ] **Step 4: Implement** — in `adjudicate/llm.py`, change `from dataclasses import dataclass` to `from dataclasses import dataclass, field`, add below `class LLMError`:

```python
DEFAULT_TIMEOUT = 120.0

# Request fields a strict server may reject with 400/422, in the order they
# are dropped on retry.
_OPTIONAL_FIELDS = ("chat_template_kwargs", "response_format")
```

and replace the `Endpoint` class's fields and `chat` method with:

```python
@dataclass
class Endpoint:
    url: str            # base URL ending in /v1
    model: str
    key: str = ""
    name: str = "custom"
    think: bool = False   # let reasoning models think before answering
    timeout: float = DEFAULT_TIMEOUT
    thinking_switch: bool = False   # server honours chat_template_kwargs.enable_thinking
    _dropped: set[str] = field(default_factory=set, init=False, repr=False, compare=False)

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json",
                "Authorization": f"Bearer {self.key or 'none'}"}

    def chat(self, system: str, user: str, timeout: float | None = None,
             json_mode: bool = True) -> str:
        timeout = self.timeout if timeout is None else timeout
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
        }
        if self.think or self.thinking_switch:
            # Reasoning models spend tokens thinking; this task doesn't need it.
            body["chat_template_kwargs"] = {"enable_thinking": self.think}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for name in self._dropped:
            body.pop(name, None)
        req = urllib.request.Request(
            self.url.rstrip("/") + "/chat/completions",
            data=json.dumps(body).encode(), headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            if e.code in (400, 422):
                # A strict server rejecting an extension: drop it for the rest of the run.
                for name in _OPTIONAL_FIELDS:
                    if name in body:
                        self._dropped.add(name)
                        return self.chat(system, user, timeout, json_mode)
            raise LLMError(f"{self.name} returned HTTP {e.code}: {detail}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise LLMError(f"cannot reach {self.name} at {self.url}: {e}") from e
        try:
            content = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"unexpected response shape from {self.name}: {str(data)[:300]}") from e
        return strip_thinking(content)
```

In `reachable`, replace the inline `headers={…}` with `headers=self._headers()`.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: 28 passed

- [ ] **Step 6: Commit**

```bash
git add adjudicate/llm.py tests/conftest.py tests/test_llm.py
git commit -m "chat_template_kwargs only on request; a 400/422 drops an optional field for the run"
```

---

### Task 3: adjudicate — layered endpoint configuration

Replace `resolve_endpoint` and delete the dgx preset. This is the core of the spec's §1; re-read "Endpoint resolution" and "Model discovery" there first.

**Files:**
- Create: `adjudicate/tests/test_config.py`
- Modify: `adjudicate/adjudicate/llm.py` (delete `read_env_file`, `dgx_endpoint`, old `resolve_endpoint`; add the functions below)
- Modify: `adjudicate/adjudicate/__init__.py` (export `ConfigError`)

**Interfaces:**
- Consumes: `Endpoint`, `DEFAULT_TIMEOUT`, `ollama_endpoint()` (existing, unchanged), fixtures from Task 2.
- Produces:
  - `class ConfigError(LLMError)`
  - `config_home() -> Path`
  - `read_config(path: Path) -> dict[str, tuple[object, str]]` — validated `[llm]` settings as `{key: (value, source)}`, with `api_key_env` already resolved into `api_key`; `{}` when the file is absent
  - `env_layer(prefix: str) -> dict[str, tuple[str, str]]` — from `<prefix>_LLM_URL/MODEL/KEY`, keys `url`/`model`/`api_key`, source the variable name
  - `merge_layers(layers: list[dict]) -> dict[str, tuple[object, str]]` — highest first
  - `list_models(ep: Endpoint, timeout: float = 5.0) -> list[str] | None` — every id at `/models`, `None` if the listing fails
  - `discover_model(ep: Endpoint, timeout: float = 5.0) -> str | None` — the first of `list_models`
  - `Endpoint.sources: dict[str, str]` — where each of `url`, `model`, `api_key`, `timeout`, `thinking_switch` came from (`api_key` absent when there is no key). Task 3b prints it.
  - `resolve_endpoint(app: str, preset: str = "auto", url: str | None = None, model: str | None = None, key: str | None = None, think: bool = False, timeout: float | None = None) -> Endpoint | None` — **`app` is now the first positional argument**; Tasks 5 and 7 call it with keywords after `app` and `preset`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_config.py`:

```python
import pytest

from adjudicate.llm import ConfigError, merge_layers, resolve_endpoint


def write(xdg, name, body):
    path = xdg / name / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return path


# --- presets ---------------------------------------------------------------

def test_none_reads_nothing(isolated_llm_config):
    write(isolated_llm_config, "adjudicate", "this is [not toml")
    assert resolve_endpoint("stylefix", "none") is None


def test_unknown_preset_is_an_error():
    with pytest.raises(ConfigError, match="dgx"):
        resolve_endpoint("stylefix", "dgx")


def test_auto_with_nothing_configured_and_no_ollama_is_none():
    assert resolve_endpoint("stylefix") is None


# --- layers ----------------------------------------------------------------

def test_shared_config_is_used(isolated_llm_config):
    write(isolated_llm_config, "adjudicate", 'llm.url = "http://a/v1"\nllm.model = "m1"\n')
    ep = resolve_endpoint("stylefix")
    assert (ep.url, ep.model, ep.name) == ("http://a/v1", "m1", "custom")


def test_app_config_refines_shared_model(isolated_llm_config):
    write(isolated_llm_config, "adjudicate", '[llm]\nurl = "http://a/v1"\nmodel = "m1"\n')
    write(isolated_llm_config, "proofix", '[llm]\nmodel = "m2"\n')
    ep = resolve_endpoint("proofix")
    assert (ep.url, ep.model) == ("http://a/v1", "m2")
    assert resolve_endpoint("stylefix").model == "m1"   # the other app is unaffected


def test_app_env_beats_app_config(isolated_llm_config, monkeypatch):
    write(isolated_llm_config, "stylefix", '[llm]\nurl = "http://a/v1"\nmodel = "a"\n')
    monkeypatch.setenv("STYLEFIX_LLM_MODEL", "b")
    ep = resolve_endpoint("stylefix")
    assert (ep.url, ep.model) == ("http://a/v1", "b")


def test_app_config_beats_shared_env(isolated_llm_config, monkeypatch):
    monkeypatch.setenv("ADJUDICATE_LLM_URL", "http://shared/v1")
    monkeypatch.setenv("ADJUDICATE_LLM_MODEL", "s")
    write(isolated_llm_config, "stylefix", '[llm]\nurl = "http://app/v1"\nmodel = "a"\n')
    assert resolve_endpoint("stylefix").url == "http://app/v1"


def test_flags_beat_everything(isolated_llm_config, monkeypatch):
    monkeypatch.setenv("STYLEFIX_LLM_URL", "http://env/v1")
    monkeypatch.setenv("STYLEFIX_LLM_MODEL", "e")
    ep = resolve_endpoint("stylefix", url="http://flag/v1", model="f", key="k")
    assert (ep.url, ep.model, ep.key) == ("http://flag/v1", "f", "k")


def test_higher_url_discards_lower_server_settings(isolated_llm_config, server):
    write(isolated_llm_config, "adjudicate",
          '[llm]\nurl = "http://dgx/v1"\nmodel = "dgx-model"\napi_key = "k"\n'
          'thinking_switch = true\ntimeout = 30\n')
    ep = resolve_endpoint("stylefix", url=server.url)
    assert ep.model == "served-model"      # discovered, not inherited
    assert ep.key == "" and ep.thinking_switch is False
    assert ep.timeout == 30                # timeout is not server-specific


def test_merge_layers_is_field_by_field():
    merged = merge_layers([{"model": ("hi", "A")},
                           {"url": ("u", "B"), "model": ("lo", "B"), "timeout": (5, "B")}])
    assert merged == {"url": ("u", "B"), "model": ("hi", "A"), "timeout": (5, "B")}


def test_sources_name_each_layer(isolated_llm_config, monkeypatch):
    monkeypatch.setenv("MY_KEY", "k")
    path = write(isolated_llm_config, "adjudicate",
                 '[llm]\nurl = "http://a/v1"\nmodel = "m"\napi_key_env = "MY_KEY"\n')
    monkeypatch.setenv("STYLEFIX_LLM_MODEL", "e")
    ep = resolve_endpoint("stylefix", timeout=9)
    assert ep.sources == {"url": str(path), "model": "STYLEFIX_LLM_MODEL",
                          "api_key": f"{path} (api_key_env MY_KEY)",
                          "timeout": "--timeout", "thinking_switch": "default"}


def test_sources_for_discovery_and_ollama(server, monkeypatch):
    ep = resolve_endpoint("stylefix", url=server.url)
    assert (ep.sources["url"], ep.sources["model"]) == ("--url", "listed by the server")
    assert "api_key" not in ep.sources
    monkeypatch.setenv("OLLAMA_HOST", server.base)
    ep = resolve_endpoint("stylefix")
    assert (ep.sources["url"], ep.sources["model"]) == ("local Ollama", "local Ollama")


# --- keys and validation ---------------------------------------------------

def test_api_key_env(isolated_llm_config, monkeypatch):
    monkeypatch.setenv("MY_KEY", "sekrit")
    write(isolated_llm_config, "adjudicate",
          '[llm]\nurl = "http://a/v1"\nmodel = "m"\napi_key_env = "MY_KEY"\n')
    assert resolve_endpoint("stylefix").key == "sekrit"


def test_api_key_env_unset_is_an_error(isolated_llm_config):
    write(isolated_llm_config, "adjudicate", '[llm]\nurl = "http://a/v1"\napi_key_env = "MY_KEY"\n')
    with pytest.raises(ConfigError, match="MY_KEY"):
        resolve_endpoint("stylefix")


def test_api_key_env_empty_is_an_error(isolated_llm_config, monkeypatch):
    monkeypatch.setenv("MY_KEY", "")
    write(isolated_llm_config, "adjudicate", '[llm]\nurl = "http://a/v1"\napi_key_env = "MY_KEY"\n')
    with pytest.raises(ConfigError, match="MY_KEY"):
        resolve_endpoint("stylefix")


def test_both_key_forms_is_an_error(isolated_llm_config):
    write(isolated_llm_config, "adjudicate", '[llm]\napi_key = "a"\napi_key_env = "B"\n')
    with pytest.raises(ConfigError, match="not both"):
        resolve_endpoint("stylefix")


def test_unknown_key_is_an_error(isolated_llm_config):
    path = write(isolated_llm_config, "stylefix", '[llm]\nurl = "http://a/v1"\nmodle = "m"\n')
    with pytest.raises(ConfigError, match="modle") as e:
        resolve_endpoint("stylefix")
    assert str(path) in str(e.value)


@pytest.mark.parametrize("value", ['"60"', "true"])
def test_wrong_type_is_an_error(isolated_llm_config, value):
    write(isolated_llm_config, "adjudicate", f'[llm]\nurl = "http://a/v1"\ntimeout = {value}\n')
    with pytest.raises(ConfigError, match="timeout"):
        resolve_endpoint("stylefix")


def test_invalid_toml_names_the_file(isolated_llm_config):
    path = write(isolated_llm_config, "adjudicate", "[llm\nurl=")
    with pytest.raises(ConfigError, match="not valid TOML") as e:
        resolve_endpoint("stylefix")
    assert str(path) in str(e.value)


def test_other_tables_are_ignored(isolated_llm_config):
    write(isolated_llm_config, "stylefix", '[llm]\nurl = "http://a/v1"\nmodel = "m"\n[other]\nx = 1\n')
    assert resolve_endpoint("stylefix").model == "m"


# --- timeout ---------------------------------------------------------------

def test_timeout_default_config_and_flag(isolated_llm_config):
    assert resolve_endpoint("stylefix", url="http://a/v1", model="m").timeout == 120.0
    write(isolated_llm_config, "adjudicate", '[llm]\nurl = "http://a/v1"\nmodel = "m"\ntimeout = 30\n')
    assert resolve_endpoint("stylefix").timeout == 30.0
    assert resolve_endpoint("stylefix", timeout=5).timeout == 5.0


# --- model discovery -------------------------------------------------------

def test_model_discovered_from_server(server):
    assert resolve_endpoint("stylefix", url=server.url).model == "served-model"


def test_empty_listing_is_an_error(server):
    server.models = []
    with pytest.raises(ConfigError, match="lists none"):
        resolve_endpoint("stylefix", url=server.url)


def test_listing_down_is_an_error(server):
    server.models_status = 500
    with pytest.raises(ConfigError, match="--model"):
        resolve_endpoint("stylefix", url=server.url)


# --- Ollama ----------------------------------------------------------------

def test_auto_finds_ollama(server, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", server.base)
    ep = resolve_endpoint("stylefix")
    assert (ep.name, ep.url, ep.model) == ("ollama", server.url, "served-model")


def test_auto_with_empty_ollama_is_none(server, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", server.base)
    server.models = []
    assert resolve_endpoint("stylefix") is None


def test_explicit_ollama_with_no_model_is_an_error(server, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", server.base)
    server.models = []
    with pytest.raises(ConfigError):
        resolve_endpoint("stylefix", "ollama")


def test_explicit_ollama_ignores_configured_url(isolated_llm_config, server, monkeypatch):
    write(isolated_llm_config, "adjudicate", '[llm]\nurl = "http://remote/v1"\nmodel = "r"\n')
    monkeypatch.setenv("OLLAMA_HOST", server.base)
    ep = resolve_endpoint("stylefix", "ollama", model="picked")
    assert (ep.name, ep.model) == ("ollama", "picked")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: collection error, `ImportError: cannot import name 'ConfigError'`

- [ ] **Step 3: Implement** — in `adjudicate/llm.py`:

1. Replace the module docstring with `"""Minimal OpenAI-compatible chat client, and endpoint resolution from flags, environment and config files."""`, add `import tomllib` to the imports, and keep `from pathlib import Path`.
2. Add below `class LLMError`:

```python
class ConfigError(LLMError):
    """An invalid endpoint setting; the message names the file or variable."""
```

3. Delete `read_env_file`, `dgx_endpoint` and the old `resolve_endpoint`. Keep `ollama_endpoint` unchanged. Add one field to `Endpoint`, after `_dropped`:

```python
    sources: dict[str, str] = field(default_factory=dict, repr=False, compare=False)
```
4. Append:

```python
# [llm] keys and the types they accept.
_CONFIG_KEYS: dict[str, tuple[type, ...]] = {
    "url": (str,), "model": (str,), "api_key": (str,), "api_key_env": (str,),
    "timeout": (int, float), "thinking_switch": (bool,),
}
# Settings that belong to one server: a layer that names a url drops these
# from the layers below it.
_SERVER_KEYS = ("model", "api_key", "thinking_switch")


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def read_config(path: Path) -> dict:
    """The validated [llm] table of a config file as {key: (value, source)},
    with api_key_env resolved into api_key; {} if the file does not exist."""
    if not path.exists():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path}: not valid TOML: {e}") from e
    table = data.get("llm", {})
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: 'llm' must be a table")
    for k, v in table.items():
        if k not in _CONFIG_KEYS:
            raise ConfigError(f"{path}: unknown key '{k}' in [llm] "
                              f"(known: {', '.join(_CONFIG_KEYS)})")
        types = _CONFIG_KEYS[k]
        if not isinstance(v, types) or (isinstance(v, bool) and bool not in types):
            raise ConfigError(f"{path}: [llm] {k} must be "
                              f"{' or '.join(t.__name__ for t in types)}, not {v!r}")
    if "api_key" in table and "api_key_env" in table:
        raise ConfigError(f"{path}: set api_key or api_key_env in [llm], not both")
    src = str(path)
    out = {k: (v, src) for k, v in table.items() if k != "api_key_env"}
    if "api_key_env" in table:
        var = table["api_key_env"]
        if not os.environ.get(var):
            raise ConfigError(f"{path}: api_key_env names {var}, which is not set")
        out["api_key"] = (os.environ[var], f"{src} (api_key_env {var})")
    return out


def env_layer(prefix: str) -> dict:
    """Settings from <prefix>_LLM_URL, _MODEL and _KEY; empty values are unset."""
    out = {}
    for key, suffix in (("url", "URL"), ("model", "MODEL"), ("api_key", "KEY")):
        name = f"{prefix}_LLM_{suffix}"
        if os.environ.get(name):
            out[key] = (os.environ[name], name)
    return out


def merge_layers(layers: list[dict]) -> dict:
    """Merge {key: (value, source)} layers field by field, highest first."""
    out: dict = {}
    for layer in reversed(layers):
        if "url" in layer:
            for k in _SERVER_KEYS:
                out.pop(k, None)
        out.update(layer)
    return out


def list_models(ep: Endpoint, timeout: float = 5.0) -> list[str] | None:
    """Every model id the server lists at /models, or None if that fails."""
    req = urllib.request.Request(ep.url.rstrip("/") + "/models", headers=ep._headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception:
        return None
    items = data.get("data", []) if isinstance(data, dict) else []
    return [m["id"] for m in items if isinstance(m, dict) and m.get("id")]


def discover_model(ep: Endpoint, timeout: float = 5.0) -> str | None:
    models = list_models(ep, timeout)
    return models[0] if models else None


_FLAG_SOURCE = {"url": "--url", "model": "--model", "api_key": "key argument",
                "timeout": "--timeout"}


def resolve_endpoint(app: str, preset: str = "auto", url: str | None = None,
                     model: str | None = None, key: str | None = None,
                     think: bool = False, timeout: float | None = None) -> Endpoint | None:
    """The endpoint `app` should use, or None for no model.

    preset: auto | ollama | none. For auto, settings come from, highest
    first: the arguments, <APP>_LLM_* variables, ~/.config/<app>/config.toml,
    ADJUDICATE_LLM_* variables, ~/.config/adjudicate/config.toml; with no
    url anywhere, a local Ollama is used if one is running with a model.
    ollama means local Ollama with only the arguments applied. The result's
    `sources` says where each setting came from. Raises ConfigError for an
    invalid setting or an endpoint with no usable model.
    """
    if preset == "none":
        return None
    if preset not in ("auto", "ollama"):
        raise ConfigError(f"unknown endpoint preset '{preset}' (choose auto, ollama or none)")
    flags = {k: (v, _FLAG_SOURCE[k]) for k, v in
             (("url", url), ("model", model), ("api_key", key), ("timeout", timeout)) if v}
    if preset == "ollama":
        settings = flags
    else:
        home = config_home()
        settings = merge_layers([
            flags,
            env_layer(app.upper()),
            read_config(home / app / "config.toml"),
            env_layer("ADJUDICATE"),
            read_config(home / "adjudicate" / "config.toml"),
        ])
    values = {k: v for k, (v, _) in settings.items()}
    sources = {"timeout": "default", "thinking_switch": "default",
               **{k: s for k, (_, s) in settings.items()}}
    t = float(values.get("timeout", DEFAULT_TIMEOUT))
    if "url" in values:
        ep = Endpoint(url=values["url"], model=values.get("model", ""),
                      key=values.get("api_key", ""), think=think, timeout=t,
                      thinking_switch=values.get("thinking_switch", False))
    else:
        ep = ollama_endpoint()
        if ep is None:
            return None
        sources["url"] = "local Ollama"
        if not values.get("model") and ep.model:
            sources["model"] = "local Ollama"
        ep.model = values.get("model") or ep.model
        ep.key = values.get("api_key", "")
        ep.think, ep.timeout = think, t
        ep.thinking_switch = values.get("thinking_switch", False)
    if not ep.model:
        ep.model = discover_model(ep) or ""
        sources["model"] = "listed by the server"
    if not ep.model:
        if ep.name == "ollama" and preset == "auto":
            return None          # Ollama is running but has no model pulled
        raise ConfigError(f"no model set for {ep.url} and the server lists none; "
                          "set `model` in config.toml or pass --model")
    ep.sources = sources
    return ep
```

5. In `adjudicate/__init__.py`, change the llm import to `from .llm import ConfigError, Endpoint, LLMError, resolve_endpoint, strip_thinking  # noqa: F401`.

- [ ] **Step 4: Run the new tests, then the whole suite**

Run: `uv run pytest tests/test_config.py -v` — Expected: all PASS.
Run: `uv run pytest -q` — Expected: 57 passed (21 + 7 + 29).

- [ ] **Step 5: Confirm nothing mentions dgx any more**

Run: `grep -rn -i "dgx" adjudicate tests; grep -n "STYLEFIX" adjudicate/*.py`
Expected: no output (the `STYLEFIX` in `tests/conftest.py` is the isolation list, and is expected).

- [ ] **Step 6: Commit**

```bash
git add adjudicate/llm.py adjudicate/__init__.py tests/test_config.py
git commit -m "Endpoint from layered flags, env and config.toml per app, with the source of each setting; model discovery; dgx preset removed"
```

---

### Task 3b: adjudicate — `setup` module: interactive setup and endpoint check

The shared logic behind `--setup` and `--check-endpoint` in both CLIs. Re-read spec §1b first. Everything takes injected streams so tests run without a terminal.

**Files:**
- Create: `adjudicate/adjudicate/setup.py`
- Create: `adjudicate/tests/test_setup.py`
- Modify: `adjudicate/adjudicate/__init__.py` (export `check_endpoint`, `run_setup`)

**Interfaces:**
- Consumes: `resolve_endpoint`, `list_models`, `ollama_endpoint`, `config_home`, `ConfigError`, `LLMError`, `Endpoint` (with `_dropped` and `sources`) from Tasks 2 and 3; fixtures `server` and `isolated_llm_config`.
- Produces:
  - `check_endpoint(app: str, out: TextIO | None = None, preset: str = "auto", url: str | None = None, model: str | None = None, timeout: float | None = None) -> int` — prints the resolved settings and a live test; returns 0 (works), 1 (no endpoint, or it does not answer), 2 (config error)
  - `run_setup(app: str, inp: TextIO | None = None, out: TextIO | None = None, require_tty: bool = True) -> int` — returns 0 when saved and the check passes, 1 when cancelled, declined or the check fails, 2 when stdin is not a terminal
  - Tasks 5 and 7 call both with `app="stylefix"` / `app="proofix"`.

- [ ] **Step 1: Write the failing tests** — create `tests/test_setup.py`:

```python
import io
import os
import stat
import tomllib

import pytest

from adjudicate.setup import check_endpoint, run_setup


def setup(answers, app="stylefix"):
    """Run setup on scripted answers, one per prompt; returns (status, output)."""
    out = io.StringIO()
    status = run_setup(app, io.StringIO("".join(a + "\n" for a in answers)), out,
                       require_tty=False)
    return status, out.getvalue()


def shared(xdg):
    return xdg / "adjudicate" / "config.toml"


def llm(path):
    return tomllib.loads(path.read_text())["llm"]


# --- the three paths --------------------------------------------------------

def test_self_hosted_detects_thinking_switch(isolated_llm_config, server):
    # kind 3 (self-hosted), url, key 3 (none), model 1, save 1 (shared)
    status, out = setup(["3", server.url, "3", "1", "1"])
    assert status == 0, out
    assert llm(shared(isolated_llm_config)) == {
        "url": server.url, "model": "served-model", "thinking_switch": True}
    assert server.requests[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert "thinking_switch = true" in out


def test_self_hosted_that_rejects_thinking_switch(isolated_llm_config, server):
    server.reject = {"chat_template_kwargs"}
    status, out = setup(["3", server.url, "3", "1", "1"])
    assert status == 0, out
    assert llm(shared(isolated_llm_config))["thinking_switch"] is False


def test_hosted_with_env_key(isolated_llm_config, server, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "k")
    # kind 2 (hosted), url, key 1 (env var), var name, model 1, save 1
    status, out = setup(["2", server.url, "1", "TEST_KEY", "1", "1"])
    assert status == 0, out
    assert llm(shared(isolated_llm_config)) == {
        "url": server.url, "model": "served-model", "api_key_env": "TEST_KEY"}
    assert server.auth[0] == "Bearer k"              # the listing was asked with the key
    assert "chat_template_kwargs" not in server.requests[0]


def test_ollama_saved_to_app_file_as_explicit_url(isolated_llm_config, server, monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", server.base)
    # kind 1 (Ollama), model 1, save 2 (stylefix only)
    status, out = setup(["1", "1", "2"])
    assert status == 0, out
    assert llm(isolated_llm_config / "stylefix" / "config.toml") == {
        "url": server.url, "model": "served-model"}
    assert not shared(isolated_llm_config).exists()


def test_ollama_not_running(isolated_llm_config):
    status, out = setup(["1"])
    assert status == 1 and "ollama serve" in out
    assert not shared(isolated_llm_config).exists()


def test_typed_model_name(isolated_llm_config, server):
    # model 2 = "Other (type a name)"
    status, out = setup(["3", server.url, "3", "2", "my-model", "1"])
    assert status == 0, out
    assert llm(shared(isolated_llm_config))["model"] == "my-model"


# --- URL handling -------------------------------------------------------------

def test_url_without_scheme_is_asked_again(isolated_llm_config, server):
    status, out = setup(["3", "gpu:8000/v1", server.base + "/v1/chat/completions/", "3", "1", "1"])
    assert status == 0, out
    assert "include the scheme" in out
    assert llm(shared(isolated_llm_config))["url"] == server.url


def test_v1_offered_and_appended(isolated_llm_config, server):
    status, out = setup(["3", server.base, "y", "3", "1", "1"])
    assert status == 0, out
    assert llm(shared(isolated_llm_config))["url"] == server.url


def test_unlistable_server_asks_to_continue(isolated_llm_config, server):
    server.models_status = 500
    status, out = setup(["3", server.url, "3", "n"])
    assert status == 1 and "could not list models" in out
    assert not shared(isolated_llm_config).exists()


# --- keys -----------------------------------------------------------------------

def test_pasted_key_is_saved_0600_and_never_shown(isolated_llm_config, server):
    status, out = setup(["2", server.url, "2", "sekrit", "1", "1"])
    assert status == 0, out
    path = shared(isolated_llm_config)
    assert llm(path)["api_key"] == "sekrit"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert "sekrit" not in out


def test_unset_env_key_warns(isolated_llm_config, server):
    status, out = setup(["2", server.url, "1", "NOT_SET_ANYWHERE", "1", "1"])
    assert "NOT_SET_ANYWHERE is not set" in out
    # saved even so; the check afterwards fails with the ConfigError for the unset variable
    assert llm(shared(isolated_llm_config))["api_key_env"] == "NOT_SET_ANYWHERE"
    assert status == 2


# --- existing files -------------------------------------------------------------

OLD = '[llm]\nurl = "http://old/v1"\nmodel = "old"\n\n[other]\nx = 1\n'


def test_replace_keeps_other_tables_and_backs_up(isolated_llm_config, server):
    path = shared(isolated_llm_config)
    path.parent.mkdir(parents=True)
    path.write_text(OLD)
    status, out = setup(["3", server.url, "3", "1", "1", "y"])
    assert status == 0, out
    assert "already has" in out and "http://old/v1" in out
    assert path.with_name("config.toml.bak").read_text() == OLD
    data = tomllib.loads(path.read_text())
    assert data["llm"]["url"] == server.url and data["other"] == {"x": 1}


def test_declining_replace_changes_nothing(isolated_llm_config, server):
    path = shared(isolated_llm_config)
    path.parent.mkdir(parents=True)
    path.write_text(OLD)
    status, out = setup(["3", server.url, "3", "1", "1", "n"])
    assert status == 1
    assert path.read_text() == OLD
    assert not path.with_name("config.toml.bak").exists()


def test_other_tables_only_gets_llm_appended(isolated_llm_config, server):
    path = shared(isolated_llm_config)
    path.parent.mkdir(parents=True)
    path.write_text("[other]\nx = 1\n")
    status, out = setup(["3", server.url, "3", "1", "1"])
    assert status == 0, out
    data = tomllib.loads(path.read_text())
    assert data["other"] == {"x": 1} and data["llm"]["url"] == server.url


def test_dotted_keys_are_not_edited(isolated_llm_config, server):
    path = shared(isolated_llm_config)
    path.parent.mkdir(parents=True)
    path.write_text('llm.url = "http://old/v1"\n')
    status, out = setup(["3", server.url, "3", "1", "1"])
    assert status == 1 and "by hand" in out and f'url = "{server.url}"' in out
    assert path.read_text() == 'llm.url = "http://old/v1"\n'


# --- cancelling and terminals -----------------------------------------------------

def test_end_of_input_cancels(isolated_llm_config):
    status, out = setup(["3"])            # input ends at the URL prompt
    assert status == 1 and "cancelled" in out
    assert not shared(isolated_llm_config).exists()


def test_refuses_without_a_terminal(isolated_llm_config):
    out = io.StringIO()
    assert run_setup("stylefix", io.StringIO(""), out) == 2
    assert "terminal" in out.getvalue()


# --- check_endpoint ---------------------------------------------------------------

def check(**kw):
    out = io.StringIO()
    return check_endpoint("stylefix", out, **kw), out.getvalue()


def test_check_with_nothing_configured():
    status, out = check()
    assert status == 1 and "stylefix --setup" in out


def test_check_config_error(isolated_llm_config):
    path = shared(isolated_llm_config)
    path.parent.mkdir(parents=True)
    path.write_text("[llm\n")
    status, out = check()
    assert status == 2 and str(path) in out


def test_check_prints_sources_and_hides_the_key(isolated_llm_config, server, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "sekrit")
    path = shared(isolated_llm_config)
    path.parent.mkdir(parents=True)
    path.write_text(f'[llm]\nurl = "{server.url}"\nmodel = "m"\napi_key_env = "TEST_KEY"\n')
    status, out = check()
    assert status == 0, out
    lines = {line.split()[0]: line for line in out.splitlines() if line.strip()}
    assert server.url in lines["url"] and str(path) in lines["url"]
    assert "(hidden)" in lines["api_key"] and "api_key_env TEST_KEY" in lines["api_key"]
    assert "default" in lines["timeout"]
    assert "sekrit" not in out
    assert "chat ✓" in out


def test_check_endpoint_that_does_not_answer():
    status, out = check(url="http://127.0.0.1:9/v1", model="m")
    assert status == 1 and "chat ✗" in out
```

That is 21 tests.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_setup.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'adjudicate.setup'`

- [ ] **Step 3: Implement** — create `adjudicate/setup.py`:

```python
"""Interactive endpoint setup (--setup) and a non-interactive check
(--check-endpoint), shared by the tools built on adjudicate."""

from __future__ import annotations

import getpass
import json
import os
import re
import shutil
import sys
import time
import tomllib
from pathlib import Path
from typing import TextIO

from .llm import (ConfigError, Endpoint, LLMError, config_home, list_models,
                  ollama_endpoint, resolve_endpoint)

ROWS = ("url", "model", "api_key", "timeout", "thinking_switch")
PING = 'Answer with the JSON object {"ok": true} and nothing else.'
_KEY_ORDER = ("url", "model", "api_key", "api_key_env", "timeout", "thinking_switch")
_VAR_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LLM_HEADER = re.compile(r"^[ \t]*\[llm\][ \t]*(?:#.*)?$", re.M)
_ANY_HEADER = re.compile(r"^[ \t]*\[", re.M)


class SetupCancelled(Exception):
    pass


class Prompter:
    """Numbered choices and questions over any pair of text streams."""

    def __init__(self, inp: TextIO, out: TextIO):
        self.inp, self.out = inp, out

    def _line(self, prompt: str) -> str:
        self.out.write(prompt)
        self.out.flush()
        line = self.inp.readline()
        if not line:
            raise SetupCancelled
        return line.strip()

    def ask(self, question: str, default: str = "") -> str:
        hint = f" [{default}]" if default else ""
        while True:
            answer = self._line(f"{question}{hint}: ") or default
            if answer:
                return answer

    def secret(self, question: str) -> str:
        if self.inp is sys.stdin and sys.stdin.isatty():
            while True:
                try:
                    answer = getpass.getpass(f"{question}: ", stream=self.out).strip()
                except EOFError:
                    raise SetupCancelled from None
                if answer:
                    return answer
        return self.ask(question)

    def choose(self, question: str, options: list[str], default: int = 0) -> int:
        self.out.write(question + "\n")
        for i, option in enumerate(options, 1):
            self.out.write(f"  {i}. {option}\n")
        while True:
            answer = self._line(f"> [{default + 1}] ") or str(default + 1)
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self.out.write(f"  choose 1-{len(options)}\n")

    def confirm(self, question: str, default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        while True:
            answer = self._line(f"{question} [{hint}] ").lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False


def llm_table(values: dict, hide_key: bool = False) -> str:
    """values as a TOML [llm] table, keys in a fixed order."""
    lines = ["[llm]"]
    for k in _KEY_ORDER:
        if k not in values:
            continue
        v = values[k]
        if k == "api_key" and hide_key:
            text = '"(hidden)"'
        elif isinstance(v, bool):
            text = "true" if v else "false"
        elif isinstance(v, str):
            text = json.dumps(v)          # a JSON string is a valid TOML basic string
        else:
            text = repr(v)
        lines.append(f"{k} = {text}")
    return "\n".join(lines) + "\n"


def replace_llm_table(text: str, table: str) -> str | None:
    """text with its [llm] table replaced by table, or table appended if
    there is none; None if llm keys are set some other way (dotted keys,
    an inline table), which is left for the user to edit."""
    m = _LLM_HEADER.search(text)
    if m is None:
        if "llm" in tomllib.loads(text):
            return None
        new = text.rstrip("\n") + ("\n\n" if text.strip() else "") + table
    else:
        nxt = _ANY_HEADER.search(text, m.end())
        end = nxt.start() if nxt else len(text)
        rest = text[end:]
        new = text[:m.start()] + table + ("\n" + rest if rest else "")
    try:
        if tomllib.loads(new).get("llm") != tomllib.loads(table)["llm"]:
            return None
    except tomllib.TOMLDecodeError:
        return None
    return new


def save_config(path: Path, values: dict, p: Prompter, secret: bool) -> bool:
    """Write values as the [llm] table of path, asking before replacing one."""
    out, table = p.out, llm_table(values)
    shown = llm_table(values, hide_key=True)
    if path.exists():
        text = path.read_text(encoding="utf-8")
        try:
            current = tomllib.loads(text).get("llm")
            new_text = replace_llm_table(text, table)
        except tomllib.TOMLDecodeError as e:
            out.write(f"{path} is not valid TOML ({e}); not editing it.\n")
            current, new_text = None, None
        if new_text is None:
            out.write(f"Add this to {path} by hand"
                      f"{' (with your key in place of (hidden))' if secret else ''}:\n\n{shown}\n")
            return False
        if current is not None:
            out.write(f"{path} already has:\n\n{llm_table(current, hide_key=True)}\n"
                      f"Replace it with:\n\n{shown}\n")
            if not p.confirm("Replace?", default=False):
                out.write("Left unchanged.\n")
                return False
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        new_text = table
    path.write_text(new_text, encoding="utf-8")
    if secret:
        os.chmod(path, 0o600)
    out.write(f"Wrote {path}\n")
    return True


def _ask_url(p: Prompter) -> str:
    while True:
        url = p.ask("Base URL (ending in /v1)").strip().rstrip("/")
        if url.endswith("/chat/completions"):
            url = url[: -len("/chat/completions")]
        if "://" not in url:
            p.out.write("  include the scheme, e.g. http://gpu-box:8000/v1\n")
            continue
        if not url.endswith("/v1") and p.confirm(f"  Add /v1, giving {url}/v1?", default=True):
            url += "/v1"
        return url


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _setup(app: str, p: Prompter) -> int:
    out = p.out
    ollama = ollama_endpoint()
    ollama_models = (list_models(ollama) or []) if ollama else []
    ollama_label = ("Local Ollama (not running)" if ollama is None
                    else f"Local Ollama (found: {_plural(len(ollama_models), 'model')})")
    kind = p.choose("Where is your model?",
                    [ollama_label, "A hosted API (OpenAI-compatible)",
                     "A self-hosted server (vLLM, LiteLLM, llama.cpp)"],
                    default=0 if ollama_models else 1)
    values: dict = {}
    secret = False
    if kind == 0:
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        if ollama is None:
            out.write(f"Ollama is not answering at {host}. Start it (`ollama serve`), pull a "
                      "model (`ollama pull <name>`), and run setup again.\n")
            return 1
        if not ollama_models:
            out.write("Ollama is running but has no models. Pull one (`ollama pull <name>`) "
                      "and run setup again.\n")
            return 1
        ep = Endpoint(ollama.url, ollama_models[p.choose("Model:", ollama_models)], name="ollama")
    else:
        url = _ask_url(p)
        ep = Endpoint(url, "")
        k = p.choose("API key:", ["From an environment variable (recommended)",
                                  "Paste it (saved in the config file, mode 0600)", "None"],
                     default=0 if kind == 1 else 2)
        if k == 0:
            while not _VAR_NAME.match(var := p.ask("Variable name")):
                out.write("  a variable name is letters, digits and _\n")
            values["api_key_env"] = var
            ep.key = os.environ.get(var, "")
            out.write(f"  {var} is set ✓\n" if ep.key else
                      f"  {var} is not set in this shell; testing without a key. "
                      f"Set it before using {app}.\n")
        elif k == 1:
            ep.key = values["api_key"] = p.secret("API key")
            secret = True
        models = list_models(ep)
        if models is None:
            out.write(f"  ✗ could not list models at {url}/models\n")
            if not p.confirm("Continue anyway?", default=False):
                return 1
            models = []
        else:
            out.write(f"  ✓ reachable; lists {_plural(len(models), 'model')}\n")
        options = models + ["Other (type a name)"]
        choice = p.choose("Model:", options) if models else len(models)
        ep.model = options[choice] if choice < len(models) else p.ask("Model name")
    values["url"], values["model"] = ep.url, ep.model

    out.write("Testing a request... ")
    out.flush()
    ep.thinking_switch = kind == 2
    t0 = time.monotonic()
    try:
        ep.chat(PING, "ping", timeout=min(ep.timeout, 30))
    except LLMError as e:
        out.write(f"✗\n  {e}\n")
        if not p.confirm("Save anyway?", default=False):
            return 1
    else:
        out.write(f"✓ {time.monotonic() - t0:.1f} s\n")
        if kind == 2:
            accepted = "chat_template_kwargs" not in ep._dropped
            values["thinking_switch"] = accepted
            out.write("  server accepts enable_thinking → thinking_switch = true\n" if accepted
                      else "  server rejects enable_thinking → thinking_switch = false\n")

    shared, own = config_home() / "adjudicate" / "config.toml", config_home() / app / "config.toml"
    where = p.choose("Save to:", [f"{shared} (shared by every tool that uses adjudicate)",
                                  f"{own} ({app} only)"])
    if not save_config((shared, own)[where], values, p, secret):
        return 1
    out.write("\n")
    return check_endpoint(app, out)


def run_setup(app: str, inp: TextIO | None = None, out: TextIO | None = None,
              require_tty: bool = True) -> int:
    """Ask where the model is, test it, and save the [llm] table."""
    inp, out = inp or sys.stdin, out or sys.stdout
    if require_tty and not inp.isatty():
        out.write(f"{app} --setup asks questions, so it needs a terminal. To configure "
                  f"without one, write the [llm] table by hand (see `{app} --help`).\n")
        return 2
    try:
        return _setup(app, Prompter(inp, out))
    except (SetupCancelled, KeyboardInterrupt):
        out.write("\nSetup cancelled; nothing was written.\n")
        return 1


def check_endpoint(app: str, out: TextIO | None = None, preset: str = "auto",
                   url: str | None = None, model: str | None = None,
                   timeout: float | None = None) -> int:
    """Print each resolved setting and where it came from, then test the endpoint."""
    out = out or sys.stdout
    try:
        ep = resolve_endpoint(app, preset, url=url, model=model, timeout=timeout)
    except ConfigError as e:
        out.write(f"{app}: {e}\n")
        return 2
    if ep is None:
        why = ("--llm none: no model is used." if preset == "none" else
               "No endpoint: nothing is configured and no local Ollama with a model is running.")
        out.write(f"{why}\nRun `{app} --setup` to configure one.\n")
        return 1
    shown = {"url": ep.url, "model": ep.model,
             "api_key": "(hidden)" if ep.key else "(none)",
             "timeout": f"{ep.timeout:g}", "thinking_switch": str(ep.thinking_switch).lower()}
    width = max(len(v) for v in shown.values())
    for name in ROWS:
        out.write(f"{name:<16} {shown[name]:<{width}}  {ep.sources.get(name, '')}".rstrip() + "\n")
    models = list_models(ep)
    listing = "✗" if models is None else f"✓ {_plural(len(models), 'model')}"
    t0 = time.monotonic()
    try:
        ep.chat(PING, "ping", timeout=min(ep.timeout, 30))
    except LLMError as e:
        out.write(f"/models {listing}   chat ✗ {e}\n")
        return 1
    out.write(f"/models {listing}   chat ✓ {time.monotonic() - t0:.1f} s\n")
    return 0
```

In `adjudicate/__init__.py`, add `from .setup import check_endpoint, run_setup  # noqa: F401`.

- [ ] **Step 4: Run the new tests, then the whole suite**

Run: `uv run pytest tests/test_setup.py -v` — Expected: 21 passed.
Run: `uv run pytest -q` — Expected: 78 passed (57 + 21).

If a scripted-answer test fails because a prompt was added or reordered, fix the implementation to match spec §1b, not the answer list; the lists encode the spec's order (kind, URL, key, model, test, save, replace).

- [ ] **Step 5: Try it by hand once** — against the fake nothing: `uv run python -c "from adjudicate import run_setup; raise SystemExit(run_setup('stylefix'))"` in a terminal, choose 2, give `http://127.0.0.1:9/v1`, choose None, answer `n` to "Continue anyway?". Expected: the prompts read cleanly, exit status 1, nothing written.

- [ ] **Step 6: Commit**

```bash
git add adjudicate/setup.py adjudicate/__init__.py tests/test_setup.py
git commit -m "setup module: interactive --setup that tests and saves [llm], and a --check-endpoint that shows each setting's source"
```

---

### Task 4: adjudicate — license, metadata, README, 0.3.0

**Files:**
- Create: `adjudicate/LICENSE`
- Create: `adjudicate/adjudicate/dict/LICENSE-en_US.txt` (moved from stylefix in Task 6; copy it here now)
- Modify: `adjudicate/pyproject.toml`, `adjudicate/adjudicate/__init__.py:16`, `adjudicate/README.md`

**Interfaces:**
- Produces: a wheel `dist/adjudicate-0.3.0-py3-none-any.whl` whose metadata carries `License-Expression: MIT AND LGPL-2.0-or-later AND LicenseRef-SCOWL`.

Licensing facts (checked 2026-09-29, recorded so the implementer need not re-derive them): en_GB's notice says "covered by his original LGPL licence" with no version, and under the LGPL's own terms an unversioned grant allows any version, hence `LGPL-2.0-or-later`. en_US is under SCOWL's permissive notice, which has no SPDX identifier, hence `LicenseRef-SCOWL`.

- [ ] **Step 1: Add the license files**

```bash
cp ../stylefix/stylefix/dict/LICENSE-en_US.txt adjudicate/dict/LICENSE-en_US.txt
```

Create `LICENSE`:

```
MIT License

Copyright (c) 2026 Andrew Brož

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Metadata** — replace the `[project]` table of `pyproject.toml` with:

```toml
[project]
name = "adjudicate"
version = "0.3.0"
description = "Bounded, auditable text edits chosen by a language model: detector proposes, model picks, applier splices."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT AND LGPL-2.0-or-later AND LicenseRef-SCOWL"
license-files = ["LICENSE", "adjudicate/dict/LICENSE-*.txt"]
authors = [{ name = "Andrew Brož" }]
dependencies = ["spylls>=0.1.7"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Topic :: Text Processing :: Linguistic",
]

[project.urls]
Homepage = "https://github.com/AndrewBroz/adjudicate"
Issues = "https://github.com/AndrewBroz/adjudicate/issues"
```

Set `__version__ = "0.3.0"` in `adjudicate/__init__.py`, and in its docstring replace "Shared by stylefix and proofix." with "The toolkit behind stylefix and proofix."

- [ ] **Step 3: README** — replace the line "Used by [stylefix](../stylefix) … commas)." and the "Modules:" paragraph with the text below, keep the rest of the README, and fix any remaining `../` links to GitHub URLs (`grep -n "\.\./" README.md` must print nothing afterwards):

````markdown
It is the toolkit behind [stylefix](https://github.com/AndrewBroz/stylefix)
(US/UK spelling and style) and [proofix](https://github.com/AndrewBroz/proofix)
(typos, punctuation, commas). It is published because they depend on it; the
API may change between 0.x releases.

```
pip install adjudicate
```

Modules: `llm` (OpenAI-compatible client and endpoint resolution), `core`
(Item, Decision, Cache, `adjudicate`), `apply` (Edit, `apply_edits`),
`context` (sentence context, Markdown prose regions), `dictionary`
(Hunspell lookups over the bundled en_US and en_GB dictionaries), `setup`
(`run_setup` and `check_endpoint`, behind the tools' `--setup` and
`--check-endpoint`).

## Choosing the model endpoint

`resolve_endpoint(app, preset="auto", url=None, model=None, key=None,
think=False, timeout=None)` merges settings from, highest first:

1. its arguments (the calling tool's `--url`, `--model`, `--timeout`)
2. `<APP>_LLM_URL`, `<APP>_LLM_MODEL`, `<APP>_LLM_KEY`, e.g. `STYLEFIX_LLM_URL`
3. `~/.config/<app>/config.toml`
4. `ADJUDICATE_LLM_URL`, `ADJUDICATE_LLM_MODEL`, `ADJUDICATE_LLM_KEY`
5. `~/.config/adjudicate/config.toml`, shared by every tool

(`$XDG_CONFIG_HOME` replaces `~/.config` when set.) Layers merge field by
field, except that a layer naming a `url` drops the `model`, key and
`thinking_switch` of the layers below it, since those described another
server. With no `url` anywhere, a local Ollama is used if it is running with
a model pulled; otherwise there is no model and callers fall back to
listing items for review.

```toml
[llm]
url = "https://api.example.com/v1"   # any OpenAI-compatible base URL
model = "some-model"                  # optional: the server's first listed model
api_key_env = "EXAMPLE_API_KEY"       # or api_key = "..."; not both
timeout = 120                         # seconds per request
thinking_switch = false               # true for vLLM/LiteLLM serving a reasoning model
```

`thinking_switch = true` sends `chat_template_kwargs: {enable_thinking:
false}`, which vLLM honours and strict APIs reject; if a server answers 400
or 422 to it, it is dropped for the rest of the run. Unknown keys, wrong
types, and an `api_key_env` naming an unset variable are errors
(`ConfigError`), so a typo is never silently ignored.

## License

The code is MIT (see `LICENSE`). The dictionaries in `adjudicate/dict/`
keep their own licenses: en_US under the SCOWL notice in
`LICENSE-en_US.txt`, en_GB under the LGPL as stated in `LICENSE-en_GB.txt`.
````

- [ ] **Step 4: Build and inspect**

Run: `uv run pytest -q && rm -rf dist && uv build --no-sources`
Expected: 78 passed; `Successfully built dist/adjudicate-0.3.0.tar.gz` and `…-py3-none-any.whl`.

Run: `unzip -l dist/adjudicate-0.3.0-py3-none-any.whl | grep -i licen && unzip -p dist/adjudicate-0.3.0-py3-none-any.whl 'adjudicate-0.3.0.dist-info/METADATA' | grep -E "^(License-Expression|License-File|Project-URL|Requires-Dist)"`
Expected: `LICENSE`, `LICENSE-en_US.txt`, `LICENSE-en_GB.txt` listed; `License-Expression: MIT AND LGPL-2.0-or-later AND LicenseRef-SCOWL`; two `Project-URL` lines; `Requires-Dist: spylls>=0.1.7`. If hatchling rejects the expression or `license-files`, stop and report the exact error; do not drop the LGPL or SCOWL terms to make it build.

- [ ] **Step 5: Commit**

```bash
git add LICENSE adjudicate/dict/LICENSE-en_US.txt pyproject.toml adjudicate/__init__.py README.md uv.lock
git commit -m "MIT license, dictionary licenses declared, PyPI metadata, README for strangers; v0.3.0"
```

---

### Task 5: stylefix — adopt adjudicate 0.3

**Files:**
- Create: `stylefix/tests/conftest.py`
- Create: `stylefix/tests/test_endpoint_cli.py`
- Modify: `stylefix/pyproject.toml:6` (dependency), `stylefix/stylefix/cli.py` (lines 17, 42-72 epilog, 130-133, 147, the start of `main`, 292-293, the "no model endpoint available" message), `stylefix/stylefix/styleitems.py:16,114`, `stylefix/scripts/eval_adjudicator.py` (lines 3, 93-102)

**Interfaces:**
- Consumes: `resolve_endpoint(app, preset, url=, model=, key=, think=, timeout=)`, `ConfigError`, `HTML_ENTITY` (Tasks 1 and 3); `run_setup(app)`, `check_endpoint(app, preset=, url=, model=, timeout=)` (Task 3b).

- [ ] **Step 1: Test isolation** — create `tests/conftest.py`:

```python
"""No test may see the developer's real endpoint config or reach a model."""

import pytest

LLM_ENV = [f"{app}_LLM_{s}" for app in ("ADJUDICATE", "STYLEFIX", "PROOFIX")
           for s in ("URL", "MODEL", "KEY")]


@pytest.fixture(autouse=True)
def isolated_llm_config(tmp_path_factory, monkeypatch):
    xdg = tmp_path_factory.mktemp("xdg")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    for name in LLM_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    return xdg
```

Do not run the suite yet: stylefix resolves adjudicate from `../adjudicate`, now 0.3, whose `resolve_endpoint` takes `app` first, so the old positional call in `cli.py` fails every end-to-end test with `ConfigError: unknown endpoint preset 'None'` until Step 4.

- [ ] **Step 2: Write the failing CLI tests** — create `tests/test_endpoint_cli.py`:

```python
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from stylefix.cli import build_parser, main

DOC = "The license was granted.\n"   # license -> UK is a sense split: always adjudicated


def test_isolation_hides_real_config(isolated_llm_config):
    assert os.environ["XDG_CONFIG_HOME"] == str(isolated_llm_config)
    assert not any(os.environ.get(f"{app}_LLM_{s}") for app in ("ADJUDICATE", "STYLEFIX", "PROOFIX")
                   for s in ("URL", "MODEL", "KEY"))


def test_dgx_preset_is_gone():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["x.md", "--target", "us", "--llm", "dgx"])


def test_timeout_flag_defaults_to_none():
    assert build_parser().parse_args(["x.md", "--target", "us"]).timeout is None


def test_bad_config_exits_2(isolated_llm_config, tmp_path, capsys):
    cfg = isolated_llm_config / "adjudicate" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("[llm]\nmodle = 'x'\n")
    src = tmp_path / "d.md"
    src.write_text(DOC)
    assert main([str(src), "--target", "uk", "--no-cache", "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("stylefix: ") and str(cfg) in err and "modle" in err


@pytest.fixture
def chat_server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            data = json.dumps({"choices": [{"message": {"content": '{"decisions": []}'}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1", received
    httpd.shutdown()
    httpd.server_close()


def test_no_endpoint_suggests_setup(tmp_path, capsys):
    src = tmp_path / "d.md"
    src.write_text(DOC)
    assert main([str(src), "--target", "uk", "--no-cache", "--dry-run"]) == 0
    assert "stylefix --setup" in capsys.readouterr().err


def test_check_endpoint_needs_no_input_file(capsys):
    assert main(["--check-endpoint"]) == 1          # nothing configured in the isolated home
    assert "stylefix --setup" in capsys.readouterr().out


def test_setup_needs_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["--setup"]) == 2
    assert "terminal" in capsys.readouterr().out


def test_config_url_reaches_the_server(isolated_llm_config, tmp_path, chat_server):
    url, received = chat_server
    cfg = isolated_llm_config / "adjudicate" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(f'[llm]\nurl = "{url}"\nmodel = "m"\n')
    src = tmp_path / "d.md"
    src.write_text(DOC)
    assert main([str(src), "--target", "uk", "--no-cache", "--dry-run"]) == 0
    assert received and received[0]["model"] == "m"
```

"license" with `--target uk` is a noun/verb sense split (`stylefix/candidates.py`, `TO_UK`), so it always becomes an adjudication item (checked 2026-09-29: `--llm none` reports "1 ambiguous word(s)"), and a configured endpoint must receive a request.

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_endpoint_cli.py -v`
Expected: `test_dgx_preset_is_gone` FAIL (dgx still a choice); `test_timeout_flag_defaults_to_none` FAIL (120.0); `test_bad_config_exits_2`, `test_no_endpoint_suggests_setup` and `test_config_url_reaches_the_server` FAIL with `ConfigError` from the old positional call; `test_check_endpoint_needs_no_input_file` and `test_setup_needs_a_terminal` FAIL (unrecognized arguments).

- [ ] **Step 4: Implement**

`pyproject.toml`: `dependencies = ["spylls>=0.1.7", "adjudicate>=0.3,<0.4"]`.

`stylefix/cli.py`:
- line 17: `from .llm import ConfigError, resolve_endpoint`
- epilog first example: replace "ambiguous words decided by the first reachable model (DGX, then Ollama)" with "ambiguous words decided by the configured model, or local Ollama", and add as the new first example:

```
  stylefix --setup
      choose and test a model endpoint, and save it for stylefix and proofix
```
- epilog `environment:` block becomes:

```
environment:
  STYLEFIX_LLM_URL, STYLEFIX_LLM_MODEL, STYLEFIX_LLM_KEY
      the model endpoint for stylefix (same as --url, --model, and the API key)
  ADJUDICATE_LLM_URL, ADJUDICATE_LLM_MODEL, ADJUDICATE_LLM_KEY
      the same, shared with proofix; below the stylefix variables and config
  OLLAMA_HOST   Ollama base URL (default http://localhost:11434)
```

  and add to the `files:` block of the epilog, as its first entries:

```
  ~/.config/stylefix/config.toml     [llm] url, model, api_key or api_key_env,
                                     timeout, thinking_switch (stylefix only)
  ~/.config/adjudicate/config.toml   the same table, shared with proofix
```

- the `--llm` argument:

```python
    m.add_argument("--llm", choices=["auto", "ollama", "none"], default="auto",
                   help="auto: the endpoint from --url, STYLEFIX_LLM_*, "
                        "~/.config/stylefix/config.toml, ADJUDICATE_LLM_* or "
                        "~/.config/adjudicate/config.toml, else local Ollama; "
                        "ollama: local Ollama only; none: skip the model, ambiguous "
                        "words go to the report (default: %(default)s)")
```

- the `--timeout` argument: `default=None`, help `"seconds to wait for one model request (default: 120, or timeout in config.toml)"`
- after the model group, a configuration group:

```python
    c = p.add_argument_group("configuration", "set up or check the model endpoint, then exit")
    c.add_argument("--setup", action="store_true",
                   help="choose a model endpoint interactively, test it, and save it to "
                        "~/.config/adjudicate/config.toml or ~/.config/stylefix/config.toml")
    c.add_argument("--check-endpoint", action="store_true",
                   help="show the endpoint stylefix would use and where each setting comes "
                        "from, then test it; exit 0 if it answers, 1 if not, 2 on a config error")
```

- at the top of `main`, directly after `args = build_parser().parse_args(argv)` and before the `--list-styles` check:

```python
    if args.setup:
        return run_setup("stylefix")
    if args.check_endpoint:
        return check_endpoint("stylefix", preset=args.llm, url=args.url, model=args.model,
                              timeout=args.timeout)
```

  with `from adjudicate import check_endpoint, run_setup` added to the imports.
- the message printed when `items and ep is None`: append `; run `stylefix --setup` to configure one` when `args.llm == "auto"`, so for `auto` it reads `stylefix: no model endpoint available (--llm auto); 1 ambiguous word(s) will be listed for review; run `stylefix --setup` to configure one`
- the `resolve_endpoint` call in `main`:

```python
    try:
        ep = resolve_endpoint("stylefix", args.llm, url=args.url, model=args.model,
                              think=args.think, timeout=args.timeout)
    except ConfigError as e:
        print(f"stylefix: {e}", file=sys.stderr)
        return 2
```

`stylefix/styleitems.py`: line 16 `from adjudicate import HTML_ENTITY`; line 114 `_HTML_ENTITY` → `HTML_ENTITY`.

`scripts/eval_adjudicator.py`: docstring line 3 becomes `    uv run python scripts/eval_adjudicator.py [--url URL] [--model X] [--think] [--parallel 4]`; the `--llm` argument becomes `ap.add_argument("--llm", choices=["auto", "ollama", "none"], default="auto")`; `--timeout` gets `default=None`; the call becomes `ep = resolve_endpoint("stylefix", args.llm, url=args.url, model=args.model, think=args.think, timeout=args.timeout)`.

Then refresh the lock: `uv lock`.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: 121 passed. **If a test that passed before this task fails now** (other than the new ones in `test_endpoint_cli.py`), the isolation fixture exposed a dependence on a live model or on the real `~/.config/stylefix/accept.txt`: report which test and why, and do not weaken the fixture to make it pass.
Also run `grep -rn -i "dgx\|_HTML_ENTITY" stylefix scripts` — expected: no output.

- [ ] **Step 6: Commit** (this includes the pre-existing one-line `uv.lock` version catch-up)

```bash
git add pyproject.toml uv.lock stylefix/cli.py stylefix/styleitems.py scripts/eval_adjudicator.py tests/conftest.py tests/test_endpoint_cli.py
git commit -m "Endpoint from adjudicate 0.3's config layers; --llm auto|ollama|none; tests never see real config"
```

---

### Task 6: stylefix — license, metadata, README, man page, 0.7.0

**Files:**
- Create: `stylefix/LICENSE` (the MIT text from Task 4, Step 1, verbatim)
- Delete: `stylefix/stylefix/dict/LICENSE-en_GB.txt`, `stylefix/stylefix/dict/LICENSE-en_US.txt`
- Modify: `stylefix/pyproject.toml`, `stylefix/stylefix/__init__.py:3`, `stylefix/README.md`, `stylefix/man/stylefix.1`
- Create: `stylefix/tests/test_docs.py`

- [ ] **Step 0: The drift test** — create `tests/test_docs.py`, run it, and expect failures (the man page says 0.6.0 and lacks the new flags); Step 4 makes it pass:

```python
"""The man page and --help must keep up with the parser."""

import re
from pathlib import Path

from stylefix import __version__
from stylefix.cli import build_parser

MAN = (Path(__file__).parent.parent / "man" / "stylefix.1").read_text(encoding="utf-8")
PLAIN = MAN.replace("\\-", "-")          # roff writes --llm as \-\-llm


def test_every_long_option_is_in_the_man_page():
    missing = [o for a in build_parser()._actions for o in a.option_strings
               if o.startswith("--") and o not in PLAIN]
    assert missing == []


def test_llm_choices_match():
    choices = next(a.choices for a in build_parser()._actions if "--llm" in a.option_strings)
    assert "{" + "|".join(choices) + "}" in PLAIN


def test_man_version_matches():
    m = re.search(r'^\.TH \S+ 1 "[^"]*" "stylefix ([^"]+)"', MAN, re.M)
    assert m and m.group(1) == __version__


def test_no_dgx_in_help_or_man():
    assert "dgx" not in build_parser().format_help().lower()
    assert "dgx" not in MAN.lower()
```

Run: `uv run pytest tests/test_docs.py -v`
Expected: `test_every_long_option_is_in_the_man_page` FAIL listing `--setup`, `--check-endpoint` (and any other option the page never documented); `test_llm_choices_match` and `test_no_dgx_in_help_or_man` FAIL; `test_man_version_matches` FAIL (`0.6.0`).

- [ ] **Step 1: License files**

```bash
git rm stylefix/dict/LICENSE-en_GB.txt stylefix/dict/LICENSE-en_US.txt
cp ../adjudicate/LICENSE LICENSE
```

- [ ] **Step 2: Metadata** — the `[project]` table becomes:

```toml
[project]
name = "stylefix"
version = "0.7.0"
description = "Regularize a Markdown file to US or UK English and a style guide, using Vale plus a language model for the ambiguous cases."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT AND LicenseRef-VarCon"
license-files = ["LICENSE", "stylefix/dict/README-varcon.txt"]
authors = [{ name = "Andrew Brož" }]
dependencies = ["spylls>=0.1.7", "adjudicate>=0.3,<0.4"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Topic :: Text Processing :: Markup :: Markdown",
]

[project.urls]
Homepage = "https://github.com/AndrewBroz/stylefix"
Issues = "https://github.com/AndrewBroz/stylefix/issues"
```

Set `__version__ = "0.7.0"` in `stylefix/__init__.py`.

- [ ] **Step 3: README**

Opening paragraph: "(Chicago or Oxford), fully automatically and fully locally." → "(Chicago, Oxford, AP, GPO, APA or Guardian), fully automatically, and locally unless you point it at a hosted model." Two lines further down, "are put to a local model" → "are put to a language model".

`## Install` section becomes:

````markdown
## Install

```
uv tool install stylefix      # or: pipx install stylefix
```

stylefix also needs [Vale](https://vale.sh/docs/install) on your PATH:
`brew install vale` on macOS, `choco install vale` on Windows, or a release
binary from GitHub on Linux. Python 3.11+.

`stylefix --help` gives the full option reference with examples. The man
page is in the repository at `man/stylefix.1` (`man ./man/stylefix.1`).
````

In `## The model`, replace everything from the heading down to (not including) "Requests go out in batches" with:

````markdown
## The model

The quickest way to set one up is

```
stylefix --setup
```

which asks where your model is (local Ollama, a hosted API, or your own
server), tests it, and saves the answer where both stylefix and proofix
find it. `stylefix --check-endpoint` shows what stylefix will use, where
each setting came from, and whether the endpoint answers.

Any OpenAI-compatible `/v1/chat/completions` endpoint works: Ollama, vLLM,
LiteLLM, llama.cpp's server, or a hosted API. stylefix takes its settings
from, highest first: `--url`/`--model`/`--timeout`; `STYLEFIX_LLM_URL`,
`STYLEFIX_LLM_MODEL`, `STYLEFIX_LLM_KEY`; `~/.config/stylefix/config.toml`;
`ADJUDICATE_LLM_*`; and `~/.config/adjudicate/config.toml`, which proofix
reads too. With nothing configured, `--llm auto` (the default) uses a local
Ollama if one is running with a model pulled, and otherwise runs as
`--llm none`: ambiguous words are left alone and listed in the report,
while capitalised deterministic swaps are applied anyway.

**Ollama**: nothing to configure; the first installed model is used.
`--model` picks another.

**A hosted API**:

```toml
# ~/.config/adjudicate/config.toml
[llm]
url = "https://api.openai.com/v1"
model = "gpt-4.1-mini"
api_key_env = "OPENAI_API_KEY"   # the key stays in your environment
```

**Self-hosted vLLM or LiteLLM with a reasoning model**:

```toml
[llm]
url = "http://gpu-box:8000/v1"
model = "qwen3"
thinking_switch = true   # send enable_thinking: false, which vLLM honours
```

Leave `model` out and the server's first listed model is used. A key the
file or environment names but that is unset, an unknown key, or a wrong
type stops the run with the file and key named. The full table is
documented in [adjudicate](https://github.com/AndrewBroz/adjudicate#choosing-the-model-endpoint).
````

In `### Choosing a model`, the command becomes `uv run python scripts/eval_adjudicator.py [--url URL --model NAME] [--think] [--parallel 8] [--repeat 4]`, and "Measured on a DGX Spark serving Qwen3.8-27B (NVFP4) through vLLM:" becomes "One measurement, on a DGX Spark serving Qwen3.8-27B (NVFP4) through vLLM:".

Add before `## Development`:

```markdown
## License

MIT (see `LICENSE`). `stylefix/dict/varcon.txt.gz` is VarCon, under the
notice in `stylefix/dict/README-varcon.txt`. The spelling dictionaries come
with [adjudicate](https://github.com/AndrewBroz/adjudicate).
```

Check: `grep -n -i "\.\./\|~/Code\|dgx-llm\|DGX_LLM" README.md` prints nothing.

- [ ] **Step 4: Man page** — in `man/stylefix.1`:

First line: `.TH STYLEFIX 1 "September 2026" "stylefix 0.7.0" "User Commands"`.

After the `.SS Model` section and before `.SS General`, add:

```
.SS Configuration
.TP
.B \-\-setup
Ask where the model is (local Ollama, a hosted OpenAI-compatible API, or a
self-hosted server), test it, and save the answer as the
.B [llm]
table of
.I ~/.config/adjudicate/config.toml
(shared with proofix) or
.IR ~/.config/stylefix/config.toml .
An existing table is shown and replaced only on confirmation, after a
backup to
.IR config.toml.bak ;
other tables are kept. For a self-hosted server it detects whether to set
.BR thinking_switch .
Needs a terminal. Ends by running the check below.
.TP
.B \-\-check\-endpoint
Print the endpoint stylefix would use, one line per setting with the
layer it came from (a key is never shown), then list the server's models
and send one small request. Honours
.BR \-\-llm ", " \-\-url ", " \-\-model " and " \-\-timeout .
```

Replace the `.BR \-\-llm " {auto|dgx|ollama|none}"` entry (from that line through the line "(the default) uses the first of dgx, ollama that answers.") with:

```
.BR \-\-llm " {auto|ollama|none}"
Endpoint choice.
.B auto
(the default) uses the endpoint configured by flags, environment or
config file (see
.BR ENVIRONMENT " and " FILES ),
or else a local Ollama with a model pulled, or else no model.
.B ollama
uses the local Ollama server and its first installed model, ignoring
configured endpoints.
.B none
skips the model: ambiguous words are left as they are and listed in the
report, while capitalised deterministic replacements are applied anyway.
```

In the `\-\-url` entry, "Overrides the preset." → "Overrides every configured endpoint." In `\-\-model`, append "If no layer sets one, the server's first listed model." In `\-\-timeout`, "Default 120." → "Default 120, or \fBtimeout\fR in config.toml."

Replace the `.SH ENVIRONMENT` entries for `STYLEFIX_LLM_*` and `DGX_LLM_DIR` with:

```
.TP
.BR STYLEFIX_LLM_URL ", " STYLEFIX_LLM_MODEL ", " STYLEFIX_LLM_KEY
Endpoint, model and API key for stylefix; below the flags, above the
config files.
.TP
.BR ADJUDICATE_LLM_URL ", " ADJUDICATE_LLM_MODEL ", " ADJUDICATE_LLM_KEY
The same, shared with proofix; below
.I ~/.config/stylefix/config.toml
and above
.IR ~/.config/adjudicate/config.toml .
```

Keep `OLLAMA_HOST`. At the top of `.SH FILES`, add:

```
.TP
.I ~/.config/stylefix/config.toml
.TQ
.I ~/.config/adjudicate/config.toml
Table
.B [llm]
with keys
.BR url ", " model ", " api_key " or " api_key_env ", " timeout ", " thinking_switch .
The first applies to stylefix only; the second is shared with proofix. A
file that sets
.B url
discards the model, key and thinking_switch of the layers below it.
```

In `.SH SEE ALSO`: `.BR pandoc (1),` → `.BR pandoc (1).` and delete `.BR dgx (1).`; "Source and README: ~/Code/stylefix." → "Source and README: https://github.com/AndrewBroz/stylefix."

Replace `.SH EXIT STATUS` with:

```
.SH EXIT STATUS
.TP
.B 0
Finished. Undecided words and review items are reported, not fatal. For
.BR \-\-check\-endpoint " and " \-\-setup :
the endpoint answers.
.TP
.B 1
.BR \-\-check\-endpoint " or " \-\-setup :
no endpoint, or it does not answer; or setup was cancelled or declined.
.TP
.B 2
Input file missing, Vale not found or failed, or an invalid endpoint
configuration (the message names the file and key). For
.BR \-\-setup :
standard input is not a terminal.
```

If `tests/test_docs.py` still lists options missing from the page, add a `.TP` entry for each in the section matching its help group, worded from its `--help` text.

Check: `uv run pytest tests/test_docs.py -v` passes; `grep -n -i "dgx\|~/Code" man/stylefix.1` prints nothing; `man ./man/stylefix.1 2>&1 >/dev/null` prints no troff warnings.

- [ ] **Step 5: Build and inspect**

Run: `uv run pytest -q && rm -rf dist && uv build --no-sources`
Expected: 125 passed; sdist and wheel for 0.7.0 built. `--no-sources` resolves `adjudicate>=0.3` from PyPI only at install time, so the build itself succeeds before adjudicate is published.

Run: `unzip -p dist/stylefix-0.7.0-py3-none-any.whl 'stylefix-0.7.0.dist-info/METADATA' | grep -E "^(License-Expression|Requires-Dist)" && unzip -l dist/stylefix-0.7.0-py3-none-any.whl | grep -c "styles/.*\.yml"`
Expected: `License-Expression: MIT AND LicenseRef-VarCon`, `Requires-Dist: adjudicate<0.4,>=0.3` and `spylls>=0.1.7`; a non-zero count of style rules (the Vale YAML ships).

- [ ] **Step 6: Commit**

```bash
git add -A LICENSE pyproject.toml stylefix/__init__.py stylefix/dict README.md man/stylefix.1 uv.lock tests/test_docs.py
git commit -m "MIT license; dictionary notices move to adjudicate; README and man page for any endpoint, --setup and --check-endpoint; a test keeps the man page in step; v0.7.0"
```

---

### Task 7: proofix — adopt adjudicate 0.3

**Files:**
- Create: `proofix/tests/conftest.py` (the same content as Task 5, Step 1, verbatim)
- Create: `proofix/tests/test_endpoint_cli.py`
- Modify: `proofix/pyproject.toml:6`, `proofix/proofix/cli.py` (`DESCRIPTION`, `EPILOG`, lines 13, 62, 94, 99, the start of `main`, 146), `proofix/proofix/commas.py:96-101`

**Interfaces:**
- Consumes: `resolve_endpoint`, `ConfigError`, `FENCE`, `FRONT_MATTER`, `run_setup`, `check_endpoint`.

- [ ] **Step 1: Test isolation** — create `tests/conftest.py` with exactly the content of Task 5, Step 1. Do not run the suite yet: the old positional `resolve_endpoint` call in `proofix/cli.py` fails against adjudicate 0.3 until Step 4.

- [ ] **Step 2: Write the failing tests** — create `tests/test_endpoint_cli.py`:

```python
import io
import os

import pytest

from proofix import cli


def test_isolation_hides_real_config(isolated_llm_config):
    assert os.environ["XDG_CONFIG_HOME"] == str(isolated_llm_config)
    assert not any(os.environ.get(f"{app}_LLM_{s}") for app in ("ADJUDICATE", "STYLEFIX", "PROOFIX")
                   for s in ("URL", "MODEL", "KEY"))


def test_dgx_preset_is_gone():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["x.md", "--llm", "dgx"])


def test_timeout_flag_defaults_to_none():
    assert cli.build_parser().parse_args(["x.md"]).timeout is None


def test_bad_config_exits_2(isolated_llm_config, tmp_path, capsys):
    cfg = isolated_llm_config / "proofix" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("[llm\n")
    src = tmp_path / "d.md"
    src.write_text("Some text.\n")
    assert cli.main([str(src), "--no-typos", "--no-cache", "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("proofix: ") and str(cfg) in err


def test_no_endpoint_suggests_setup(tmp_path, capsys):
    src = tmp_path / "d.md"
    src.write_text("Some text.\n")
    assert cli.main([str(src), "--no-lt", "--no-typos", "--no-cache", "--dry-run"]) == 0
    assert "proofix --setup" in capsys.readouterr().err


def test_check_endpoint_needs_no_input_file(capsys):
    assert cli.main(["--check-endpoint"]) == 1
    assert "proofix --setup" in capsys.readouterr().out


def test_setup_needs_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["--setup"]) == 2


def test_input_still_required_for_a_run(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 2 and "input" in capsys.readouterr().err


def test_stylefix_env_no_longer_configures_proofix(monkeypatch):
    monkeypatch.setenv("STYLEFIX_LLM_URL", "http://stylefix-only/v1")
    monkeypatch.setenv("STYLEFIX_LLM_MODEL", "m")
    from adjudicate import resolve_endpoint
    assert resolve_endpoint("proofix") is None
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_endpoint_cli.py -v`
Expected: `test_dgx_preset_is_gone`, `test_timeout_flag_defaults_to_none`, `test_bad_config_exits_2`, `test_no_endpoint_suggests_setup`, `test_check_endpoint_needs_no_input_file` and `test_setup_needs_a_terminal` FAIL; the isolation, required-input and STYLEFIX tests PASS (the last already, because Task 3 changed the library).

- [ ] **Step 4: Implement**

`pyproject.toml`: `dependencies = ["adjudicate>=0.3,<0.4"]`.

`proofix/cli.py`:
- `DESCRIPTION`, tier 2: "a local model picks one or KEEP" → "a language model picks one or KEEP".
- `EPILOG` becomes:

```
examples:
  proofix --setup                        # choose, test and save a model endpoint
  proofix draft.md                       # -> draft.proofed.md, US English
  proofix draft.md --target uk -o out.md
  proofix draft.md --changes             # list every change as it is made
  proofix draft.md --no-commas --llm none
      LanguageTool's mechanical fixes only; nothing needs a model

Requires languagetool on PATH for tiers 1 and 2 (brew install languagetool);
tier 3 needs only a model. Accept lists: --accept, ~/.config/proofix/accept.txt,
~/.config/stylefix/accept.txt and ./.stylefix/accept.txt are all honoured.

environment:
  PROOFIX_LLM_URL, PROOFIX_LLM_MODEL, PROOFIX_LLM_KEY
      the model endpoint for proofix (same as --url, --model, and the API key)
  ADJUDICATE_LLM_URL, ADJUDICATE_LLM_MODEL, ADJUDICATE_LLM_KEY
      the same, shared with stylefix; below the proofix variables and config
  OLLAMA_HOST   Ollama base URL (default http://localhost:11434)

files:
  ~/.config/proofix/config.toml      [llm] url, model, api_key or api_key_env,
                                     timeout, thinking_switch (proofix only)
  ~/.config/adjudicate/config.toml   the same table, shared with stylefix
```

- line 13: `from adjudicate import Cache, ConfigError, Edit, adjudicate, apply_edits, check_endpoint, resolve_endpoint, run_setup, system_prompt`
- line 62: `p.add_argument("input", type=Path, nargs="?", help="Markdown file to proofread")`
- after the `--timeout` argument:

```python
    c = p.add_argument_group("configuration", "set up or check the model endpoint, then exit")
    c.add_argument("--setup", action="store_true",
                   help="choose a model endpoint interactively, test it, and save it to "
                        "~/.config/adjudicate/config.toml or ~/.config/proofix/config.toml")
    c.add_argument("--check-endpoint", action="store_true",
                   help="show the endpoint proofix would use and where each setting comes "
                        "from, then test it; exit 0 if it answers, 1 if not, 2 on a config error")
```

- at the top of `main`, replacing `args = build_parser().parse_args(argv)` and the `if not args.input.exists():` check that follows it:

```python
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.setup:
        return run_setup("proofix")
    if args.check_endpoint:
        return check_endpoint("proofix", preset=args.llm, url=args.url, model=args.model,
                              timeout=args.timeout)
    if args.input is None:
        parser.error("the following arguments are required: input")
    if not args.input.exists():
```

  (the body of the `exists` check is unchanged).
- line 94: `p.add_argument("--llm", choices=["auto", "ollama", "none"], default="auto", help="auto: the endpoint from --url, PROOFIX_LLM_*, ~/.config/proofix/config.toml, ADJUDICATE_LLM_* or ~/.config/adjudicate/config.toml, else local Ollama; ollama: local Ollama only; none: report instead of deciding (default: %(default)s)")`
- line 99: `p.add_argument("--timeout", type=float, default=None, metavar="SEC", help="seconds per model request (default: 120, or timeout in config.toml)")`
- line 146:

```python
    try:
        ep = resolve_endpoint("proofix", args.llm, url=args.url, model=args.model,
                              timeout=args.timeout)
    except ConfigError as e:
        print(f"proofix: {e}", file=sys.stderr)
        return 2
    if ep is None and args.llm == "auto":
        print("proofix: no model endpoint found; tiers 2 and 3 will be reported, not applied. "
              "Run `proofix --setup` to configure one.", file=sys.stderr)
```

`proofix/commas.py`: delete the function-local `from adjudicate.context import _FENCE, _FRONT   # noqa` line, add `FENCE, FRONT_MATTER` to the module's `from adjudicate import …` on line 16, and in `_paragraphs` replace `_FRONT` with `FRONT_MATTER` and `_FENCE` with `FENCE`.

Then: `uv lock`.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: 22 passed. If a test that passed before this task fails now, it depended on a live model or real config: report it; do not weaken the fixture. `grep -rn -i "dgx\|_FENCE\|_FRONT" proofix` prints nothing.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock proofix/cli.py proofix/commas.py tests/conftest.py tests/test_endpoint_cli.py
git commit -m "Endpoint from adjudicate 0.3's config layers; --llm auto|ollama|none; tests never see real config"
```

---

### Task 8: proofix — license, metadata, README, man page, 0.5.0

**Files:**
- Create: `proofix/LICENSE` (the MIT text from Task 4, verbatim)
- Modify: `proofix/pyproject.toml`, `proofix/proofix/__init__.py:3`, `proofix/README.md`, `proofix/man/proofix.1`
- Create: `proofix/tests/test_docs.py`

- [ ] **Step 0: The drift test** — create `tests/test_docs.py`; it is Task 6's test with the names changed:

```python
"""The man page and --help must keep up with the parser."""

import re
from pathlib import Path

from proofix import __version__
from proofix.cli import build_parser

MAN = (Path(__file__).parent.parent / "man" / "proofix.1").read_text(encoding="utf-8")
PLAIN = MAN.replace("\\-", "-")          # roff writes --llm as \-\-llm


def test_every_long_option_is_in_the_man_page():
    missing = [o for a in build_parser()._actions for o in a.option_strings
               if o.startswith("--") and o not in PLAIN]
    assert missing == []


def test_llm_choices_match():
    choices = next(a.choices for a in build_parser()._actions if "--llm" in a.option_strings)
    assert "{" + "|".join(choices) + "}" in PLAIN


def test_man_version_matches():
    m = re.search(r'^\.TH \S+ 1 "[^"]*" "proofix ([^"]+)"', MAN, re.M)
    assert m and m.group(1) == __version__


def test_no_dgx_in_help_or_man():
    assert "dgx" not in build_parser().format_help().lower()
    assert "dgx" not in MAN.lower()
```

Run: `uv run pytest tests/test_docs.py -v`
Expected: all four FAIL; the first lists at least `--setup`, `--check-endpoint`, `--version` and `--help`.

- [ ] **Step 1: License and metadata**

```bash
cp ../adjudicate/LICENSE LICENSE
```

The `[project]` table becomes:

```toml
[project]
name = "proofix"
version = "0.5.0"
description = "Fix typos and punctuation in Markdown: LanguageTool detects, a language model adjudicates, comma placement is corrected under a diff guard."
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
license-files = ["LICENSE"]
authors = [{ name = "Andrew Brož" }]
dependencies = ["adjudicate>=0.3,<0.4"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Topic :: Text Processing :: Markup :: Markdown",
]

[project.urls]
Homepage = "https://github.com/AndrewBroz/proofix"
Issues = "https://github.com/AndrewBroz/proofix/issues"
```

Set `__version__ = "0.5.0"`.

- [ ] **Step 2: README**

The "Run it after" paragraph becomes: "Run it after [stylefix](https://github.com/AndrewBroz/stylefix), so the grammar checker sees the target variety."

(mdmemo is not published; drop the mention rather than link a private path.)

Before the benchmark table, the line "DGX Spark serving Qwen3.8-27B, 8 requests in parallel:" becomes "One measurement, on a DGX Spark serving Qwen3.8-27B, 8 requests in parallel:".

`## Install` becomes:

````markdown
## Install

```
uv tool install proofix       # or: pipx install proofix
```

Optional, and worth having:

- [LanguageTool](https://languagetool.org) on your PATH as `languagetool`
  (`brew install languagetool`; it needs Java). Without it, tiers 1 and 2
  are skipped with a warning and only hygiene and commas run.
- [typos](https://github.com/crate-ci/typos) (`brew install typos-cli` or
  `cargo install typos-cli`) for known-misspelling fixes in tier 1.

Run `proofix --setup` to choose and test a model endpoint, and
`proofix --check-endpoint` to see which one proofix will use. The endpoint
is configured as for stylefix: `--url`/`--model`,
`PROOFIX_LLM_URL`/`_MODEL`/`_KEY`, `~/.config/proofix/config.toml`, then
the shared `ADJUDICATE_LLM_*` and `~/.config/adjudicate/config.toml`; with
nothing configured, a local Ollama if one is running. See
[adjudicate](https://github.com/AndrewBroz/adjudicate#choosing-the-model-endpoint)
for the config table. `STYLEFIX_LLM_*` no longer configures proofix; use the
shared file or `ADJUDICATE_LLM_*` to set both tools at once.

Accept lists: `--accept FILE`, `~/.config/proofix/accept.txt`, and
stylefix's `~/.config/stylefix/accept.txt` and `./.stylefix/accept.txt`
are all honoured for spelling.
````

Add before `## Development`:

```markdown
## License

MIT (see `LICENSE`).
```

Check: `grep -n -i "\.\./\|~/Code\|mdmemo" README.md` prints nothing.

- [ ] **Step 3: Man page** — first line: `.TH PROOFIX 1 "September 2026" "proofix 0.5.0" "User Commands"`. In SYNOPSIS, add a second form below the existing one:

```
.br
.B proofix
.RB [ \-\-setup " | " \-\-check\-endpoint ]
```

The `--llm` entry becomes:

```
.BR \-\-llm " {auto|ollama|none}" ", " \-\-url ", " \-\-model ", " \-\-timeout
Model endpoint, configured as in stylefix but from
.BR PROOFIX_LLM_* " and " ~/.config/proofix/config.toml ,
then the shared
.BR ADJUDICATE_LLM_* " and " ~/.config/adjudicate/config.toml .
With none, tiers two and three are reported, not applied.
```

After the `--llm` entry's following entries (at the end of `.SH OPTIONS`, before `.SH PERFORMANCE`), add:

```
.TP
.B \-\-setup
Ask where the model is (local Ollama, a hosted OpenAI-compatible API, or a
self-hosted server), test it, and save the answer as the
.B [llm]
table of
.I ~/.config/adjudicate/config.toml
(shared with stylefix) or
.IR ~/.config/proofix/config.toml .
An existing table is shown and replaced only on confirmation, after a
backup to
.IR config.toml.bak .
Needs a terminal. Ends by running the check below.
.TP
.B \-\-check\-endpoint
Print the endpoint proofix would use, one line per setting with the layer
it came from (a key is never shown), then list the server's models and
send one small request.
.TP
.BR \-v ", " \-\-verbose
Report model batches on standard error.
.TP
.B \-\-version
Print the version and exit.
.TP
.BR \-h ", " \-\-help
Print the usage summary and exit.
```

(Drop any of the last three if the page already has them; the drift test is the judge.) Before `.SH SEE ALSO`, add:

```
.SH ENVIRONMENT
.TP
.BR PROOFIX_LLM_URL ", " PROOFIX_LLM_MODEL ", " PROOFIX_LLM_KEY
Endpoint, model and API key for proofix; below the flags, above the config
files.
.TP
.BR ADJUDICATE_LLM_URL ", " ADJUDICATE_LLM_MODEL ", " ADJUDICATE_LLM_KEY
The same, shared with stylefix; below
.I ~/.config/proofix/config.toml
and above
.IR ~/.config/adjudicate/config.toml .
.TP
.B OLLAMA_HOST
Ollama base URL. Default http://localhost:11434.
.SH FILES
.TP
.I ~/.config/proofix/config.toml
.TQ
.I ~/.config/adjudicate/config.toml
Table
.B [llm]
with keys
.BR url ", " model ", " api_key " or " api_key_env ", " timeout ", " thinking_switch .
The first applies to proofix only; the second is shared with stylefix.
.TP
.IR ~/.config/proofix/accept.txt ", " ~/.config/stylefix/accept.txt ", " .stylefix/accept.txt ", " .proofix/accept.txt
Words never flagged as misspelled, one per line.
.SH EXIT STATUS
.TP
.B 0
Finished. For
.BR \-\-check\-endpoint " and " \-\-setup :
the endpoint answers.
.TP
.B 1
.BR \-\-check\-endpoint " or " \-\-setup :
no endpoint, or it does not answer; or setup was cancelled or declined.
.TP
.B 2
Input file missing, LanguageTool failed, or an invalid endpoint
configuration (the message names the file and key). For
.BR \-\-setup :
standard input is not a terminal.
```

In `.SH SEE ALSO`, delete the `.BR mdmemo (1),` line.

Check: `uv run pytest tests/test_docs.py -v` passes; `man ./man/proofix.1 2>&1 >/dev/null` prints no troff warnings.

- [ ] **Step 4: Build and inspect**

Run: `uv run pytest -q && rm -rf dist && uv build --no-sources && unzip -p dist/proofix-0.5.0-py3-none-any.whl 'proofix-0.5.0.dist-info/METADATA' | grep -E "^(License-Expression|Requires-Dist)"`
Expected: 26 passed; `License-Expression: MIT`, `Requires-Dist: adjudicate<0.4,>=0.3`.

- [ ] **Step 5: Commit**

```bash
git add LICENSE pyproject.toml proofix/__init__.py README.md man/proofix.1 uv.lock tests/test_docs.py
git commit -m "MIT license, PyPI metadata; README and man page for any endpoint, --setup and --check-endpoint; a test keeps the man page in step; v0.5.0"
```

---

### Task 9: The author's own config through `--setup`, and a live check

Keeps the dgx gateway working after the preset is gone, and is the setup flow's real-world test. Needs the author at the keyboard: the implementer prepares, the author types.

**Files:**
- Create (through setup): `~/.config/adjudicate/config.toml` (outside every repo; not committed)

- [ ] **Step 1: Read the gateway address** — from `~/Code/dgx-llm/.env` take `DGX_HTTP_HOST` and `PRIMARY_MODEL_ALIAS` (do not print `LITELLM_MASTER_KEY`):

```bash
grep -E "^(DGX_HTTP_HOST|PRIMARY_MODEL_ALIAS)=" ~/Code/dgx-llm/.env
```

- [ ] **Step 2: Ask the author how the key should be held** — (a) from an environment variable (setup's recommended choice): they add `export LITELLM_MASTER_KEY=…` to their shell profile and open a new shell first; or (b) pasted into setup, stored in the file with mode 0600. Do not choose for them.

- [ ] **Step 3: The author runs setup** — suggest they type, in this session, `! cd ~/Code/stylefix && uv run stylefix --setup` and answer: **3** (self-hosted), `http://<DGX_HTTP_HOST>:4000/v1`, the key choice from Step 2, the model matching `PRIMARY_MODEL_ALIAS`, **1** (shared file).

Expected: "server accepts enable_thinking → thinking_switch = true", "Wrote ~/.config/adjudicate/config.toml", and a check ending `chat ✓`. If `thinking_switch` comes out false, or any step reads badly, that is a finding for the setup flow: note it for the author and fix it in adjudicate before Task 11, with a test.

- [ ] **Step 4: Live check, both tools**

```bash
(cd ~/Code/proofix && uv run proofix --check-endpoint)
(cd ~/Code/stylefix && uv run stylefix examples/sample.md --target uk --dry-run --no-cache -v 2>&1 | tail -5)
(cd ~/Code/proofix && uv run proofix examples/typos.md --dry-run --no-cache -v 2>&1 | tail -5)
```

Expected: proofix's check shows every row sourced from `~/.config/adjudicate/config.toml` and exits 0; both runs report adjudicated items with few or no undecided, and `-v` shows batches going to the gateway. `--dry-run` writes nothing, so the repos' own examples are safe to use. If either reports `cannot reach`, stop and show the author the message.

---

### Task 10: GitHub repositories

Outward-facing: ask the author before each `gh repo create`, and before each push.

- [ ] **Step 1: For each of adjudicate, stylefix, proofix, in that order**, after the author confirms:

```bash
cd ~/Code/<pkg>
git status --short        # must be clean
gh repo create AndrewBroz/<pkg> --public --source . --remote origin \
  --description "<the pyproject description>"
git push -u origin master
```

- [ ] **Step 2: Verify** — `gh repo view AndrewBroz/<pkg> --json url,visibility` shows `PUBLIC`, and the README renders on the repo page. Check that the Homepage URLs in each `pyproject.toml` match.

---

### Task 11: Release to TestPyPI, then PyPI

Order matters: each package must resolve its dependency from an index. The author supplies tokens; the implementer never reads or stores them. Ask before every upload.

- [ ] **Step 1: adjudicate to TestPyPI** — the author runs, or approves running, with their TestPyPI token in `UV_PUBLISH_TOKEN`:

```bash
cd ~/Code/adjudicate && rm -rf dist && uv build --no-sources
uv publish --publish-url https://test.pypi.org/legacy/ dist/*
```

- [ ] **Step 2: stylefix and proofix to TestPyPI** — the same two commands in each repo, stylefix first.

- [ ] **Step 3: Clean install from TestPyPI** — in a scratch directory, with no `~/Code` on any path:

```bash
export UV_TOOL_DIR=<scratch>/tools UV_TOOL_BIN_DIR=<scratch>/bin
for pkg in stylefix proofix; do
  uv tool install --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ --index-strategy unsafe-best-match "$pkg"
done
<scratch>/bin/stylefix --version && <scratch>/bin/proofix --version
<scratch>/bin/stylefix ~/Code/stylefix/examples/sample.md --target uk --llm none --dry-run --no-cache | head
<scratch>/bin/proofix ~/Code/proofix/examples/typos.md --llm none --dry-run --no-cache --no-typos | head
```

Expected: `stylefix 0.7.0`, `proofix 0.5.0`, and both print a diff. Then prove adjudicate came from the index, not a path:

```bash
<scratch>/tools/stylefix/bin/python -c "import adjudicate; print(adjudicate.__version__, adjudicate.__file__)"
```

Expected: `0.3.0` and a path inside `<scratch>/tools/stylefix/lib/…/site-packages`, never `~/Code/adjudicate`.

- [ ] **Step 4: PyPI** — with the author's go-ahead and PyPI token, `uv publish dist/*` in adjudicate, then stylefix, then proofix. Then repeat Step 3 without the `--index-url`/`--extra-index-url` flags against real PyPI.

- [ ] **Step 5: Tag** — in each repo, after its upload: `git tag v<version> && git push origin v<version>` (ask first).
