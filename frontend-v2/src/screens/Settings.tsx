import { useState } from "react";
import { useConfirm, type ConfirmOptions } from "../ui/Dialog";
import { ACCENTS, MODES, useAppearance, type Accent, type Mode } from "../lib/appearance";
import { ApiError } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import {
  auth, friends, privateLibrary, type ApiKey, type CreatedKey, type Friend, type Invite, type Me,
} from "../lib/auth";
import { ChangePassword } from "./Login";
import { DeepResearchSettings } from "../components/deep/DeepResearchSettings";
import { Secret } from "../ui/Secret";

function message(err: unknown): string {
  return err instanceof ApiError ? err.detailMessage : String(err);
}


/** FRIENDS-ACCESS-V1 D7/D8 — shown ONCE: the new key and the prompt with it filled in. */
function ShownOnce({ created, onDone }: { created: CreatedKey; onDone: () => void }) {
  return (
    <div className="card stack settings__once">
      <div className="banner banner--info">
        This key is shown only now. Copy it (or the prompt, which contains it) before closing this box.
      </div>
      <div className="field">
        <span className="label">Your new key{created.label ? ` — ${created.label}` : ""}</span>
        <Secret value={created.key} what="key" />
      </div>
      <div className="field">
        <span className="label">Prompt for your agent (key included)</span>
        <Secret value={created.prompt} what="prompt" block rows={12} />
      </div>
      <div className="row"><button className="btn btn--primary" type="button" onClick={onDone}>I've saved it</button></div>
    </div>
  );
}

function MyKeys({ me }: { me: Me }) {
  const [confirm, confirmDialog] = useConfirm();
  const [nonce, setNonce] = useState(0);
  const keys = useAsync((s) => auth.keys(s), [nonce]);
  const prompt = useAsync((s) => auth.prompt(s), []);
  const [label, setLabel] = useState("");
  const [created, setCreated] = useState<CreatedKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const active = (keys.data?.keys ?? []).filter((k) => !k.revoked_at);
  const max = keys.data?.max_active ?? null;

  async function create() {
    setBusy(true); setError("");
    try {
      setCreated(await auth.createKey(label.trim()));
      setLabel("");
      setNonce((n) => n + 1);
    } catch (err) {
      setError(err instanceof ApiError && err.code === "KEY_LIMIT" ? `You already have ${max} active keys: revoke one first.` : message(err));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(k: ApiKey) {
    if (!(await confirm({ title: `Revoke the key ${k.label || k.key_id}?`, action: "Revoke key", danger: true,
      body: "Agents using this key stop working at once." }))) return;
    try { await auth.revokeKey(k.key_id); setNonce((n) => n + 1); } catch (err) { setError(message(err)); }
  }

  return (
    <div className="card stack">
      {confirmDialog}
      <h2 className="settings__title">API keys for your agents</h2>
      {me.is_owner ? (
        <p className="faint">
          Your admin key is <span className="mono">POLYMATH_MCP_API_KEY</span> in the server's <span className="mono">.env</span>;
          it is never shown in a browser. Make keys for friends in the Friends section below: they make their own here.
        </p>
      ) : (
        <>
          <p className="faint">
            A key lets your agent (Claude Code, Codex, Hermes, ChatGPT…) use Polymath's tools as you. You can hold
            {max ? ` ${max}` : ""} active keys{max ? ` (${active.length} now)` : ""}.
          </p>
          {error && <div className="banner banner--bad" role="alert">{error}</div>}
          {created && <ShownOnce created={created} onDone={() => setCreated(null)} />}
          <div className="row">
            <input type="text" placeholder="Label, e.g. my laptop's Claude Code" value={label} maxLength={60}
                   onChange={(e) => setLabel(e.target.value)} />
            <button className="btn btn--primary" type="button" disabled={busy || (max != null && active.length >= max)}
                    onClick={() => void create()}>{busy ? "Creating…" : "Create key"}</button>
          </div>
          <table className="settings__table">
            <thead><tr><th>Label</th><th>Key id</th><th>Created</th><th>Status</th><th /></tr></thead>
            <tbody>
              {(keys.data?.keys ?? []).map((k) => (
                <tr key={k.key_id}>
                  <td>{k.label || <span className="faint">—</span>}</td>
                  <td className="mono">{k.key_id}</td>
                  <td>{k.created_at ?? ""}</td>
                  <td>{k.revoked_at ? <span className="faint">revoked</span> : "active"}</td>
                  <td>{!k.revoked_at && <button className="btn files__del" type="button" onClick={() => void revoke(k)}>Revoke</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {keys.data && !keys.data.keys.length && <div className="empty">No keys yet.</div>}
        </>
      )}
      <div className="field">
        <span className="label">Connect your agent</span>
        <p className="faint">
          Paste this into your agent. {me.is_owner ? "Replace the placeholder with a key." : "When you create a key, the prompt shown then already contains it; this copy has a placeholder."}
        </p>
        <Secret value={prompt.data?.prompt ?? ""} what="prompt" block rows={10} />
      </div>
    </div>
  );
}

function FriendRow({ f, libraries, onChanged, confirm }: {
  f: Friend; libraries: string[]; onChanged: () => void; confirm: (o: ConfirmOptions) => Promise<boolean>;
}) {
  const [open, setOpen] = useState<"" | "libraries" | "keys">("");
  const [chosen, setChosen] = useState<string[]>(f.corpus_ids.filter((c) => !c.startsWith("fr-")));
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const keys = useAsync((s) => (open === "keys" ? auth.friendKeys(f.username, s) : Promise.resolve(null)), [open]);

  async function act(action: "enable" | "disable" | "reset-password") {
    if (action === "reset-password" && !(await confirm({ title: `Reset ${f.username}'s password?`, action: "Reset password",
      body: "They get a new first password, shown once, and must choose their own at next sign-in." }))) return;
    try {
      const r = await auth.friendAction(f.username, action);
      if (r.first_password) setSecret(r.first_password);
      onChanged();
    } catch (err) { setError(message(err)); }
  }

  async function saveLibraries() {
    try { await auth.setLibraries(f.username, chosen); setOpen(""); onChanged(); } catch (err) { setError(message(err)); }
  }

  return (
    <>
      <tr>
        <td><strong>{f.username}</strong>{f.name && f.name !== f.username ? <span className="faint"> · {f.name}</span> : null}</td>
        <td>{f.enabled ? (f.must_change_password ? "must set password" : "active") : <span className="faint">disabled</span>}</td>
        <td>{f.corpus_ids.length}</td>
        <td>{f.active_keys}</td>
        <td className="row">
          <button className="btn" type="button" onClick={() => void act(f.enabled ? "disable" : "enable")}>{f.enabled ? "Disable" : "Enable"}</button>
          <button className="btn" type="button" onClick={() => void act("reset-password")}>Reset password</button>
          <button className="btn" type="button" onClick={() => setOpen(open === "libraries" ? "" : "libraries")}>Libraries</button>
          <button className="btn" type="button" onClick={() => setOpen(open === "keys" ? "" : "keys")}>Keys</button>
        </td>
      </tr>
      {(open || secret || error) && (
        <tr><td colSpan={5}>
          {error && <div className="banner banner--bad">{error}</div>}
          {secret && (
            <div className="banner banner--info row">
              New password for {f.username} (shown once): <Secret value={secret} what="password" />
              <button className="btn" type="button" onClick={() => setSecret("")}>Done</button>
            </div>
          )}
          {open === "libraries" && (
            <div className="stack">
              {libraries.map((c) => (
                <label key={c} className="row">
                  <input type="checkbox" checked={chosen.includes(c)}
                         onChange={(e) => setChosen((xs) => (e.target.checked ? [...xs, c] : xs.filter((x) => x !== c)))} />
                  <span className="mono">{c}</span>
                </label>
              ))}
              <div className="faint">Their private library <span className="mono">fr-{f.username}</span> is always included.</div>
              <div className="row"><button className="btn btn--primary" type="button" onClick={() => void saveLibraries()}>Save libraries</button></div>
            </div>
          )}
          {open === "keys" && (
            <table className="settings__table">
              <tbody>
                {(keys.data?.keys ?? []).map((k) => (
                  <tr key={k.key_id}>
                    <td>{k.label || "—"}</td><td className="mono">{k.key_id}</td>
                    <td>{k.revoked_at ? <span className="faint">revoked</span> : "active"}</td>
                    <td>{!k.revoked_at && (
                      <button className="btn files__del" type="button"
                              onClick={() => void auth.revokeFriendKey(f.username, k.key_id).then(onChanged).catch((e) => setError(message(e)))}>
                        Revoke
                      </button>)}
                    </td>
                  </tr>
                ))}
                {keys.data && !keys.data.keys.length && <tr><td className="faint">No keys.</td></tr>}
              </tbody>
            </table>
          )}
        </td></tr>
      )}
    </>
  );
}

/** INVITE-SIGNUP — the owner's one invite code: shown with the answers' hover copy button; Regenerate asks first (friends who
 *  have not signed up yet need the new code); "Create invite code" until the first one exists. */
function InviteCard() {
  const [confirm, confirmDialog] = useConfirm();
  const invite = useAsync((s) => friends.invite(s), []);
  const [fresh, setFresh] = useState<Invite | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = fresh ?? invite.data;
  const code = current?.code ?? null;

  async function regenerate() {
    if (code && !(await confirm({ title: "Regenerate the invite code?", action: "Regenerate",
      body: "Friends who have not signed up yet will need the new code." }))) return;
    setBusy(true); setError("");
    try { setFresh(await friends.rotateInvite()); } catch (err) { setError(message(err)); } finally { setBusy(false); }
  }

  return (
    <div className="card stack">
      {confirmDialog}
      <h2 className="settings__title">Invite</h2>
      <p className="faint">Send a friend the website address and this code; they create their own account.</p>
      {error && <div className="banner banner--bad" role="alert">{error}</div>}
      {invite.error && !fresh && <div className="banner banner--bad">{invite.error}</div>}
      {code ? (
        <>
          <div className="field">
            <span className="label">Invite code</span>
            <Secret value={code} what="invite code" />
          </div>
          <div className="row">
            <button className="btn" type="button" disabled={busy} onClick={() => void regenerate()}>
              {busy ? "Regenerating…" : "Regenerate"}
            </button>
            {current?.rotated_at && <span className="faint">Since {current.rotated_at}</span>}
          </div>
        </>
      ) : (
        !invite.loading && !invite.error && (
          <div className="row">
            <span className="faint">No invite code yet.</span>
            <button className="btn btn--primary" type="button" disabled={busy} onClick={() => void regenerate()}>
              {busy ? "Creating…" : "Create invite code"}
            </button>
          </div>
        )
      )}
    </div>
  );
}

function Friends() {
  const [confirm, confirmDialog] = useConfirm();
  const [nonce, setNonce] = useState(0);
  const admin = useAsync((s) => auth.friends(s), [nonce]);
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [made, setMade] = useState<{ username: string; password: string } | null>(null);
  const [error, setError] = useState("");

  async function add() {
    setError("");
    try {
      const r = await auth.addFriend(username.trim().toLowerCase(), name.trim());
      setMade({ username: r.friend.username, password: r.first_password });
      setUsername(""); setName("");
      setNonce((n) => n + 1);
    } catch (err) { setError(message(err)); }
  }

  return (
    <div className="card stack">
      {confirmDialog}
      <h2 className="settings__title">Friends</h2>
      <p className="faint">
        Each friend gets their own sign-in, every shared library by default, their own private library, and up to
        {` ${admin.data?.max_active_keys ?? 3}`} API keys. They can never use your admin key, your server's files, or your
        browser's web reader. Friends create their own account with the invite code above; you can also add one here.
      </p>
      {error && <div className="banner banner--bad" role="alert">{error}</div>}
      {made && (
        <div className="banner banner--info row">
          Created <strong>{made.username}</strong>. First password (shown once): <Secret value={made.password} what="password" />
          <button className="btn" type="button" onClick={() => setMade(null)}>Done</button>
        </div>
      )}
      <div className="row">
        <input type="text" placeholder="username (lowercase)" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input type="text" placeholder="display name (optional)" value={name} onChange={(e) => setName(e.target.value)} />
        <button className="btn btn--primary" type="button" disabled={username.trim().length < 2} onClick={() => void add()}>Add friend</button>
      </div>
      <table className="settings__table">
        <thead><tr><th>Friend</th><th>Status</th><th>Libraries</th><th>Keys</th><th /></tr></thead>
        <tbody>
          {(admin.data?.friends ?? []).map((f) => (
            <FriendRow key={f.username} f={f} libraries={admin.data?.libraries ?? []} onChanged={() => setNonce((n) => n + 1)} confirm={confirm} />
          ))}
        </tbody>
      </table>
      {admin.data && !admin.data.friends.length && <div className="empty">No friends yet.</div>}
      {admin.error && <div className="banner banner--bad">{message(admin.error)}</div>}
    </div>
  );
}

const MODE_LABEL: Record<Mode, string> = { light: "Light", dark: "Dark", system: "System" };
const ACCENT_LABEL: Record<Accent, string> = { indigo: "Indigo", teal: "Teal", amber: "Amber", rose: "Rose" };

/** FRONTEND-REFRESH-V1 §3.2 — the mode and the accent, stored in this browser. */
function AppearanceCard() {
  const [a, setA] = useAppearance();
  return (
    <div className="card stack">
      <h2 className="settings__title">Appearance</h2>
      <div className="field">
        <span className="label" id="appearance-mode">Mode</span>
        <div className="seg" role="group" aria-labelledby="appearance-mode">
          {MODES.map((m) => (
            <button key={m} type="button" className="seg__btn" aria-pressed={a.mode === m} onClick={() => setA({ ...a, mode: m })}>
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
      </div>
      <div className="field">
        <span className="label" id="appearance-accent">Accent</span>
        <div className="swatches" role="group" aria-labelledby="appearance-accent">
          {ACCENTS.map((c) => (
            <button key={c} type="button" className="swatch" aria-pressed={a.accent === c} onClick={() => setA({ ...a, accent: c })}>
              <span className="swatch__dot" style={{ background: `var(--swatch-${c})` }} aria-hidden="true" />
              {ACCENT_LABEL[c]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/** On the server itself: set King's password for signing in on the website (one login there; no terminal needed). */
function OwnerWebPassword({ initiallySet }: { initiallySet: boolean }) {
  const [isSet, setIsSet] = useState(initiallySet);
  const [pw, setPw] = useState("");
  const [again, setAgain] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const mismatch = again.length > 0 && again !== pw;
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setErr(""); setMsg("");
    try {
      await auth.setOwnerPassword(pw);
      setIsSet(true); setPw(""); setAgain("");
      setMsg("Saved. On the website, sign in as king with this password.");
    } catch (x) { setErr(message(x)); }
  }
  return (
    <form className="card stack" onSubmit={(e) => void save(e)}>
      <h2 className="settings__title">Website sign-in</h2>
      <p className="dim" style={{ margin: 0 }}>
        {isSet ? "Your website password is set. You can change it here." : "Set the password you use on the website. Your username there is king."}
      </p>
      <label className="field"><span className="label">New password</span>
        <input type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} /></label>
      <label className="field"><span className="label">Type it again</span>
        <input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} /></label>
      {mismatch && <p className="faint" style={{ margin: 0 }}>The two entries differ.</p>}
      {msg && <div className="banner banner--ok">{msg}</div>}
      {err && <div className="banner banner--bad">{err}</div>}
      <div className="row"><button className="btn btn--primary" type="submit" disabled={pw.length === 0 || again !== pw}>
        {isSet ? "Change password" : "Save password"}</button></div>
    </form>
  );
}

/** FRIENDS-ACCESS-V1 F4 — Settings: my account, my API keys + the connect prompt, and (owner) the friends. */
export function Settings({ me, onMeChanged, onSignOut }: { me: Me; onMeChanged: (me: Me) => void; onSignOut: () => void }) {
  const lib = privateLibrary(me);
  return (
    <div className="screen screen--wide">
      <div className="screen__head">
        <h1 className="screen__title">Settings</h1>
        <p className="screen__sub">
          {me.local ? "You are on the server itself: no sign-in here." : <>Signed in as <strong>{me.display_name}</strong> ({me.username}){me.is_owner ? " · owner" : ""}</>}
          {lib && <> · your private library: <span className="mono">{lib}</span></>}
        </p>
      </div>
      <div className="stack">
        <AppearanceCard />
        <DeepResearchSettings />
        {me.local && me.is_owner && <OwnerWebPassword initiallySet={!!me.web_password_set} />}
        {!me.local && (
          <div className="card stack">
            <h2 className="settings__title">Account</h2>
            <ChangePassword me={me} onChanged={onMeChanged} />
            <div className="row"><button className="btn" type="button" onClick={onSignOut}>Sign out</button></div>
          </div>
        )}
        <MyKeys me={me} />
        {me.is_owner && <InviteCard />}
        {me.is_owner && <Friends />}
      </div>
    </div>
  );
}
