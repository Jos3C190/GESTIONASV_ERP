import { redirect } from '@sveltejs/kit';
import { browser } from '$app/environment';

export const load = () => {
  if (browser) {
    const token = sessionStorage.getItem('erp_access_token');
    if (token) {
      throw redirect(307, '/companies');
    }
    throw redirect(307, '/login');
  }
  // SSR: no redirect, let the page render (it'll redirect on hydration).
  return {};
};
