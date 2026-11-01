import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

// Herramienta interna para calibrar las zonas de logo; no existe fuera de desarrollo.
export const load: PageLoad = () => {
  if (!import.meta.env.DEV) error(404, 'No encontrado');
};
