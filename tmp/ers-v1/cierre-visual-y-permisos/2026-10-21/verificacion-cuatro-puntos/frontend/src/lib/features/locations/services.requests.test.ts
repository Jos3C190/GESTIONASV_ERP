import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock('$lib/api/client', () => ({
  apiFetch: apiMocks.apiFetch,
  HttpError: class HttpError extends Error {
    status = 500;
  }
}));

import { getLocation, listLocations, updateLocation } from './services';

describe('location service requests', () => {
  beforeEach(() => vi.clearAllMocks());

  it('envía el sentinel acordado para filtrar ubicaciones sin área', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      items: [],
      meta: { page: 1, size: 25, total: 0, pages: 1 }
    });

    await listLocations('warehouse-1', { area: '__none__' });

    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/warehouses/warehouse-1/locations?page=1&size=25&area=__none__',
      { signal: undefined }
    );
  });

  it('serializa la estructura y su alcance jerárquico', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      items: [],
      meta: { page: 1, size: 25, total: 0, pages: 1 }
    });

    await listLocations('warehouse-1', {
      capacity_group_id: 'group-1',
      include_descendants: true
    });

    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/warehouses/warehouse-1/locations?page=1&size=25&capacity_group_id=group-1&include_descendants=true',
      { signal: undefined }
    );
  });

  it('serializa las ubicaciones sin estructura', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      items: [],
      meta: { page: 1, size: 25, total: 0, pages: 1 }
    });

    await listLocations('warehouse-1', { unassigned: true });

    expect(apiMocks.apiFetch).toHaveBeenCalledWith(
      '/warehouses/warehouse-1/locations?page=1&size=25&unassigned=true',
      { signal: undefined }
    );
  });

  it('incluye la versión temporal esperada en el PATCH de una ubicación', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      id: 'location-1',
      warehouse_id: 'warehouse-1',
      code: 'A-01-01-01',
      aisle: 'A',
      rack: '01',
      level: '01',
      position: '01',
      certified_max_weight_kg: 1000,
      operational_max_weight_kg: 900,
      is_active: true
    });
    const input = {
      capacity_group_id: null,
      area: null,
      aisle: 'A',
      rack: '01',
      level: '01',
      position: '01',
      certified_max_weight_kg: 1000,
      operational_max_weight_kg: 900,
      certified_usable_volume_m3: 100,
      operational_usable_volume_m3: 90,
      capacity_profile: 'general_mixed' as const,
      capacity_enforcement_mode: 'observe' as const,
      storage_eligible: true,
      usable_length_m: 10,
      usable_width_m: 8,
      usable_height_m: 3,
      notes: null,
      location_type: 'standard',
      lifecycle_status: 'active',
      pick_sequence: null,
      putaway_sequence: null,
      external_id: null,
      barcode: null,
      verification_code: null,
      expected_updated_at: '2026-08-12T15:30:45Z'
    };

    await updateLocation('warehouse-1', 'location-1', input);

    expect(apiMocks.apiFetch).toHaveBeenCalledWith('/warehouses/warehouse-1/locations/location-1', {
      method: 'PATCH',
      body: JSON.stringify(input)
    });
  });

  it('carga una ubicación individual para la página de edición', async () => {
    apiMocks.apiFetch.mockResolvedValueOnce({
      id: 'location-1',
      warehouse_id: 'warehouse-1',
      code: 'A-01-01-01',
      aisle: 'A',
      rack: '01',
      level: '01',
      position: '01',
      is_active: true
    });

    const result = await getLocation('warehouse-1', 'location-1');

    expect(result.id).toBe('location-1');
    expect(apiMocks.apiFetch).toHaveBeenCalledWith('/warehouses/warehouse-1/locations/location-1', {
      signal: undefined
    });
  });
});
