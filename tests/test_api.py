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
