import { useState, type FormEvent } from "react";
import { Icon } from "../ui/icons";
import { PasswordInput } from "../ui/PasswordInput";
import { ApiError } from "../lib/api";
import { auth, type Me } from "../lib/auth";

/** A refused sign-in in the app's words (the codes /auth/login answers). */
export function signInProblem(err: unknown): string {
  const code = err instanceof ApiError ? err.code : null;
  switch (code) {
    case "BAD_LOGIN": return "Wrong username or password.";
    case "TOO_MANY_ATTEMPTS": return "Too many tries. Wait 15 minutes, then try again.";
    case "OWNER_PASSWORD_NOT_SET":
      return "King's password isn't set yet. On the Mac, open Polymath, go to Settings and set it under Website password.";
    case "LOGIN_NOT_CONFIGURED": return "Sign-in isn't set up on the server yet.";
    default: return `Couldn't sign in: ${err instanceof ApiError ? err.detailMessage : String(err)}`;
  }
}

/** ONE-PROFILE (the owner, 2026-09-28: "universal log in is King ... just keep it 1 profile") — the sign-in screen
 *  (rag.kingsleylab.xyz): a username and a password, nothing else. The server decides; this only asks. */
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
      setError(signInProblem(err));
      setPassword("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth__panel">
        <div className="auth__brand">
          <div className="auth__mark" aria-hidden="true"><Icon name="research" size={26} /></div>
          <h1 className="auth__title">Polymath</h1>
          <p className="auth__sub">Sign in to your research library.</p>
        </div>
        <form className="card auth__card" aria-label="Sign in" onSubmit={(e) => void submit(e)}>
          {error && <div className="banner banner--bad" role="alert">{error}</div>}
          <div className="auth__field">
            <label className="auth__label" htmlFor="signin-username">Username</label>
            <input id="signin-username" type="text" autoComplete="username" autoCapitalize="none" autoCorrect="off"
                   spellCheck={false} autoFocus value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="auth__field">
            <label className="auth__label" htmlFor="signin-password">Password</label>
            <PasswordInput id="signin-password" value={password} onChange={setPassword} autoComplete="current-password" />
          </div>
          <button className="btn btn--primary auth__submit" type="submit" disabled={busy || !username.trim() || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="auth__foot"><Icon name="lock" size={13} /> Private site · one account</p>
      </div>
    </main>
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
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setDone(false);
    try {
      const updated = await auth.changePassword(current, next);
      setDone(true);
      setCurrent(""); setNext("");
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
    <form className="stack" aria-label="Change password" onSubmit={(e) => void submit(e)}>
      {forced && (
        <div className="banner banner--info">
          Welcome, {me.display_name}. Choose your own password to continue.
        </div>
      )}
      {error && <div className="banner banner--bad" role="alert">{error}</div>}
      {done && !forced && <div className="banner banner--ok">Password changed. Other devices are signed out.</div>}
      <label className="field">
        <span className="label">{forced ? "The password you were given" : "Current password"}</span>
        <PasswordInput value={current} onChange={setCurrent} autoComplete="current-password" />
      </label>
      <label className="field">
        <span className="label">New password</span>
        <PasswordInput value={next} onChange={setNext} autoComplete="new-password" />
      </label>
      <div className="row">
        <button className="btn btn--primary" type="submit" disabled={busy || !current || next.length === 0}>
          {busy ? "Saving…" : "Change password"}
        </button>
        {forced && onSignOut && <button className="btn" type="button" onClick={onSignOut}>Sign out</button>}
      </div>
    </form>
  );

  if (!forced) return form;
  return (
    <main className="auth">
      <div className="auth__panel">
        <div className="auth__brand">
          <div className="auth__mark" aria-hidden="true"><Icon name="research" size={26} /></div>
          <h1 className="auth__title">Polymath</h1>
        </div>
        <div className="card auth__card">{form}</div>
      </div>
    </main>
  );
}
