"""ENV-OVERLAY-ON-SPAWN-V1: every spawn carries the CURRENT .env, so a
rotated key never needs a full fleet restart (2026-09-02: openrouter
lanes 401'd on a replaced key because children inherited the boot
snapshot)."""
from control.process_supervisor import _dotenv_overlay


def test_overlay_parses_env_lines(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        "# comment\n"
        "OPENROUTER_API_KEY=sk-new\n"
        "export GROQ_API_KEY_1='quoted'\n"
        "SPACED = value with spaces \n"
        "NOEQUALS\n"
        "\n"
        "EMPTY=\n")
    got = _dotenv_overlay(f)
    assert got["OPENROUTER_API_KEY"] == "sk-new"
    assert got["GROQ_API_KEY_1"] == "quoted"
    assert got["SPACED"] == "value with spaces"
    assert got["EMPTY"] == ""
    assert "NOEQUALS" not in got and "# comment" not in got


def test_overlay_missing_file_is_empty(tmp_path):
    assert _dotenv_overlay(tmp_path / "nope.env") == {}


def test_spawn_reads_overlay_from_repo_env():
    """The spawn path must call the overlay on the repo's .env — pin the
    wiring, not just the parser."""
    import inspect
    from control import process_supervisor as ps
    src = inspect.getsource(ps.Supervisor._spawn)
    assert "_dotenv_overlay(" in src and '".env"' in src
