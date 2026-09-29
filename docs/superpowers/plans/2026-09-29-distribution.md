# Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish adjudicate 0.3.0, stylefix 0.7.0 and proofix 0.5.0 to PyPI, each configurable to any OpenAI-compatible endpoint through layered flags, env vars and TOML config files.

**Architecture:** Endpoint resolution moves wholly into `adjudicate.llm`: `resolve_endpoint(app, …)` merges five layers (flags, `<APP>_LLM_*`, `~/.config/<app>/config.toml`, `ADJUDICATE_LLM_*`, `~/.config/adjudicate/config.toml`) and falls back to local Ollama. The `dgx` preset is deleted; the author's gateway becomes a config file. stylefix and proofix become thin callers. Release goes adjudicate → stylefix → proofix via TestPyPI.

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

## Review Focus

1. **The author's shared config carries a dgx `model` and `thinking_switch = true`, and they pass `--url` to try another server.** Expected: nothing from the dgx layer leaks through (the model is discovered or taken from `--model`, and `chat_template_kwargs` is not sent). Pinned in Task 3 (`test_higher_url_discards_lower_server_settings`).
2. **Default `--llm auto` on a machine where Ollama is running but no model is pulled.** Expected: the run proceeds as `--llm none`, not exit 2. Pinned in Task 3 (`test_auto_with_empty_ollama_is_none`).
3. **Running the test suites on the author's machine, which will have a real `~/.config/adjudicate/config.toml` after Task 9.** Expected: no test reaches a real endpoint. Pinned by the autouse isolation fixture in each repo's `tests/conftest.py` (Tasks 2, 5, 7) and `test_isolation_hides_real_config` in each.
4. **`api_key_env` naming a variable that is set but empty** (a common shell-profile slip). Expected: the same `ConfigError` as unset, not a silent unauthenticated request. Pinned in Task 3 (`test_api_key_env_empty_is_an_error`).
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
- Produces: `Endpoint(url, model, key="", name="custom", think=False, timeout=120.0, thinking_switch=False)`; `Endpoint.chat(system, user, timeout=None, json_mode=True) -> str` (unchanged signature); `Endpoint._headers() -> dict[str, str]`; module constant `DEFAULT_TIMEOUT = 120.0`. Fixtures `server` (a `FakeServer` with `.url`, `.base`, `.models`, `.models_status`, `.reject`, `.requests`) and autouse `isolated_llm_config`.

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
            if self.path == "/v1/models":
                if state.models_status != 200:
                    return self._send(state.models_status, {"error": "down"})
                return self._send(200, {"data": [{"id": m} for m in state.models]})
            if self.path == "/api/tags":           # Ollama's own listing
                return self._send(200, {"models": [{"name": m} for m in state.models]})
            self._send(404, {})

        def do_POST(self):
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
  - `read_config(path: Path) -> dict` — validated `[llm]` settings with `api_key_env` already resolved into `api_key`; `{}` when the file is absent
  - `env_layer(prefix: str) -> dict` — from `<prefix>_LLM_URL/MODEL/KEY`, keys `url`/`model`/`api_key`
  - `merge_layers(layers: list[dict]) -> dict` — highest first
  - `discover_model(ep: Endpoint, timeout: float = 5.0) -> str | None`
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
    merged = merge_layers([{"model": "hi"}, {"url": "u", "model": "lo", "timeout": 5}])
    assert merged == {"url": "u", "model": "hi", "timeout": 5}


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

3. Delete `read_env_file`, `dgx_endpoint` and the old `resolve_endpoint`. Keep `ollama_endpoint` unchanged.
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
    """The validated [llm] table of a config file, with api_key_env resolved
    into api_key; {} if the file does not exist."""
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
    out = {k: v for k, v in table.items() if k != "api_key_env"}
    if "api_key_env" in table:
        var = table["api_key_env"]
        if not os.environ.get(var):
            raise ConfigError(f"{path}: api_key_env names {var}, which is not set")
        out["api_key"] = os.environ[var]
    return out


def env_layer(prefix: str) -> dict:
    """Settings from <prefix>_LLM_URL, _MODEL and _KEY; empty values are unset."""
    out = {}
    for key, suffix in (("url", "URL"), ("model", "MODEL"), ("api_key", "KEY")):
        value = os.environ.get(f"{prefix}_LLM_{suffix}")
        if value:
            out[key] = value
    return out


def merge_layers(layers: list[dict]) -> dict:
    """Merge settings field by field, highest-precedence layer first."""
    out: dict = {}
    for layer in reversed(layers):
        if "url" in layer:
            for k in _SERVER_KEYS:
                out.pop(k, None)
        out.update(layer)
    return out


def discover_model(ep: Endpoint, timeout: float = 5.0) -> str | None:
    """The first model the server lists at /models, or None."""
    req = urllib.request.Request(ep.url.rstrip("/") + "/models", headers=ep._headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception:
        return None
    for m in data.get("data", []) if isinstance(data, dict) else []:
        if isinstance(m, dict) and m.get("id"):
            return m["id"]
    return None


def resolve_endpoint(app: str, preset: str = "auto", url: str | None = None,
                     model: str | None = None, key: str | None = None,
                     think: bool = False, timeout: float | None = None) -> Endpoint | None:
    """The endpoint `app` should use, or None for no model.

    preset: auto | ollama | none. For auto, settings come from, highest
    first: the arguments, <APP>_LLM_* variables, ~/.config/<app>/config.toml,
    ADJUDICATE_LLM_* variables, ~/.config/adjudicate/config.toml; with no
    url anywhere, a local Ollama is used if one is running with a model.
    ollama means local Ollama with only the arguments applied. Raises
    ConfigError for an invalid setting or an endpoint with no usable model.
    """
    if preset == "none":
        return None
    if preset not in ("auto", "ollama"):
        raise ConfigError(f"unknown endpoint preset '{preset}' (choose auto, ollama or none)")
    flags = {k: v for k, v in (("url", url), ("model", model), ("api_key", key),
                               ("timeout", timeout)) if v}
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
    t = float(settings.get("timeout", DEFAULT_TIMEOUT))
    if "url" in settings:
        ep = Endpoint(url=settings["url"], model=settings.get("model", ""),
                      key=settings.get("api_key", ""), think=think, timeout=t,
                      thinking_switch=settings.get("thinking_switch", False))
    else:
        ep = ollama_endpoint()
        if ep is None:
            return None
        ep.model = settings.get("model") or ep.model
        ep.key = settings.get("api_key", "")
        ep.think, ep.timeout = think, t
        ep.thinking_switch = settings.get("thinking_switch", False)
    if not ep.model:
        ep.model = discover_model(ep) or ""
    if not ep.model:
        if ep.name == "ollama" and preset == "auto":
            return None          # Ollama is running but has no model pulled
        raise ConfigError(f"no model set for {ep.url} and the server lists none; "
                          "set `model` in config.toml or pass --model")
    return ep
```

5. In `adjudicate/__init__.py`, change the llm import to `from .llm import ConfigError, Endpoint, LLMError, resolve_endpoint, strip_thinking  # noqa: F401`.

- [ ] **Step 4: Run the new tests, then the whole suite**

Run: `uv run pytest tests/test_config.py -v` — Expected: all PASS.
Run: `uv run pytest -q` — Expected: 55 passed (21 + 7 + 27).

- [ ] **Step 5: Confirm nothing mentions dgx any more**

Run: `grep -rn -i "dgx" adjudicate tests; grep -n "STYLEFIX" adjudicate/*.py`
Expected: no output (the `STYLEFIX` in `tests/conftest.py` is the isolation list, and is expected).

- [ ] **Step 6: Commit**

```bash
git add adjudicate/llm.py adjudicate/__init__.py tests/test_config.py
git commit -m "Endpoint from layered flags, env and config.toml per app; model discovery; dgx preset removed"
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
(Hunspell lookups over the bundled en_US and en_GB dictionaries).

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
Expected: 55 passed; `Successfully built dist/adjudicate-0.3.0.tar.gz` and `…-py3-none-any.whl`.

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
- Modify: `stylefix/pyproject.toml:6` (dependency), `stylefix/stylefix/cli.py` (lines 17, 42-72 epilog, 130-133, 147, 292-293), `stylefix/stylefix/styleitems.py:16,114`, `stylefix/scripts/eval_adjudicator.py` (lines 3, 93-102)

**Interfaces:**
- Consumes: `resolve_endpoint(app, preset, url=, model=, key=, think=, timeout=)`, `ConfigError`, `HTML_ENTITY` (Tasks 1 and 3).

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
Expected: `test_dgx_preset_is_gone` FAIL (dgx still a choice); `test_timeout_flag_defaults_to_none` FAIL (120.0); `test_bad_config_exits_2` FAIL with `TypeError` from the old positional call or a traceback; `test_config_url_reaches_the_server` FAIL.

- [ ] **Step 4: Implement**

`pyproject.toml`: `dependencies = ["spylls>=0.1.7", "adjudicate>=0.3,<0.4"]`.

`stylefix/cli.py`:
- line 17: `from .llm import ConfigError, resolve_endpoint`
- epilog first example: replace "ambiguous words decided by the first reachable model (DGX, then Ollama)" with "ambiguous words decided by the configured model, or local Ollama"
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
Expected: 118 passed. **If a test that passed before this task fails now** (other than the four new ones), the isolation fixture exposed a dependence on a live model or on the real `~/.config/stylefix/accept.txt`: report which test and why, and do not weaken the fixture to make it pass.
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

Check: `grep -n -i "dgx\|~/Code" man/stylefix.1` prints nothing, and `man ./man/stylefix.1 | col -b | grep -A3 "\-\-llm"` renders without troff warnings.

- [ ] **Step 5: Build and inspect**

Run: `uv run pytest -q && rm -rf dist && uv build --no-sources`
Expected: 118 passed; sdist and wheel for 0.7.0 built. `--no-sources` resolves `adjudicate>=0.3` from PyPI only at install time, so the build itself succeeds before adjudicate is published.

Run: `unzip -p dist/stylefix-0.7.0-py3-none-any.whl 'stylefix-0.7.0.dist-info/METADATA' | grep -E "^(License-Expression|Requires-Dist)" && unzip -l dist/stylefix-0.7.0-py3-none-any.whl | grep -c "styles/.*\.yml"`
Expected: `License-Expression: MIT AND LicenseRef-VarCon`, `Requires-Dist: adjudicate<0.4,>=0.3` and `spylls>=0.1.7`; a non-zero count of style rules (the Vale YAML ships).

- [ ] **Step 6: Commit**

```bash
git add -A LICENSE pyproject.toml stylefix/__init__.py stylefix/dict README.md man/stylefix.1 uv.lock
git commit -m "MIT license; dictionary notices move to adjudicate; README and man page for any endpoint; v0.7.0"
```

---

### Task 7: proofix — adopt adjudicate 0.3

**Files:**
- Create: `proofix/tests/conftest.py` (the same content as Task 5, Step 1, verbatim)
- Create: `proofix/tests/test_endpoint_cli.py`
- Modify: `proofix/pyproject.toml:6`, `proofix/proofix/cli.py` (lines 13, 94, 99, 146), `proofix/proofix/commas.py:96-101`

**Interfaces:**
- Consumes: `resolve_endpoint`, `ConfigError`, `FENCE`, `FRONT_MATTER`.

- [ ] **Step 1: Test isolation** — create `tests/conftest.py` with exactly the content of Task 5, Step 1. Do not run the suite yet: the old positional `resolve_endpoint` call in `proofix/cli.py` fails against adjudicate 0.3 until Step 4.

- [ ] **Step 2: Write the failing tests** — create `tests/test_endpoint_cli.py`:

```python
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


def test_stylefix_env_no_longer_configures_proofix(monkeypatch):
    monkeypatch.setenv("STYLEFIX_LLM_URL", "http://stylefix-only/v1")
    monkeypatch.setenv("STYLEFIX_LLM_MODEL", "m")
    from adjudicate import resolve_endpoint
    assert resolve_endpoint("proofix") is None
```

- [ ] **Step 3: Run them to verify they fail**

Run: `uv run pytest tests/test_endpoint_cli.py -v`
Expected: `test_dgx_preset_is_gone`, `test_timeout_flag_defaults_to_none` and `test_bad_config_exits_2` FAIL; the isolation and STYLEFIX tests PASS (the latter already, because Task 3 changed the library).

- [ ] **Step 4: Implement**

`pyproject.toml`: `dependencies = ["adjudicate>=0.3,<0.4"]`.

`proofix/cli.py`:
- line 13: `from adjudicate import Cache, ConfigError, Edit, adjudicate, apply_edits, resolve_endpoint, system_prompt`
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
```

`proofix/commas.py`: delete the function-local `from adjudicate.context import _FENCE, _FRONT   # noqa` line, add `FENCE, FRONT_MATTER` to the module's `from adjudicate import …` on line 16, and in `_paragraphs` replace `_FRONT` with `FRONT_MATTER` and `_FENCE` with `FENCE`.

Then: `uv lock`.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: 18 passed. If a test that passed before this task fails now, it depended on a live model or real config: report it; do not weaken the fixture. `grep -rn -i "dgx\|_FENCE\|_FRONT" proofix` prints nothing.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock proofix/cli.py proofix/commas.py tests/conftest.py tests/test_endpoint_cli.py
git commit -m "Endpoint from adjudicate 0.3's config layers; --llm auto|ollama|none; tests never see real config"
```

---

### Task 8: proofix — license, metadata, README, man page, 0.5.0

**Files:**
- Create: `proofix/LICENSE` (the MIT text from Task 4, verbatim)
- Modify: `proofix/pyproject.toml`, `proofix/proofix/__init__.py:3`, `proofix/README.md`, `proofix/man/proofix.1:104-106`

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

The model endpoint is configured as for stylefix: `--url`/`--model`,
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

- [ ] **Step 3: Man page** — the `--llm` entry becomes:

```
.BR \-\-llm " {auto|ollama|none}" ", " \-\-url ", " \-\-model ", " \-\-timeout
Model endpoint, configured as in stylefix but from
.BR PROOFIX_LLM_* " and " ~/.config/proofix/config.toml ,
then the shared
.BR ADJUDICATE_LLM_* " and " ~/.config/adjudicate/config.toml .
With none, tiers two and three are reported, not applied.
```

In `.SH SEE ALSO`, delete the `.BR mdmemo (1),` line.

- [ ] **Step 4: Build and inspect**

Run: `uv run pytest -q && rm -rf dist && uv build --no-sources && unzip -p dist/proofix-0.5.0-py3-none-any.whl 'proofix-0.5.0.dist-info/METADATA' | grep -E "^(License-Expression|Requires-Dist)"`
Expected: 18 passed; `License-Expression: MIT`, `Requires-Dist: adjudicate<0.4,>=0.3`.

- [ ] **Step 5: Commit**

```bash
git add LICENSE pyproject.toml proofix/__init__.py README.md man/proofix.1 uv.lock
git commit -m "MIT license, PyPI metadata, README and man page for any endpoint; v0.5.0"
```

---

### Task 9: The author's own config, and a live check

Keeps the dgx gateway working after the preset is gone. Needs the author at the keyboard.

**Files:**
- Create: `~/.config/adjudicate/config.toml` (outside every repo; not committed)

- [ ] **Step 1: Read the gateway settings** — from `~/Code/dgx-llm/.env` take `DGX_HTTP_HOST` and `PRIMARY_MODEL_ALIAS` (do not print `LITELLM_MASTER_KEY`):

```bash
grep -E "^(DGX_HTTP_HOST|PRIMARY_MODEL_ALIAS)=" ~/Code/dgx-llm/.env
```

- [ ] **Step 2: Ask the author how the key should be held** — either (a) `api_key_env = "LITELLM_MASTER_KEY"` and they add `export LITELLM_MASTER_KEY=…` to their shell profile themselves, or (b) `api_key = "…"` in the file with `chmod 600`. Do not choose for them.

- [ ] **Step 3: Write the file** (shown for option a; substitute the two values from Step 1):

```toml
# dgx-llm LiteLLM gateway, formerly stylefix's built-in "dgx" preset
[llm]
url = "http://<DGX_HTTP_HOST>:4000/v1"
model = "<PRIMARY_MODEL_ALIAS>"
api_key_env = "LITELLM_MASTER_KEY"
thinking_switch = true
```

- [ ] **Step 4: Live check, both tools** — in a scratch directory:

```bash
(cd ~/Code/stylefix && uv run stylefix examples/sample.md --target uk --dry-run --no-cache -v 2>&1 | tail -5)
(cd ~/Code/proofix && uv run proofix examples/typos.md --dry-run --no-cache -v 2>&1 | tail -5)
```

`--dry-run` writes nothing, so running against the repos' own examples is safe.

Expected: both summaries report adjudicated items with `0 undecided` or a small number, and `-v` shows batches going to the gateway URL. If either reports `cannot reach`, stop and show the author the message.

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
