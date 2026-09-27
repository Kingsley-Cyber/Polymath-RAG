# Friends access: runbook

How friends use **https://rag.kingsleylab.xyz** and its MCP server with their own sign-in, and how King (the owner and only
admin) runs it. Design and proof: `docs/wiki/plans/FRIENDS-ACCESS-V1.md`, registers 11.497–11.502.

## 1. For a friend

**Create your account** (King sent you the website address and an invite code)
1. Open https://rag.kingsleylab.xyz and click **New here? Create your account** under the sign-in form.
2. Choose a username (lowercase letters, digits, `-` or `_`; 2–32 characters) and a password, type the password again, and
   paste the invite code King sent you → **Create account**.
3. You are signed in at once, with the same libraries every friend gets. Next time, sign in with that username and password.
4. You stay signed in for 7 days on that browser. Changing your password (Settings → Account) signs out your other browsers.

If it says **The invite code is wrong**, check it with King: the code changes when King regenerates it. After five wrong
codes the site pauses sign-ups for 15 minutes.

**Sign in with a password King made** (the alternative: King added you in Settings and sent you a first password)
1. Sign in with the username and first password King sent you.
2. You are asked to choose your own password before anything else.

**What you can do**
- Chat, Compare, Files and Graph over the libraries King shared with you.
- Upload into your own private library, `fr-<your username>`. Only you and King see it.
- Run the research adapters King allowed, and follow your own runs.

**What you cannot do**
- King's admin pages: Overview, Control Plane, Models, and the friends list.
- The web research host (`research_acquire`); it drives King's own browser.
- Uploads from paths on the server.

**Connect your agent (Claude Code, Codex, Cursor, …)**
1. Settings → **API keys for your agents** → give the key a label → **Create key**.
2. The key and a ready-made prompt are shown **once**. Copy the prompt and paste it into your agent. Then click **I've saved it**.
3. You can hold up to 3 active keys. **Revoke** one on the same page (for example after losing a laptop).

The prompt carries these connection details, with your key filled in:

| Setting | Value |
|---|---|
| MCP URL | `https://mcp.kingsleylab.xyz/mcp` |
| Transport | Streamable HTTP |
| Header | `Authorization: Bearer <YOUR_KEY>` |

The key reads the same libraries as your web sign-in. It is not a web password: you cannot sign in to the site with it.

**Forgot your password?** Ask King to reset it. You get a new first password and choose your own again.

## 2. For King

**Your own access**
- On this Mac (`http://127.0.0.1:7200/v2/`) there is no sign-in: a direct local caller is the owner.
- Through the website, sign in as `king`. Your password was set at the hidden prompt during go-live. Nobody else knows it, and
  it is stored only as a scrypt hash.
- Your admin MCP key is `POLYMATH_MCP_API_KEY` in `.env`. It is never shown in a browser, and **Create key** refuses it (friends only).

**Invite a friend** (Settings → Invite, above Friends)
1. The card shows your one invite code; hover it for the copy button. Until you have one, click **Create invite code**.
2. Send a friend the website address and this code; they create their own account (username and password of their choice)
   and are signed in at once, with every shared library and every adapter, like a friend you add yourself.
3. **Regenerate** makes a new code and refuses the old one from then on; friends who have not signed up yet need the new
   code. Friends who already have an account are not affected.
4. The code lives, in plain text, in the owner-only accounts file (it opens nothing but a limited friend account, and you
   must be able to read it again to share it). It is never shown to friends, never in `/auth/me`, never logged.

**Add a friend yourself** (Settings → Friends)
1. Type a lowercase username (2–32 characters; and a display name, if you like) → **Add friend**.
2. The first password is shown **once**. Send it to the friend privately. They must replace it at first sign-in.
3. By default a friend reads every shared library (never another friend's `fr-*` library) and may run every adapter.

**Manage a friend**

| Action | What it does |
|---|---|
| **Libraries** + **Save libraries** | Changes what the friend (web and keys) can read. Their private library always stays. |
| **Disable** / **Enable** | Blocks or restores sign-in and every key at once. Disabling ends their sessions. |
| **Reset password** | Shows a new first password once and ends their sessions. |
| **Keys** | Lists the friend's keys; revoke any of them. |

**Command-line fallback** (from the repo root; the accounts file is `POLYMATH_MCP_PRINCIPALS_FILE` in `.env`):

```bash
.venv/bin/python scripts/web_accounts.py list
```

Other commands: `set-owner-password`, `add-friend --username <name> [--corpus <id>] [--adapter <id>] --password-out <new file>`,
`reset-password --username <name> --password-out <new file>`, `enable --username <name>`, `disable --username <name>`.
A first password goes to a NEW owner-only file, never to the screen (unless `--print-password`).

## 3. How it works

- Browser → Cloudflare → Caddy (`:8794`, `~/.hermes/rag-proxy/Caddyfile`) → the orchestrator (`:7200`). Caddy no longer
  asks for a shared password. It strips any `X-Polymath-Principal` header a browser sends.
- The orchestrator's **web boundary** (`orchestrator/orchestrator/web_boundary.py`) handles every request that came through the proxy:
  - public routes: the app shell, `/health`, `/ready`, `/auth/login`, `/auth/register` (the sign-up with the invite code);
  - everything else needs a signed session cookie (HttpOnly, Secure, SameSite=Strict);
  - a state-changing request also needs the CSRF header;
  - owner routes refuse friends;
  - a route missing from the policy table is refused.
- A friend is forwarded as `prn_<username>`, so every route narrows to that friend's libraries (`web_scope.py`). Accounts, password
  hashes and hashed keys live in the principal registry file (mode 600) next to the MCP principals.
- MCP Server A checks the Bearer key itself; its calls into the orchestrator are local, so the web boundary leaves them alone.
- Sign-in throttle: 5 failed attempts per username and per address, per 15 minutes. A wrong invite code counts against the
  address and against one shared `invite` key, so guessing the code stops for everyone after 5 wrong codes. There is no
  daily spend cap per friend (the owner's decision).
- The invite code: `GET /friends/invite` and `POST /friends/invite/rotate` are owner routes (a friend gets `OWNER_ONLY`);
  `POST /auth/register` `{username, password, invite_code}` is public and answers like `/auth/me`, with the sign-in cookies.

## 4. When something is wrong

| The message says | Meaning | Fix |
|---|---|---|
| `LOGIN_REQUIRED` | No session, or it expired | Sign in again. |
| `BAD_LOGIN` | Wrong username or password | Check both; King can reset the password. |
| `TOO_MANY_ATTEMPTS` (429) | 5 failed tries in 15 minutes (sign-in, or wrong invite codes) | Wait 15 minutes. |
| `INVITE_INVALID` (403) | The invite code is wrong or was regenerated | Ask King for the current code. |
| `INVITES_OFF` (503) | King has not created an invite code yet | King: Settings → Invite → **Create invite code**. |
| `USERNAME_TAKEN` (409) / `USERNAME_INVALID` (422) | That name exists (any case), or breaks the rule | Choose another: lowercase letters, digits, `-` or `_`, 2–32 characters. |
| `PASSWORD_CHANGE_REQUIRED` | First sign-in, or after a reset | Choose a new password. |
| `CSRF_FAILED` | The page's security token is stale | Reload the page. |
| `OWNER_ONLY` | A friend opened an admin action | Only King can do it. |
| `KEY_LIMIT` | Already 3 active keys | Revoke one, then create a new one. |
| `LOGIN_NOT_CONFIGURED` (503) | The server has no session secret, or cannot read the accounts file | King: `POLYMATH_WEB_SESSION_SECRET` must be in `.env` (32+ characters) and the accounts file must be mode 600; then run `bash scripts/bounce_fleet.sh`. |
| The agent gets 401 from the MCP URL | The key was revoked or mistyped | Create a new key and paste the new prompt. |
| The agent gets 403 from Cloudflare | Cloudflare refused the agent's user-agent | Follow the user-agent line in the connect prompt. |

**Check the live site** ($0, read-only, one wrong-password attempt per run):

```bash
cd /Users/king/Documents/polymath-rebuild/polymath-v4 && .venv/bin/python docs/wiki/experiments/friends-access-2026-09-26/live_check.py
```

**Go back to the old shared password** (emergency only):
1. Copy the newest `~/.hermes/rag-proxy/Caddyfile.bak.<time>` back to `Caddyfile`.
2. Restart Caddy:

```bash
launchctl kickstart -k gui/$(id -u)/com.hermes.rag-caddy
```

The code itself stays. Behind the old password the app still asks each person to sign in.
