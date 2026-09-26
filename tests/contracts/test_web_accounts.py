"""Web accounts (FRIENDS-ACCESS-V1 F1): logins live in the principal registry Server A already reads; passwords are scrypt
hashes, never stored or printed raw; sessions are signed cookies whose version dies on a password change, reset or disable;
guesses are throttled; a friend holds at most 3 active keys, each authenticated by Server A's own store."""
import importlib.util
import json
import pathlib
import stat
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))

import pytest

from orchestrator import mcp_principals as P
from orchestrator import web_accounts as W

SECRET = b"s" * 40
GOOD = "correct horse battery"


def _cli():
    spec = importlib.util.spec_from_file_location("web_accounts_cli", ROOT / "scripts" / "web_accounts.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _reg(tmp_path):
    return tmp_path / "state" / "principals.json"


def test_the_module_under_test_is_this_checkout():
    assert pathlib.Path(W.__file__).is_relative_to(ROOT)


def test_passwords_are_salted_scrypt_and_verify_in_constant_time():
    a, b = W.hash_password(GOOD), W.hash_password(GOOD)
    assert a != b and a.startswith("scrypt$") and GOOD not in a
    assert W.verify_password(GOOD, a) and not W.verify_password(GOOD + "x", a)
    assert not W.verify_password(GOOD, "not-a-hash") and not W.verify_password(GOOD, None)


@pytest.mark.parametrize("pw", ["short", "aaaaaaaaaaaa", "123123123123"])
def test_weak_passwords_are_refused(tmp_path, pw):
    with pytest.raises(W.AccountError) as err:
        W.set_owner_password(_reg(tmp_path), pw)
    assert err.value.code == "WEAK_PASSWORD"


def test_owner_login_is_case_insensitive_and_wrong_passwords_fail(tmp_path):
    reg = _reg(tmp_path)
    W.set_owner_password(reg, GOOD)
    doc = W.read_registry(reg)
    who = W.authenticate_password(doc, "King", GOOD)
    assert who and who.is_owner and who.principal_id == P.OWNER_ID and who.display_name == "King"
    assert W.authenticate_password(doc, "king", "wrong password!") is None
    assert GOOD not in reg.read_text() and stat.S_IMODE(reg.stat().st_mode) == 0o600


def test_a_friend_is_a_principal_server_a_can_load_with_everything_but_admin(tmp_path):
    reg = _reg(tmp_path)
    rec = W.add_friend(reg, "Fred", GOOD, display_name="Fred", corpus_ids=["cinema"], adapter_ids=["ecommerce.product_research"])
    assert rec["username"] == "fred" and rec["corpus_ids"] == ["cinema", "fr-fred"] and rec["writable_corpus_ids"] == ["fr-fred"]
    assert "password_hash" not in json.dumps(rec) and rec["must_change_password"] is True
    store = P.PrincipalStore(path=reg)
    store._load()
    assert store.last_error is None and len(store._records) == 1
    p = P.principal_from_record(store._records[0])
    assert P.ADMIN not in p.scopes and {P.UPLOAD_TEXT, P.HISTORY_READ, P.KNOWLEDGE_ANSWER, P.ADAPTER_START} <= p.scopes
    assert P.authorize(p, "upload_text", {"corpus_id": "fr-fred"}).allowed
    assert not P.authorize(p, "upload_text", {"corpus_id": "cinema"}).allowed
    assert not P.authorize(p, "upload_document", {"corpus_id": "fr-fred", "path": "/etc/passwd"}).allowed
    who = W.authenticate_password(W.read_registry(reg), "fred", GOOD)
    assert who and not who.is_owner and who.must_change_password
    with pytest.raises(W.AccountError):
        W.add_friend(reg, "fred", GOOD)
    with pytest.raises(W.AccountError):
        W.add_friend(reg, "king", GOOD)


def test_sessions_are_signed_expire_and_die_when_the_version_moves(tmp_path):
    reg = _reg(tmp_path)
    W.add_friend(reg, "fred", GOOD)
    doc = W.read_registry(reg)
    who = W.authenticate_password(doc, "fred", GOOD)
    cookie, csrf = W.make_session(SECRET, who, now=1000.0, ttl_s=60)
    payload = W.read_session(SECRET, cookie, now=1010.0)
    assert payload and W.resolve_session(doc, payload) == who and W.csrf_ok(payload, csrf) and not W.csrf_ok(payload, "x")
    assert W.read_session(SECRET, cookie, now=1061.0) is None                       # expired
    assert W.read_session(b"t" * 40, cookie, now=1010.0) is None                    # another secret
    body, sig = cookie.split(".")
    assert W.read_session(SECRET, body + "x." + sig, now=1010.0) is None            # tampered
    W.set_friend_enabled(reg, "fred", False)
    assert W.resolve_session(W.read_registry(reg), payload) is None                 # disabled: the version moved
    W.set_friend_enabled(reg, "fred", True)
    assert W.resolve_session(W.read_registry(reg), payload) is None                 # an old cookie stays dead


def test_changing_a_password_needs_the_old_one_and_kills_old_sessions(tmp_path):
    reg = _reg(tmp_path)
    W.add_friend(reg, "fred", GOOD)
    who = W.authenticate_password(W.read_registry(reg), "fred", GOOD)
    payload = W.read_session(SECRET, W.make_session(SECRET, who)[0])
    with pytest.raises(W.AccountError):
        W.change_password(reg, who.principal_id, "not the password", "brand new passphrase")
    W.change_password(reg, who.principal_id, GOOD, "brand new passphrase")
    doc = W.read_registry(reg)
    assert W.resolve_session(doc, payload) is None
    again = W.authenticate_password(doc, "fred", "brand new passphrase")
    assert again and not again.must_change_password and W.authenticate_password(doc, "fred", GOOD) is None


def test_the_throttle_stops_guessing_per_username_and_per_address():
    t = W.LoginThrottle(limit=5, window_s=900)
    keys = ["user:fred", "addr:203.0.113.9"]
    for i in range(5):
        assert t.allowed(keys, now=100.0 + i)
        t.failed(keys, now=100.0 + i)
    assert not t.allowed(keys, now=110.0) and not t.allowed(["addr:203.0.113.9"], now=110.0)
    assert t.allowed(keys, now=100.0 + 901 + 5)                                     # the window passed
    t.failed(keys, now=2000.0)
    t.succeeded(["user:fred"])
    assert t.allowed(["user:fred"], now=2001.0)


def test_a_friend_holds_at_most_three_active_keys_and_server_a_accepts_them(tmp_path):
    reg = _reg(tmp_path)
    W.add_friend(reg, "fred", GOOD)
    pid = W.principal_id_for("fred")
    raws = [W.create_key(reg, pid, label=f"agent {i}")[0] for i in range(3)]
    with pytest.raises(W.AccountError) as err:
        W.create_key(reg, pid)
    assert err.value.code == "KEY_LIMIT"
    text = reg.read_text()
    assert all(r not in text for r in raws)
    store = P.PrincipalStore(path=reg)
    assert store.authenticate(raws[0]).principal_id == pid
    first = W.list_keys(W.read_registry(reg), pid)[0]
    W.revoke_key(reg, pid, first["key_id"])
    assert P.PrincipalStore(path=reg).authenticate(raws[0]) is None
    assert W.create_key(reg, pid)[1]["key_id"]                                        # a slot is free again


def test_the_cli_writes_a_first_password_to_a_new_owner_only_file_and_prints_none(tmp_path, capsys):
    cli, reg, out = _cli(), _reg(tmp_path), tmp_path / "keys" / "fred.password"
    assert cli.main(["--file", str(reg), "add-friend", "--username", "fred", "--corpus", "cinema", "--password-out", str(out)]) == 0
    printed = capsys.readouterr().out
    pw = out.read_text().strip()
    assert pw and pw not in printed and pw not in reg.read_text() and stat.S_IMODE(out.stat().st_mode) == 0o600
    assert W.authenticate_password(W.read_registry(reg), "fred", pw)
    with pytest.raises(FileExistsError):
        cli.main(["--file", str(reg), "reset-password", "--username", "fred", "--password-out", str(out)])
    with pytest.raises(SystemExit):
        cli.main(["--file", str(reg), "add-friend", "--username", "ann"])            # neither --password-out nor --print-password
    listing = json.loads((cli.main(["--file", str(reg), "list"]), capsys.readouterr().out)[1])
    assert listing["owner_login"] == "NOT SET" and listing["friends"][0]["username"] == "fred"
    assert "password_hash" not in json.dumps(listing)
