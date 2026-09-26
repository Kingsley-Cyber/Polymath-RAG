/**
 * FRIENDS-ACCESS-V1 — the account and Settings client: sign-in, my API keys, the connect prompt, the owner's friend admin.
 * Same rules as lib/api.ts: screens call these and render what comes back; the backend decides who may do what.
 */
import { http } from "./api";

export interface Me {
  username: string;
  display_name: string;
  is_owner: boolean;
  must_change_password: boolean;
  principal_id: string;
  /** true when the owner opened the app on the server itself (http://127.0.0.1:7200): no sign-in exists there */
  local: boolean;
}

export interface ApiKey {
  key_id: string;
  label: string;
  created_at: string | null;
  revoked_at: string | null;
}

export interface CreatedKey extends ApiKey {
  key: string;
  prompt: string;
  shown_once: boolean;
}

export interface Friend {
  principal_id: string;
  username: string;
  name: string;
  enabled: boolean;
  corpus_ids: string[];
  writable_corpus_ids: string[];
  adapter_ids: string[];
  must_change_password: boolean;
  created_at: string | null;
  active_keys: number;
}

export interface MyKeys {
  is_owner: boolean;
  keys: ApiKey[];
  max_active: number | null;
  mcp_url: string;
  note?: string;
}

export interface FriendsAdmin {
  friends: Friend[];
  libraries: string[];
  adapters: string[];
  max_active_keys: number;
}

const u = encodeURIComponent;

/** A backend with no logins (older than FRIENDS-ACCESS-V1, or the brief merge -> bounce window, where /auth/me is a 404)
 *  behaves as before: the caller is the owner. Display only: the server enforces every rule itself. */
export const LEGACY_OWNER: Me = {
  username: "king", display_name: "King", is_owner: true, must_change_password: false, principal_id: "prn_owner", local: true,
};

export function normalizeMe(raw: unknown): Me {
  const m = raw as Partial<Me> | null;
  if (!m || typeof m.is_owner !== "boolean" || typeof m.username !== "string") return LEGACY_OWNER;
  return { ...LEGACY_OWNER, ...m, local: Boolean(m.local) } as Me;
}

export const auth = {
  me: (s?: AbortSignal) => http.get<unknown>("/auth/me", s).then(normalizeMe),
  login: (username: string, password: string) => http.post<Me>("/auth/login", { username, password }),
  logout: () => http.post<{ signed_out: boolean }>("/auth/logout", {}),
  changePassword: (current_password: string, new_password: string) =>
    http.post<Me>("/auth/password", { current_password, new_password }),

  keys: (s?: AbortSignal) => http.get<MyKeys>("/keys", s),
  createKey: (label: string) => http.post<CreatedKey>("/keys", { label }),
  revokeKey: (keyId: string) => http.del<{ revoked: string }>(`/keys/${u(keyId)}`),
  prompt: (s?: AbortSignal) => http.get<{ prompt: string; placeholder: string; mcp_url: string }>("/keys/prompt", s),

  friends: (s?: AbortSignal) => http.get<FriendsAdmin>("/admin/friends", s),
  addFriend: (username: string, display_name: string) =>
    http.post<{ friend: Friend; first_password: string }>("/admin/friends", { username, display_name }),
  friendAction: (username: string, action: "enable" | "disable" | "reset-password") =>
    http.post<{ first_password?: string }>(`/admin/friends/${u(username)}/${action}`, {}),
  setLibraries: (username: string, corpus_ids: string[]) =>
    http.put<{ friend: Friend }>(`/admin/friends/${u(username)}/libraries`, { corpus_ids }),
  friendKeys: (username: string, s?: AbortSignal) => http.get<{ keys: ApiKey[] }>(`/admin/friends/${u(username)}/keys`, s),
  revokeFriendKey: (username: string, keyId: string) =>
    http.del<{ revoked: string }>(`/admin/friends/${u(username)}/keys/${u(keyId)}`),
};

/** The private library the server creates for a friend on their first upload. */
export function privateLibrary(me: Me): string | null {
  return me.is_owner ? null : `fr-${me.username}`;
}

/** Copy text; falls back to a hidden textarea where the async clipboard API is unavailable (plain http, old browsers). */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
