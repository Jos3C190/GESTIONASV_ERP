import { describe, expect, it } from 'vitest';
import type { SiteOut } from '$lib/api/client';
import { describeEvent } from './events';
import { distanceM } from './geofences';
import { siteAreas, siteEventTitle, sitePopup } from './sites';

const site: SiteOut = {
  kind: 'branch',
  id: 'b1',
  name: 'Roosevelt <b>',
  code: 'ROO',
  address: 'Av. Roosevelt',
  latitude: 13.48,
  longitude: -88.18,
  radius_m: 200,
  status: 'active',
  branch_id: 'b1',
  branch_name: 'Roosevelt',
  warehouses: [
    { id: 'w1', name: 'Bodega central', code: null, is_central: true, status: 'active' },
    { id: 'w2', name: 'Frío', code: null, is_central: false, status: 'maintenance' }
  ]
};

describe('tracking sites', () => {
  it('draws each site as a circle of its arrival radius', () => {
    const [feature] = siteAreas([site]).features;
    const ring = feature!.geometry.coordinates[0]!;
    expect(distanceM([site.longitude, site.latitude], ring[0] as [number, number])).toBeCloseTo(
      200,
      -1
    );
  });

  it('builds the popup as text, listing the warehouses at the site', () => {
    const popup = sitePopup(site);
    expect(popup.querySelector('strong')?.textContent).toBe('Sucursal Roosevelt <b>');
    expect(popup.querySelector('b')).toBeNull();
    expect([...popup.querySelectorAll('li')].map((item) => item.textContent)).toEqual([
      'Bodega central (central)',
      'Frío · en mantenimiento'
    ]);
  });

  it('labels arrivals only for automatic site geofences', () => {
    expect(siteEventTitle('geofenceEnter', 'Sucursal Roosevelt', true)).toBe(
      'Llegó a Sucursal Roosevelt'
    );
    expect(siteEventTitle('geofenceExit', 'Almacén Externo', true)).toBe(
      'Salió de Almacén Externo'
    );
    expect(siteEventTitle('geofenceEnter', 'Sucursal falsa', false)).toBeNull();
    const event = describeEvent({
      type: 'geofenceEnter',
      geofence_name: 'Sucursal Roosevelt',
      geofence_system: true,
      alarm: null,
      speed_kmh: null
    });
    expect(event).toMatchObject({
      group: 'geofence',
      tone: 'success',
      title: 'Llegó a Sucursal Roosevelt'
    });
  });
});
