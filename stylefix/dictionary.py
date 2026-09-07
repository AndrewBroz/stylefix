"""Base word lists from the SCOWL-derived Hunspell dictionaries (see dict/)."""

from __future__ import annotations

import gzip
from functools import lru_cache
from pathlib import Path

DICT_DIR = Path(__file__).parent / "dict"
VARIETY_FILE = {"us": "en_US.txt.gz", "uk": "en_GB.txt.gz"}


@lru_cache(maxsize=None)
def words(variety: str) -> frozenset[str]:
    path = DICT_DIR / VARIETY_FILE[variety]
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return frozenset(w.strip().lower() for w in f if w.strip())


def known(word: str, variety: str) -> bool:
    return word.lower() in words(variety)


def known_anywhere(word: str) -> bool:
    return known(word, "us") or known(word, "uk")
