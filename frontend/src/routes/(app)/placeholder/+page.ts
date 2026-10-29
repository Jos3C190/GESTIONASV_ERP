import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
  if (url.searchParams.get('module') === 'Flota') redirect(307, '/fleet');
};
