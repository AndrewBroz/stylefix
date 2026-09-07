"""Run Vale with the packaged styles and return its alerts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

STYLES_DIR = Path(__file__).parent / "styles"

STYLE_SETS = {
    "us": ["ToUS"],
    "uk": ["ToUK"],
}
from .styleguides import GUIDES as _GUIDES
GUIDES = {name: (g.title or None) for name, g in _GUIDES.items()}


class ValeError(RuntimeError):
    pass


@dataclass
class Alert:
    line: int          # 1-indexed
    start: int         # 1-indexed inclusive column (characters)
    end: int           # 1-indexed inclusive column
    check: str         # e.g. "ToUS.Variants"
    match: str
    message: str
    severity: str
    action: str        # "replace" or ""
    params: list[str]

    @property
    def replacement(self) -> str | None:
        return self.params[0] if self.action == "replace" and self.params else None

    @classmethod
    def from_json(cls, d: dict) -> "Alert":
        act = d.get("Action") or {}
        return cls(
            line=d["Line"], start=d["Span"][0], end=d["Span"][1],
            check=d["Check"], match=d["Match"], message=d["Message"],
            severity=d["Severity"], action=act.get("Name") or "",
            params=list(act.get("Params") or []),
        )


def find_vale() -> str:
    exe = shutil.which("vale")
    if not exe:
        raise ValeError("vale not found on PATH. Install it: https://vale.sh/docs/install "
                        "(e.g. `brew install vale`).")
    return exe


def build_config(workdir: Path, target: str, guide: str, oxford_ize: bool,
                 accept_words: list[str] | None = None) -> Path:
    """Write a .vale.ini (and vocab, if any) into workdir; return the ini path."""
    styles = list(STYLE_SETS[target])
    if GUIDES[guide]:
        styles.append(GUIDES[guide])
    lines = [f"StylesPath = {STYLES_DIR}", "MinAlertLevel = suggestion"]
    if accept_words:
        # Vale requires vocabularies to live under StylesPath, so build a
        # shadow StylesPath with symlinks to the packaged styles.
        shadow = workdir / "styles"
        shadow.mkdir()
        for d in STYLES_DIR.iterdir():
            if d.is_dir():
                os.symlink(d, shadow / d.name)
        vocab = shadow / "config" / "vocabularies" / "Project"
        vocab.mkdir(parents=True)
        (vocab / "accept.txt").write_text("\n".join(accept_words) + "\n")
        lines[0] = f"StylesPath = {shadow}"
        lines.append("Vocab = Project")
    lines += ["", "[*]", f"BasedOnStyles = {', '.join(styles)}"]
    if target == "uk":
        # Non-Oxford UK converts -ize to -ise; Oxford does the reverse.
        off = ["Ise", "PatIze"] if oxford_ize else ["Oxford", "PatIse"]
        for rule in sorted(STYLES_DIR.joinpath("ToUK").glob("*.yml")):
            if any(rule.stem.startswith(o) for o in off):
                lines.append(f"ToUK.{rule.stem} = NO")
    ini = workdir / ".vale.ini"
    ini.write_text("\n".join(lines) + "\n")
    return ini


def run_vale(path: Path, target: str, guide: str = "none", oxford_ize: bool = False,
             accept_words: list[str] | None = None) -> list[Alert]:
    exe = find_vale()
    with tempfile.TemporaryDirectory(prefix="stylefix-") as tmp:
        ini = build_config(Path(tmp), target, guide, oxford_ize, accept_words)
        proc = subprocess.run(
            [exe, "--config", str(ini), "--output=JSON", "--no-exit", str(path)],
            capture_output=True, text=True,
        )
    if proc.returncode != 0:
        raise ValeError(f"vale exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}")
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        raise ValeError(f"could not parse vale output: {e}\n{proc.stdout[:500]}") from e
    alerts: list[Alert] = []
    for _file, items in data.items():
        alerts.extend(Alert.from_json(d) for d in items)
    alerts.sort(key=lambda a: (a.line, a.start))
    return alerts
