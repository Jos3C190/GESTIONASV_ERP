import { redirect } from '@sveltejs/kit';
import { browser } from '$app/environment';
import { restoreAppContext } from '$lib/auth/restore-app-context';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async ({ url }) => {
  // Client-side only guard. The backend remains the source of truth — every
  // API call is validated server-side via JWT.
  if (browser) {
    const context = await restoreAppContext(url.searchParams.get('companyId'));
    if (!context.authenticated) {
      const returnTo = `${url.pathname}${url.search}`;
      throw redirect(307, `/login?returnTo=${encodeURIComponent(returnTo)}`);
    }
    if (!context.companySelected) {
      const returnTo = `${url.pathname}${url.search}`;
      throw redirect(307, `/companies?returnTo=${encodeURIComponent(returnTo)}`);
    }
  }
  return {};
};
