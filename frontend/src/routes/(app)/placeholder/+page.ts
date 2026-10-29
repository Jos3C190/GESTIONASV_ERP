import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
  const module = url.searchParams.get('module');
  if (module === 'Flota') redirect(307, '/fleet');
  if (module === 'Seguimiento') redirect(307, '/tracking');
};
