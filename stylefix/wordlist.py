"""Source table for the deterministic spelling swaps.

Run ``python -m stylefix.wordlist`` to regenerate the Vale substitution
rules under ``stylefix/styles/ToUS`` and ``stylefix/styles/ToUK``.

Each entry is ``(uk, us, cls)``. ``cls`` selects how inflected forms are
generated:

- ``x``   exact form only
- ``n``   noun: base, base+s
- ``v``   verb ending in -e: base, +s, +d, +ing (drop e)
- ``vn``  base, +s, +ed, +ing (colour, colours, coloured, colouring)
- ``re``  centre, centres, centred, centring / center, centers, centered, centering
- ``ll``  base is the stem (travel): travelling, travelled, traveller(s) / traveling ...
- ``yse`` analyse, analysed, analysing / analyze ... (no -es form: clashes with the noun plural)
"""

from __future__ import annotations

from pathlib import Path

STYLES_DIR = Path(__file__).parent / "styles"

# -ise/-ize group. Off when the UK target uses Oxford -ize spelling.
ISE = [
    ("organise", "organize", "v"), ("realise", "realize", "v"),
    ("recognise", "recognize", "v"), ("apologise", "apologize", "v"),
    ("emphasise", "emphasize", "v"), ("criticise", "criticize", "v"),
    ("minimise", "minimize", "v"), ("maximise", "maximize", "v"),
    ("optimise", "optimize", "v"), ("prioritise", "prioritize", "v"),
    ("summarise", "summarize", "v"), ("specialise", "specialize", "v"),
    ("standardise", "standardize", "v"), ("categorise", "categorize", "v"),
    ("characterise", "characterize", "v"), ("authorise", "authorize", "v"),
    ("capitalise", "capitalize", "v"), ("civilise", "civilize", "v"),
    ("colonise", "colonize", "v"), ("customise", "customize", "v"),
    ("finalise", "finalize", "v"), ("harmonise", "harmonize", "v"),
    ("legalise", "legalize", "v"), ("memorise", "memorize", "v"),
    ("mobilise", "mobilize", "v"), ("modernise", "modernize", "v"),
    ("monopolise", "monopolize", "v"), ("neutralise", "neutralize", "v"),
    ("normalise", "normalize", "v"), ("patronise", "patronize", "v"),
    ("popularise", "popularize", "v"), ("publicise", "publicize", "v"),
    ("randomise", "randomize", "v"), ("sanitise", "sanitize", "v"),
    ("socialise", "socialize", "v"), ("stabilise", "stabilize", "v"),
    ("symbolise", "symbolize", "v"), ("sympathise", "sympathize", "v"),
    ("synchronise", "synchronize", "v"), ("utilise", "utilize", "v"),
    ("visualise", "visualize", "v"), ("familiarise", "familiarize", "v"),
    ("generalise", "generalize", "v"), ("internalise", "internalize", "v"),
    ("jeopardise", "jeopardize", "v"), ("localise", "localize", "v"),
    ("materialise", "materialize", "v"), ("personalise", "personalize", "v"),
    ("rationalise", "rationalize", "v"), ("scrutinise", "scrutinize", "v"),
    ("serialise", "serialize", "v"), ("stigmatise", "stigmatize", "v"),
    ("subsidise", "subsidize", "v"), ("theorise", "theorize", "v"),
    ("tokenise", "tokenize", "v"), ("vandalise", "vandalize", "v"),
    ("vaporise", "vaporize", "v"), ("initialise", "initialize", "v"),
    ("globalise", "globalize", "v"), ("digitise", "digitize", "v"),
    ("itemise", "itemize", "v"), ("industrialise", "industrialize", "v"),
    ("centralise", "centralize", "v"), ("decentralise", "decentralize", "v"),
    ("formalise", "formalize", "v"), ("marginalise", "marginalize", "v"),
    ("maximise", "maximize", "v"), ("parametrise", "parametrize", "v"),
    ("penalise", "penalize", "v"), ("polarise", "polarize", "v"),
    ("revolutionise", "revolutionize", "v"), ("terrorise", "terrorize", "v"),
    ("verbalise", "verbalize", "v"), ("westernise", "westernize", "v"),
    ("regularise", "regularize", "v"), ("regularisation", "regularization", "n"),
    ("normalise", "normalize", "v"), ("legitimise", "legitimize", "v"),
    ("hypothesise", "hypothesize", "v"), ("apologise", "apologize", "v"),
    ("agonise", "agonize", "v"), ("antagonise", "antagonize", "v"),
    ("baptise", "baptize", "v"), ("brutalise", "brutalize", "v"),
    ("computerise", "computerize", "v"), ("criminalise", "criminalize", "v"),
    ("demonise", "demonize", "v"), ("dramatise", "dramatize", "v"),
    ("economise", "economize", "v"), ("equalise", "equalize", "v"),
    ("fantasise", "fantasize", "v"), ("fertilise", "fertilize", "v"),
    ("fossilise", "fossilize", "v"), ("galvanise", "galvanize", "v"),
    ("hospitalise", "hospitalize", "v"), ("humanise", "humanize", "v"),
    ("idealise", "idealize", "v"), ("immunise", "immunize", "v"),
    ("incentivise", "incentivize", "v"), ("liberalise", "liberalize", "v"),
    ("magnetise", "magnetize", "v"), ("mechanise", "mechanize", "v"),
    ("militarise", "militarize", "v"), ("minimalise", "minimalize", "v"),
    ("monetise", "monetize", "v"), ("moralise", "moralize", "v"),
    ("nationalise", "nationalize", "v"), ("operationalise", "operationalize", "v"),
    ("oxidise", "oxidize", "v"), ("pasteurise", "pasteurize", "v"),
    ("plagiarise", "plagiarize", "v"), ("pressurise", "pressurize", "v"),
    ("privatise", "privatize", "v"), ("professionalise", "professionalize", "v"),
    ("pulverise", "pulverize", "v"), ("radicalise", "radicalize", "v"),
    ("recognise", "recognize", "v"), ("reorganise", "reorganize", "v"),
    ("romanticise", "romanticize", "v"), ("satirise", "satirize", "v"),
    ("secularise", "secularize", "v"), ("sensationalise", "sensationalize", "v"),
    ("sensitise", "sensitize", "v"), ("sterilise", "sterilize", "v"),
    ("systematise", "systematize", "v"), ("temporise", "temporize", "v"),
    ("traumatise", "traumatize", "v"), ("trivialise", "trivialize", "v"),
    ("unionise", "unionize", "v"), ("urbanise", "urbanize", "v"),
    ("weaponise", "weaponize", "v"), ("reorganisation", "reorganization", "n"),
    ("nationalisation", "nationalization", "n"), ("privatisation", "privatization", "n"),
    ("liberalisation", "liberalization", "n"), ("militarisation", "militarization", "n"),
    ("monetisation", "monetization", "n"), ("radicalisation", "radicalization", "n"),
    ("sterilisation", "sterilization", "n"), ("urbanisation", "urbanization", "n"),
    ("immunisation", "immunization", "n"), ("hospitalisation", "hospitalization", "n"),
    ("computerisation", "computerization", "n"), ("decentralisation", "decentralization", "n"),
    ("harmonisation", "harmonization", "n"), ("polarisation", "polarization", "n"),
    ("industrialisation", "industrialization", "n"), ("socialisation", "socialization", "n"),
    ("legalisation", "legalization", "n"), ("formalisation", "formalization", "n"),
    ("marginalisation", "marginalization", "n"), ("materialisation", "materialization", "n"),
    ("neutralisation", "neutralization", "n"), ("personalisation", "personalization", "n"),
    ("popularisation", "popularization", "n"), ("randomisation", "randomization", "n"),
    ("sanitisation", "sanitization", "n"), ("stigmatisation", "stigmatization", "n"),
    ("subsidisation", "subsidization", "n"), ("vaporisation", "vaporization", "n"),
    ("westernisation", "westernization", "n"), ("optimiser", "optimizer", "n"),
    ("organiser", "organizer", "n"), ("synthesise", "synthesize", "v"),
    ("synthesiser", "synthesizer", "n"), ("tokeniser", "tokenizer", "n"),
    ("serialiser", "serializer", "n"), ("analyser", "analyzer", "n"),
    ("appetiser", "appetizer", "n"), ("fertiliser", "fertilizer", "n"),
    ("moisturiser", "moisturizer", "n"), ("stabiliser", "stabilizer", "n"),
    ("sympathiser", "sympathizer", "n"), ("visualiser", "visualizer", "n"),
    ("organisation", "organization", "n"), ("realisation", "realization", "n"),
    ("authorisation", "authorization", "n"), ("optimisation", "optimization", "n"),
    ("capitalisation", "capitalization", "n"), ("categorisation", "categorization", "n"),
    ("characterisation", "characterization", "n"), ("civilisation", "civilization", "n"),
    ("customisation", "customization", "n"), ("globalisation", "globalization", "n"),
    ("initialisation", "initialization", "n"), ("localisation", "localization", "n"),
    ("minimisation", "minimization", "n"), ("modernisation", "modernization", "n"),
    ("normalisation", "normalization", "n"), ("prioritisation", "prioritization", "n"),
    ("serialisation", "serialization", "n"), ("specialisation", "specialization", "n"),
    ("standardisation", "standardization", "n"), ("summarisation", "summarization", "n"),
    ("synchronisation", "synchronization", "n"), ("utilisation", "utilization", "n"),
    ("visualisation", "visualization", "n"), ("digitisation", "digitization", "n"),
    ("tokenisation", "tokenization", "n"), ("mobilisation", "mobilization", "n"),
    ("stabilisation", "stabilization", "n"), ("centralisation", "centralization", "n"),
    ("generalisation", "generalization", "n"), ("rationalisation", "rationalization", "n"),
    ("recognisable", "recognizable", "x"), ("customisable", "customizable", "x"),
    ("realisable", "realizable", "x"), ("organisational", "organizational", "x"),
    ("recognisably", "recognizably", "x"),
]

# Symmetric pairs: safe to swap deterministically in both directions.
BOTH = [
    # -our / -or
    ("colour", "color", "vn"), ("honour", "honor", "vn"), ("flavour", "flavor", "vn"),
    ("favour", "favor", "vn"), ("labour", "labor", "vn"), ("neighbour", "neighbor", "vn"),
    ("behaviour", "behavior", "n"), ("humour", "humor", "vn"), ("harbour", "harbor", "vn"),
    ("armour", "armor", "n"), ("vapour", "vapor", "n"), ("rumour", "rumor", "vn"),
    ("savour", "savor", "vn"), ("odour", "odor", "n"), ("candour", "candor", "x"),
    ("clamour", "clamor", "vn"), ("endeavour", "endeavor", "vn"), ("fervour", "fervor", "x"),
    ("valour", "valor", "x"), ("vigour", "vigor", "x"), ("splendour", "splendor", "n"),
    ("colourful", "colorful", "x"), ("favourite", "favorite", "n"), ("favourable", "favorable", "x"),
    ("honourable", "honorable", "x"), ("behavioural", "behavioral", "x"),
    ("neighbourhood", "neighborhood", "n"), ("flavoursome", "flavorsome", "x"),
    ("humourless", "humorless", "x"), ("labourer", "laborer", "n"),
    # -re / -er
    ("centre", "center", "re"), ("metre", "meter", "n"), ("litre", "liter", "n"),
    ("theatre", "theater", "n"), ("fibre", "fiber", "n"), ("calibre", "caliber", "n"),
    ("sombre", "somber", "x"), ("lustre", "luster", "x"), ("spectre", "specter", "n"),
    ("sabre", "saber", "n"), ("meagre", "meager", "x"), ("kilometre", "kilometer", "n"),
    ("centimetre", "centimeter", "n"), ("millimetre", "millimeter", "n"),
    ("millilitre", "milliliter", "n"),
    # -yse / -yze
    ("analyse", "analyze", "yse"), ("paralyse", "paralyze", "yse"),
    ("catalyse", "catalyze", "yse"), ("breathalyse", "breathalyze", "yse"),
    # -ll- / -l-
    ("travel", "travel", "ll"), ("model", "model", "ll"), ("label", "label", "ll"),
    ("cancel", "cancel", "ll"), ("fuel", "fuel", "ll"), ("signal", "signal", "ll"),
    ("counsel", "counsel", "ll"), ("channel", "channel", "ll"), ("level", "level", "ll"),
    ("marvel", "marvel", "ll"), ("quarrel", "quarrel", "ll"), ("dial", "dial", "ll"),
    ("total", "total", "ll"), ("equal", "equal", "ll"), ("jewellery", "jewelry", "x"),
    ("marvellous", "marvelous", "x"), ("woollen", "woolen", "x"),
    ("enrol", "enroll", "x"), ("enrolment", "enrollment", "n"),
    ("fulfil", "fulfill", "x"), ("fulfilment", "fulfillment", "x"),
    ("instalment", "installment", "n"), ("skilful", "skillful", "x"),
    ("wilful", "willful", "x"), ("distil", "distill", "x"), ("instil", "instill", "x"),
    ("enthral", "enthrall", "x"), ("counsellor", "counselor", "n"),
    # -ence / -ense
    ("defence", "defense", "n"), ("offence", "offense", "n"), ("pretence", "pretense", "n"),
    ("defenceless", "defenseless", "x"),
    # -ogue / -og
    ("catalogue", "catalog", "n"), ("catalogued", "cataloged", "x"),
    ("cataloguing", "cataloging", "x"), ("analogue", "analog", "n"),
    # ae / oe
    ("encyclopaedia", "encyclopedia", "n"), ("anaemia", "anemia", "x"),
    ("anaemic", "anemic", "x"), ("paediatric", "pediatric", "x"),
    ("paediatrician", "pediatrician", "n"), ("orthopaedic", "orthopedic", "x"),
    ("haemorrhage", "hemorrhage", "n"), ("haemoglobin", "hemoglobin", "x"),
    ("oesophagus", "esophagus", "x"), ("foetus", "fetus", "n"), ("foetal", "fetal", "x"),
    ("diarrhoea", "diarrhea", "x"), ("manoeuvre", "maneuver", "v"),
    ("mediaeval", "medieval", "x"), ("leukaemia", "leukemia", "x"),
    ("oestrogen", "estrogen", "x"), ("anaesthesia", "anesthesia", "x"),
    ("anaesthetic", "anesthetic", "n"), ("aetiology", "etiology", "x"),
    # miscellaneous
    ("grey", "gray", "vn"), ("aluminium", "aluminum", "x"), ("mould", "mold", "vn"),
    ("mouldy", "moldy", "x"), ("plough", "plow", "vn"), ("sceptic", "skeptic", "n"),
    ("sceptical", "skeptical", "x"), ("scepticism", "skepticism", "x"),
    ("aeroplane", "airplane", "n"), ("pyjamas", "pajamas", "x"), ("ageing", "aging", "x"),
    ("artefact", "artifact", "n"), ("cosy", "cozy", "x"), ("maths", "math", "x"),
    ("moustache", "mustache", "n"), ("omelette", "omelet", "n"), ("yoghurt", "yogurt", "n"),
    ("sulphur", "sulfur", "x"), ("tonne", "ton", "n"), ("whisky", "whiskey", "x"),
    ("kerb", "curb", "n"), ("cheque", "check", "n"), ("chequebook", "checkbook", "n"),
    ("tyre", "tire", "n"), ("storey", "story", "x"), ("storeys", "stories", "x"),
    ("programme", "program", "n"), ("enquiry", "inquiry", "x"), ("enquiries", "inquiries", "x"),
    ("enquire", "inquire", "v"), ("draught", "draft", "n"), ("judgement", "judgment", "n"),
    ("acknowledgement", "acknowledgment", "n"), ("dreamt", "dreamed", "x"),
    ("learnt", "learned", "x"), ("spoilt", "spoiled", "x"), ("spelt", "spelled", "x"), ("disc", "disk", "n"),
    ("practise", "practice", "x"), ("practises", "practices", "x"),
    ("practised", "practiced", "x"), ("practising", "practicing", "x"),
    ("licence", "license", "n"), ("mum", "mom", "n"),
]

# UK words whose US mapping is unambiguous, but whose US form maps back to
# more than one UK spelling (noun/verb split or sense split). They go in
# ToUS/Variants.yml only; the US form is handled by ToUK/Ambiguous.yml.
US_ONLY = {
    "kerb", "cheque", "chequebook", "tyre", "storey", "storeys", "programme",
    "enquiry", "enquiries", "enquire", "draught", "judgement", "learnt",
    "spoilt", "dreamt", "spelt", "disc", "practise", "practises", "licence", "metre",
    "tonne", "whisky", "mum",
}

# UK words with a sense split going *to* US (disc/disk, tonne/ton). They
# are excluded from ToUS/Variants.yml and handled by ToUS/Ambiguous.yml.
UK_AMBIGUOUS_TO_US = {"disc", "tonne", "whisky", "mum"}


def inflect(uk: str, us: str, cls: str) -> list[tuple[str, str]]:
    """Return every (uk_form, us_form) pair for one table entry."""
    if cls == "x":
        return [(uk, us)]
    if cls == "n":
        return [(uk, us), (uk + "s", us + "s")]
    if cls == "v":
        return [(uk, us), (uk + "s", us + "s"), (uk + "d", us + "d"),
                (uk[:-1] + "ing", us[:-1] + "ing")]
    if cls == "vn":
        return [(uk, us), (uk + "s", us + "s"), (uk + "ed", us + "ed"),
                (uk + "ing", us + "ing")]
    if cls == "re":
        stem_uk, stem_us = uk[:-2], us[:-2]  # cent / cent
        return [(uk, us), (uk + "s", us + "s"), (uk + "d", us + "ed"),
                (stem_uk + "ring", stem_us + "ering")]
    if cls == "ll":
        return [(uk + "ling", us + "ing"), (uk + "led", us + "ed"),
                (uk + "ler", us + "er"), (uk + "lers", us + "ers")]
    if cls == "yse":
        return [(uk, us), (uk + "d", us + "d"),
                (uk[:-1] + "ing", us[:-1] + "ing")]
    raise ValueError(f"unknown class {cls!r}")


def to_us_map(include_ise: bool = True) -> dict[str, str]:
    out: dict[str, str] = {}
    for uk, us, cls in BOTH + (ISE if include_ise else []):
        for u, a in inflect(uk, us, cls):
            if u == a:
                continue
            base = uk if cls != "ll" else None
            if base in UK_AMBIGUOUS_TO_US:
                continue
            out[u] = a
    return out


def to_uk_map(ise: bool = True) -> dict[str, str]:
    out: dict[str, str] = {}
    for uk, us, cls in BOTH:
        if uk in US_ONLY:
            continue
        for u, a in inflect(uk, us, cls):
            if u != a:
                out[a] = u
    if ise:
        for uk, us, cls in ISE:
            for u, a in inflect(uk, us, cls):
                out[a] = u
    return out


def render_rule(message: str, swap: dict[str, str]) -> str:
    lines = [
        "# Generated by `python -m stylefix.wordlist`. Edit wordlist.py, not this file.",
        "extends: substitution",
        f"message: \"{message}\"",
        "level: error",
        "ignorecase: true",
        "action:",
        "  name: replace",
        "swap:",
    ]
    for k in sorted(swap):
        lines.append(f"  {k}: {swap[k]}")
    return "\n".join(lines) + "\n"


def write_styles(styles_dir: Path = STYLES_DIR) -> None:
    (styles_dir / "ToUS").mkdir(parents=True, exist_ok=True)
    (styles_dir / "ToUK").mkdir(parents=True, exist_ok=True)
    (styles_dir / "ToUS" / "Variants.yml").write_text(
        render_rule("Use US spelling '%s' instead of '%s'.", to_us_map()))
    (styles_dir / "ToUK" / "Variants.yml").write_text(
        render_rule("Use UK spelling '%s' instead of '%s'.", to_uk_map(ise=False)))
    (styles_dir / "ToUK" / "Ise.yml").write_text(
        render_rule("Use UK -ise spelling '%s' instead of '%s'.",
                    {k: v for k, v in to_uk_map(ise=True).items()
                     if k not in to_uk_map(ise=False)}))


if __name__ == "__main__":
    write_styles()
    print(f"wrote styles to {STYLES_DIR}")
