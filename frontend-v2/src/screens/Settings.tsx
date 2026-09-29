import { useState, type FormEvent, type ReactNode } from "react";
import { useConfirm } from "../ui/Dialog";
import { ACCENTS, MODES, useAppearance, type Accent, type Mode } from "../lib/appearance";
import { ApiError } from "../lib/api";
import { useAsync } from "../lib/useAsync";
import { auth, privateLibrary, type ApiKey, type CreatedKey, type Me } from "../lib/auth";
import { ChangePassword } from "./Login";
import { DeepResearchSettings } from "../components/deep/DeepResearchSettings";
import { CopyField } from "../ui/CopyField";
import { Icon, type IconName } from "../ui/icons";
import { PasswordInput } from "../ui/PasswordInput";
import { Secret } from "../ui/Secret";

function message(err: unknown): string {
  return err instanceof ApiError ? err.detailMessage : String(err);
}

function CardHead({ icon, id, title, lead, aside }: { icon: IconName; id: string; title: string; lead?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="settings__head">
      <span className="settings__icon" aria-hidden="true"><Icon name={icon} size={18} /></span>
      <div className="settings__headtext">
        <h2 id={id} className="settings__title">{title}</h2>
        {lead && <p className="settings__lead">{lead}</p>}
      </div>
      {aside}
    </div>
  );
}

/** Who is signed in, and Sign out on the website (nobody signs in on the server itself). */
function ProfileCard({ me, onSignOut }: { me: Me; onSignOut: () => void }) {
  const name = me.display_name || me.username;
  const initials = name.split(/\s+/).map((w) => w[0] ?? "").join("").slice(0, 2).toUpperCase() || "?";
  const lib = privateLibrary(me);
  return (
    <section className="card profile" aria-label="Profile">
      <div className="profile__avatar" aria-hidden="true">{initials}</div>
      <div className="profile__who">
        <div className="profile__name">{name}</div>
        <div className="profile__meta">
          {me.local ? "On this Mac: no sign-in needed here" : `Signed in as ${me.username}`}
          {lib && <> · your private library: <span className="mono">{lib}</span></>}
        </div>
      </div>
      {!me.local && (
        <button className="btn" type="button" onClick={onSignOut}><Icon name="signOut" size={15} />Sign out</button>
      )}
    </section>
  );
}

/** ONE-PROFILE (the owner, 2026-09-28: "copy and paste should work without creating a api") — two copies, nothing to create:
 *  the connect command (it reads the key on the Mac; the key never reaches this page) and the prompt for the agent. */
function ConnectCard() {
  const data = useAsync((s) => auth.prompt(s), []);
  return (
    <section className="card settings__card" aria-labelledby="connect-title">
      <CardHead icon="plug" id="connect-title" title="Connect Claude Code and Codex"
                lead="Two copies and you're done. There is no key to create." />
      {data.error && <div className="banner banner--bad" role="alert">{data.error}</div>}
      <ol className="steps">
        <li className="step">
          <span className="step__num" aria-hidden="true">1</span>
          <div className="step__body">
            <h3 className="step__title">Run this once in Terminal on the Mac</h3>
            <p className="step__text">It connects both apps with your key, which it reads on the Mac itself: the key is never shown. Safe to run again.</p>
            <CopyField value={data.data?.connect_command ?? ""} what="command" />
          </div>
        </li>
        <li className="step">
          <span className="step__num" aria-hidden="true">2</span>
          <div className="step__body">
            <h3 className="step__title">Restart the app, then paste this into it</h3>
            <p className="step__text">It tells your agent what your library holds and how to use it.</p>
            <CopyField value={data.data?.prompt ?? ""} what="prompt" block primary />
          </div>
        </li>
      </ol>
    </section>
  );
}

/** A friend's key, shown ONCE with the prompt filled in (their own account; the owner's page has no keys). */
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

/** A friend (an account made before ONE-PROFILE): their own keys, up to the limit. */
function FriendKeysCard() {
  const [confirm, confirmDialog] = useConfirm();
  const [nonce, setNonce] = useState(0);
  const keys = useAsync((s) => auth.keys(s), [nonce]);
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
    <section className="card settings__card" aria-labelledby="keys-title">
      {confirmDialog}
      <CardHead icon="plug" id="keys-title" title="Connect your AI tools"
                lead={`Create a key: it comes with a prompt that already contains it. You can hold${max ? ` ${max}` : ""} active keys${max ? ` (${active.length} now)` : ""}.`} />
      {error && <div className="banner banner--bad" role="alert">{error}</div>}
      {created && <ShownOnce created={created} onDone={() => setCreated(null)} />}
      <div className="row">
        <input type="text" placeholder="Label, e.g. my laptop's Claude Code" value={label} maxLength={60}
               onChange={(e) => setLabel(e.target.value)} />
        <button className="btn btn--primary" type="button" disabled={busy || (max != null && active.length >= max)}
                onClick={() => void create()}>{busy ? "Creating…" : "Create key"}</button>
      </div>
      {(keys.data?.keys ?? []).length > 0 && (
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
      )}
    </section>
  );
}

/** ONE-PROFILE — King's website password, set from the server itself (http://127.0.0.1:7200, where nobody signs in). One field
 *  with Show; the website then signs in username King with it. */
function OwnerPasswordCard({ isSet, onSaved }: { isSet: boolean; onSaved: () => void }) {
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(""); setMsg("");
    try {
      await auth.setOwnerPassword(pw);
      setPw("");
      onSaved();
      setMsg("Saved. On the website, sign in with username King and this password.");
    } catch (x) {
      setErr(message(x));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className={`card settings__card${isSet ? "" : " settings__card--todo"}`} aria-labelledby="password-title"
          onSubmit={(e) => void save(e)}>
      <CardHead icon="lock" id="password-title" title="Website password"
                lead={<>For signing in on the website. Username: <strong>King</strong></>}
                aside={<span className={`pill ${isSet ? "pill--ready" : "pill--degraded"}`}>{isSet ? "Set" : "Not set"}</span>} />
      {!isSet && <p className="settings__todo">You can't sign in on the website until this is set.</p>}
      <div className="settings__pwrow">
        <label className="sr-only" htmlFor="owner-password">{isSet ? "New password" : "Password"}</label>
        <PasswordInput id="owner-password" value={pw} onChange={setPw} autoComplete="new-password"
                       placeholder={isSet ? "New password" : "Choose a password"} />
        <button className="btn btn--primary" type="submit" disabled={busy || pw.length === 0}>
          {busy ? "Saving…" : isSet ? "Change" : "Save"}
        </button>
      </div>
      {msg && <div className="banner banner--ok" role="status">{msg}</div>}
      {err && <div className="banner banner--bad" role="alert">{err}</div>}
    </form>
  );
}

/** Signed in on the website: change my own password (the current one first). */
function AccountPasswordCard({ me, onMeChanged }: { me: Me; onMeChanged: (me: Me) => void }) {
  return (
    <section className="card settings__card" aria-labelledby="account-password-title">
      <CardHead icon="lock" id="account-password-title" title="Website password" lead={`Change the password for ${me.username}.`} />
      <ChangePassword me={me} onChanged={onMeChanged} />
    </section>
  );
}

const MODE_LABEL: Record<Mode, string> = { light: "Light", dark: "Dark", system: "System" };
const ACCENT_LABEL: Record<Accent, string> = { indigo: "Indigo", teal: "Teal", amber: "Amber", rose: "Rose" };

/** FRONTEND-REFRESH-V1 §3.2 — the mode and the accent, stored in this browser. */
function AppearanceCard() {
  const [a, setA] = useAppearance();
  return (
    <section className="card settings__card" aria-labelledby="appearance-title">
      <CardHead icon="sun" id="appearance-title" title="Appearance" />
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
    </section>
  );
}

/** ONE-PROFILE Settings (the owner, 2026-09-28: "just keep it 1 profile and copy and paste should work without creating a api,
 *  logging in should be good enough"): who I am, connect my agents, my website password, appearance, deep research. While King's
 *  website password is unset (on the server itself), its card comes first: nothing on the website works without it. */
export function Settings({ me, onMeChanged, onSignOut }: { me: Me; onMeChanged: (me: Me) => void; onSignOut: () => void }) {
  const [passwordSet, setPasswordSet] = useState(!!me.web_password_set);
  const ownerHere = me.local && me.is_owner;
  const connect = me.is_owner ? <ConnectCard key="connect" /> : <FriendKeysCard key="keys" />;
  const password = ownerHere
    ? <OwnerPasswordCard key="password" isSet={passwordSet} onSaved={() => setPasswordSet(true)} />
    : !me.local ? <AccountPasswordCard key="password" me={me} onMeChanged={onMeChanged} /> : null;
  const first = ownerHere && !passwordSet ? [password, connect] : [connect, password];
  return (
    <div className="screen settings">
      <div className="screen__head">
        <h1 className="screen__title">Settings</h1>
      </div>
      <div className="settings__cards">
        <ProfileCard me={me} onSignOut={onSignOut} />
        {first}
        <AppearanceCard />
        <DeepResearchSettings />
      </div>
    </div>
  );
}
