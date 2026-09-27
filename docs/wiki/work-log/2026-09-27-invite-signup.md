---
change_id: INVITE-SIGNUP
owner: "@king"
date: 2026-09-27
status: complete
status_note: "Self sign-up for friends with the owner's one invite code: the sign-in page gains Create your account (username, password, invite code) and signs the person in at once; the owner holds one rotatable code in Settings → Invite (hover copy, Regenerate). Unit and worktree proven on feat/invite-signup; not merged, not deployed."
architecture_impact: "orchestrator/orchestrator/web_accounts.py (the `invite` record, rotate_invite, register_friend, identity_for, one username rule 2-32); orchestrator/orchestrator/api/web_auth.py (POST /auth/register); orchestrator/orchestrator/api/web_settings.py (GET /friends/invite, POST /friends/invite/rotate, friend_defaults); orchestrator/orchestrator/web_boundary.py (three rules); frontend-v2: screens/Login.tsx (Create your account), screens/Settings.tsx (Invite card), lib/auth.ts (auth.register, friends.invite, friends.rotateInvite), vite.config.ts (/friends proxied); tests: tests/contracts/test_web_invite_signup.py (new), tests/contracts/test_web_boundary.py, frontend-v2/src/__tests__/invite-signup.test.tsx (new); docs/runbooks/friends-access.md; scripts/scaffold_polymath_v4.py (3 TREE entries)."
last_reviewed: 2026-09-27
---

# INVITE-SIGNUP: friends create their own account with the owner's invite code

## Contract
- The owner, 2026-09-27: "one master sign in and they add their username and password" → ONE sign-in page for everyone
  with a "Create your account" form (username, password, invite code). The owner holds one invite code, shown in Settings
  with a copy button and a Regenerate button.
- Boundaries: worktree `pmv4-inv`, branch `feat/invite-signup` from `feat/fix-it-all` at `84a67f49`. `App.tsx`, `Chat.tsx`
  and the chat tests belong to another agent and were not touched. No live system, no register / CONTINUITY / plan edits,
  no push.

## Changes
- **The registry** (`web_accounts.py`). A top-level `invite` record on the registry document:
  `{"code": <plain>, "created_at", "rotated_at"}`. Plain at rest is the owner's choice for THIS secret: it only lets someone
  create a limited friend account, it is rotatable, and the owner must be able to read it again to share it; the file is
  owner-only (mode 600) and `RegistryCache` refuses a wider mode. It is never logged.
  - `new_invite_code()`: three groups of four from an alphabet without 0/o, 1/l/i (`k7mp-4xwq-9nfr`; 31^12 ≈ 2^59 codes).
  - `invite_record(doc)`, `invite_code(doc) -> str | None`, `rotate_invite(path) -> str` (`created_at` stays, `rotated_at`
    moves; the old code is refused from then on).
  - `register_friend(path, username, password, code, *, corpus_ids, adapter_ids)`: under the registry lock, in order: a code
    exists (`INVITES_OFF`), the code matches in constant time (`INVITE_INVALID`; checked before the username so a stranger
    learns nothing about names; the typed code is stripped and lower-cased first), the username (`USERNAME_INVALID` for the
    shape; `USERNAME_TAKEN` for the owner's name, the reserved `owner`, and any existing account, case-insensitive), the
    password (`WEAK_PASSWORD`: only an empty one, the owner's rule). It makes the record `add_friend` makes — same shape,
    scopes, private library `fr-<name>`, default libraries and adapters — with `must_change_password=False`, because the
    person chose the password. `_friend_record` and `_taken` are the one shape both paths share.
  - `identity_for(doc, username)`: the identity of an active account without a password check, for signing in a person who
    just proved themselves with the code.
  - **One username rule.** The task's rule for sign-up is 2–32 characters; the old regex was 3–31 and the owner's Add friend
    said `min_length=3, max_length=31`. Two rules for one field would let a friend choose a name the owner could not add, so
    the regex, its message (`USERNAME_RULE`), `FriendBody` and the Add friend button now all say 2–32. `prn_<name>` and
    `fr-<name>` stay within their own limits.
- **Routes.**
  - `POST /auth/register` `{username, password, invite_code}` (`web_auth.py`), PUBLIC like `/auth/login` and used the same
    way from the public site: 503 `LOGIN_NOT_CONFIGURED` without a session secret or a readable registry; the login
    THROTTLE with the keys `invite` (shared by everyone) and `addr:<address>`; 429 `TOO_MANY_ATTEMPTS` after five wrong
    codes; only a wrong code counts as a failure (a taken or bad username, an empty password and `INVITES_OFF` do not). The
    friend gets `web_settings.friend_defaults()` (every shared library, every adapter). On success the same cookies
    `/auth/login` sets (`_with_session`) and the body `/auth/me` returns, status 201. Codes → status: `INVITE_INVALID` 403,
    `USERNAME_TAKEN` 409, `USERNAME_INVALID` / `WEAK_PASSWORD` 422, `INVITES_OFF` 503. The body has no `min_length` on the
    password so the registry's rule answers in the app's error shape.
  - `GET /friends/invite` → `{code: str | null, rotated_at}` and `POST /friends/invite/rotate` → `{code, rotated_at}`
    (`web_settings.py`), OWNER, `cache-control: no-store`, the belt-and-braces `_require_owner`.
  - `web_boundary.py`: `(_POST, ^/auth/(login|register)$, PUBLIC)`, `(_GET, ^/friends/invite$, OWNER)`,
    `(_POST, ^/friends/invite/rotate$, OWNER)`. Anything else under `/friends` stays unclassified (refused).
- **The sign-in page** (`Login.tsx`). Under the unchanged sign-in form: "New here? Create your account" (a `linklike` button)
  switches the card to the sign-up form: Username (with the rule as a hint), Password, Type it again, Invite code, "Create
  account", "Back to sign in". The button waits until every field is filled and the two passwords match ("The two passwords
  differ."). Refusals in the app's words: "The invite code is wrong.", "That username is taken.", "Usernames are 2–32
  characters: lowercase letters, digits, - or _.", "Choose a password.", "Sign-ups are not open yet. Ask King for an invite
  code.", "Too many failed tries. Wait 15 minutes and try again.", "Sign-in is not set up on the server yet."; anything else
  "Could not create the account: <the server's message>". A success calls `onSignedIn(me)`: the app continues as a signed-in
  friend, and `must_change_password` is false so no first-password step appears.
- **Settings → Invite** (`Settings.tsx`, owner only, rendered above Friends). The sentence "Send a friend the website
  address and this code; they create their own account.", the code in a `Secret` (the answers' hover copy button, "Copy
  invite code"), "Since <rotated_at>", and **Regenerate**, which first asks with the app's `useConfirm` dialog ("Regenerate
  the invite code?" / "Friends who have not signed up yet will need the new code."); Cancel changes nothing. With no code yet:
  "No invite code yet." and **Create invite code** (no dialog). The Friends card and its Add friend flow stay below it, with
  one added sentence and the 2-character minimum.
- **Client** (`lib/auth.ts`): `auth.register(username, password, invite_code)`, `friends.invite(signal)`,
  `friends.rotateInvite()`, the `Invite` type. `vite.config.ts`: `/friends` joins the proxied prefixes (the
  proxy-covers-backend guard walks the live `/openapi.json`, and a missing prefix is a vite 404 in the UI).
- **Runbook** `docs/runbooks/friends-access.md`: §1 leads with Create your account; the first-password path stays as the
  alternative King can use; §2 gains "Invite a friend" (the card, Regenerate, where the code lives); §3 names the new routes
  and the shared throttle key; §4 adds `INVITE_INVALID`, `INVITES_OFF`, `USERNAME_TAKEN` / `USERNAME_INVALID`.
- `scripts/scaffold_polymath_v4.py`: TREE entries for the two new tests and this work-log.

## Proof
- **Contracts** (`tests/contracts/test_web_invite_signup.py`, 22 cases, each written against the routes and the registry
  through the real boundary middleware, the registry in `tmp_path`, `base_url="https://testserver"` for the Secure cookies):
  the registry record and its rotation (created_at kept, Server A's `PrincipalStore` still loads the file); `register_friend`
  makes the same record as `add_friend` (every key, the scopes, the profile) with `must_change_password` false and the
  password never in the file; the nine username refusals with the codes a person sees; the check order (INVITES_OFF, then
  the code before the username, then the empty password; a code typed with spaces or capitals is accepted); a valid code →
  201, the `/auth/me` body, HttpOnly + Secure + SameSite=Strict cookies, `no-store`, `/auth/me` then shows the friend with
  `must_change_password` false, a CSRF-headered `POST /keys` works, and the owner's listing shows today's defaults
  (`cinema`, `commerce-v1`, `fr-ann`; both adapters; never `fr-someone`); five wrong codes → 429 even with the right code,
  and from another address too (the shared key), with no account made; seven other refusals do not count; no code yet → 503
  six times, never 429; no session secret → 503 `LOGIN_NOT_CONFIGURED`; the owner reads (`null` first) and rotates the code
  (shape, `no-store`, the loopback owner too), a friend gets 403 `OWNER_ONLY` on both, no session 401, the old code is
  refused after a rotation and the new one works; the owner may still add a two-letter friend; the boundary classes; the
  code appears in no `/auth/me`, `/admin/friends`, `/keys` body and not in the DEBUG log capture.
- `tests/contracts/test_web_boundary.py`: seven new classification cases (`/auth/register` POST public / GET none;
  `/friends/invite` GET owner; `/friends/invite/rotate` POST owner; the three near-misses none); the every-route-classified
  test now covers the three new routes of `orchestrator.main`.
- **vitest** (`invite-signup.test.tsx`, 6 cases, the real `App` with fetch stubbed): the sign-in form is untouched (two
  inputs) until "New here? Create your account"; the four fields in order; the form posts `{username, password, invite_code}`
  and the friend's workspace appears (Chat, no Overview, no first-password step); the button holds on a mismatch or an empty
  field and "Back to sign in" returns; all eight refusals in words, the form and its values kept; the owner's card with the
  code, `Copy invite code` on the answers' hover copy button, the card above Add friend, the dialog's sentence, Cancel keeps
  the old code, the dialog's Regenerate posts `/friends/invite/rotate` and shows the new code; "Create invite code" with no
  dialog while none exists; a friend sees no card and no `/friends/invite` request.
- **Guards** on the final tree (the worktree, `PYTHONPATH` on its four package dirs, `POLYMATH_PG_DSN` pinned to a dead
  socket, both account variables unset):
  - `tests/contracts` (`-k "not test_live_"`): 799 passed, 29 of them new (22 in the new file, 7 boundary cases); the five
    web account files: 100 passed (71 at `84a67f49`, measured before the change).
  - `npx tsc -p . --noEmit` exit 0; vitest (live-contract and proxy-covers-backend excluded): 19 files, 141 tests passed,
    6 of them new.
  - ruff on the changed Python files: the one pre-existing finding in `web_auth.py` (I001, the import block of
    `/auth/owner-password`) and the six in `scripts/scaffold_polymath_v4.py`; none added.
  - `scripts/agent_preflight.py` ok, `scripts/repo_guard.py` ok, `scripts/wiki_worm.py --check` ok (exit 0 each);
    `scripts/contract_impact.py --check --staged`: "none (no changed file maps to an architecture contract)".
  - Not run live: the two vitest files that need `:7200` (live-contract, proxy-covers-backend) were excluded; the
    contracts run excluded `test_live_*`. Nothing here touched the live system.

## Rejected claims
- "Hash the invite code like a password": no. The owner must read it again to share it, it opens only a limited friend
  account, and it is rotatable; the file is owner-only. Plain at rest is the owner's decision for this one secret.
- "Two username rules (2–32 for sign-up, 3–31 for Add friend)": no. One field, one rule, or a friend can choose a name the
  owner cannot add and the runbook lies to one of them.
- "A taken username or a bad password should count toward the throttle": no. Only a wrong code is a guess at the secret;
  the rest are the person's own typing, and the code is checked first, so nothing about names leaks to a stranger.
- "Clear the shared `invite` key on success": mirrored from `/auth/login`, which clears the proved key (the username) and
  keeps the address key; the address key stays here too.
- "Put the code in `/auth/me` so the owner's page has it at once": no. `/auth/me` is on every page load and in every friend's
  session; the owner reads the code with one owner-only `GET /friends/invite` from the Settings card.

## Open contract gaps
- Live proof after the owner's deploy: `GET /friends/invite` on the server itself → `code: null`; Settings → Invite → Create
  invite code; on the public site, New here? → Create your account with that code → the friend's workspace with `/auth/me`
  `must_change_password: false`; Settings → Friends lists the new friend with every shared library; Regenerate, then the old
  code answers `INVITE_INVALID`; the live contract test (`npx vitest run src/__tests__/live-contract.test.ts` and
  `proxy-covers-backend.test.ts`) against `:7200`, which now sees `/friends/invite` in `/openapi.json`.
- The throttle is per orchestrator process (in memory), as for sign-in; a bounce forgets the failures.
- `scripts/web_accounts.py` has no `invite` command; the owner creates and rotates the code from Settings (the local
  `http://127.0.0.1:7200/v2/` counts as the owner). The plan FRIENDS-ACCESS-V1 §3 still lists the old public routes; the plan
  and register rows are the lead's.
