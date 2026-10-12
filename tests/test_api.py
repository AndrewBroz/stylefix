from pathlib import Path

import pytest

from adjudicate import Cache, apply_changes
from stylefix import api

SAMPLE = (Path(__file__).parent.parent / "examples" / "sample.md").read_text()


def test_fix_does_no_file_io_on_callers_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = api.fix(SAMPLE, api.Options(target="us"), None, Cache(None))
    assert list(tmp_path.iterdir()) == []
    assert r.text != SAMPLE


def test_changes_reproduce_the_output():
    r = api.fix(SAMPLE, api.Options(target="us"), None, Cache(None))
    assert apply_changes(SAMPLE, r.changes) == r.text
    assert {c.decided_by for c in r.changes} <= {"rule", "model", "cache"}


def test_unasked_counts_items_without_a_model():
    r = api.fix("The license was granted.\n", api.Options(target="uk"), None, Cache(None))
    assert r.unasked == 1
    assert any(i.kind == "undecided" for i in r.review)


def test_tier_of():
    assert api.tier_of("ToUK.Ambiguous") == "ambiguous"
    assert api.tier_of("Chicago.Numbers") == "numbers"
    assert api.tier_of("ToUS.Variants") == "variety"
    assert api.tier_of("Oxford.Towards") == "guide"


def test_cli_still_writes_the_same_file(tmp_path):
    from stylefix.cli import load_accept_lists, main
    src = tmp_path / "doc.md"
    src.write_text(SAMPLE)
    out = tmp_path / "out.md"
    assert main([str(src), "--target", "us", "-o", str(out), "--llm", "none", "--no-cache"]) == 0
    accept = load_accept_lists(None, False)                 # what the CLI uses
    assert out.read_text() == api.fix(SAMPLE, api.Options(target="us", accept=accept),
                                      None, Cache(None)).text


def test_no_model_fallbacks_are_labelled_rule():
    r = api.fix(SAMPLE, api.Options(target="us"), None, Cache(None))
    assert not any(c.decided_by == "model" for c in r.changes)
    centre = [c for c in r.changes if c.before.lower() == "centre"]
    assert centre and all(c.decided_by == "rule" for c in centre)


def test_without_vale_the_python_tiers_still_run(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(api.ValeNotFound):
        api.fix(SAMPLE, api.Options(target="us"), None, Cache(None))
    r = api.fix('He said "hi" -- then left.\n', api.Options(target="us", require_vale=False),
                None, Cache(None))
    assert r.skipped and r.skipped[0].why == "Vale not found"
    assert "—" in r.text                                # punctuation still normalised


def test_skip_punctuation_leaves_quotes():
    r = api.fix('He said "hi".\n', api.Options(target="us", skip=frozenset({"punctuation"})),
                None, Cache(None))
    assert '"hi"' in r.text


def test_skip_all_vale_tiers_does_not_need_vale(monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    r = api.fix("Text.\n", api.Options(target="us", skip=api.VALE_TIERS), None, Cache(None))
    assert r.skipped == []


def test_replay_cache_answers_from_cache(tmp_path):
    from adjudicate import Decision, Item
    text = "The license was granted.\n"
    first = api.fix(text, api.Options(target="uk", replay_cache=True), None, Cache(None))
    [it] = [d.item for d in first.decisions]
    cache = Cache(tmp_path / "c.json")
    cache.put(Cache.key("uk", it), Decision(it, "licence", 0.95, "noun"))
    r = api.fix(text, api.Options(target="uk", replay_cache=True), None, cache)
    assert "licence" in r.text
    [c] = [c for c in r.changes if c.after == "licence"]
    assert c.decided_by == "cache"


def test_replay_cache_gates_style_items():
    from adjudicate import Decision
    text = "We bought apples, pears and plums.\n"
    opts = dict(target="us", style="chicago")
    off = api.fix(text, api.Options(**opts), None, Cache(None))
    assert off.text == text and off.decisions == []
    assert any(i.kind == "alert" and "SerialComma" in i.check for i in off.review)

    on = api.fix(text, api.Options(**opts, replay_cache=True), None, Cache(None))
    assert on.text == text and on.unasked == 0
    assert any(i.kind == "undecided" for i in on.review)

    [it] = [d.item for d in on.decisions]
    cache = Cache(None)
    cache.put(Cache.key("us", it), Decision(it, it.options[0], 0.95, "serial comma"))
    r = api.fix(text, api.Options(**opts, replay_cache=True), None, cache)
    assert "pears, and plums" in r.text
    [c] = [c for c in r.changes if "," in c.after and c.after != c.before]
    assert c.decided_by == "cache"


def test_replay_cache_gates_capitalised_fallback():
    on_text = lambda rc: api.fix(SAMPLE, api.Options(target="us", replay_cache=rc),
                                 None, Cache(None))
    off, on = on_text(False), on_text(True)
    assert "Center" in off.text
    assert any(c.before == "Centre" and c.decided_by == "rule" for c in off.changes)
    assert "Centre" in on.text and not any(c.before == "Centre" for c in on.changes)
