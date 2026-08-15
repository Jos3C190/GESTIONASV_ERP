import { describe, expect, it, vi } from 'vitest';
import { apiFetch } from '$lib/api/client';
import { getLocationSummary, normalizeLocation, normalizeLocationBatch } from './services';
import { locationBatchRequiredPermissions } from './types';

vi.mock('$lib/api/client', () => ({
  apiFetch: vi.fn()
}));

describe('location service normalization', () => {
  it('unifica el bucket legado "Sin área" con el sentinel técnico', async () => {
    vi.mocked(apiFetch).mockResolvedValueOnce({
      total: 4,
      total_capacity: 110,
      active: 4,
      inactive: 0,
      by_status: { active: 4 },
      by_type: { standard: 4 },
      areas: { 'Sin área': 2, __none__: 1, PICKING: 1 }
    });

    const result = await getLocationSummary('warehouse-1');

    expect(result.areas).toEqual({ __none__: 3, PICKING: 1 });
  });

  it('adapta el contrato legado a la entidad tipada durante un despliegue escalonado', () => {
    const result = normalizeLocation(
      {
        id: 'loc-1',
        code: 'A-01-02-03',
        aisle: 'A',
        rack: '1',
        level: '2',
        position: '3',
        capacity: '40',
        is_active: true
      },
      'warehouse-1'
    );

    expect(result).toMatchObject({
      id: 'loc-1',
      warehouse_id: 'warehouse-1',
      capacity: 40,
      location_type: 'standard',
      lifecycle_status: 'active',
      code_source: 'legacy'
    });
    expect(result.area).toBeNull();
    expect(result.scheme_version).toBeNull();
  });

  it('preserva metadatos profesionales del nuevo contrato', () => {
    const result = normalizeLocation({
      id: 'loc-2',
      warehouse_id: 'warehouse-1',
      code: 'PICK-A-01-02-03',
      area: 'PICK',
      aisle: 'A',
      rack: '01',
      level: '02',
      position: '03',
      capacity: 20,
      location_type: 'picking',
      lifecycle_status: 'blocked_out',
      scheme_id: 'scheme-1',
      scheme_version: 3,
      code_source: 'generated',
      external_id: 'OLD-15',
      is_active: true
    });

    expect(result.scheme_version).toBe(3);
    expect(result.code_source).toBe('generated');
    expect(result.external_id).toBe('OLD-15');
    expect(result.lifecycle_status).toBe('blocked_out');
  });

  it('normaliza paginación y permisos de lote desde contratos nuevos o transitorios', () => {
    const result = normalizeLocationBatch(
      {
        id: 'job-1',
        warehouse_id: 'warehouse-1',
        kind: 'import',
        total_rows: 250,
        create_count: 200,
        update_count: 50,
        summary: { required_permissions: ['locations.import', 'locations.create'] },
        rows_meta: { page: 2, size: 100, total: 250, pages: 3 },
        rows: [
          {
            id: 'row-101',
            row_number: 101,
            operation: 'create',
            normalized_data: {},
            diff: {},
            errors: []
          }
        ]
      },
      2,
      100
    );

    expect(result.rows_meta).toEqual({ page: 2, size: 100, total: 250, pages: 3 });
    expect(result.rows).toHaveLength(1);
    expect(locationBatchRequiredPermissions(result)).toEqual([
      'locations.import',
      'locations.create'
    ]);
  });
});
