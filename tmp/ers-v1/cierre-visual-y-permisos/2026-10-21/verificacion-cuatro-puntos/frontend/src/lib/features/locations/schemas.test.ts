import { describe, expect, it } from 'vitest';
import { axisSize, batchCardinality, validateLocationDraft } from './schemas';
import type { LocationDraft } from './types';

const validDraft = (): LocationDraft => ({
  capacity_group_id: '',
  area: ' Picking ',
  aisle: ' A ',
  rack: '03',
  level: '02',
  position: '04',
  certified_max_weight_kg: '1000',
  operational_max_weight_kg: '900',
  certified_usable_volume_m3: '120',
  operational_usable_volume_m3: '100',
  capacity_profile: 'general_mixed',
  capacity_enforcement_mode: 'observe',
  storage_eligible: true,
  usable_length_m: '10',
  usable_width_m: '8',
  usable_height_m: '3',
  notes: '',
  location_type: 'standard',
  lifecycle_status: 'active',
  pick_sequence: '10',
  putaway_sequence: '',
  external_id: '',
  barcode: '',
  verification_code: ''
});

describe('location schemas', () => {
  it('normaliza el formulario y convierte campos numéricos sin aceptar un código manual', () => {
    const result = validateLocationDraft(validDraft());
    expect(result.success).toBe(true);
    if (!result.success) return;
    expect(result.data).toMatchObject({
      area: 'Picking',
      aisle: 'A',
      certified_max_weight_kg: 1000,
      operational_max_weight_kg: 900,
      certified_usable_volume_m3: 120,
      operational_usable_volume_m3: 100,
      pick_sequence: 10,
      putaway_sequence: null
    });
    expect(result.data).not.toHaveProperty('code');
  });

  it('acepta los números que entregan los inputs HTML de tipo number', () => {
    const result = validateLocationDraft({
      ...validDraft(),
      certified_max_weight_kg: 1200,
      operational_max_weight_kg: 1000,
      pick_sequence: 3,
      putaway_sequence: 0
    });

    expect(result.success).toBe(true);
    if (!result.success) return;
    expect(result.data).toMatchObject({
      certified_max_weight_kg: 1200,
      operational_max_weight_kg: 1000,
      pick_sequence: 3,
      putaway_sequence: 0
    });
  });

  it('entrega errores asociados a campos para límites y coordenadas inválidas', () => {
    const result = validateLocationDraft({
      ...validDraft(),
      aisle: '',
      operational_max_weight_kg: '1200'
    });
    expect(result.success).toBe(false);
    if (result.success) return;
    expect(result.errors.aisle).toContain('obligatorio');
    expect(result.errors.operational_max_weight_kg).toContain('superar');
  });

  it('calcula rangos alfabéticos, numéricos y cardinalidad cartesiana', () => {
    expect(axisSize({ key: 'aisle', start: 'A', end: 'D' })).toBe(4);
    expect(axisSize({ key: 'rack', start: '1', end: '10', step: 2 })).toBe(5);
    expect(axisSize({ key: 'rack', start: 'A01', end: 'A10' })).toBe(10);
    expect(
      batchCardinality([
        { key: 'aisle', start: 'A', end: 'B' },
        { key: 'rack', start: '1', end: '10' },
        { key: 'level', start: '1', end: '4' },
        { key: 'position', values: ['1', '2'] }
      ])
    ).toBe(160);
  });

  it('rechaza rangos invertidos, valores repetidos y notación numérica ambigua', () => {
    expect(axisSize({ key: 'aisle', start: 'D', end: 'A' })).toBe(0);
    expect(axisSize({ key: 'position', values: ['01', '01', '02'] })).toBe(0);
    expect(axisSize({ key: 'position', values: ['01', '', '02'] })).toBe(0);
    expect(axisSize({ key: 'rack', start: '1e1', end: '1e3' })).toBe(0);
    expect(axisSize({ key: 'rack', start: '1.1', end: '1.9' })).toBe(0);
    expect(axisSize({ key: 'rack', start: 'A01', end: 'B10' })).toBe(0);
    expect(axisSize({ key: 'rack', start: 'A01', end: 'A10', step: 1.5 })).toBe(0);
  });
});
