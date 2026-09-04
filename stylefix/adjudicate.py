"""Ask the model to choose between candidate spellings for ambiguous words."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .llm import Endpoint, LLMError

VARIETY = {"us": "American English", "uk": "British English"}

SYSTEM = """You are a meticulous copy editor regularizing a document to {variety}.
For each item, choose exactly one option from its list. Choose KEEP when the marked word is
part of a proper name, an organisation name, the title of a published work, a direct quotation
from a source written in another variety, a URL or code identifier, or is already correct
for {variety} in this context. Otherwise choose the option that is correct for {variety}.
Respond with JSON only, in this shape:
{{"decisions": [{{"id": 1, "choice": "<one of the options, verbatim>", "confidence": 0.0, "reason": "<under 12 words>"}}]}}"""


@dataclass
class Item:
    id: int
    word: str
    options: tuple[str, ...]
    rule: str
    context: str
    line: int
    start: int
    end: int
    source: str = "ambiguous"     # "ambiguous" | "capitalized"


@dataclass
class Decision:
    item: Item
    choice: str | None            # None = could not decide
    confidence: float
    reason: str
    cached: bool = False

    @property
    def replacement(self) -> str | None:
        """The text to substitute, or None to leave the word alone."""
        if self.choice is None or self.choice == "KEEP":
            return None
        if self.choice.lower() == self.item.word.lower():
            return None
        return self.choice


class Cache:
    def __init__(self, path: Path | None):
        self.path = path
        self.data: dict[str, dict] = {}
        if path and path.exists():
            try:
                self.data = json.loads(path.read_text())
            except json.JSONDecodeError:
                self.data = {}

    @staticmethod
    def key(target: str, item: Item) -> str:
        norm = re.sub(r"\s+", " ", item.context).strip().lower()
        h = hashlib.sha256(f"{target}|{item.word.lower()}|{norm}".encode()).hexdigest()
        return h[:24]

    def get(self, k: str) -> dict | None:
        return self.data.get(k)

    def put(self, k: str, d: Decision) -> None:
        self.data[k] = {"word": d.item.word, "choice": d.choice,
                        "confidence": d.confidence, "reason": d.reason,
                        "context": d.item.context}

    def save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1, ensure_ascii=False))


def render_batch(items: list[Item]) -> str:
    parts = []
    for it in items:
        parts.append(
            f"Item {it.id} — word: \"{it.word}\" — options: {' | '.join(it.options)}\n"
            f"Rule: {it.rule}\n"
            f"Context: {it.context}")
    return "\n\n".join(parts)


def parse_response(text: str) -> dict[int, dict]:
    """Return {id: {choice, confidence, reason}} from the model's reply."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    m = re.search(r"[\[{]", text)
    if not m:
        return {}
    try:
        data = json.loads(text[m.start():])
    except json.JSONDecodeError:
        # Try to salvage the largest balanced object.
        end = max(text.rfind("}"), text.rfind("]"))
        try:
            data = json.loads(text[m.start():end + 1])
        except json.JSONDecodeError:
            return {}
    if isinstance(data, dict):
        data = data.get("decisions", data.get("items", []))
    out = {}
    for d in data if isinstance(data, list) else []:
        if isinstance(d, dict) and "id" in d:
            try:
                out[int(d["id"])] = d
            except (TypeError, ValueError):
                continue
    return out


def decide_batch(ep: Endpoint, target: str, items: list[Item]) -> list[Decision]:
    try:
        reply = ep.chat(SYSTEM.format(variety=VARIETY[target]), render_batch(items))
    except LLMError as e:
        return [Decision(it, None, 0.0, f"model error: {e}") for it in items]
    answers = parse_response(reply)
    out = []
    for it in items:
        a = answers.get(it.id)
        if not a:
            out.append(Decision(it, None, 0.0, "no answer from model"))
            continue
        choice = str(a.get("choice", "")).strip()
        matched = next((o for o in it.options if o.lower() == choice.lower()), None)
        try:
            conf = float(a.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        reason = str(a.get("reason", ""))[:200]
        if matched is None:
            out.append(Decision(it, None, 0.0, f"invalid choice {choice!r}"))
        else:
            out.append(Decision(it, matched, conf, reason))
    return out


def adjudicate(ep: Endpoint | None, target: str, items: list[Item], cache: Cache,
               batch_size: int = 20, parallel: int = 4, verbose: bool = False) -> list[Decision]:
    decisions: dict[int, Decision] = {}
    todo: list[Item] = []
    for it in items:
        k = Cache.key(target, it)
        hit = cache.get(k)
        if hit and hit.get("choice") in it.options:
            decisions[it.id] = Decision(it, hit["choice"], float(hit.get("confidence", 1.0)),
                                        hit.get("reason", ""), cached=True)
        else:
            todo.append(it)
    if todo and ep is None:
        for it in todo:
            decisions[it.id] = Decision(it, None, 0.0, "no model configured")
    elif todo:
        batches = [todo[i:i + batch_size] for i in range(0, len(todo), batch_size)]
        if verbose:
            print(f"stylefix: asking {ep.name} ({ep.model}) about {len(todo)} items "
                  f"in {len(batches)} batch(es), {parallel} in parallel", file=sys.stderr)
        with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
            for result in pool.map(lambda b: decide_batch(ep, target, b), batches):
                for d in result:
                    decisions[d.item.id] = d
                    if d.choice is not None:
                        cache.put(Cache.key(target, d.item), d)
        cache.save()
    return [decisions[it.id] for it in items]
