"""CONNECT-AGENTS (ONE-PROFILE, the owner 2026-09-28): `scripts/connect_agents.sh` connects this Mac's Claude Code and Codex with
the key from `.env`, never prints it, replaces an old entry (Codex: through `codex mcp remove`, then ONE new section with the key as
a fixed header), and changes nothing when the server refuses the key.

Everything runs in a sandbox: stub `claude` / `codex` on a PATH without the real ones, HOME and CODEX_HOME in tmp, a fake key, and
a stub MCP server on loopback. The owner's real agent configs are never touched."""
from __future__ import annotations

import http.server
import os
import pathlib
import stat
import subprocess
import sys
import threading
import tomllib
from typing import ClassVar

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "connect_agents.sh"
KEY = "test-key-0123456789abcdef"
OLD = """model = "gpt-5"

[mcp_servers.polymath]
url = "https://mcp.kingsleylab.xyz/mcp"
bearer_token_env_var = "POLYMATH_MCP_KEY"

[mcp_servers.other]
command = "other-server"
"""

CLAUDE_STUB = """#!{py}
import json, pathlib, sys
log = pathlib.Path({log!r})
with log.open("a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
sys.exit(0)
"""

# `codex mcp remove polymath`: drop the [mcp_servers.polymath] table (and its sub-tables) the way Codex does.
CODEX_STUB = """#!{py}
import json, os, pathlib, sys
pathlib.Path({log!r}).open("a").write(json.dumps(sys.argv[1:]) + "\\n")
if sys.argv[1:4] == ["mcp", "remove", "polymath"] and {removes!r}:
    cfg = pathlib.Path(os.environ["CODEX_HOME"]) / "config.toml"
    if cfg.exists():
        out, skip = [], False
        for line in cfg.read_text().splitlines(keepends=True):
            s = line.strip()
            if s.startswith("["):
                skip = s.startswith("[mcp_servers.polymath]") or s.startswith("[mcp_servers.polymath.")
            if not skip:
                out.append(line)
        cfg.write_text("".join(out))
sys.exit(0)
"""


def _stub(path: pathlib.Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class _Mcp(http.server.BaseHTTPRequestHandler):
    seen: ClassVar[list[str]] = []

    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length") or 0))
        auth = self.headers.get("authorization") or ""
        type(self).seen.append(auth)
        ok = auth == f"Bearer {KEY}"
        body = b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"polymath"}}}' if ok else b'{"detail":"unauthorized"}'
        self.send_response(200 if ok else 401)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Mcp.seen = []
    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Mcp)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/mcp"
    httpd.shutdown()


def _sandbox(tmp_path, *, claude=True, codex=True, codex_removes=True, env_line=f"POLYMATH_MCP_API_KEY={KEY}", config=OLD):
    bin_dir, home = tmp_path / "bin", tmp_path / "home"
    bin_dir.mkdir()
    (home / ".codex").mkdir(parents=True)
    if config is not None:
        (home / ".codex" / "config.toml").write_text(config)
    (tmp_path / ".env").write_text(f"OTHER=1\n{env_line}\n")
    log = tmp_path / "calls.jsonl"
    if claude:
        _stub(bin_dir / "claude", CLAUDE_STUB.format(py=sys.executable, log=str(log)))
    if codex:
        _stub(bin_dir / "codex", CODEX_STUB.format(py=sys.executable, log=str(log), removes=codex_removes))
    return bin_dir, home, log


def _run(tmp_path, bin_dir, home, url):
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": str(home), "CODEX_HOME": str(home / ".codex"),
           "POLYMATH_ENV_FILE": str(tmp_path / ".env"), "POLYMATH_CONNECT_URL": url}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60, check=False)


def _calls(log: pathlib.Path) -> list[list[str]]:
    import json
    return [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []


def test_the_real_agents_are_not_on_the_sandbox_path(tmp_path):
    bin_dir, _, _ = _sandbox(tmp_path, claude=False, codex=False)
    found = subprocess.run(["bash", "-c", "command -v claude codex"], env={"PATH": f"{bin_dir}:/usr/bin:/bin"},
                           capture_output=True, text=True, check=False)
    assert found.stdout.strip() == ""


def test_it_connects_both_agents_with_the_key_and_never_prints_it(tmp_path, server):
    bin_dir, home, log = _sandbox(tmp_path)
    r = _run(tmp_path, bin_dir, home, server)
    assert r.returncode == 0, r.stdout + r.stderr
    assert KEY not in r.stdout and KEY not in r.stderr
    assert _Mcp.seen == [f"Bearer {KEY}"]                                       # the key was checked with the server first
    calls = _calls(log)
    assert ["mcp", "remove", "polymath", "-s", "user"] in calls
    assert ["mcp", "add", "-s", "user", "-t", "http", "polymath", server, "-H", f"Authorization: Bearer {KEY}"] in calls
    assert ["mcp", "remove", "polymath"] in calls
    cfg_path = home / ".codex" / "config.toml"
    cfg = tomllib.loads(cfg_path.read_text())
    assert cfg["mcp_servers"]["polymath"] == {"url": server, "http_headers": {"Authorization": f"Bearer {KEY}"}}
    assert cfg["mcp_servers"]["other"] == {"command": "other-server"} and cfg["model"] == "gpt-5"
    assert stat.S_IMODE(cfg_path.stat().st_mode) == 0o600


def test_running_it_twice_leaves_one_codex_section(tmp_path, server):
    bin_dir, home, _ = _sandbox(tmp_path)
    assert _run(tmp_path, bin_dir, home, server).returncode == 0
    assert _run(tmp_path, bin_dir, home, server).returncode == 0
    text = (home / ".codex" / "config.toml").read_text()
    assert text.count("[mcp_servers.polymath]") == 1
    assert tomllib.loads(text)["mcp_servers"]["polymath"]["http_headers"] == {"Authorization": f"Bearer {KEY}"}


def test_a_refused_key_changes_nothing(tmp_path, server):
    bin_dir, home, log = _sandbox(tmp_path, env_line="POLYMATH_MCP_API_KEY=wrong-key-000")
    r = _run(tmp_path, bin_dir, home, server)
    assert r.returncode == 2 and "refused" in r.stdout and "wrong-key-000" not in r.stdout
    assert _calls(log) == [] and (home / ".codex" / "config.toml").read_text() == OLD


def test_no_key_in_env_means_nothing_to_connect(tmp_path, server):
    bin_dir, home, log = _sandbox(tmp_path, env_line="SOMETHING_ELSE=1")
    r = _run(tmp_path, bin_dir, home, server)
    assert r.returncode == 1 and "POLYMATH_MCP_API_KEY" in r.stdout
    assert _calls(log) == [] and _Mcp.seen == []


def test_a_quoted_key_is_read_without_its_quotes(tmp_path, server):
    bin_dir, home, _ = _sandbox(tmp_path, env_line=f'POLYMATH_MCP_API_KEY="{KEY}"')
    assert _run(tmp_path, bin_dir, home, server).returncode == 0
    assert _Mcp.seen == [f"Bearer {KEY}"]


def test_neither_agent_installed(tmp_path, server):
    bin_dir, home, _ = _sandbox(tmp_path, claude=False, codex=False)
    r = _run(tmp_path, bin_dir, home, server)
    assert r.returncode == 1 and "Neither" in r.stdout and _Mcp.seen == []


def test_only_codex_installed_and_no_config_yet(tmp_path, server):
    bin_dir, home, _ = _sandbox(tmp_path, claude=False, config=None)
    r = _run(tmp_path, bin_dir, home, server)
    assert r.returncode == 0 and "Claude Code: not installed" in r.stdout
    cfg = tomllib.loads((home / ".codex" / "config.toml").read_text())
    assert cfg["mcp_servers"]["polymath"]["url"] == server


def test_it_never_appends_a_second_polymath_section(tmp_path, server):
    bin_dir, home, _ = _sandbox(tmp_path, codex_removes=False)                   # a Codex that did not remove the old one
    r = _run(tmp_path, bin_dir, home, server)
    assert r.returncode == 3 and "delete it by hand" in r.stdout
    assert (home / ".codex" / "config.toml").read_text() == OLD


def test_a_server_that_is_down_still_connects_the_agents(tmp_path):
    bin_dir, home, _ = _sandbox(tmp_path)
    r = _run(tmp_path, bin_dir, home, "http://127.0.0.1:9/mcp")                 # nothing listens on port 9
    assert r.returncode == 0 and "not answering" in r.stdout
    assert tomllib.loads((home / ".codex" / "config.toml").read_text())["mcp_servers"]["polymath"]["url"] == "http://127.0.0.1:9/mcp"


def test_the_settings_route_names_this_script():
    for sub in ("orchestrator", "shared"):
        sys.path.insert(0, str(ROOT / sub))
    from orchestrator.api import web_settings
    assert pathlib.Path(web_settings.__file__).is_relative_to(ROOT)
    assert web_settings.CONNECT_SCRIPT == SCRIPT and web_settings.connect_command() == f"bash {SCRIPT}"
    assert os.access(SCRIPT, os.R_OK)
