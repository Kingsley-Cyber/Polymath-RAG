import { useCallback, useEffect, useState } from "react";

/** LLM-PROVIDER-LAYER-V1: configure any API provider through LiteLLM.
 * A provider row holds credentials + model strings (openai/gpt-4o,
 * anthropic/claude-sonnet-4-5, gemini/gemini-2.5-flash, groq/llama-3.3,
 * ollama/qwen3, ...). Configured models appear in the synthesizer
 * dropdown; keys never round-trip to the browser (masked, last 4). */

interface ProviderRow {
  provider_id: string;
  provider: string;
  api_key: string;
  api_key_set: boolean;
  api_base: string;
  models: string[];
  enabled: boolean;
}

const PRESETS: Record<string, { hint: string; base?: string; examples: string[] }> = {
  openai: { hint: "sk-…", examples: ["openai/gpt-5.2", "openai/gpt-5.2-mini"] },
  anthropic: { hint: "sk-ant-…", examples: ["anthropic/claude-sonnet-4-5", "anthropic/claude-haiku-4-5"] },
  gemini: { hint: "AIza…", examples: ["gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash"] },
  groq: { hint: "gsk_…", examples: ["groq/llama-3.3-70b-versatile"] },
  mistral: { hint: "…", examples: ["mistral/mistral-large-latest"] },
  deepseek: { hint: "…", examples: ["deepseek/deepseek-chat"] },
  openrouter: { hint: "sk-or-…", examples: ["openrouter/anthropic/claude-sonnet-4.5"] },
  ollama: { hint: "(no key needed)", examples: ["ollama/qwen3", "ollama/deepseek-v4-flash:cloud"] },
  custom: { hint: "key (optional)", base: "http://host:port/v1", examples: ["openai/<model-name> + api_base"] },
};

export default function ModelsView({ onChanged }: { onChanged?: () => void }) {
  const [rows, setRows] = useState<ProviderRow[]>([]);
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [models, setModels] = useState("");
  const [msg, setMsg] = useState("");
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    try {
      const r = await fetch("/llm/providers");
      setRows((await r.json()).providers ?? []);
    } catch {
      setRows([]);
    }
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);

  const save = async () => {
    const body = {
      provider,
      api_key: apiKey,
      api_base: apiBase,
      models: models.split("\n").map((m) => m.trim()).filter(Boolean),
    };
    const r = await fetch("/llm/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    setMsg(r.ok ? `saved ${provider}` : `save failed: ${r.status}`);
    setApiKey("");
    await refresh();
    onChanged?.();
  };

  const test = async (model: string) => {
    setTesting(model);
    try {
      const r = await fetch("/llm/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      });
      const out = await r.json();
      setTestResults((t) => ({
        ...t,
        [model]: out.ok ? `✓ ${out.reply || "ok"}` : `✗ ${out.error}`,
      }));
    } catch (e: any) {
      setTestResults((t) => ({ ...t, [model]: `✗ ${String(e)}` }));
    }
    setTesting(null);
  };

  const remove = async (pid: string) => {
    if (window.prompt(`Type the provider id to remove it:\n${pid}`) !== pid)
      return;
    await fetch(`/llm/providers/${encodeURIComponent(pid)}`, {
      method: "DELETE",
    });
    await refresh();
    onChanged?.();
  };

  const preset = PRESETS[provider] ?? PRESETS.custom;

  return (
    <div className="files">
      <div className="files-inner">
        <div className="panel">
          <h3>Add / update provider</h3>
          <div className="readiness" style={{ marginBottom: 10 }}>
            Any provider LiteLLM supports. Model strings are
            provider-prefixed (e.g. <span className="mono">openai/gpt-5.2</span>,{" "}
            <span className="mono">anthropic/claude-sonnet-4-5</span>,{" "}
            <span className="mono">ollama/qwen3</span>). Configured models
            appear in the chat model dropdown.
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, maxWidth: 520 }}>
            <div className="control">
              <label>Provider</label>
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                {Object.keys(PRESETS).map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div className="control">
              <label>API key ({preset.hint}; blank keeps stored key)</label>
              <input type="password" value={apiKey} placeholder={preset.hint}
                     onChange={(e) => setApiKey(e.target.value)}
                     style={{ background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 8px" }} />
            </div>
            <div className="control">
              <label>API base (optional; for custom/self-hosted)</label>
              <input value={apiBase} placeholder={preset.base ?? ""}
                     onChange={(e) => setApiBase(e.target.value)}
                     style={{ background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 8px" }} />
            </div>
            <div className="control">
              <label>Models (one per line)</label>
              <textarea rows={3} value={models} placeholder={preset.examples.join("\n")}
                        onChange={(e) => setModels(e.target.value)}
                        style={{ background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 8px", fontFamily: "ui-monospace, monospace", fontSize: 12 }} />
            </div>
            <div>
              <button className="send" onClick={save}>Save provider</button>
              {msg && <span className="mono" style={{ marginLeft: 10 }}>{msg}</span>}
            </div>
          </div>
        </div>

        <div className="panel">
          <h3>Configured providers ({rows.length})</h3>
          {rows.length === 0 && (
            <div className="readiness">None yet. Ollama models on this
              machine also appear in the dropdown automatically without
              configuration.</div>
          )}
          {rows.map((r) => (
            <div key={r.provider_id} className="chunks-panel" style={{ marginBottom: 8 }}>
              <div className="chunk-row">
                <b>{r.provider}</b>{" "}
                <span className="mono">
                  key {r.api_key_set ? `…${r.api_key}` : "none"}
                  {r.api_base ? ` · base ${r.api_base}` : ""}
                </span>{" "}
                <button className="chunk-chip" onClick={() => remove(r.provider_id)}>✕ remove</button>
              </div>
              {r.models.map((m) => (
                <div key={m} className="chunk-row" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span className="chunk-loc">{m}</span>
                  <button className="chunk-chip" disabled={testing === m}
                          onClick={() => test(m)}>
                    {testing === m ? "testing…" : "test"}
                  </button>
                  {testResults[m] && (
                    <span className="phase-detail">{testResults[m]}</span>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
