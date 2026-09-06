#!/usr/bin/env python3
"""CHAT-MODEL-CATALOG-V1 setup (owner decision 2026-09-06): the chat model dropdown offers OpenCode Zen's FREE models
and Ollama's FREE cloud tier, nothing else.

  --opencode-free   upsert the `opencode-free` provider row (LiteLLM provider `openai`, api_base https://opencode.ai/zen/v1,
                    api_key `env:OPENCODE_API_KEY`) with the models in config/chat_models/opencode_free.json; the key itself
                    is read from .env at call time and never stored. `--refresh` re-fetches the zero-cost list from
                    models.dev into that config file first.
  --reconcile       OPENCODE-RECONCILE-V1 (measured 2026-09-06: models.dev listed 31 zero-cost ids, the endpoint served 8 of
                    them — the rest answered "Model glm-5-free is not supported"): GET <api_base>/models with the key from .env
                    and keep only the free ids the endpoint lists; unserved ids are recorded in the config (`unserved`), never
                    offered. Runs with --opencode-free automatically when the key is set.
  --alibaba         upsert the `alibaba-model-studio` row (Bailian token plan, ap-southeast-1, Anthropic-messages app; api_key
                    `env:ALIBABA_MODEL_STUDIO_API_KEY`) with the nine models in config/chat_models/alibaba_model_studio.json.
  --ollama-free     disable any LiteLLM provider row that routes to the Ollama daemon (paid cloud models), then
                    `ollama pull` each free cloud model the UI allowlists (a cloud pull registers a name; no weights).
  --show            print the catalog the UI will offer (GET /synthesizers on the orchestrator when it is up).

Run on a new machine after the stores are up:  .venv/bin/python scripts/chat_models_setup.py --opencode-free --ollama-free --show
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "chat_models" / "opencode_free.json"
ALIBABA = ROOT / "config" / "chat_models" / "alibaba_model_studio.json"
MODELS_DEV = "https://models.dev/api.json"


def free_models_from_models_dev(catalog: dict) -> tuple[dict, list[str]]:
    """(provider record, sorted zero-cost model ids) for the `opencode` provider of a models.dev catalog."""
    p = catalog["opencode"]
    free = sorted(mid for mid, m in p["models"].items()
                  if float((m.get("cost") or {}).get("input") or 0) == 0 and float((m.get("cost") or {}).get("output") or 0) == 0)
    return p, free


def refresh_config() -> dict:
    import datetime as dt
    with urllib.request.urlopen(MODELS_DEV, timeout=30) as r:
        catalog = json.load(r)
    p, free = free_models_from_models_dev(catalog)
    out = {"contract": "CHAT-MODEL-CATALOG-V1", "provider_id": "opencode-free", "litellm_provider": "openai",
           "api_base": p["api"], "api_key_env": p["env"][0],
           "source": f"{MODELS_DEV} (provider opencode, cost.input == 0 and cost.output == 0)",
           "fetched": dt.date.today().isoformat(), "models": ["openai/" + m for m in free],
           "names": {"openai/" + m: p["models"][m].get("name") for m in free}}
    CONFIG.write_text(json.dumps(out, indent=1) + "\n")
    return out


def served_model_ids(api_base: str, api_key: str, timeout: float = 30) -> set[str]:
    """The model ids the OpenAI-format endpoint lists at GET /models (the key is used, never printed). A browser-like
    User-Agent: the Cloudflare edge in front of opencode.ai answers Python's default UA with 403 / error 1010."""
    req = urllib.request.Request(f"{api_base.rstrip('/')}/models", headers={
        "authorization": f"Bearer {api_key}", "accept": "application/json",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    rows = data.get("data") if isinstance(data, dict) else data
    return {str(row.get("id")) for row in (rows or []) if row.get("id")}


def reconcile_with_endpoint(cfg: dict, served: set[str]) -> dict:
    """Keep only the snapshot's free ids the endpoint serves; the rest move to `unserved` (pure: no I/O)."""
    prefix = cfg["litellm_provider"] + "/"
    keep = [m for m in cfg["models"] if m.split("/", 1)[-1] in served]
    drop = [m for m in cfg["models"] if m.split("/", 1)[-1] not in served]
    out = dict(cfg)
    out["models"] = keep
    out["names"] = {m: cfg.get("names", {}).get(m) for m in keep}
    out["unserved"] = drop
    out["served_total"] = len(served)
    out["prefix"] = prefix
    return out


def upsert_provider(cfg: dict) -> str:
    """Upsert one provider row from a config snapshot (api_key stored as `env:<api_key_env>` — the value stays in .env)."""
    import psycopg
    dsn = os.environ.get("POLYMATH_PG_DSN") or os.environ.get("POLYMATH_TEST_DSN")
    if not dsn:
        sys.exit("POLYMATH_PG_DSN not set — source .env")
    with psycopg.connect(dsn) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS llm_providers (
                 provider_id text PRIMARY KEY, provider text NOT NULL, api_key text NOT NULL DEFAULT '',
                 api_base text NOT NULL DEFAULT '', models jsonb NOT NULL DEFAULT '[]',
                 enabled boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now())""")
        conn.execute("""INSERT INTO llm_providers (provider_id, provider, api_key, api_base, models, enabled)
                        VALUES (%s, %s, %s, %s, %s, true)
                        ON CONFLICT (provider_id) DO UPDATE SET provider=EXCLUDED.provider, api_key=EXCLUDED.api_key,
                          api_base=EXCLUDED.api_base, models=EXCLUDED.models, enabled=true""",
                     (cfg["provider_id"], cfg["litellm_provider"], f"env:{cfg['api_key_env']}", cfg["api_base"], json.dumps(cfg["models"])))
        conn.commit()
    return cfg["provider_id"]


def disable_litellm_ollama_rows() -> list[str]:
    """The owner's rule: Ollama is offered ONLY through the free-tier allowlist. Any LiteLLM provider row that routes to
    the Ollama daemon (`provider = 'ollama'`, e.g. the paid kimi / deepseek cloud models) is disabled — not deleted, so the
    Models view can re-enable it deliberately."""
    import psycopg
    dsn = os.environ.get("POLYMATH_PG_DSN") or os.environ.get("POLYMATH_TEST_DSN")
    if not dsn:
        sys.exit("POLYMATH_PG_DSN not set — source .env")
    with psycopg.connect(dsn) as conn:
        rows = conn.execute("UPDATE llm_providers SET enabled=false WHERE lower(provider)='ollama' AND enabled RETURNING provider_id").fetchall()
        conn.commit()
    return [r[0] for r in rows]


def pull_ollama_free() -> list[tuple[str, str]]:
    sys.path.insert(0, str(ROOT / "orchestrator"))
    from orchestrator.api.ui import OLLAMA_FREE_CLOUD_MODELS  # the UI's allowlist is the single source of truth
    out = []
    for name in OLLAMA_FREE_CLOUD_MODELS:
        r = subprocess.run(["ollama", "pull", name], capture_output=True, text=True)
        out.append((name, "ok" if r.returncode == 0 else (r.stderr or r.stdout).strip()[-120:]))
    return out


def show() -> None:
    url = os.environ.get("POLYMATH_ORCH_URL", "http://127.0.0.1:7200").rstrip("/") + "/synthesizers"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            entries = json.load(r)["synthesizers"]
    except Exception as exc:  # noqa: BLE001
        print(f"orchestrator not reachable at {url}: {type(exc).__name__}"); return
    print(f"{len(entries)} chat models offered (first = default for new chats):")
    for e in entries:
        print(f"  {'*' if e.get('default') else ' '} {e['id']:44s} {e['label']}{'' if e.get('available', True) else '   [NOT AVAILABLE: ' + e['description'] + ']'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--opencode-free", action="store_true")
    ap.add_argument("--refresh", action="store_true", help="re-fetch the free list from models.dev into the config first")
    ap.add_argument("--reconcile", action="store_true", help="OPENCODE-RECONCILE-V1: keep only the free ids the endpoint's /models lists (needs the key in .env)")
    ap.add_argument("--alibaba", action="store_true", help="upsert the Alibaba Model Studio row (Bailian token plan, ap-southeast-1, Anthropic-messages app) from config/chat_models/alibaba_model_studio.json")
    ap.add_argument("--ollama-free", action="store_true")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.refresh:
        cfg = refresh_config(); print(f"config refreshed: {len(cfg['models'])} free models ({cfg['fetched']})")
    if a.opencode_free or a.reconcile:
        cfg = json.loads(CONFIG.read_text())
        key = os.environ.get(cfg["api_key_env"], "")
        if key and (a.reconcile or a.opencode_free):
            import datetime as dt
            try:
                served = served_model_ids(cfg["api_base"], key)
            except Exception as exc:  # noqa: BLE001 — the endpoint's listing is advisory; the snapshot stays
                print(f"reconcile skipped: {type(exc).__name__}: {str(exc)[:120]}")
            else:
                full = json.loads(CONFIG.read_text())
                base_models = full.get("models_snapshot") or full["models"]
                full["models_snapshot"] = base_models
                full["names_snapshot"] = full.get("names_snapshot") or full.get("names", {})
                rec = reconcile_with_endpoint({**full, "models": base_models, "names": full["names_snapshot"]}, served)
                full.update({"models": rec["models"], "names": rec["names"], "unserved": rec["unserved"],
                             "served_total": rec["served_total"], "reconciled": dt.date.today().isoformat()})
                CONFIG.write_text(json.dumps(full, indent=1) + "\n")
                cfg = full
                print(f"reconciled with {cfg['api_base']}/models: {len(cfg['models'])} free ids served of {len(base_models)} in the snapshot "
                      f"({len(cfg['unserved'])} unserved kept out of the row; endpoint lists {cfg['served_total']} models in total)")
        elif a.reconcile:
            print(f"reconcile skipped: {cfg['api_key_env']} not set")
    if a.opencode_free:
        pid = upsert_provider(cfg)
        print(f"provider row `{pid}` upserted: {len(cfg['models'])} models, api_base {cfg['api_base']}, key env:{cfg['api_key_env']} "
              f"({'set' if os.environ.get(cfg['api_key_env']) else 'NOT SET — add it to .env; the models stay hidden until then'})")
    if a.alibaba:
        cfg = json.loads(ALIBABA.read_text())
        pid = upsert_provider(cfg)
        print(f"provider row `{pid}` upserted: {len(cfg['models'])} models, api_base {cfg['api_base']}, key env:{cfg['api_key_env']} "
              f"({'set' if os.environ.get(cfg['api_key_env']) else 'NOT SET — add it to .env; the models stay hidden until then'})")
    if a.ollama_free:
        for pid in disable_litellm_ollama_rows():
            print(f"  disabled LiteLLM provider row `{pid}` (Ollama is offered only through the free-tier allowlist)")
        for name, status in pull_ollama_free():
            print(f"  ollama pull {name:28s} {status}")
    if a.show:
        show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
