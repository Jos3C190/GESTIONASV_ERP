import type { SiteOut } from '$lib/api/client';
import { circleRing } from './geofences';

const STATUS_LABELS: Record<string, string> = {
  active: 'Operando',
  maintenance: 'En mantenimiento'
};

/** Radio de llegada de cada sucursal o almacén, como polígonos para el mapa. */
export function siteAreas(
  sites: Pick<SiteOut, 'id' | 'name' | 'latitude' | 'longitude' | 'radius_m'>[]
) {
  return {
    type: 'FeatureCollection',
    features: sites.map((site) => ({
      type: 'Feature',
      properties: { name: site.name },
      geometry: {
        type: 'Polygon',
        coordinates: [circleRing([site.longitude, site.latitude], site.radius_m, 48)]
      }
    }))
  };
}

function node<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string) {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  return element;
}

/** Contenido del popup; se arma con nodos de texto para no interpretar datos como HTML. */
export function sitePopup(site: SiteOut): HTMLElement {
  const root = node('div');
  root.className = 'tm-site-popup';
  root.append(node('strong', `${site.kind === 'branch' ? 'Sucursal' : 'Almacén'} ${site.name}`));
  if (site.address) root.append(node('span', site.address));
  const meta = [
    site.kind === 'warehouse' ? `Sucursal ${site.branch_name}` : null,
    STATUS_LABELS[site.status] ?? site.status,
    `Radio de llegada ${site.radius_m} m`
  ].filter(Boolean);
  root.append(node('small', meta.join(' · ')));
  const warehouses = site.kind === 'branch' ? site.warehouses : [];
  if (warehouses.length) {
    root.append(node('small', 'Almacenes en este lugar:'));
    const list = node('ul');
    for (const warehouse of warehouses)
      list.append(
        node(
          'li',
          `${warehouse.name}${warehouse.is_central ? ' (central)' : ''}${
            warehouse.status === 'maintenance' ? ' · en mantenimiento' : ''
          }`
        )
      );
    root.append(list);
  }
  return root;
}

/** "Llegó a Sucursal X" / "Salió de Almacén Y" para las geocercas automáticas. */
export function siteEventTitle(
  type: string,
  geofenceName: string | null,
  system: boolean
): string | null {
  if (!system || !geofenceName) return null;
  if (type === 'geofenceEnter') return `Llegó a ${geofenceName}`;
  if (type === 'geofenceExit') return `Salió de ${geofenceName}`;
  return null;
}
