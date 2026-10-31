import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

/**
 * La importación masiva queda temporalmente fuera de la interfaz.
 * Conservamos la página y sus servicios para reactivar la función después,
 * pero los accesos directos regresan al listado de ubicaciones.
 */
export const load: PageLoad = ({ params }) => {
  throw redirect(307, `/warehouses/${params.id}/locations`);
};
