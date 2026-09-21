"""The principal registry and its CLI (owner decision 2026-09-21): a file outside the repository, owner-only, written
atomically, holding key ids and digests — never a raw bearer; the bearer is written ONCE to `--key-out` and not printed."""
import importlib.util
import json
import pathlib
import stat
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "orchestrator"))

import pytest

from orchestrator import mcp_principals as P


def _cli():
    spec = importlib.util.spec_from_file_location("mcp_principals_cli", ROOT / "scripts" / "mcp_principals.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_add_writes_an_owner_only_registry_and_key_file_and_prints_no_secret(tmp_path, capsys):
    assert pathlib.Path(P.__file__).is_relative_to(ROOT)
    cli, reg, key_out = _cli(), tmp_path / "state" / "principals.json", tmp_path / "keys" / "fred.key"
    assert cli.main(["--file", str(reg), "add", "--id", "prn_fred", "--name", "Fred", "--corpus", "commerce-v1",
                     "--adapter", "ecommerce.product_research", "--rate", "60", "--key-out", str(key_out)]) == 0
    printed = capsys.readouterr().out
    raw = key_out.read_text().strip()
    assert P.BEARER_RE.match(raw) and raw not in printed and raw not in reg.read_text()
    assert _mode(reg) == 0o600 and _mode(key_out) == 0o600
    rec = json.loads(reg.read_text())["principals"][0]
    assert rec["scopes"] == sorted(P.FRIEND_PROFILE) and rec["writable_corpus_ids"] == [] and rec["rate_per_minute"] == 60
    assert rec["keys"][0]["secret_sha256"] == P.hash_key(raw) and set(rec["keys"][0]) == {"key_id", "secret_sha256", "created_at", "revoked_at"}
    who = P.PrincipalStore(path=reg).authenticate(raw)
    assert who.principal_id == "prn_fred" and not who.is_admin and who.corpus_ids == {"commerce-v1"}
    assert not list(reg.parent.glob(".*tmp"))                                     # the atomic write left nothing behind
    with pytest.raises(FileExistsError):                                          # a key file is never overwritten
        cli.main(["--file", str(reg), "rotate", "--id", "prn_fred", "--key-out", str(key_out)])


def test_a_bearer_is_never_shown_by_default_and_admin_is_never_grantable(tmp_path):
    cli, reg = _cli(), tmp_path / "principals.json"
    with pytest.raises(SystemExit, match="never shown by default"):
        cli.main(["--file", str(reg), "add", "--id", "prn_gina", "--corpus", "c"])
    assert not reg.exists()
    with pytest.raises(SystemExit):                                               # argparse: admin is not a choice
        cli.main(["--file", str(reg), "add", "--id", "prn_gina", "--scope", "admin", "--key-out", str(tmp_path / "g.key")])
    with pytest.raises(SystemExit, match="writable-corpus"):
        cli.main(["--file", str(reg), "add", "--id", "prn_gina", "--scope", "upload.text", "--key-out", str(tmp_path / "g.key")])
    with pytest.raises(ValueError, match="admin scope"):
        P.principal_from_record({"principal_id": "prn_gina", "scopes": ["admin"]})
    for bad in ("fred", "prn_Owner", "prn_owner", "prn_a b"):
        with pytest.raises(ValueError):
            P.principal_from_record({"principal_id": bad})


def test_rotate_revoke_disable_take_effect_through_the_store(tmp_path):
    cli, reg = _cli(), tmp_path / "principals.json"
    k1, k2 = tmp_path / "1.key", tmp_path / "2.key"
    cli.main(["--file", str(reg), "add", "--id", "prn_hana", "--corpus", "c", "--key-out", str(k1)])
    store = P.PrincipalStore(path=reg)
    first = k1.read_text().strip()
    assert store.authenticate(first)
    cli.main(["--file", str(reg), "rotate", "--id", "prn_hana", "--revoke-old", "--key-out", str(k2)])
    second = k2.read_text().strip()
    assert store.authenticate(first) is None and store.authenticate(second).principal_id == "prn_hana"
    cli.main(["--file", str(reg), "disable", "--id", "prn_hana"])
    assert store.authenticate(second) is None
    cli.main(["--file", str(reg), "enable", "--id", "prn_hana"])
    assert store.authenticate(second)
    cli.main(["--file", str(reg), "revoke", "--id", "prn_hana"])
    assert store.authenticate(second) is None
    listing = json.dumps(cli.cmd_list(type("A", (), {"file": str(reg)})()))
    assert "secret_sha256" not in listing and "prn_hana" in listing


def test_a_broken_or_tampered_registry_authenticates_nobody(tmp_path):
    reg = tmp_path / "principals.json"
    raw, key = P.new_bearer()
    good = {"principal_id": "prn_ivy", "enabled": True, "scopes": list(P.FRIEND_PROFILE), "keys": [key]}
    for doc in ({"schema": "something.else", "principals": [good]},
                {"schema": P.SCHEMA, "principals": [{**good, "keys": [{**key, "secret": raw}]}]},          # a raw secret in the registry
                {"schema": P.SCHEMA, "principals": [good, {**good}]},                                      # duplicate principal / key id
                {"schema": P.SCHEMA, "principals": [{**good, "scopes": ["knowledge.search", "everything"]}]}):
        reg.write_text(json.dumps(doc))
        reg.chmod(0o600)
        store = P.PrincipalStore(path=reg)
        assert store.authenticate(raw) is None and store.last_error, doc
    reg.write_text(json.dumps({"schema": P.SCHEMA, "principals": [good]}))
    reg.chmod(0o600)
    assert P.PrincipalStore(path=reg).authenticate(raw).principal_id == "prn_ivy"
    assert P.PrincipalStore(path=reg, owner_key="owner").authenticate("owner").is_admin                   # the owner key never depends on the file
    assert P.PrincipalStore(path=None, owner_key="owner").authenticate(raw) is None
