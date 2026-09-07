"""Style guides as parameters. Each guide fixes the mechanical conventions
stylefix can enforce; spelling is the target variety's business.

Run ``python -m stylefix.wordlist`` to regenerate the Vale rule directories
under ``stylefix/styles/`` from this registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StyleGuide:
    name: str                       # CLI value
    title: str                      # Vale style directory and display name
    summary: str
    dash: str | None                # "em" (unspaced), "em-spaced", "en-spaced", None = leave
    serial_comma: str | None        # "require", "omit", None = no opinion
    spell_out_below: int | None     # flag numerals below this in running text; None = no rule
    adverb_s: str | None            # "drop" (toward, among), "keep" (towards, amongst), None
    punctuation_inside_quotes: bool # move commas and periods inside closing quotes
    variety: str                    # "us" or "uk": the variety the guide assumes
    url: str = ""
    abbreviations: str = ""         # one-line summary of the abbreviation forms


GUIDES: dict[str, StyleGuide] = {g.name: g for g in [
    StyleGuide("chicago", "Chicago",
               "Chicago Manual of Style (18th ed.): unspaced em dash, serial comma, "
               "numbers one through one hundred spelled out, toward/among, "
               "commas and periods inside closing quotes.",
               dash="em", serial_comma="require", spell_out_below=101, adverb_s="drop",
               punctuation_inside_quotes=True, variety="us",
               url="https://www.chicagomanualofstyle.org/",
               abbreviations="US, UK, EU without periods; PhD; 10 a.m.; vs.; e.g."),
    StyleGuide("gpo", "GPO",
               "U.S. Government Publishing Office Style Manual: the federal standard. "
               "Unspaced em dash, serial comma, numerals from 10, toward, "
               "punctuation inside quotes.",
               dash="em", serial_comma="require", spell_out_below=10, adverb_s="drop",
               punctuation_inside_quotes=True, variety="us",
               url="https://www.govinfo.gov/collection/gpo-style-manual",
               abbreviations="U.S., U.K. with periods; Ph.D.; 10 a.m.; vs.; e.g."),
    StyleGuide("ap", "AP",
               "Associated Press Stylebook: journalism. Spaced em dash, no serial "
               "comma in a simple series, numerals from 10, toward, punctuation "
               "inside quotes.",
               dash="em-spaced", serial_comma="omit", spell_out_below=10, adverb_s="drop",
               punctuation_inside_quotes=True, variety="us",
               url="https://www.apstylebook.com/",
               abbreviations="U.S., U.K. with periods in text; Ph.D.; 10 a.m.; vs.; e.g."),
    StyleGuide("apa", "APA",
               "APA Publication Manual (7th ed.): academic and policy research. "
               "Unspaced em dash, serial comma, numerals from 10, punctuation "
               "inside quotes.",
               dash="em", serial_comma="require", spell_out_below=10, adverb_s=None,
               punctuation_inside_quotes=True, variety="us",
               url="https://apastyle.apa.org/",
               abbreviations="U.S. with periods (as an adjective); PhD; 10 a.m.; vs.; e.g."),
    StyleGuide("oxford", "Oxford",
               "New Hart's Rules (Oxford): spaced en dash, Oxford comma, numbers "
               "up to one hundred spelled out in general text, towards/amongst, "
               "logical punctuation (only what belongs to the quote goes inside).",
               dash="en-spaced", serial_comma="require", spell_out_below=101, adverb_s="keep",
               punctuation_inside_quotes=False, variety="uk",
               url="https://global.oup.com/academic/product/new-harts-rules-9780199570027",
               abbreviations="US, UK without points; PhD; 10 a.m.; vs; e.g."),
    StyleGuide("guardian", "Guardian",
               "Guardian and Observer style guide: UK journalism. Spaced en dash, "
               "no serial comma unless needed, numerals from 10, towards, logical "
               "punctuation.",
               dash="en-spaced", serial_comma="omit", spell_out_below=10, adverb_s="keep",
               punctuation_inside_quotes=False, variety="uk",
               url="https://www.theguardian.com/guardian-observer-style-guide-a",
               abbreviations="US, UK; PhD; 10am; v; eg, ie, etc without points"),
    StyleGuide("none", "",
               "No style guide. Spelling and the target variety's punctuation "
               "conventions only: curly quotes with the variety's primary style, "
               "apostrophes, en dashes in number ranges, date order. Dashes, serial "
               "commas, numerals, toward/towards and punctuation placement are left "
               "exactly as written.",
               dash=None, serial_comma=None, spell_out_below=None, adverb_s=None,
               punctuation_inside_quotes=False, variety=""),
]}

DEFAULT_FOR = {"us": "chicago", "uk": "oxford"}


def get(name: str) -> StyleGuide:
    return GUIDES[name]


def choices() -> list[str]:
    return list(GUIDES)


def describe() -> str:
    lines = []
    for g in GUIDES.values():
        lines.append(f"{g.name:9} {g.summary}")
        if g.abbreviations:
            lines.append(f"{'':9} abbreviations: {g.abbreviations}")
        if g.url:
            lines.append(f"{'':9} {g.url}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------ Vale rules

_S_WORDS = {"towards": "toward", "afterwards": "afterward", "amongst": "among",
            "whilst": "while", "amidst": "amid"}


def vale_rules(g: StyleGuide) -> dict[str, str]:
    rules: dict[str, str] = {}
    head = "# Generated by `python -m stylefix.wordlist` from stylefix/styleguides.py.\n"
    if g.adverb_s == "drop":
        swap = "\n".join(f"  {k}: {v}" for k, v in _S_WORDS.items())
        rules["Toward.yml"] = (head + "extends: substitution\n"
                               f"message: \"{g.title} prefers '%s' to '%s'.\"\n"
                               "level: warning\nignorecase: true\naction:\n  name: replace\nswap:\n"
                               + swap + "\n")
    elif g.adverb_s == "keep":
        rules["Towards.yml"] = (head + "extends: substitution\n"
                                f"message: \"British usage prefers '%s' to '%s'.\"\n"
                                "level: warning\nignorecase: true\naction:\n  name: replace\nswap:\n"
                                "  toward: towards\n  afterward: afterwards\n")
    if g.serial_comma == "require":
        rules["SerialComma.yml"] = (head + "# Heuristic: \"a, b and c\" without the serial comma. Flag only.\n"
                                    "extends: existence\n"
                                    f"message: \"{g.title} uses the serial comma: check '%s'.\"\n"
                                    "level: suggestion\nnonword: true\ntokens:\n"
                                    "  - '\\w+, \\w+ (?:and|or) \\w+'\n")
    elif g.serial_comma == "omit":
        rules["SerialComma.yml"] = (head + "# Heuristic: \"a, b, and c\" with a serial comma in a simple series. Flag only.\n"
                                    "extends: existence\n"
                                    f"message: \"{g.title} omits the serial comma in a simple series: check '%s'.\"\n"
                                    "level: suggestion\nnonword: true\ntokens:\n"
                                    "  - '\\w+, \\w+, (?:and|or) \\w+'\n")
    if g.spell_out_below:
        hi = g.spell_out_below - 1
        rx = r"[1-9]|[1-9]\d" if hi >= 99 else r"[1-9]"
        rules["Numbers.yml"] = (head + f"# {g.title} spells out whole numbers below {g.spell_out_below} in running text.\n"
                                "# Heuristic: a bare number between spaces. Flag only.\n"
                                "extends: existence\n"
                                f"message: \"{g.title} spells out numbers below {g.spell_out_below} in running text: '%s'.\"\n"
                                "level: suggestion\nnonword: true\ntokens:\n"
                                f"  - '\\s(?:{rx})\\s'\n")
    return rules


def write_styles(styles_dir: Path) -> None:
    import shutil
    for g in GUIDES.values():
        if not g.title:
            continue
        d = styles_dir / g.title
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for name, body in vale_rules(g).items():
            (d / name).write_text(body)
