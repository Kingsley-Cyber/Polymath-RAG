"""The go-live kit (FRIENDS-ACCESS-V1 F5): the Caddy change removes only the shared basic-auth and adds the principal-header
strip, keeps the rest, is idempotent, and writes nothing without --apply; the Run-button script is valid bash, runs its steps in
order, merges fast-forward only and never prints the secret; the live check imports without touching the network."""
import importlib.util
import pathlib
import py_compile
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import pytest

CURRENT = """{
  admin off
}
:8794 {
  basic_auth {
    King $2a$14$notarealhashnotarealhashnotarealhashnotarealhash
  }
  redir / /v2/ 302
  reverse_proxy 127.0.0.1:7200
}
"""


def _mod():
    spec = importlib.util.spec_from_file_location("friends_access_caddy", ROOT / "scripts" / "friends_access_caddy.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_caddy_change_removes_only_basic_auth_and_strips_the_principal_header():
    new, changes = _mod().transform(CURRENT)
    assert "basic_auth" not in new and "notarealhash" not in new
    assert "request_header -X-Polymath-Principal" in new
    assert "admin off" in new and "redir / /v2/ 302" in new and "reverse_proxy 127.0.0.1:7200" in new
    assert new.index("request_header -X-Polymath-Principal") < new.index("reverse_proxy 127.0.0.1:7200")
    assert len(changes) == 2
    again, more = _mod().transform(new)
    assert again == new and more == []


def test_a_caddyfile_without_the_site_is_refused():
    with pytest.raises(ValueError):
        _mod().transform("{\n  admin off\n}\n:9999 {\n  respond ok\n}\n")


def test_without_apply_nothing_is_written(tmp_path, capsys):
    f = tmp_path / "Caddyfile"
    f.write_text(CURRENT)
    assert _mod().main(["--caddyfile", str(f)]) == 0
    assert f.read_text() == CURRENT and "would change" in capsys.readouterr().out
    assert not list(tmp_path.glob("Caddyfile.bak.*"))


def test_the_run_button_script_is_valid_and_ordered():
    script = ROOT / "scripts" / "friends_access_go_live.sh"
    assert subprocess.run(["bash", "-n", str(script)], capture_output=True, check=False).returncode == 0
    text = script.read_text()
    steps = [text.index(f'say "{n}/6') for n in range(1, 7)]
    assert steps == sorted(steps)
    assert "git merge --ff-only feat/friends-access" in text and "set -euo pipefail" in text
    assert "friends_access_caddy.py --caddyfile" in text and "--apply" in text
    assert 'echo "$secret' not in text and "token_urlsafe(48)" in text                  # generated inline, never echoed
    assert "bounce_fleet.sh" in text and "set-owner-password" in text


def test_the_live_check_compiles_and_imports_without_network():
    path = ROOT / "docs" / "wiki" / "experiments" / "friends-access-2026-09-26" / "live_check.py"
    py_compile.compile(str(path), doraise=True)
    spec = importlib.util.spec_from_file_location("friends_live_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.code('{"detail": {"error_code": "LOGIN_REQUIRED"}}') == "LOGIN_REQUIRED" and mod.code("oops") is None
