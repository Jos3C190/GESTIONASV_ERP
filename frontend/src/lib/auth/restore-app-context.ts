import { browser } from '$app/environment';
import { api } from '$lib/api/client';
import { branch } from '$lib/stores/branch.svelte';
import { company } from '$lib/stores/company.svelte';
import { permissions } from '$lib/stores/permissions.svelte';
import { session } from '$lib/stores/session.svelte';

export interface AppContextRestoreResult {
  authenticated: boolean;
  companySelected: boolean;
}

/**
 * Restores the authenticated application context in a fresh browser tab.
 * Access tokens stay in sessionStorage; the backend's HttpOnly refresh cookie
 * is the only credential shared between tabs.
 */
export async function restoreAppContext(
  requestedCompanyId?: string | null
): Promise<AppContextRestoreResult> {
  if (!browser) return { authenticated: true, companySelected: true };

  const needsUserContext = !session.token || !session.user;
  try {
    if (!session.token) {
      const tokens = await api.auth.refresh();
      session.setToken(tokens.access_token);
    }

    if (needsUserContext) {
      const [user, effectivePermissions] = await Promise.all([
        api.auth.me(),
        api.auth.myPermissions()
      ]);
      session.setUser(user);
      permissions.set(effectivePermissions.permissions, effectivePermissions.is_superuser);
    }
  } catch {
    session.clear();
    permissions.clear();
    company.clear();
    branch.clear();
    return { authenticated: false, companySelected: false };
  }

  if (!session.isAuthenticated) {
    company.clear();
    branch.clear();
    return { authenticated: false, companySelected: false };
  }

  if (!company.id) {
    try {
      const accessibleCompanies = await api.companies.accessible();
      const requestedCompany = requestedCompanyId
        ? accessibleCompanies.find((item) => item.id === requestedCompanyId && item.is_active)
        : accessibleCompanies.length === 1 && accessibleCompanies[0]?.is_active
          ? accessibleCompanies[0]
          : undefined;
      if (requestedCompany) {
        company.select({
          id: requestedCompany.id,
          name: requestedCompany.name,
          commercial_name: requestedCompany.commercial_name,
          logo: requestedCompany.logo
        });
      }
    } catch {
      // Keep the authenticated session and let the app route to the company selector.
    }
  }

  return { authenticated: true, companySelected: Boolean(company.id) };
}
