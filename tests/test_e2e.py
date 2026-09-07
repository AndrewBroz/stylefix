"""End-to-end: real Vale, stub model server, real CLI."""

import json
import shutil
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from stylefix.cli import main

pytestmark = pytest.mark.skipif(shutil.which("vale") is None, reason="vale not installed")

SAMPLE = Path(__file__).parent.parent / "examples" / "sample.md"


class StubModel(BaseHTTPRequestHandler):
    """Answers every item with a canned choice keyed on the word."""
    answers = {"license": "licence", "practice": "practice", "program": "programme",
               "check": "cheque", "story": "story", "labour": "KEEP", "centre": "Centre",
               "defence": "KEEP", "colour": "color", "disc": "disc", "tire": "tire"}
    requests: list[dict] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        StubModel.requests.append(body)
        user = body["messages"][1]["content"]
        decisions = []
        for line in user.splitlines():
            if line.startswith("Item "):
                _, num, _, _, word, *_ = line.split(" ", 5)
                word = word.strip('"“”—').lower()
                options = line.split("options: ")[1].split(" | ")
                choice = self.answers.get(word, "KEEP")
                match = next((o for o in options if o.lower() == choice.lower()), "KEEP")
                decisions.append({"id": int(num), "choice": match, "confidence": 0.9, "reason": "stub"})
        out = json.dumps({"choices": [{"message": {"content": json.dumps({"decisions": decisions})}}]})
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(out.encode())

    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"{}")

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def stub_url():
    srv = HTTPServer(("127.0.0.1", 0), StubModel)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


def run(tmp_path, target, extra=()):
    src = tmp_path / "doc.md"
    shutil.copy(SAMPLE, src)
    out = tmp_path / f"out.{target}.md"
    rc = main([str(src), "-o", str(out), "--target", target, "--cache",
               str(tmp_path / "cache.json"), *extra])
    assert rc == 0
    return out.read_text(), (tmp_path / "out.us.md.report.md" if target == "us"
                             else tmp_path / "out.uk.md.report.md").read_text()


def test_to_us_chicago(tmp_path, stub_url):
    text, rep = run(tmp_path, "us", ["--url", stub_url, "--model", "stub"])
    assert text.startswith("---\ntitle: Colour Management Programme\n")   # front matter untouched
    assert "# Color management program" in text
    assert "organizes its work around a simple license" in text
    assert "Members practice what they preach: every program is analyzed" in text
    assert "story of the building is cataloged" in text and "is spelled the British way" in text
    assert "“color” is spelled the British way—while our American colleagues favor “color.”" in text
    assert "runs 3–5 sessions" in text
    assert "Labour Party office by September 4, 2026" in text          # KEEP via stub
    assert "theater program lists the meter readings, the tire pressures" in text
    assert "disc brakes we’ve organized for the aluminum trailer" in text
    assert "Defence Ministry" in text and "“the color scheme was unauthorised.”" in text  # quoted: stub keeps
    assert "made us tire of the whole thing. It’s the Joneses’ problem now, toward the end\nof the ’90s." in text
    assert 'colour = "unchanged in code"  # organise nothing here' in text
    assert "`colour_utils.organise()`" in text and "(https://example.org/colour)" in text
    assert "[the color guide]" in text
    assert "| deterministic replacements |" in rep and "Labour" in rep


def test_to_uk_oxford(tmp_path, stub_url):
    text, rep = run(tmp_path, "uk", ["--url", stub_url, "--model", "stub"])
    assert "The programme crashed after the cheque cleared, and the story about the storey" in text
    assert "made us tire of the whole thing" in text
    assert "‘colour’ is spelt the British way – whilst our American colleagues favour ‘color’." in text  # quoted: stub keeps
    assert "by 4 September 2026" in text
    assert "## Adjudicated" in rep


def test_no_llm_lists_for_review(tmp_path):
    text, rep = run(tmp_path, "uk", ["--llm", "none"])
    assert "The program crashed after the check cleared" in text     # left alone
    assert "UNDECIDED" in rep and "no model configured" in rep


def test_dry_run_writes_nothing(tmp_path, capsys):
    src = tmp_path / "doc.md"; shutil.copy(SAMPLE, src)
    rc = main([str(src), "--target", "us", "--llm", "none", "--dry-run", "--no-cache"])
    assert rc == 0
    assert not (tmp_path / "doc.us.md").exists()
    assert "-# Colour management programme" in capsys.readouterr().out


def test_accept_list_protects_words(tmp_path, stub_url):
    (tmp_path / "accept.txt").write_text("aluminium\n")
    text, _ = run(tmp_path, "us", ["--url", stub_url, "--model", "stub",
                                    "--accept", str(tmp_path / "accept.txt")])
    assert "aluminium trailer" in text


def test_oxford_ize(tmp_path, stub_url):
    src = tmp_path / "d.md"; src.write_text("We organize and analyze color.\n")
    out = tmp_path / "o.md"
    main([str(src), "-o", str(out), "--target", "uk", "--oxford-ize", "--llm", "none", "--no-cache"])
    assert out.read_text() == "We organize and analyse colour.\n"


def test_builtin_accept_list_silences_technical_terms(tmp_path):
    src = tmp_path / "t.md"
    src.write_text("Cybersecurity and sandboxing are auditable colour choices.\n")
    out = tmp_path / "o.md"
    rep = tmp_path / "o.report.md"
    main([str(src), "-o", str(out), "--target", "us", "--llm", "none", "--no-cache",
          "--report", str(rep)])
    r = rep.read_text()
    assert "cybersecurity" not in r.lower().split("## for human review")[-1]
    assert "sandboxing" not in r and "auditable" not in r
    assert out.read_text().startswith("Cybersecurity and sandboxing are auditable color")


def test_user_and_project_accept_lists(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    (tmp_path / "cfg" / "stylefix").mkdir(parents=True)
    (tmp_path / "cfg" / "stylefix" / "accept.txt").write_text("# mine\nfooberry\n")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".stylefix").mkdir()
    (tmp_path / ".stylefix" / "accept.txt").write_text("barberry\n")
    src = tmp_path / "t.md"
    src.write_text("fooberry barberry bazberry\n")
    rep = tmp_path / "o.report.md"
    main([str(src), "-o", str(tmp_path / "o.md"), "--target", "us", "--llm", "none",
          "--no-cache", "--report", str(rep)])
    r = rep.read_text()
    assert "fooberry" not in r and "barberry" not in r and "bazberry" in r
