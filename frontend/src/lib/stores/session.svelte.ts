/**
 * Session store (Svelte 5 runes). Holds the current user and access token.
 * The refresh token is stored in an httpOnly cookie by the backend, so the
 * frontend never reads it directly — we only pass it via the API client when
 * the backend sets it as a cookie (automatic for same-origin requests).
 */
import { browser } from '$app/environment';

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

const TOKEN_STORAGE_KEY = 'erp_access_token';
const USER_STORAGE_KEY = 'erp_current_user';

function createSessionStore() {
  let user = $state<CurrentUser | null>(loadUser());
  let accessToken = $state<string | null>(loadToken());
  let loading = $state(false);

  function loadToken(): string | null {
    if (!browser) return null;
    try {
      return sessionStorage.getItem(TOKEN_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function loadUser(): CurrentUser | null {
    if (!browser) return null;
    try {
      const raw = sessionStorage.getItem(USER_STORAGE_KEY);
      return raw ? (JSON.parse(raw) as CurrentUser) : null;
    } catch {
      return null;
    }
  }

  function persist() {
    if (!browser) return;
    try {
      if (accessToken) sessionStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
      else sessionStorage.removeItem(TOKEN_STORAGE_KEY);
      if (user) sessionStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
      else sessionStorage.removeItem(USER_STORAGE_KEY);
    } catch {
      // ignore quota / private mode
    }
  }

  return {
    get user(): CurrentUser | null {
      return user;
    },
    get token(): string | null {
      return accessToken;
    },
    get isAuthenticated(): boolean {
      return accessToken !== null && user !== null;
    },
    get isLoading(): boolean {
      return loading;
    },
    setSession(token: string, u: CurrentUser) {
      accessToken = token;
      user = u;
      persist();
    },
    setToken(token: string) {
      accessToken = token;
      persist();
    },
    setUser(u: CurrentUser) {
      user = u;
      persist();
    },
    clear() {
      accessToken = null;
      user = null;
      loading = false;
      persist();
      if (browser) sessionStorage.removeItem('erp_active_company');
      if (browser) sessionStorage.removeItem('erp_operational_branch');
    },
    setLoading(v: boolean) {
      loading = v;
    }
  };
}

export const session = createSessionStore();
