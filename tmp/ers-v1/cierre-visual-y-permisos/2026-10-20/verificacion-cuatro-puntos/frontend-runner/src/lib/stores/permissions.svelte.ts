/**
 * Permissions store (Svelte 5 runes). Holds the current user's effective
 * permission codes. Loaded after login via GET /auth/me/permissions.
 *
 * hasPermission(code) returns true for superusers (who have all permissions)
 * or for normal users whose list contains the code.
 */
import { browser } from '$app/environment';

const PERMS_STORAGE_KEY = 'erp_permissions';
const SUPERUSER_KEY = 'erp_is_superuser';

function loadPermissions(): string[] {
  if (!browser) return [];
  try {
    const raw = sessionStorage.getItem(PERMS_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

function loadSuperuser(): boolean {
  if (!browser) return false;
  try {
    return sessionStorage.getItem(SUPERUSER_KEY) === 'true';
  } catch {
    return false;
  }
}

function createPermissionsStore() {
  let permissions = $state<string[]>(loadPermissions());
  let isSuperuser = $state<boolean>(loadSuperuser());

  function persist() {
    if (!browser) return;
    try {
      sessionStorage.setItem(PERMS_STORAGE_KEY, JSON.stringify(permissions));
      sessionStorage.setItem(SUPERUSER_KEY, String(isSuperuser));
    } catch {
      // ignore
    }
  }

  return {
    get permissions(): string[] {
      return permissions;
    },
    get isSuperuser(): boolean {
      return isSuperuser;
    },
    hasPermission(code: string): boolean {
      if (isSuperuser) return true;
      return permissions.includes(code);
    },
    hasAnyPermission(codes: string[]): boolean {
      if (isSuperuser) return true;
      return codes.some((c) => permissions.includes(c));
    },
    set(perms: string[], superuser: boolean) {
      permissions = perms;
      isSuperuser = superuser;
      persist();
    },
    clear() {
      permissions = [];
      isSuperuser = false;
      persist();
    }
  };
}

export const permissions = createPermissionsStore();