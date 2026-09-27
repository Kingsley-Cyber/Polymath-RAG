import { useState, type FormEvent } from "react";
import { Icon } from "../ui/icons";
import { ApiError } from "../lib/api";
import { auth, type Me } from "../lib/auth";

/** FRIENDS-ACCESS-V1 — the sign-in screen (rag.kingsleylab.xyz). The server decides; this only asks. */
export function Login({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSignedIn(await auth.login(username.trim(), password));
    } catch (err) {
      const code = err instanceof ApiError ? err.code : null;
      setError(
        code === "BAD_LOGIN" ? "Wrong username or password."
          : code === "TOO_MANY_ATTEMPTS" ? "Too many failed sign-ins. Wait 15 minutes and try again."
          : code === "LOGIN_NOT_CONFIGURED" ? "Sign-in is not set up on the server yet."
          : `Sign-in failed: ${err instanceof ApiError ? err.detailMessage : String(err)}`,
      );
    } finally {
      setBusy(false);
      setPassword("");
    }
  }

  return (
    <div className="auth">
      <form className="card auth__card stack" onSubmit={(e) => void submit(e)}>
        <div className="auth__mark" aria-hidden="true"><Icon name="research" size={22} /></div>
        <h1 className="screen__title">Polymath</h1>
        <p className="screen__sub">Sign in to continue.</p>
        {error && <div className="banner banner--bad" role="alert">{error}</div>}
        <label className="field">
          <span className="label">Username</span>
          <input type="text" autoComplete="username" autoFocus value={username}
                 onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label className="field">
          <span className="label">Password</span>
          <input type="password" autoComplete="current-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} />
        </label>
        <button className="btn btn--primary" type="submit" disabled={busy || !username.trim() || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

/** Change my password. `forced`: the first sign-in with a password the owner generated (nothing else opens until done). */
export function ChangePassword({ me, forced, onChanged, onSignOut }: {
  me: Me;
  forced?: boolean;
  onChanged: (me: Me) => void;
  onSignOut?: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const tooShort = next.length > 0 && next.length < 10;
  const mismatch = again.length > 0 && again !== next;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const updated = await auth.changePassword(current, next);
      setDone(true);
      setCurrent(""); setNext(""); setAgain("");
      onChanged(updated);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : null;
      setError(code === "BAD_PASSWORD" ? "The current password is wrong."
        : err instanceof ApiError ? err.detailMessage : String(err));
    } finally {
      setBusy(false);
    }
  }

  const form = (
    <form className="stack" onSubmit={(e) => void submit(e)}>
      {forced && (
        <div className="banner banner--info">
          Welcome, {me.display_name}. Choose your own password to continue (at least 10 characters).
        </div>
      )}
      {error && <div className="banner banner--bad" role="alert">{error}</div>}
      {done && !forced && <div className="banner banner--ok">Password changed. Other devices are signed out.</div>}
      <label className="field">
        <span className="label">{forced ? "The password you were given" : "Current password"}</span>
        <input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
      </label>
      <label className="field">
        <span className="label">New password (10+ characters)</span>
        <input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
      </label>
      <label className="field">
        <span className="label">New password again</span>
        <input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
      </label>
      {(tooShort || mismatch) && (
        <div className="faint">{tooShort ? "At least 10 characters." : "The two new passwords differ."}</div>
      )}
      <div className="row">
        <button className="btn btn--primary" type="submit"
                disabled={busy || !current || next.length < 10 || next !== again}>
          {busy ? "Saving…" : "Change password"}
        </button>
        {forced && onSignOut && <button className="btn" type="button" onClick={onSignOut}>Sign out</button>}
      </div>
    </form>
  );

  if (!forced) return form;
  return (
    <div className="auth">
      <div className="card auth__card stack">
        <h1 className="screen__title">Polymath</h1>
        {form}
      </div>
    </div>
  );
}
