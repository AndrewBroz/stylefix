"""Ambiguous words: the options the adjudicator may choose between."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    options: tuple[str, ...]  # first option is the variety-specific form
    rule: str


def _pair(uk_or_us: str, same: str, rule: str, plural: str | None = None,
          plural_same: str | None = None) -> dict[str, Candidate]:
    out = {same: Candidate((uk_or_us, same, "KEEP"), rule)}
    if plural:
        out[plural_same or same + "s"] = Candidate((plural, plural_same or same + "s", "KEEP"), rule)
    return out


TO_UK: dict[str, Candidate] = {}
TO_UK.update(_pair("licence", "license",
                   "British: 'licence' is the noun (a driving licence); 'license' is the verb (to license software).",
                   "licences"))
TO_UK.update(_pair("practise", "practice",
                   "British: 'practice' is the noun (medical practice, in practice); 'practise' is the verb (to practise the piano).",
                   "practises"))
TO_UK.update(_pair("programme", "program",
                   "British: 'programme' for broadcasts, events, plans and schedules; 'program' only for computer software.",
                   "programmes"))
TO_UK.update(_pair("cheque", "check",
                   "British: 'cheque' only for the bank instrument; 'check' for verifying, restraining, chess, patterns.",
                   "cheques"))
TO_UK.update(_pair("storey", "story",
                   "British: 'storey' is a floor of a building; 'story' is a narrative.",
                   "storeys", "stories"))
TO_UK.update(_pair("tyre", "tire",
                   "British: 'tyre' is the rubber ring on a wheel; 'tire' is the verb (to grow weary).",
                   "tyres"))
TO_UK.update(_pair("metre", "meter",
                   "British: 'metre' is the unit of length (and poetic metre); 'meter' is a measuring device (gas meter).",
                   "metres"))
TO_UK.update(_pair("kerb", "curb",
                   "British: 'kerb' is the edge of a pavement; 'curb' is the verb (to restrain).",
                   "kerbs"))
TO_UK.update(_pair("enquiry", "inquiry",
                   "British: 'enquiry' is an ordinary question or request; 'inquiry' is a formal investigation.",
                   "enquiries", "inquiries"))
TO_UK.update(_pair("draught", "draft",
                   "British: 'draught' for air currents, beer, ships' depth, draught animals, and the game; 'draft' for preliminary versions, banking, and conscription.",
                   "draughts"))
TO_UK.update(_pair("judgement", "judgment",
                   "British: 'judgement' in general use; 'judgment' for a court's formal decision.",
                   "judgements"))
TO_UK.update(_pair("learnt", "learned",
                   "British: 'learnt' as the past tense/participle of learn; 'learned' (two syllables) as the adjective meaning scholarly."))
TO_UK.update(_pair("disc", "disk",
                   "British: 'disc' for optical discs, brake discs, anatomy and flat round objects; 'disk' for magnetic computer disks.",
                   "discs"))
TO_UK.update(_pair("tonne", "ton",
                   "British: 'tonne' is the metric unit (1000 kg); 'ton' is the imperial unit or figurative ('tons of').",
                   "tonnes"))
TO_UK.update(_pair("whisky", "whiskey",
                   "British: 'whisky' for Scotch and Canadian; 'whiskey' for Irish and American.",
                   "whiskies", "whiskeys"))
TO_UK.update(_pair("mum", "mom",
                   "British: 'mum' for mother; keep 'mom' only inside a quotation or a name.",
                   "mums"))

TO_US: dict[str, Candidate] = {}
TO_US.update(_pair("disk", "disc",
                   "American: 'disk' for computer disks and general use; 'disc' for optical discs (compact disc), brake discs and anatomy.",
                   "disks"))
TO_US.update(_pair("metric ton", "tonne",
                   "American: 'metric ton' for 1000 kg; keep 'tonne' only inside a quotation or a proper name.",
                   "metric tons"))
TO_US.update(_pair("whiskey", "whisky",
                   "American: 'whiskey' in general; 'whisky' stays for Scotch and Canadian.",
                   "whiskeys", "whiskys"))
TO_US.update(_pair("mom", "mum",
                   "American: 'mom' for mother; keep 'mum' when it means silent ('keep mum') or the flower.",
                   "moms"))

TABLES = {"uk": TO_UK, "us": TO_US}


def lookup(target: str, word: str) -> Candidate | None:
    return TABLES[target].get(word.lower())
