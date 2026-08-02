import { redirect } from '@sveltejs/kit';
import { browser } from '$app/environment';
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = async () => {
  // Client-side only guard. The backend remains the source of truth — every
  // API call is validated server-side via JWT.
  if (browser) {
    const token = sessionStorage.getItem('erp_access_token');
    if (!token) {
      throw redirect(307, '/login');
    }
    if (!sessionStorage.getItem('erp_active_company')) {
      throw redirect(307, '/companies');
    }
  }
  return {};
};
