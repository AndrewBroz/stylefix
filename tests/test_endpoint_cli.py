import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from stylefix.cli import build_parser, main

DOC = "The license was granted.\n"   # license -> UK is a sense split: always adjudicated


def test_isolation_hides_real_config(isolated_llm_config):
    assert os.environ["XDG_CONFIG_HOME"] == str(isolated_llm_config)
    assert not any(os.environ.get(f"{app}_LLM_{s}") for app in ("ADJUDICATE", "STYLEFIX", "PROOFIX")
                   for s in ("URL", "MODEL", "KEY"))


def test_dgx_preset_is_gone():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["x.md", "--target", "us", "--llm", "dgx"])


def test_timeout_flag_defaults_to_none():
    assert build_parser().parse_args(["x.md", "--target", "us"]).timeout is None


def test_bad_config_exits_2(isolated_llm_config, tmp_path, capsys):
    cfg = isolated_llm_config / "adjudicate" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("[llm]\nmodle = 'x'\n")
    src = tmp_path / "d.md"
    src.write_text(DOC)
    assert main([str(src), "--target", "uk", "--no-cache", "--dry-run"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("stylefix: ") and str(cfg) in err and "modle" in err


@pytest.fixture
def chat_server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            data = json.dumps({"choices": [{"message": {"content": '{"decisions": []}'}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1", received
    httpd.shutdown()
    httpd.server_close()


def test_no_endpoint_suggests_setup(tmp_path, capsys):
    src = tmp_path / "d.md"
    src.write_text(DOC)
    assert main([str(src), "--target", "uk", "--no-cache", "--dry-run"]) == 0
    assert "stylefix --setup" in capsys.readouterr().err


def test_check_endpoint_needs_no_input_file(capsys):
    assert main(["--check-endpoint"]) == 1          # nothing configured in the isolated home
    assert "stylefix --setup" in capsys.readouterr().out


def test_setup_needs_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert main(["--setup"]) == 2
    captured = capsys.readouterr()
    assert "terminal" in captured.err and "terminal" not in captured.out


def test_config_url_reaches_the_server(isolated_llm_config, tmp_path, chat_server):
    url, received = chat_server
    cfg = isolated_llm_config / "adjudicate" / "config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(f'[llm]\nurl = "{url}"\nmodel = "m"\n')
    src = tmp_path / "d.md"
    src.write_text(DOC)
    assert main([str(src), "--target", "uk", "--no-cache", "--dry-run"]) == 0
    assert received and received[0]["model"] == "m"
