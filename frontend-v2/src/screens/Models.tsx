import { useState } from "react";
import { api, ApiError } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { StatePill } from "../components/Pill";
import type { LlmProvider, LlmTestResult } from "../lib/contracts";

/**
 * F1 — Models (parity with the legacy `/ui` Models screen).
 *
 * Manage the LiteLLM providers the chat synthesizer can use: list them, add or update
 * one (provider + endpoint + key + model list), test a model's connectivity, remove one.
 * The backend NEVER returns a raw key — a row shows only the last 4 chars, or the env
 * var NAME (`env:NAME`) — and an empty key on save keeps the stored one, so editing a
 * provider does not force re-entering its secret. Keys are entered by the operator here;
 * the UI never displays or transmits them back.
 */
function keyLabel(p: LlmProvider): string {
  if (p.api_key.startsWith("env:")) return `${p.api_key} (${p.api_key_set ? "set" : "UNSET"})`;
  if (p.api_key_set) return `…${p.api_key}`;
  return "no key";
}

export function Models() {
  const [nonce, setNonce] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tests, setTests] = useState<Record<string, LlmTestResult>>({});

  // add/edit form
  const [provider, setProvider] = useState("");
  const [apiBase, setApiBase] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [models, setModels] = useState("");
  const [enabled, setEnabled] = useState(true);

  const providers = useAsync((s) => api.llmProviders(s), [nonce]);
  const rows = providers.data ?? [];
  const refresh = () => setNonce((n) => n + 1);

  function describeError(e: unknown): string {
    if (e instanceof ApiError) {
      try {
        const body = JSON.parse(e.message.slice(e.message.indexOf("{")));
        if (body?.message) return `${body.error_code ?? "error"}: ${body.message}`;
      } catch { /* not JSON */ }
      return e.message;
    }
    return e instanceof Error ? e.message : String(e);
  }

  function editRow(p: LlmProvider) {
    setProvider(p.provider);
    setApiBase(p.api_base);
    setApiKey("");                       // never prefill a secret; blank keeps the stored key
    setModels(p.models.join(", "));
    setEnabled(p.enabled);
    setNotice(`Editing "${p.provider}". Leave the key blank to keep the stored one.`);
    setErr(null);
  }

  function resetForm() {
    setProvider(""); setApiBase(""); setApiKey(""); setModels(""); setEnabled(true);
  }

  async function onSave() {
    if (!provider.trim()) { setErr("Provider is required."); return; }
    setBusy(`Saving ${provider.trim()}…`); setErr(null); setNotice(null);
    try {
      const out = await api.saveProvider({
        provider: provider.trim(),
        api_key: apiKey,                 // "" keeps the stored key on an existing provider
        api_base: apiBase.trim(),
        models: models.split(",").map((m) => m.trim()).filter(Boolean),
        enabled,
      });
      setNotice(`Saved provider "${out.saved}".`);
      resetForm();
    } catch (e) {
      setErr(describeError(e));
    } finally {
      setBusy(null);
      refresh();
    }
  }

  async function onDelete(p: LlmProvider) {
    if (!window.confirm(`Delete provider "${p.provider}"?\n\nThis removes its configuration (endpoint, key reference, model list). Chats using its models will fall back to another provider.`)) return;
    setBusy(`Deleting ${p.provider}…`); setErr(null); setNotice(null);
    try {
      await api.deleteProvider(p.provider_id);
      setNotice(`Deleted "${p.provider}".`);
    } catch (e) {
      setErr(describeError(e));
    } finally {
      setBusy(null);
      refresh();
    }
  }

  async function onTest(p: LlmProvider) {
    const model = p.models[0];
    if (!model) { setErr(`"${p.provider}" has no model to test.`); return; }
    setBusy(`Testing ${model}…`); setErr(null);
    try {
      const res = await api.testModel(model);
      setTests((t) => ({ ...t, [p.provider_id]: res }));
    } catch (e) {
      setTests((t) => ({ ...t, [p.provider_id]: { ok: false, model, error: describeError(e) } }));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Models</h1>
        <p className="screen__sub">
          LLM providers the chat synthesizer can use — <b>{rows.length}</b> configured,{" "}
          <b>{rows.filter((r) => r.ready).length}</b> ready. Keys are stored server-side and
          never shown back.
        </p>
      </div>

      {busy && <div className="banner" style={{ marginBottom: 12 }}>{busy}</div>}
      {notice && <div className="banner banner--ok" style={{ marginBottom: 12 }}>{notice}</div>}
      {err && <div className="banner banner--bad" style={{ marginBottom: 12 }}>{err}</div>}
      {providers.error && <div className="banner banner--bad" style={{ marginBottom: 12 }}>{providers.error}</div>}

      <div className="card" style={{ overflowX: "auto" }}>
        <table className="t">
          <thead>
            <tr>
              <th>Provider</th><th>Endpoint</th><th>Models</th><th>Key</th>
              <th>Enabled</th><th>Ready</th><th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const test = tests[p.provider_id];
              return (
                <tr key={p.provider_id}>
                  <td><div className="files__name">{p.provider}</div>
                    <div className="files__docid mono">{p.provider_id}</div></td>
                  <td className="mono" title={p.api_base}>{p.api_base || "—"}</td>
                  <td>
                    <div className="models__chips">
                      {p.models.length
                        ? p.models.map((m) => <span key={m} className="pill" title={m}>{m}</span>)
                        : <span className="faint">none</span>}
                    </div>
                    {test && (
                      <div className={`models__test ${test.ok ? "ok" : "bad"}`}>
                        {test.ok ? `✓ ${test.reply || "ok"}` : `✕ ${test.error || "failed"}`}
                      </div>
                    )}
                  </td>
                  <td className="mono">{keyLabel(p)}</td>
                  <td>{p.enabled
                    ? <span className="pill pill--ready">on</span>
                    : <span className="pill pill--blocked">off</span>}</td>
                  <td>{p.ready
                    ? <StatePill state="ready" label="READY" />
                    : <StatePill state="degraded" label="NOT READY" />}</td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      <button className="btn" disabled={!!busy || !p.models.length}
                              onClick={() => void onTest(p)}>Test</button>
                      <button className="btn" disabled={!!busy}
                              onClick={() => editRow(p)}>Edit</button>
                      <button className="btn files__del" disabled={!!busy}
                              onClick={() => void onDelete(p)}>Delete</button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!rows.length && !providers.loading && (
          <div className="empty">No providers configured — add one below.</div>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2 className="models__form-title">Add / update a provider</h2>
        <div className="models__form">
          <label className="field">
            <span className="label">Provider</span>
            <input type="text" value={provider} placeholder="openai · anthropic · groq · …"
                   onChange={(e) => setProvider(e.target.value)} />
          </label>
          <label className="field">
            <span className="label">Endpoint (api_base, optional)</span>
            <input type="text" value={apiBase} placeholder="https://api.example.com/v1"
                   onChange={(e) => setApiBase(e.target.value)} />
          </label>
          <label className="field">
            <span className="label">API key</span>
            <input type="password" value={apiKey} autoComplete="off"
                   placeholder="blank keeps the stored key · or env:VAR_NAME"
                   onChange={(e) => setApiKey(e.target.value)} />
          </label>
          <label className="field models__models">
            <span className="label">Models (comma-separated)</span>
            <input type="text" value={models} placeholder="openai/gpt-4o, openai/gpt-4o-mini"
                   onChange={(e) => setModels(e.target.value)} />
          </label>
          <label className="field models__enabled">
            <span className="label">Enabled</span>
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          </label>
          <div className="models__form-actions">
            <button className="btn btn--primary" disabled={!!busy || !provider.trim()}
                    onClick={() => void onSave()}>Save provider</button>
            <button className="btn" disabled={!!busy} onClick={resetForm}>Clear</button>
          </div>
        </div>
        <div className="faint" style={{ marginTop: 8, fontSize: 12 }}>
          The key is written to the server and never returned to the browser. Use{" "}
          <span className="mono">env:VAR_NAME</span> to reference a key from the server's
          environment instead of storing a literal.
        </div>
      </div>
    </div>
  );
}
