"""stylefix's adjudication task on top of the adjudicate library."""

from __future__ import annotations

from adjudicate.core import (Cache, Decision, Item, decide_batch, parse_response,  # noqa: F401
                             render_batch, system_prompt)
from adjudicate.core import adjudicate as _adjudicate
from adjudicate.llm import Endpoint

VARIETY = {"us": "American English", "uk": "British English"}

TASK = "You are a meticulous copy editor regularizing a document to {variety}."
KEEP_RULE = ("Choose KEEP when the marked text is part of a proper name, an organisation name, "
             "the title of a published work, a direct quotation from a source written in another "
             "variety, a URL or code identifier, or is already correct for {variety} in this "
             "context. Otherwise choose the option that is correct for {variety}.")


def system_for(target: str) -> str:
    v = VARIETY[target]
    return system_prompt(TASK.format(variety=v), KEEP_RULE.format(variety=v))


def adjudicate(ep: Endpoint | None, target: str, items: list[Item], cache: Cache,
               batch_size: int = 20, parallel: int = 4, verbose: bool = False) -> list[Decision]:
    return _adjudicate(ep, target, items, cache, batch_size, parallel, verbose,
                       system=system_for(target), log_name="stylefix")
