"""The man page and --help must keep up with the parser."""

import re
from pathlib import Path

import pytest

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


def test_help_points_at_documentation_that_ships():
    text = build_parser().format_help()
    assert "https://github.com/AndrewBroz/stylefix" in text
    assert "man/stylefix.1" in text
    assert "README.md in the source tree" not in text
    assert "local language model" not in " ".join(text.split())


def test_url_help_states_the_key_reset():
    url = next(a for a in build_parser()._actions if "--url" in a.option_strings)
    assert "overrides every configured url" in url.help
    assert "STYLEFIX_LLM_KEY" in url.help and "api_key_env" in url.help


@pytest.mark.parametrize("value", ["0", "-5", "nan", "inf", "soon"])
def test_timeout_must_be_positive(value, capsys):
    with pytest.raises(SystemExit) as e:
        build_parser().parse_args(["--timeout", value])
    assert e.value.code == 2 and "--timeout" in capsys.readouterr().err


def test_timeout_accepts_a_positive_number():
    assert build_parser().parse_args(["--timeout", "0.5"]).timeout == 0.5
